import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


def module():
    script = Path(__file__).resolve().parents[2] / "scripts/e1/activate_repl.py"
    spec = importlib.util.spec_from_file_location("activate", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("tamper", [None, "binary", "manifest"])
def test_only_the_reviewed_manifested_binary_can_be_staged(tmp_path, tamper):
    binary = tmp_path / "repl"
    binary.write_bytes(b"reviewed runtime")
    sha = hashlib.sha256(binary.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"outputs": {str(binary): sha}}))
    pin = tmp_path / "pin.json"
    pin.write_text(
        json.dumps(
            {
                "manifest": str(manifest),
                "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "binary": str(binary),
                "binary_sha256": sha,
            }
        )
    )
    if tamper == "binary":
        binary.write_bytes(b"changed runtime")
    if tamper == "manifest":
        manifest.write_text("{}")
    target = tmp_path / "staged"
    if tamper:
        with pytest.raises(ValueError, match="differs"):
            module().activate(pin, target)
        assert not target.exists()
    else:
        assert module().activate(pin, target) == str(manifest)
        assert target.read_bytes() == binary.read_bytes()
