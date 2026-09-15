"""Validate immutable inputs inside the allocation before any generation."""

from pathlib import Path

from onebigjump.e1.artifacts import digest, read_json, verify_manifest

HERE = Path("/beegfs/home/denis.rakhmankin/onebigjump/audit/p5_repair_20260914_v2")


def main():
    receipt = read_json(HERE / "preflight-result.json")
    manifest = Path(receipt["manifest"])
    if digest(manifest) != receipt["manifest_sha256"]:
        raise ValueError("changed preflight manifest")
    verify_manifest(manifest)
    metrics = read_json(manifest)["metrics"]
    if not metrics["passed"]:
        raise ValueError("CPU preflight did not pass")
    for name, expected in metrics["operational_files"].items():
        if digest(name) != expected:
            raise ValueError("changed operational file: " + name)
    source = HERE / "source/source-manifest.json"
    if digest(source) != receipt["source_sha256"]:
        raise ValueError("changed source identity")
    verify_manifest(source)
    print("P5 isolated pilot inputs verified", flush=True)


if __name__ == "__main__":
    main()
