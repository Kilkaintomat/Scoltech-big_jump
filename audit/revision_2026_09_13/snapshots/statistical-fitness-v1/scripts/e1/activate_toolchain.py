"""Validate and unpack a pinned toolchain archive onto node-local storage."""

import hashlib
import json
import os
import sys
import tarfile
from pathlib import Path, PurePosixPath


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    target = Path(sys.argv[2])
    manifest_path = Path(config["manifest"])
    if digest(manifest_path) != config["manifest_sha256"]:
        raise ValueError("toolchain manifest digest mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    archive = Path(config["archive"])
    if digest(archive) != config["archive_sha256"]:
        raise ValueError("toolchain archive digest mismatch")
    if manifest["outputs"][str(archive.resolve())] != config["archive_sha256"]:
        raise ValueError("toolchain archive is not an output of the pinned run")
    inventory_path = archive.parent / "inventory.json"
    if digest(inventory_path) != manifest["outputs"][str(inventory_path.resolve())]:
        raise ValueError("toolchain inventory digest mismatch")
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if inventory["toolchain"] != config["toolchain"]:
        raise ValueError("toolchain version mismatch")
    with tarfile.open(str(archive), "r") as handle:
        for member in handle.getmembers():
            for value in [member.name] + (
                [member.linkname] if member.issym() or member.islnk() else []
            ):
                path = PurePosixPath(value)
                if path.is_absolute() or ".." in path.parts:
                    raise ValueError("unsafe toolchain archive member: " + value)
        handle.extractall(str(target))
    for entry in inventory["entries"]:
        path = target / entry["path"]
        if "sha256" in entry and digest(path) != entry["sha256"]:
            raise ValueError("unpacked toolchain digest mismatch: " + str(path))
        if "symlink" in entry and os.readlink(str(path)) != entry["symlink"]:
            raise ValueError("unpacked toolchain symlink mismatch: " + str(path))
    print(str(manifest_path))


if __name__ == "__main__":
    main()
