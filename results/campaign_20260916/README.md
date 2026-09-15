# Experimental evidence snapshot — 2026-09-16

Exported UTC: 2026-09-15T23:28:59.191538+00:00

This folder contains compact reports, metrics, protocols and original manifests. All copied bytes are indexed in [export-manifest.json](export-manifest.json). Original manifest paths remain absolute Zhores paths; they are provenance, not a claim that omitted arrays or model weights are bundled here.

## Current evidence

- [Completed three-model miniF2F review](main-review/REPORT_RU.md).

- [Independent calibration, label audit and prospective ProofNet design](independent-design-and-audit/REPORT_RU.md).

- [P5 independent evaluation and analysis](p5-final/metrics.json): completed.

- [P2 fixed prospective protocol](../../audit/followthrough_20260915_v1/p2-confirmatory-protocol.json): acquisition ongoing at capture; no confirmatory P2 result is declared.

## P5 accounting

| Split | Assigned attempts | Verified | Invalid inference |
| --- | ---: | ---: | ---: |
| Calibration | 2000 | 359 | 1641 |
| Independent evaluation | 1000 | 175 | 825 |

Calibration/evaluation task overlap: 0.

The length predictor and jump localization are separate endpoints. A length trend alone does not identify a heavy-tail mechanism. All assigned attempts are retained in denominators.

## Reproduction

Use the code and frozen source/protocol manifests under `audit/`, plus the current `src/`, `scripts/` and `tests/`. Cluster entrypoints contain explicit Zhores paths. Rehydrating original execution requires the pinned model weights, benchmark inputs, Lean runtime and retained source/data stores; these are not Git objects. Do not rewrite original historical manifests after relocating files.

The small dated status PDF predates the final P5 result; `p5-final/metrics.json` and the table above supersede its in-progress P5 status. Earlier reviews remain dated historical evidence.

Model weights, activation matrices, large proof journals, runtime binaries, caches and credentials are intentionally not part of this source-and-evidence commit.
