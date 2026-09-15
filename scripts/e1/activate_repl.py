"""Python 3.6 file management: stage only the REPL binary pinned by immutable source."""

import hashlib
import json
import shutil
import sys
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def activate(pin_path, destination):
    pin = json.loads(Path(pin_path).read_text(encoding="utf-8"))
    manifest = Path(pin["manifest"])
    if digest(manifest) != pin["manifest_sha256"]:
        raise ValueError("REPL runtime manifest differs from frozen source pin")
    record = json.loads(manifest.read_text(encoding="utf-8"))
    binary = Path(pin["binary"])
    if record["outputs"].get(str(binary)) != pin["binary_sha256"]:
        raise ValueError("REPL binary is not an output of its build manifest")
    if digest(binary) != pin["binary_sha256"]:
        raise ValueError("REPL runtime binary differs from frozen source pin")
    shutil.copy2(str(binary), str(destination))
    if digest(destination) != pin["binary_sha256"]:
        raise ValueError("staged REPL binary copy failed validation")
    return str(manifest)


if __name__ == "__main__":
    print(activate(sys.argv[1], sys.argv[2]))
