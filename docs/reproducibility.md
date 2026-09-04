# Reproducibility

## The rule

No number in `paper_outputs/` is typed by a human. Every figure and table is generated from a
metrics file, and every metrics file is written by a run that leaves a manifest beside it.

## What a manifest records

`<out_dir>/manifest.json`, written by `onebigjump.manifests.run_manifest`, whether the run
succeeded or raised:

| Field | Why |
|---|---|
| `config` | the fully resolved, validated config -- not the file, the values |
| `seed` | every stochastic component is seeded from it |
| `environment.git` | commit, branch, and **whether the tree was dirty** |
| `environment.packages` | versions of the 13 packages that can change a number |
| `environment.hardware` | platform, cores, RAM, torch build, CUDA/MPS availability |
| `outputs` | every file produced, with size and SHA-256 |
| `metrics` | the headline numbers, so a run can be compared without re-reading its outputs |
| `notes` | **deviations from the paper's protocol**, recorded at the point they are made |
| `duration_s`, `status`, `error` | including for failed runs |

`manifest["reproducible"]` is `false` whenever the working tree was dirty. A figure produced from
a dirty tree cannot be regenerated from any commit, and is not shippable.

## Seeding

`onebigjump.reproducibility.seed_everything` seeds `random`, the legacy `numpy.random` global
(third-party code still draws from it) and torch. Project code does not use the global: it takes
an explicit `numpy.random.Generator` from `rng(seed)`, so two runs never share hidden state.

In the simulation each `(config, p)` gets its own generator seeded from the pair, so settings are
independent of each other and each is reproducible on its own.

## Strict JSON

`write_json` writes standards-conformant JSON: NaN and infinity become `null`. Both occur
legitimately -- the moment estimator's denominator can vanish, a bootstrap interval is NaN when
too few resamples survive, and `alpha` is infinite at `p = 0`, where no root of `E a^alpha = 1`
exists. `json.dumps` would emit the bare tokens `NaN` and `Infinity`, which are not JSON.

Writes are atomic: a temporary file in the same directory, renamed onto the target on success.
An interrupted run leaves no half-written metrics file to be mistaken for a finished one.

## Reproducing what exists

```bash
uv sync --python 3.11 --extra stats --extra viz --extra ml --extra dev
uv run python scripts/doctor.py --write
./scripts/run_tests.sh
uv run onebigjump run configs/simulation/figure1.yaml
```

The last command takes about two minutes on an Apple M4 and writes
`results/simulations/kesten/` (metrics, summary CSV, manifest),
`paper_outputs/metrics/figure1.json` and `paper_outputs/figures/figure1_kesten_dichotomy.{pdf,png}`.

## Known sources of non-determinism

| Source | Status |
|---|---|
| NumPy RNG | fully seeded and reproducible |
| Bootstrap and permutation resampling | seeded from the run seed |
| BLAS thread count | can change the last bits of a norm; never a reported digit |
| torch on MPS | not bitwise reproducible across torch versions; relevant to stage 11 only |
| Model sampling | to be pinned per run when stage 9 lands |
