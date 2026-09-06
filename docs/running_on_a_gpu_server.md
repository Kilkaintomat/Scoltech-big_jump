# Running this repository on a GPU server

A runbook and the audit behind it. Portability was checked by resolving the lockfile against
`x86_64-unknown-linux-gnu`, not by assumption.

**Read [section 0](#0-before-booking-the-machine) before booking a machine**: the lock pins the
CUDA 13 runtime, which needs a driver of the 580 series or newer, and on an older one the install
succeeds while `torch.cuda.is_available()` quietly returns false.

## What was verified

| Check | Result |
|---|---|
| `uv sync --frozen --python-platform x86_64-unknown-linux-gnu` with `stats,viz,ml,dev` | resolves from the committed lock |
| CUDA stack pulled | 15 `nvidia-*` packages plus `triton`, i.e. the CUDA build of torch 2.13 |
| `--extra inference` (vllm) | resolves on the same platform |
| macOS-specific paths in `src/`, `scripts/`, `configs/`, `Makefile` | none |
| Device selection | `cuda` before `mps` before `cpu`; the MPS probe is guarded and is safe where the backend is absent |
| Lean toolchain | `elan` installs on Linux in user space; the toolchain and `lake-manifest.json` are committed, so the Mathlib revision is the one the labels were produced against |

If the driver is older than the 580 series, pin an earlier torch in `pyproject.toml` and re-lock;
nothing else in the repository depends on the torch version.

## Runbook: what to do on the server, in order

Each step has a check. Do not go past a failing one -- every later stage inherits the fault, and
the failure surfaces as a wall of parse errors or an empty table rather than as an error message.

### 0. Before booking the machine

```bash
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
```

**Check:** driver 580 or newer (the lock pins the CUDA 13 runtime) and at least 24 GB of memory
for a 7-8B prover. On an older driver the install still succeeds and
`torch.cuda.is_available()` then quietly returns false.

### 1. Environment

```bash
git clone <repo> && cd Scoltech-big_jump
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --python 3.11 --extra stats --extra viz --extra ml --extra dev --extra inference
uv run onebigjump doctor
```

**Check:** `doctor` prints a CUDA version rather than `-`. Drop `--extra inference` if vLLM is not
wanted; sampling then falls back to `transformers`.

### 2. Lean

```bash
./scripts/setup_lean.sh          # ~8 GB, user space, no sudo, 10-30 min
uv run onebigjump lean-doctor
```

**Check:** `Lean is usable`, and the toolchain reads `leanprover/lean4:v4.34.0-rc2` with Mathlib
`85e3a25e`. Those come from the committed `lean-toolchain` and `lake-manifest.json`; the script
deliberately does **not** run `lake update`, because several of Mathlib's dependencies are pinned
to `main` and re-resolving would verify against a different Mathlib than the recorded one.

### 3. Everything that needs no GPU, as a smoke test

```bash
make test-all                    # 429 tests, ~15 min, includes the live kernel
make figure1                     # ~6 min
```

**Check:** all tests pass and `paper_outputs/figures/figure1_kesten_dichotomy.pdf` appears. If the
Lean tests are *skipped* rather than passing, step 2 did not finish.

### 4. Problems to prove

The statements are committed, so there is nothing to do unless you want to refetch:

```bash
uv run python scripts/fetch_problems.py --all
```

1086 problems, about 1 MB: miniF2F 226 test + 231 valid, ProofNet 179 + 178, PutnamBench 272.
They are normalised against **this repository's Mathlib** -- statements opened at `:= by`, the
deprecated `∑ x in S` binder rewritten, stale import blocks split from the `open` lines that
matter, 38 commented-out placeholder rows dropped, and the scopes PutnamBench's `n !` and `uᵀ`
need supplied. A 180-statement sample elaborates at 98%, with miniF2F and PutnamBench at 60 of 60.

**Check:**

```bash
uv run python -c "from onebigjump.lean import load_problems; ps = load_problems('data/raw/minif2f_test.jsonl'); print(len(ps), ps[0].problem_id)"
```

142 of PutnamBench's 272 problems open with an `abbrev ..._solution := sorry` the model must fill
as well; they are flagged `requires_solution_term` and cannot verify as pure proofs. Filter them
out if you want a clean P1-P3 set.

### 5. Sample proofs

Edit `configs/models/prover_sampling.yaml` -- at least `model_id` and `problems`. Start small:
set `max_problems: 20` and confirm the output looks like Lean before committing a GPU-day.

```bash
uv run onebigjump run configs/models/prover_sampling.yaml
head -1 data/raw/prover-sampling/samples.jsonl | python -m json.tool | head -20
```

**Check:** the `proof` field starts with `theorem` and contains tactics. If it is prose, the prompt
template is wrong for this model family -- add one to `PROMPT_TEMPLATES` in
`src/onebigjump/lean/problems.py` rather than editing the config.

### 6. Label every tactic

```bash
uv run onebigjump lean-verify data/raw/prover-sampling/samples.jsonl --out-dir results/full/lean
```

**Check:** the printed table. `verified` must be well above zero -- stage 7 fits the whitening on
verified traces and a prover that proved nothing gives nothing to fit on. A large
`parse_error_discarded` count means the prompt template is still wrong. The manifest records
`whole_proof_vs_replay_disagreements`, which should be **0**; anything else means the labels are
not trustworthy and the run says so.

The Lean kernel is single-threaded per REPL and this is usually the slowest stage. Shard it:

```bash
for i in 0 1 2 3; do
  uv run onebigjump lean-verify data/raw/prover-sampling/samples.jsonl \
      --out-dir results/full/lean --shard $i --n-shards 4 &
done; wait
```

Shards are assigned by a hash of the trace id, so they are disjoint and stable. Each writes its
own `traces.shard0N.jsonl`. An interrupted run **resumes** by default, skipping traces already in
its output -- a full Mathlib import costs two minutes on every restart, so losing hours of work
to one crash is not a small thing. `--no-resume` re-verifies everything.

### 7. Residual streams, the table, and P1-P5

```bash
uv run onebigjump run configs/models/extract_activations.yaml
```

**Check:** the printed row count and the statistics present. If only `raw` appears, the calibration
was refused -- see the sizing note above; you need several hundred verified traces in the held-out
half. The manifest carries the reason.

### 8. Report

```bash
uv run onebigjump report
```

**Check:** no section says `dirty working tree`. If one does, the run was made from a modified
tree and its numbers cannot be tied to a commit; commit and re-run that stage.

## What runs without a GPU

| Command | GPU helps? |
|---|---|
| `make figure1` | no -- pure NumPy, ~6 min |
| `uv run onebigjump analyse-kesten` | no |
| `make lean-verify` | no -- the Lean kernel is CPU-bound |
| `make p4` | somewhat: 20-35 min per seed on an M4 |
| `make test-all` | no |

## Two things that will bite on a first real run

**The whitening needs a big calibration split.** `(mu, Sigma)` is fitted on verified traces of a
disjoint problem split, and a residual stream of width `d` needs on the order of `2d` increments
before the fit is determined. At `d = 4096` and ~10 steps per trace that is several hundred
verified traces in the *held-out* half alone. Below that the fit is refused, the run continues
with the raw statistic, and both the log and the manifest say so -- it does not silently return a
statistic with no spread left. If `whitened` and `innovation` are missing from your table, that
is why.

**A prover that proves nothing gives you no calibration.** The split prefers problems with at
least one verified trace, but if the model verifies nothing there is nothing to fit on. Check the
verified count from stage 2 before running stage 3.

## Memory

An 8B model in bfloat16 is about 16 GB of weights, so a 24 GB card is the practical floor for
Section 5.1 and 40 GB is comfortable. Sampling and extraction load the model separately, in two
runs, so they never have to share a card. The activations themselves are negligible: three read-out
layers times `(L+1)` positions times `d` in float32 is a few megabytes per trace. The binding
constraint is the model, not the extraction -- which is why `hooks.py` keeps only the requested
token positions rather than whole `(batch, seq, d)` tensors.

## Reproducibility on the new machine

Run from a **clean** working tree. Every run records the commit and whether the tree was dirty,
and a figure produced from a dirty tree cannot be regenerated from any commit; the report marks
those. See [`reproducibility.md`](reproducibility.md).
