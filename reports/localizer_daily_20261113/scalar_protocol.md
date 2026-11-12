# Position, surprisal and tactic-feature ablations, 13 November 2026

Exploratory analysis requested after observing differing DeepSeek and Goedel localization gains. This is not new confirmatory data and not a test of Kesten dynamics.

Population: unchanged historical ProofNet learned cohort, DeepSeek 452 traces/166 tasks; Goedel 259/133. Frozen transfer to eligible Putnam traces 118/58 and 48/35. Target: first Lean-rejected tactic, conditional on a localized failed proof; full generated proof is available. This is retrospective localization, not streaming, proof success, or causal error prevention.

Feature groups:
* P: spline absolute and relative tactic position, first/last indicators.
* S: spline of mean token surprisal of the current tactic only. No position, no missing-predecessor indicator, no adjacent difference.
* C: spline log(1+token count), tactic category. C can indirectly correlate with position.
* W: standardized log(1+whitened jump norm), scalar only.
* U: uniform position probability; reported Hit is expected 1/L, not earliest-tie accuracy.
* MD, MDW: historical full baseline with signed/absolute adjacent surprisal change, with/without W. These are reproduction controls; delta-q is not called position-free because its first value is constructed as zero.

18 arms: U/P/S/C/PS/PC/SC/PSC and each with W, plus MD/MDW. Existing nested five outer / three inner group folds and ridge lambda grid 0.0001,0.001,0.01,0.1,1,10 are frozen. Train-only weighted spline knots, scales, category grouping. Optimize same conditional-softmax task-weighted NLL. All subsets are retrained; no test-set feature or lambda selection. Expected approximately 3264 nonuniform fits including frozen fits. 0 GPU-hours; CPU Slurm only. Each arm's Putnam lambda uses mean inner-CV errors over the five ProofNet outer folds, then train on all ProofNet. No Putnam tuning.

Primary numerical output: equal-task, then equal-attempt within-task Hit and NLL; secondary window +/-1 and attempt weighting. Paired task bootstrap of fixed OOF/frozen predictions with 20000 draws; no claim it includes refitting uncertainty. For fewer than20 tasks no interval. Predefined contrast family, per model/dataset: adding P to S, S to P, C to PS, P to SC, S to PC, W to P/S/PS/PSC/MD. Report unadjusted intervals and Holm-corrected two-sided centered-bootstrap p across all80 metric contrasts. All remain exploratory.

Full 2^3 P/S/C factorial permits Shapley decomposition of held-out NLL reduction from uniform to PSC. This quantifies predictive contribution under this fitting procedure, not a semantic or causal explanation. Direct PSC logit margin contributions true rejection versus strongest wrong candidate saved per trace. Report nonfirst subset retaining all candidate positions and fixed predictions, first-error subset, and lengths2-4/5-10/11+; these are descriptive stratification, not retraining or chosen thresholds.

Quality checks: exact reproduction of historical M0/M0W/MD/MDW probabilities (<1e-6), disjoint group folds, train-only preprocessing, excluded-feature invariance and S candidate permutation equivariance, finite converged optimization, probabilities sum1. Do not modify previous experiments, checkpoints, or queue priorities. No public publication.
