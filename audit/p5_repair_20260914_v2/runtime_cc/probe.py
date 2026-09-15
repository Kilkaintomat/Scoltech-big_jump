from pathlib import Path
import ctypes
import os
import subprocess
import sysconfig

from onebigjump.e1.artifacts import digest, finish, read_json, verify_manifest, write_once

BASE = Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE = BASE / "audit/p5_repair_20260914_v2"
ROOT = HERE / "runtime_cc"
OUT = ROOT / ("probe-" + os.environ["SLURM_JOB_ID"])
SOURCE = HERE / "source/source-manifest.json"
CANDIDATES = [
    "/beegfs/shared/opt/rh/devtoolset-11/root/usr/bin/gcc",
    "/beegfs/shared/opt/rh/gcc-12.2.0/bin/gcc",
    "/beegfs/shared/opt/rh/devtoolset-9/root/usr/bin/gcc",
]


def main():
    OUT.mkdir(parents=True)
    src = OUT / "check.c"
    src.write_text("#include <Python.h>\n#include <stdint.h>\nint probe(void) { return (int)(sizeof(uint32_t)*10+2); }\n", encoding="utf-8")
    attempts = []
    selected = None
    for i, cc in enumerate(CANDIDATES):
        if not Path(cc).is_file():
            continue
        folder = str(Path(cc).parent) + "/"
        out = OUT / ("check-" + str(i) + ".so")
        extra = ["-fuse-ld=bfd", "-B" + folder, "-B/beegfs/shared/opt/rh/devtoolset-11/root/usr/bin/",
                 "-isystem", "/usr/include/x86_64-linux-gnu",
                 "-B/usr/lib/x86_64-linux-gnu/", "-L/usr/lib/x86_64-linux-gnu"]
        args = [cc, *extra, "-shared", "-fPIC", "-I" + sysconfig.get_paths()["include"], str(src), "-o", str(out)]
        compiler_libs = "/beegfs/shared/opt/rh/gcc-12.2.0/lib64:/beegfs/shared/opt/rh/devtoolset-11/root/usr/lib64"
        compiler_env = dict(os.environ)
        compiler_env["LD_LIBRARY_PATH"] = compiler_libs + ":" + os.environ.get("LD_LIBRARY_PATH", "")
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=compiler_env)
        log = OUT / ("compiler-" + str(i) + ".log")
        log.write_text(p.stdout, encoding="utf-8")
        print(cc, p.returncode, p.stdout, flush=True)
        attempts.append({"cc": cc, "exit_code": p.returncode, "log": str(log)})
        if p.returncode == 0:
            assert ctypes.CDLL(str(out)).probe() == 42
            selected = cc
            break
    if selected is None:
        raise RuntimeError("no compiler passed actual container build and load")
    wrapper = ROOT / "cc-wrapper.sh"
    # Paths are fixed, trusted, whitespace-free toolchain locations.
    wrapper.write_text('#!/usr/bin/env bash\nexport LD_LIBRARY_PATH="' + compiler_libs + ':${LD_LIBRARY_PATH:-}"\nexec ' + selected + ' ' + ' '.join(extra) + ' "$@"\n', encoding="utf-8")
    wrapper.chmod(0o555)
    version = subprocess.check_output([selected, "--version"], text=True)
    metrics = {"passed": True, "compiler": selected, "compiler_sha256": digest(selected),
               "version": version, "compiler_flags": extra, "compiler_library_path": compiler_libs, "attempts": attempts, "cpython_headers_and_shared_library_load": True}
    metric = write_once(OUT / "metrics.json", metrics)
    outputs = [metric, wrapper, src, *OUT.glob("*.log"), *OUT.glob("*.so")]
    manifest = finish(OUT, stage="P5-isolated-C-compiler-probe", context={"source": digest(SOURCE)},
        inputs=[SOURCE, Path(__file__), ROOT / "probe.sbatch", Path(selected)],
        outputs=outputs, metrics=metrics)
    write_once(ROOT / "probe-result.json", {"job_id": os.environ["SLURM_JOB_ID"],
        "manifest": str(manifest), "sha256": digest(manifest)})
    print(manifest, flush=True)


if __name__ == "__main__":
    main()
