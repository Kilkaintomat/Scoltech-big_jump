"""Exercise the actual CUDA mask before loading a model; retain its runtime provenance."""
from pathlib import Path
import os

import torch
import xgrammar as xgr
from onebigjump.e1.artifacts import digest, finish, read_json, verify_manifest, write_once

HERE = Path("/beegfs/home/denis.rakhmankin/onebigjump/audit/p5_repair_20260914_v2")
ROOT = HERE / "runtime_cc"
SOURCE = HERE / "source/source-manifest.json"


def main():
    receipt = read_json(ROOT / "probe-result.json")
    upstream = Path(receipt["manifest"])
    assert digest(upstream) == receipt["sha256"]
    verify_manifest(upstream)
    assert read_json(upstream)["metrics"]["passed"]
    assert os.environ["CC"] == str(ROOT / "cc-wrapper.sh")
    out = ROOT / ("mask-" + os.environ["SLURM_JOB_ID"])
    checks = []
    for vocab, cols, indices in [(151936, 151936, None), (151936, 151936, [0, 2]), (47, 64, None)]:
        generator = torch.Generator().manual_seed(2026091405)
        values = torch.randn((4, cols), generator=generator, dtype=torch.float32)
        masks = torch.randint(-(2**31), 2**31-1, (4, (vocab+31)//32),
                              generator=generator, dtype=torch.int32)
        expected = values.clone()
        xgr.apply_token_bitmask_inplace(expected, masks, vocab_size=vocab, indices=indices)
        actual = values.cuda()
        xgr.apply_token_bitmask_inplace(actual, masks.cuda(), vocab_size=vocab, indices=indices)
        torch.cuda.synchronize()
        assert torch.equal(actual.cpu(), expected)
        checks.append({"vocab_size": vocab, "logit_columns": cols, "indices": indices, "exact_cpu_gpu_match": True})
    metrics = {"passed": True, "checks": checks, "CC": os.environ["CC"],
               "compiler": read_json(upstream)["metrics"]["compiler"],
               "compiler_probe_manifest": str(upstream),
               "bind": os.environ.get("SINGULARITY_BIND"),
               "triton_cache": os.environ["TRITON_CACHE_DIR"]}
    metric = write_once(out / "metrics.json", metrics)
    manifest = finish(out, stage="P5-CUDA-bitmask-runtime-validation",
        context={"source": digest(SOURCE)}, inputs=[SOURCE, upstream, Path(__file__), ROOT/"resume.sbatch"],
        outputs=[metric], metrics=metrics)
    write_once(ROOT / "mask-result.json", {"manifest": str(manifest), "sha256": digest(manifest)})
    print("Actual CUDA grammar bitmask matches CPU exactly", flush=True)


if __name__ == "__main__":
    main()
