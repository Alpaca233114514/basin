"""Import declared SmolVLA training settings without executing training code."""

from pathlib import Path

from .io import child, dumps, loads, outside, read_bytes, sha


SCHEMA = "training_config.v1"
FILES = ("snapshot.json", "plan.json", "plan-original.raw", "launch.json", "runtime.json")


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _digest(value, label):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"Invalid {label} SHA256")
    return value


def _phase(plan, phase):
    if phase not in ("train", "smoke"):
        raise ValueError("Training config phase must be train or smoke")
    return _object(plan.get("training" if phase == "train" else "optimizer_smoke"), "plan phase")


def normalized(plan, phase, runtime=None, launch=None, plan_sha=None):
    """Use only declared settings; null means the source did not establish a value."""
    plan = _object(plan, "plan")
    if plan.get("schema_version") != 2 or plan.get("role") != "vla":
        raise ValueError("Expected a SmolVLA version-2 plan")
    if "extends" in plan and "plan_inheritance" not in plan:
        raise ValueError("Inherited plans require a resolved plan copy")
    section = _phase(plan, phase)
    training = _object(plan.get("training"), "training")
    if (training.get("optimizer") is None) != (training.get("scheduler") is None):
        raise ValueError("Optimizer and scheduler declarations must be paired")
    optimizer = _object(training.get("optimizer"), "optimizer") if training.get("optimizer") is not None else {}
    scheduler = _object(training.get("scheduler"), "scheduler") if training.get("scheduler") is not None else {}
    resources = _object(plan.get("resources"), "resources")
    runtime = _object(runtime, "runtime") if runtime is not None else None
    launch = _object(launch, "launch") if launch is not None else None
    dataset = _object(runtime.get("dataset"), "dataset") if runtime else {}
    model = _object(runtime.get("model"), "model") if runtime else {}
    code = launch.get("code_identity") if launch else None
    values = {
        "seed": runtime.get("seed") if runtime else None,
        "batch_size": section.get("batch_size"),
        "gradient_accumulation_steps": 1 if launch else section.get("gradient_accumulation_steps"),
        "max_steps": section.get("steps", 1),
        "optimizer": {"type": optimizer.get("type"), "learning_rate": optimizer.get("lr"),
                      "betas": optimizer.get("betas"), "eps": optimizer.get("eps"),
                      "weight_decay": optimizer.get("weight_decay"),
                      "gradient_clip_norm": optimizer.get("grad_clip_norm")},
        "scheduler": {"type": scheduler.get("type"), "warmup_steps": scheduler.get("num_warmup_steps"),
                      "decay_steps": scheduler.get("num_decay_steps"),
                      "peak_learning_rate": scheduler.get("peak_lr"),
                      "decay_learning_rate": scheduler.get("decay_lr")},
        "precision": resources.get("mixed_precision"),
        "dataset": {"identifier": dataset.get("identifier"), "revision": dataset.get("revision"),
                    "episodes": section.get("episodes"),
                    "view_manifest_sha256": launch.get("dataset_view_manifest_sha256") if launch else None,
                    "normalization_report_sha256": launch.get("normalization_report_sha256") if launch else None},
    }
    identity = {
        "plan_id": plan.get("plan_id"), "experiment_id": launch.get("experiment_id") if launch else
        _object(plan.get("parent_experiment"), "parent_experiment").get("experiment_id"),
        "code": code,
        "plan_sha256": launch.get("formal_plan_sha256") if launch else plan_sha,
        "experiment_config_sha256": launch.get("experiment_config_sha256") if launch else
        _object(plan.get("parent_experiment"), "parent_experiment").get("sha256"),
        "runtime_experiment_sha256": launch.get("runtime_experiment_sha256") if launch else None,
        "action_contract_sha256": launch.get("action_contract_sha256") if launch else None,
        "model_revision": model.get("revision") if model else None,
        "dataset_revision": dataset.get("revision"),
    }
    return values, identity


def _validate_values(values):
    training = _object(values, "training settings")
    for key in ("batch_size", "max_steps"):
        value = training.get(key)
        if type(value) is not int or value <= 0:
            raise ValueError(f"Invalid training {key}")
    accumulation = training.get("gradient_accumulation_steps")
    if accumulation is not None and (type(accumulation) is not int or accumulation <= 0):
        raise ValueError("Invalid gradient accumulation")
    seed = training.get("seed")
    if seed is not None and type(seed) is not int:
        raise ValueError("Invalid training seed")
    episodes = _object(training.get("dataset"), "training dataset").get("episodes")
    if not isinstance(episodes, list) or not episodes or any(type(x) is not int or x < 0 for x in episodes):
        raise ValueError("Invalid training episode selection")
    for item in (training.get("optimizer"), training.get("scheduler")):
        _object(item, "optimizer or scheduler")


def _read_bundle(source, relative):
    root = child(source, relative)
    manifest_data = read_bytes(child(root, "manifest.json"))
    manifest = _object(loads(manifest_data), "training config manifest")
    specs = _object(manifest.get("files"), "training config files")
    if manifest.get("schema") != SCHEMA or set(specs) != set(FILES):
        raise ValueError("Unsupported training config bundle")
    artifacts = {"manifest.json": manifest_data}
    for name in FILES:
        data = read_bytes(child(root, name))
        if sha(data) != _digest(specs[name], name):
            raise ValueError(f"Training config digest mismatch: {name}")
        artifacts[name] = data
    return artifacts


def import_training_config(store, source, relative, run_id, *, launch_path=None, runtime_path=None,
                           resolved_plan_path=None):
    """Import a sealed launch bundle or existing v2 plan and optional launch pair."""
    outside(store.root, source)
    source = Path(source).resolve()
    if (launch_path is None) != (runtime_path is None):
        raise ValueError("Launch manifest and runtime experiment must be supplied together")
    candidate = child(source, relative)
    if candidate.is_dir():
        if launch_path or runtime_path or resolved_plan_path:
            raise ValueError("Bundle import does not accept separate source files")
        artifacts = _read_bundle(source, relative)
        snapshot = _object(loads(artifacts["snapshot.json"]), "snapshot")
        plan = _object(loads(artifacts["plan.json"]), "resolved plan")
        launch = _object(loads(artifacts["launch.json"]), "launch manifest")
        runtime = _object(loads(artifacts["runtime.json"]), "runtime experiment")
        original_sha = sha(artifacts["plan-original.raw"])
    else:
        artifacts = {"plan-original.raw": read_bytes(candidate)}
        if resolved_plan_path:
            artifacts["plan.json"] = read_bytes(child(source, resolved_plan_path))
            plan = _object(loads(artifacts["plan.json"]), "resolved plan")
        else:
            try:
                plan = _object(loads(artifacts["plan-original.raw"]), "plan")
            except (ValueError, UnicodeDecodeError) as exc:
                raise ValueError("Non-JSON version-2 plans require a resolved_plan_path JSON export") from exc
        if resolved_plan_path:
            try:
                original_object = loads(artifacts["plan-original.raw"])
            except (ValueError, UnicodeDecodeError):
                original_object = None
            if isinstance(original_object, dict) and "extends" not in original_object and original_object != plan:
                raise ValueError("Resolved plan differs from the original JSON plan")
        launch = runtime = None
        if launch_path:
            artifacts["launch.json"] = read_bytes(child(source, launch_path))
            artifacts["runtime.json"] = read_bytes(child(source, runtime_path))
            launch = _object(loads(artifacts["launch.json"]), "launch manifest")
            runtime = _object(loads(artifacts["runtime.json"]), "runtime experiment")
        original_sha = sha(artifacts["plan-original.raw"])
        phase = launch.get("mode") if launch else "train"
        source_run = launch.get("run_name") if launch else plan.get("run_name")
        values, identity = normalized(plan, phase, runtime, launch, original_sha)
        snapshot = {"schema": SCHEMA, "source_run": source_run, "phase": phase,
                    "status": "launch_prepared" if launch else "plan_only",
                    "parameters": {"training": values, "identity": identity}}
    if snapshot.get("schema") != SCHEMA or snapshot.get("status") not in ("launch_prepared", "plan_only"):
        raise ValueError("Unsupported training config snapshot")
    phase = snapshot.get("phase")
    if launch:
        parent = _object(plan.get("parent_experiment"), "parent experiment")
        selected_run = plan.get("run_name") if phase == "train" else _phase(plan, phase).get("run_name")
        contract = (
            _object(launch["optimizer_contract"], "launch optimizer contract")
            if launch.get("optimizer_contract") is not None else {}
        )
        contract_optimizer = _object(contract.get("optimizer"), "launch optimizer") if contract else {}
        contract_scheduler = _object(contract.get("scheduler"), "launch scheduler") if contract else {}
        source_optimizer = plan["training"].get("optimizer") or {}
        source_scheduler = plan["training"].get("scheduler") or {}
        if (launch.get("formal_plan_sha256") != original_sha
                or launch.get("runtime_experiment_sha256") != sha(artifacts["runtime.json"])
                or launch.get("mode") != phase
                or launch.get("run_name") != snapshot.get("source_run")
                or launch.get("run_name") != selected_run
                or snapshot.get("status") != "launch_prepared"
                or launch.get("experiment_id") != runtime.get("experiment_id")
                or launch.get("experiment_id") != parent.get("experiment_id")
                or launch.get("experiment_config_sha256") != parent.get("sha256")
                or launch.get("model_revision") != runtime.get("model", {}).get("revision")
                or launch.get("dataset_revision") != runtime.get("dataset", {}).get("revision")
                or bool(contract) != bool(source_optimizer)
                or contract_optimizer.get("lr") != source_optimizer.get("lr")
                or contract_optimizer.get("weight_decay") != source_optimizer.get("weight_decay")
                or contract_optimizer.get("grad_clip_norm") != source_optimizer.get("grad_clip_norm")
                or contract_scheduler.get("num_warmup_steps") != source_scheduler.get("num_warmup_steps")
                or contract_scheduler.get("num_decay_steps") != source_scheduler.get("num_decay_steps")):
            raise ValueError("Training launch identity or source digest mismatch")
    elif snapshot["status"] != "plan_only":
        raise ValueError("Missing launch evidence")
    expected_values, expected_identity = normalized(plan, phase, runtime, launch, original_sha)
    params = _object(snapshot.get("parameters"), "snapshot parameters")
    if set(params) != {"training", "identity"}:
        raise ValueError("Unexpected training snapshot parameter sections")
    if params.get("training") != expected_values or params.get("identity") != expected_identity:
        raise ValueError("Training snapshot does not match source configuration")
    _validate_values(expected_values)
    if not isinstance(snapshot.get("source_run"), str) or not snapshot["source_run"]:
        raise ValueError("Training source_run is missing")
    resolution = ("rosetta_bundle" if candidate.is_dir() else
                  "operator_supplied" if resolved_plan_path else "source_json")
    record = {"schema_version": 1, "id": run_id, "adapter": SCHEMA,
              "source_run": snapshot["source_run"], "source_path": Path(relative).as_posix(),
              "evidence_kind": "declared_training_configuration", "status": snapshot["status"],
              "gate": {}, "parameters": params, "dimensions": [],
              "verification": {"source_hashes": "verified_at_import", "execution": "not_verified",
                               "plan_resolution": resolution},
              "limitations": ["Launch preparation is not proof of optimizer updates or completed training."]}
    return store.add(record, [], artifacts)
