"""Training configuration evidence is declared, source-bound and create-only."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from basin.__main__ import main
from basin.api import BasinAPI
from basin.io import dumps, loads, sha, write_new
from basin.mcp import Server
from basin.store import Store
from basin.training_config import import_training_config, normalized


class TrainingConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.store = Store(self.root / "history")
        self.plan = {"schema_version": 2, "role": "vla", "plan_id": "plan-1",
                     "run_name": "train-1", "parent_experiment": {"experiment_id": "exp-1", "sha256": "a" * 64},
                     "resources": {"mixed_precision": "bf16"},
                     "training": {"episodes": [3, 7], "batch_size": 4, "steps": 20,
                                  "optimizer": {"type": "adamw", "lr": 0.0001, "betas": [0.9, 0.95],
                                                "eps": 1e-8, "weight_decay": 0.01, "grad_clip_norm": 10.0},
                                  "scheduler": {"type": "cosine_decay_with_warmup",
                                                "num_warmup_steps": 2, "num_decay_steps": 20,
                                                "peak_lr": 0.0001, "decay_lr": 1e-6}},
                     "optimizer_smoke": {"run_name": "smoke-1", "episodes": [3],
                                         "batch_size": 2, "steps": 2}}
        self.runtime = {"experiment_id": "exp-1", "seed": 17,
                        "model": {"revision": "model-1"},
                        "dataset": {"identifier": "dataset-1", "revision": "data-1"}}
        self.plan_bytes = dumps(self.plan).encode()
        self.runtime_bytes = dumps(self.runtime).encode()
        self.launch = {"mode": "train", "run_name": "train-1", "experiment_id": "exp-1",
                       "formal_plan_sha256": sha(self.plan_bytes),
                       "experiment_config_sha256": "a" * 64,
                       "runtime_experiment_sha256": sha(self.runtime_bytes),
                       "action_contract_sha256": "b" * 64,
                       "normalization_report_sha256": "c" * 64,
                       "dataset_view_manifest_sha256": "d" * 64,
                       "model_revision": "model-1", "dataset_revision": "data-1",
                       "optimizer_contract": {"optimizer": {"lr": 0.0001, "weight_decay": 0.01,
                                                            "grad_clip_norm": 10.0},
                                              "scheduler": {"num_warmup_steps": 2,
                                                            "num_decay_steps": 20}},
                       "code_identity": {"revision": "rev-1", "dirty": False}}

    def bundle(self, *, phase="train"):
        plan = dict(self.plan)
        launch = dict(self.launch)
        launch["mode"] = phase
        launch["run_name"] = "train-1" if phase == "train" else "smoke-1"
        folder = self.source / phase
        values, identity = normalized(plan, phase, self.runtime, launch)
        snapshot = {"schema": "training_config.v1", "source_run": launch["run_name"],
                    "phase": phase, "status": "launch_prepared",
                    "parameters": {"training": values, "identity": identity}}
        files = {"snapshot.json": dumps(snapshot).encode(), "plan.json": dumps(plan).encode(),
                 "plan-original.raw": self.plan_bytes, "launch.json": dumps(launch).encode(),
                 "runtime.json": self.runtime_bytes}
        for name, data in files.items():
            write_new(folder / name, data)
        write_new(folder / "manifest.json", dumps({"schema": "training_config.v1",
                                                  "files": {name: sha(data) for name, data in files.items()}}))
        return folder

    def test_bundle_query_dataset_and_idempotency(self):
        self.bundle()
        self.assertEqual(import_training_config(self.store, self.source, "train", "config-1")["status"], "imported")
        self.assertEqual(import_training_config(self.store, self.source, "train", "config-1")["status"], "already_present")
        api = BasinAPI(self.store.root)
        self.assertEqual(api.call("basin_get_run", {"run_id": "config-1",
                                                    "pointer": "/parameters/training/dataset/episodes"})["data"], [3, 7])
        self.assertEqual(api.call("basin_get_run", {"run_id": "config-1",
                                                    "pointer": "/parameters/training/optimizer/learning_rate"})["data"], 0.0001)
        self.assertEqual(api.call("basin_history", {"source_run": "train-1"})["data"]["total"], 1)
        self.assertEqual(self.store.verify("config-1")["files"]["artifacts/plan-original.raw"], sha(self.plan_bytes))

    def test_smoke_is_separate_and_plan_only_has_explicit_missing_values(self):
        self.bundle(phase="smoke")
        import_training_config(self.store, self.source, "smoke", "config-smoke")
        record = self.store.get("config-smoke")[0]
        self.assertEqual(record["source_run"], "smoke-1")
        self.assertEqual(record["parameters"]["training"]["dataset"]["episodes"], [3])
        self.assertEqual(record["parameters"]["training"]["max_steps"], 2)
        write_new(self.source / "plan-only.json", self.plan_bytes)
        import_training_config(self.store, self.source, "plan-only.json", "plan-only")
        plan_record = self.store.get("plan-only")[0]
        self.assertEqual(plan_record["status"], "plan_only")
        self.assertIsNone(plan_record["parameters"]["training"]["seed"])
        self.assertIsNone(plan_record["parameters"]["training"]["dataset"]["identifier"])

    def test_direct_existing_v2_sources_and_cli(self):
        write_new(self.source / "plan.json", self.plan_bytes)
        write_new(self.source / "launch.json", dumps(self.launch))
        write_new(self.source / "runtime.json", self.runtime_bytes)
        api = BasinAPI(self.store.root, {"input": self.source})
        result = api.call("basin_import_training_config", {"source": "input", "path": "plan.json",
                                                           "launch_path": "launch.json", "runtime_path": "runtime.json",
                                                           "run_id": "direct"})
        self.assertEqual(result["data"]["status"], "imported")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--store", str(self.store.root), "import-training-config", str(self.source),
                         "plan.json", "--launch", "launch.json", "--runtime", "runtime.json", "--id", "cli"])
        self.assertEqual(code, 0)
        self.assertEqual(loads(output.getvalue())["id"], "cli")
        server = Server(api)
        self.assertIn("basin_import_training_config", {tool["name"] for tool in api.tools()})
        self.assertEqual(server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                        "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                                                   "clientInfo": {"name": "test", "version": "1"}}})["result"]["protocolVersion"], "2025-11-25")
        self.assertIsNone(server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        imported = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                  "params": {"name": "basin_import_training_config",
                                             "arguments": {"source": "input", "path": "plan.json",
                                                           "launch_path": "launch.json", "runtime_path": "runtime.json",
                                                           "run_id": "mcp"}}})
        self.assertEqual(imported["result"]["structuredContent"]["data"]["status"], "imported")

    def test_mismatch_missing_and_conflict_preserve_evidence(self):
        folder = self.bundle()
        import_training_config(self.store, self.source, "train", "config-1")
        original = self.store.get("config-1")[0]
        (folder / "runtime.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            import_training_config(self.store, self.source, "train", "config-2")
        self.assertEqual(self.store.get("config-1")[0], original)
        with self.assertRaises(FileNotFoundError):
            import_training_config(self.store, self.source, "missing", "missing")
        write_new(self.source / "plan.json", self.plan_bytes)
        with self.assertRaisesRegex(ValueError, "different evidence"):
            import_training_config(self.store, self.source, "plan.json", "config-1")

    def test_resealed_snapshot_cannot_change_selected_training_set(self):
        folder = self.bundle()
        snapshot_path = folder / "snapshot.json"
        snapshot = loads(snapshot_path.read_bytes())
        snapshot["parameters"]["training"]["dataset"]["episodes"] = [99]
        snapshot_path.write_text(dumps(snapshot), encoding="utf-8")
        manifest_path = folder / "manifest.json"
        manifest = loads(manifest_path.read_bytes())
        manifest["files"]["snapshot.json"] = sha(snapshot_path.read_bytes())
        manifest_path.write_text(dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "does not match source configuration"):
            import_training_config(self.store, self.source, "train", "forged")

    def test_yaml_source_requires_separate_resolved_plan(self):
        yaml_bytes = b"schema_version: 2\nrole: vla\nplan_id: plan-1\nrun_name: train-1\n"
        write_new(self.source / "plan.yaml", yaml_bytes)
        write_new(self.source / "resolved.json", self.plan_bytes)
        launch = dict(self.launch, formal_plan_sha256=sha(yaml_bytes))
        write_new(self.source / "launch.json", dumps(launch))
        write_new(self.source / "runtime.json", self.runtime_bytes)
        with self.assertRaisesRegex(ValueError, "resolved_plan_path"):
            import_training_config(self.store, self.source, "plan.yaml", "blocked")
        import_training_config(self.store, self.source, "plan.yaml", "yaml-history",
                               launch_path="launch.json", runtime_path="runtime.json",
                               resolved_plan_path="resolved.json")
        record = self.store.get("yaml-history")[0]
        self.assertEqual(record["parameters"]["identity"]["plan_sha256"], sha(yaml_bytes))
        self.assertEqual(record["verification"]["plan_resolution"], "operator_supplied")


if __name__ == "__main__":
    unittest.main()
