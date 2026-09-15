# Publication validation — 16 September 2026

Validation ran on Zhores through Slurm job `8468381` in the isolated publication checkout.
The commands in `validation.sbatch` implement the repository's `make test` and `make test-all`
checks using the existing pinned environment rather than installing dependencies again.

- Ruff lint and formatting: passed.
- Mypy: passed.
- Fast pytest suite: 635 passed; 0 failures, 0 errors, 0 skips.
- Full pytest suite: 734 passed; 0 failures, 0 errors, 0 skips.

The full suite includes actual Lean and GPT-2 integration tests. JUnit XML files are retained beside this report.
Source/evidence SHA-256 values were checked against Git's staged bytes, including CSV line endings.
No paper-output numbers were edited. Frozen historical source snapshots remain byte-preserved;
whitespace checks apply to current code and publication documentation.

Current src/scripts/tests validated using pinned installed environment in isolated publication checkout. Historical snapshots retain original bytes and are not claimed to have been re-executed. Original REPO provides container and Lean assets; E1_SNAPSHOT/PYTHONPATH point to publication checkout. The environment's original dirty-tree provenance warning is retained, not retroactively relabeled.

Model weights, large journals/activation arrays and installed third-party packages remain outside Git.
See `source-inventory.json`, `validation.json` and `../../results/campaign_20260916/export-manifest.json` for machine-readable provenance.
