"""Optional integration tests; run in the bounded TorchLens container only."""

import json
import subprocess
import sys

import pytest


def test_core_backend_import_is_lazy():
    result = subprocess.run([sys.executable, "-c",
        "import sys; import basin.torchlens_backend; "
        "assert 'torch' not in sys.modules; assert 'torchlens' not in sys.modules"],
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_real_capture_import_query_and_repeat(tmp_path):
    from basin.adapters import import_native
    from basin.api import BasinAPI
    from basin.store import Store

    source = '''
import torch
from basin.torchlens_backend import capture_synthetic
class Model(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.shared = torch.nn.Linear(3, 3)
    def forward(self, x):
        return self.shared(self.shared(x))
torch.manual_seed(7)
capture_synthetic(Model().eval(), (torch.ones(2, 3),), run_id="basin-torchlens-stage1",
                  selected_modules=["shared"], forward_seed=7, output=__import__('sys').argv[1])
'''
    output = tmp_path / "capture"
    process = subprocess.run([sys.executable, "-c", source, str(output)],
                             capture_output=True, text=True, timeout=45)
    (tmp_path / "worker.log").write_text(process.stdout + process.stderr)
    assert process.returncode == 0, process.stderr
    envelope = json.loads((output / "native.json").read_text())
    assert envelope["parameters"]["collector"] == "basin.torchlens.v1"
    assert envelope["parameters"]["consistency"] == "not_assessed"
    assert not envelope["parameters"]["live_integration_accepted"]
    selected = [event["values"] for event in envelope["events"]
                if event["values"]["module"] == "shared" and event["values"]["saved"]]
    assert {row["call_index"] for row in selected} == {1, 2}
    store = Store(tmp_path / "history")
    assert import_native(store, output / "native.json", "capture")["status"] == "imported"
    assert import_native(store, output / "native.json", "capture")["status"] == "already_present"
    api = BasinAPI(store.root)
    assert api.call("basin_verify", {"run_id": "capture"})["data"]["integrity"] == "verified"
    result = api.call("basin_events", {"run_id": "capture", "step": 0})
    assert result["data"]["items"]
    artifact = api.call("basin_read_artifact", {
        "run_id": "capture", "name": "native.json", "pointer": "/parameters/collector"})
    assert artifact["data"]["value"] == "basin.torchlens.v1"


def test_selection_fails_before_capture(tmp_path):
    from basin.torchlens_backend import capture_synthetic

    with pytest.raises(ValueError, match="nonempty"):
        capture_synthetic(None, (), run_id="x", selected_modules=[],
                          forward_seed=0, output=tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()
