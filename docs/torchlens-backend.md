# TorchLens optional backend — stage 1

Basin now owns `basin.torchlens_backend.capture_synthetic`, a real opt-in
TorchLens 2.23.0 capture API. It produces a JSON native envelope. The dedicated
`import-torchlens` command validates and indexes that envelope; `import-native`
remains available for generic imports, but dedicated TorchLens analysis requires
a record imported with the TorchLens adapter.
Core imports remain standard-library only. Torch/TorchLens are imported only
inside an explicit capture call; there is no automatic model execution via MCP.

The operator constructs a trusted eval-mode synthetic model inside a disposable
worker and calls:

```python
from basin.torchlens_backend import capture_synthetic
capture_synthetic(model, inputs, run_id="example", selected_modules=["shared"],
                  forward_seed=7, output="new-capture-directory")
```

Use the Rosetta WSL/Docker runner with its reviewed, hash-pinned optional wheels,
2 CPU, 4 GiB, no network and 180-second cap. The backend does not load models,
weights, executable evidence or datasets. JSON is limited to 16 MiB, selected
tensors to 4096 elements and exported graphs to 4096 ops. A new output directory
is mandatory; failure leaves an incomplete failure record. System Graphviz is
not required because this stage exports graph data without rendering diagrams.

`status=complete` means collection finished. `consistency=not_assessed` and
`live_integration_accepted=false` explicitly prevent it being mistaken for
transparent execution. The Rosetta three-case audit found exact selected
activations/output for torch/NumPy-noise examples, but Python-random computation
changed under tracing. Python global RNG also changed after all three cases.
Do not transparently insert this backend into training or rollout.

## Offline import and analysis

```bash
python -m basin --store outputs/history import-torchlens new-capture-directory/native.json --id capture-001
python -m basin --store outputs/history analyze-torchlens capture-001
python -m basin --store outputs/history artifact capture-001 torchlens.json --pointer /events/0
```

Python callers can use `basin.torchlens_data.import_torchlens(store, source, run_id)`
and `analyze_torchlens(store, run_id)`. The model API/MCP offers
`basin_import_torchlens` only with an operator-configured `--source` alias; the
read-only `basin_analyze_torchlens` pages `modules`, `edges`, or `issues` via its
`section`, `offset`, and `limit` parameters. The original JSON bytes are copied
to `artifacts/torchlens.json` and covered by Basin's run manifest SHA-256.

Statistics cover only saved finite JSON activation values: operation and element
counts, minimum, maximum, mean, RMS, and L2 norm. Empty observations report
null numeric statistics. A norm outside finite JSON range is null while any
representable RMS is retained. The per-activation SHA-256 is a collector claim;
the importer checks its syntax but does not reconstruct Torch's dtype-specific
raw bytes. Basin independently computes statistics from the stored JSON values.

Graph analysis matches each parent string to a unique exported operation label.
It returns resolved edges and unresolved/ambiguous/self/cyclic issues. Root count
and longest observed path are available only when references resolve without
ambiguity or cycles. These values describe the exported graph; they do not prove
TorchLens captured the complete model graph. `failure.json` can also be imported
as an incomplete record with no published operations.

This stage establishes Basin backend ownership, real synthetic capture and
native import/query. Moving Rosetta's existing collector to this backend,
general live-model execution, RNG isolation and complete graph validation are
not part of this five-minute stage. No historical evidence or existing store
is replaced or appended.
