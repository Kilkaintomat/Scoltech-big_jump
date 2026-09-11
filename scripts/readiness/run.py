"""Execute exactly one immutable, resumable expansion stage inside a Slurm job."""

import argparse
import os
from pathlib import Path

from filelock import FileLock

from onebigjump.e1.artifacts import read_json, verify_manifest
from onebigjump.readiness import controls, deduction, p4, whitening


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--phase", default="pilot")
    parser.add_argument("--scenario")
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--n-shards", type=int, default=1)
    args = parser.parse_args()
    source = Path(os.environ["E1_SNAPSHOT"]) / "source-manifest.json"
    verify_manifest(source)
    args.folder.mkdir(parents=True, exist_ok=True)
    with FileLock(str(args.folder / "stage.lock"), timeout=0):
        if (args.folder / "manifest.json").exists():
            verify_manifest(args.folder / "manifest.json")
            return
        if args.stage == "calibration":
            controls.calibrate(
                args.folder, read_json(args.config), source, args.scenario, args.shard
            )
        elif args.stage == "calibration-summary":
            controls.summarize_calibration(args.folder, args.root, source)
        elif args.stage == "positional":
            controls.sidecar(args.folder, args.root, args.phase, source)
        elif args.stage == "whitening":
            whitening.run(args.folder, args.root, args.phase, source, args.shard)
        elif args.stage == "p4-train":
            p4.train(args.folder, read_json(args.config), source)
        elif args.stage == "p4-measure":
            p4.measure(args.folder, args.root, read_json(args.config), source)
        elif args.stage == "p4-tail":
            p4.full_tail(args.folder, args.root, source)
        elif args.stage == "p4-summary":
            p4.summarize(args.folder, args.root, source)
        elif args.stage == "deduction-population":
            deduction.population(args.root, source)
        elif args.stage == "deduction-generate":
            deduction.generate(args.root, args.phase, source, args.shard, args.n_shards)
        elif args.stage in {
            "deduction-verify",
            "deduction-extract",
            "deduction-measure",
            "deduction-analyze",
        }:
            getattr(deduction, args.stage.split("-")[1])(args.root, args.phase, source)
        elif args.stage == "deduction-gate":
            deduction.gate(args.root, source)
        else:
            raise ValueError("unknown stage " + args.stage)


if __name__ == "__main__":
    main()
