# Released execution scope

The runnable entry point is the E1 **development pilot** described in PROTOCOL.md.
It uses the frozen development IDs, model revision, temperatures, attempts, original
token sequences and independent calibration split. Main is explicitly blocked in
scripts/e1/run.py until the scientific gates in PROTOCOL.md are implemented and met.

The pilot stages are generation, verification, extraction, measurement and descriptive
P1-P3 analysis. Each stage verifies its upstream manifests and accounts for every
attempt. A failed import of Mathlib is an infrastructure error, never a kernel label.
An unsuccessful stage prevents its dependent Slurm jobs from starting.

No pilot confidence intervals or confirmatory decisions are claimed. The main protocol's
task-bootstrap contrasts, simulation calibration, task-trajectory positional null,
refitted-transformation sensitivities and full family analyses are not implemented by
the descriptive pilot reporter. Pilot estimates/exclusions determine technical readiness
and must not be used to choose a favorable scientific hypothesis or test threshold.

Start after successful server checks and the live Lean gate:

```bash
bash scripts/e1/submit_pilot.sh /beegfs/home/denis.rakhmankin/onebigjump/runs/e1_20260908T171727Z FINAL_CHECK_JOB_ID [GPU_PREFLIGHT_JOB_ID]
```

The launcher creates an immutable source snapshot and submits separate GPU and CPU jobs.
Submission IDs are recorded under pilot/submission-*.json. The current exclusion of cn69
reflects a recorded Remote I/O error during this revision, not a general hardware claim.
Completed scientific outputs are not overwritten. New protocol/source revisions require
a new stage/run rather than rewriting a completed journal.

On Zhores, the pilot stage directories and Mathlib build/cache directories are backed
by GPFS through symlinks. Frozen protocol/input paths remain the same; manifests record
resolved artifact paths. The original BeeGFS Lean directories are retained separately.

Lean jobs verify lean-runtime.tar.sha256, extract the pinned runtime onto node-local
storage and bind it over the configured workspace inside the container. This avoids
slow random mmap reads over the network. The job removes its temporary copy on exit.
