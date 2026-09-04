"""P1-P5 against the Kesten surrogate, where the answer is known in closed form."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from onebigjump.config import TailEstimationConfig
from onebigjump.experiments.dataset import SUBSETS, from_kesten, subset, validate_table
from onebigjump.experiments.p1_tail_separation import run_p1, tail_separation
from onebigjump.experiments.p2_localization import localization_rates, run_p2
from onebigjump.experiments.p3_overshoot import run_p3
from onebigjump.experiments.p5_length_law import fit_length_law, run_p5
from onebigjump.simulation.kesten import simulate

FAST = TailEstimationConfig(
    bootstrap_resamples=60, double_bootstrap_resamples=50, k_selector="fixed_frac", k_min=20
)


@pytest.fixture(scope="module")
def heuristic() -> pd.DataFrame:
    return from_kesten(simulate(0.05, n_traces=2500, n_steps=64, seed=1))


@pytest.fixture(scope="module")
def algorithmic() -> pd.DataFrame:
    return from_kesten(simulate(0.0, n_traces=2500, n_steps=64, seed=1))


class TestDataset:
    def test_the_table_has_the_declared_schema(self, heuristic: pd.DataFrame) -> None:
        from onebigjump.experiments.dataset import COLUMNS

        assert list(heuristic.columns) == list(COLUMNS)
        assert len(heuristic) == 2500 * 64

    def test_labels_are_absorbing(self, heuristic: pd.DataFrame) -> None:
        g = heuristic[heuristic["trace_id"] == heuristic["trace_id"].iloc[0]].sort_values("t")
        assert not np.any(np.diff(g["valid"].to_numpy().astype(int)) > 0)

    def test_a_non_absorbing_table_is_rejected(self, heuristic: pd.DataFrame) -> None:
        bad = heuristic.head(64).copy()
        bad.loc[bad.index[0], "valid"] = False
        bad.loc[bad.index[1], "valid"] = True
        with pytest.raises(ValueError, match="non-absorbing"):
            validate_table(bad)

    def test_a_missing_column_is_rejected(self, heuristic: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="missing columns"):
            validate_table(heuristic.drop(columns=["t_star"]))

    @pytest.mark.parametrize("name", sorted(SUBSETS))
    def test_every_subset_is_selectable(self, heuristic: pd.DataFrame, name: str) -> None:
        part = subset(heuristic, name)
        assert len(part) > 0

    def test_the_subsets_partition_the_refuted_traces(self, heuristic: pd.DataFrame) -> None:
        pre = subset(heuristic, "refuted_pre")
        post = subset(heuristic, "refuted_post")
        allr = subset(heuristic, "refuted_all")
        assert len(pre) + len(post) == len(allr)

    def test_pre_rejection_steps_come_strictly_before_t_star(self, heuristic: pd.DataFrame) -> None:
        pre = subset(heuristic, "refuted_pre")
        assert np.all(pre["t"].to_numpy() < pre["t_star"].to_numpy())

    def test_an_unknown_subset_raises(self, heuristic: pd.DataFrame) -> None:
        with pytest.raises(ValueError, match="unknown subset"):
            subset(heuristic, "nonsense")


class TestP1:
    def test_the_refuted_tail_is_heavier_than_the_verified_one(self, heuristic) -> None:
        res = run_p1(heuristic, FAST, min_steps=300, with_hill_plot=False)[0]
        assert res.separation["gamma_refuted"] > res.separation["gamma_verified"]
        assert res.separation["delta_refuted_minus_verified"] > 0

    def test_intervals_are_not_degenerate(self, heuristic) -> None:
        """A single bootstrap group collapses the interval to a point and reads as precision."""
        res = run_p1(heuristic, FAST, min_steps=300, with_hill_plot=False)[0]
        for name, est in res.estimates.items():
            boot = est["bootstrap"]["hill"]
            assert boot["ci_high"] > boot["ci_low"], name
            assert est["meta"]["bootstrap_unit"] == "trace"

    def test_the_verdict_is_conservative_when_intervals_overlap(self) -> None:
        estimates = {
            "verified": {"hill": 0.30, "bootstrap": {"hill": {"ci_low": 0.28, "ci_high": 0.32}}},
            "refuted_all": {"hill": 0.33, "bootstrap": {"hill": {"ci_low": 0.22, "ci_high": 0.44}}},
        }
        out = tail_separation(estimates)
        assert out["gamma_refuted"] > out["gamma_verified"]
        assert out["refuted_above_verified"] is False

    def test_separation_is_declared_when_intervals_are_disjoint(self) -> None:
        estimates = {
            "verified": {"hill": 0.10, "bootstrap": {"hill": {"ci_low": 0.08, "ci_high": 0.12}}},
            "refuted_all": {"hill": 0.40, "bootstrap": {"hill": {"ci_low": 0.35, "ci_high": 0.45}}},
        }
        assert tail_separation(estimates)["refuted_above_verified"] is True

    def test_missing_subsets_do_not_crash_the_verdict(self) -> None:
        out = tail_separation({"verified": {"hill": 0.3, "bootstrap": {"hill": {}}}})
        assert out["refuted_above_verified"] is None


class TestP2:
    @pytest.fixture(scope="class")
    def result(self, heuristic):
        return run_p2(heuristic, permutation_resamples=300, seed=0)[0]

    def test_localisation_reproduces_the_papers_numbers(self, result) -> None:
        """The paper predicts 0.85 top-1 at p = 0.05 and prints 0.016 for chance."""
        assert result.top1 == pytest.approx(0.85, abs=0.08)
        assert result.top3 > 0.94
        assert result.chance == pytest.approx(1 / 64, rel=1e-6)

    def test_it_is_far_above_chance(self, result) -> None:
        assert result.lift > 30

    def test_the_permutation_null_sits_at_chance(self, result) -> None:
        assert result.permutation["mean"] == pytest.approx(result.chance, abs=0.01)
        assert result.permutation["p_value"] < 0.01

    def test_the_jump_is_a_strong_per_step_detector(self, result) -> None:
        assert result.roc["auc"] > 0.95
        assert result.roc["n_positive"] == result.n_refuted

    def test_chance_is_reported_per_length_as_well(self, result) -> None:
        assert result.by_length
        for row in result.by_length:
            assert row["chance"] == pytest.approx(1.0 / row["L"])

    def test_the_algorithmic_control_localises_too(self, algorithmic) -> None:
        """Localisation tests the coupling and holds under both hypotheses (Theorem 4(ii))."""
        res = run_p2(algorithmic, permutation_resamples=200, seed=0)[0]
        assert res.top1 > 0.9

    def test_a_constant_score_localises_at_chance(self) -> None:
        traces = [{"z": np.ones(10), "t_star": 3, "L": 10, "surprisal": np.zeros(10)}]
        assert localization_rates(traces)["top1"] == 1.0  # rank 1 under ties by construction
        assert localization_rates(traces)["mean_rank"] == 1.0


class TestP3:
    def test_the_algorithmic_control_shows_a_marginal_overshoot(self, algorithmic) -> None:
        """Proposition 1 under rapid variation: Z/u -> 1 given Z > u."""
        tau = algorithmic.attrs["tau"]
        res = run_p3(
            algorithmic,
            thresholds_q=(1e-3,),
            bootstrap_resamples=100,
            min_over_tau=15,
            tau_override=tau,
        )[0]
        assert res.median_overshoot < 1.1
        assert res.frac_above["2"] < 0.05
        # Section 5.1: "under H_alg it should be <= 0". A significantly negative shape is the
        # bounded-support case, which is still xi = 0 and still algorithmic.
        assert res.shape_ci[1] <= 0.05

    def test_the_heuristic_mixture_overshoots_by_a_real_factor(self, heuristic) -> None:
        tau = heuristic.attrs["tau"]
        res = run_p3(
            heuristic,
            thresholds_q=(1e-3,),
            bootstrap_resamples=100,
            min_over_tau=15,
            tau_override=tau,
        )[0]
        assert res.median_overshoot > 1.15

    def test_all_three_overshoot_variants_are_reported(self, heuristic) -> None:
        res = run_p3(
            heuristic,
            thresholds_q=(1e-3,),
            bootstrap_resamples=50,
            min_over_tau=15,
            tau_override=heuristic.attrs["tau"],
        )[0]
        assert set(res.variants) == {"first", "trace_max", "unconditional"}
        assert np.isfinite(res.theta)

    def test_the_variants_coincide_when_there_is_no_clustering(self, algorithmic) -> None:
        """At theta = 1 the first exceedance is the only one, so the three must agree."""
        res = run_p3(
            algorithmic,
            thresholds_q=(1e-3,),
            bootstrap_resamples=50,
            min_over_tau=15,
            tau_override=algorithmic.attrs["tau"],
        )[0]
        assert res.theta == pytest.approx(1.0, abs=0.05)
        shapes = [v["shape"] for v in res.variants.values()]
        assert max(shapes) - min(shapes) < 0.05

    def test_clustering_attenuates_the_first_exceedance_variant(self, heuristic) -> None:
        """The finding: Theorem 4(ii) assumes extremal independence, which fails here."""
        res = run_p3(
            heuristic,
            thresholds_q=(1e-3,),
            bootstrap_resamples=50,
            min_over_tau=15,
            tau_override=heuristic.attrs["tau"],
        )[0]
        assert res.theta < 0.95
        assert res.variants["unconditional"]["shape"] > res.variants["first"]["shape"]


class TestP5:
    @pytest.fixture(scope="class")
    def varying_length(self) -> pd.DataFrame:
        ref = simulate(0.05, n_traces=2000, n_steps=64, seed=5)
        tau = ref.tolerance(0.98)
        parts = []
        for length in range(3, 13):
            tr = simulate(0.05, n_traces=400, n_steps=length, seed=100 + length)
            z = tr.z
            over = z > tau
            first = np.where(over.any(axis=1), over.argmax(axis=1), -1)
            ids = [f"L{length}-{i}" for i in range(z.shape[0])]
            part = pd.DataFrame(
                {
                    "trace_id": np.repeat(ids, length),
                    "prompt_id": f"L{length}",
                    "model": "kesten",
                    "layer": 0,
                    "statistic": "raw",
                    "t": np.tile(np.arange(length), z.shape[0]),
                    "L": length,
                    "z": z.ravel(),
                    "valid": True,
                    "t_star": np.repeat(np.where(first < 0, np.nan, first), length),
                    "outcome": np.repeat(np.where(first < 0, "verified", "refuted"), length),
                    "surprisal": np.nan,
                }
            )
            part["valid"] = part["t_star"].isna() | (part["t"] < part["t_star"])
            parts.append(part)
        return pd.concat(parts, ignore_index=True)

    def test_the_law_is_not_rejected(self, varying_length) -> None:
        fit = run_p5(varying_length)[0].fit
        assert fit.p_value > 0.01
        assert fit.fits

    def test_the_degrees_of_freedom_count_one_free_parameter(self, varying_length) -> None:
        """Only c = theta * Fbar(tau) enters the likelihood, so df = n_lengths - 1."""
        res = run_p5(varying_length)[0]
        assert res.fit.df == len(res.observed) - 1

    def test_theta_comes_from_the_extremal_index(self, varying_length) -> None:
        fit = run_p5(varying_length)[0].fit
        assert fit.theta_source == "extremal index"
        assert 0.0 < fit.theta <= 1.0

    def test_predictions_track_the_observed_accuracies(self, varying_length) -> None:
        res = run_p5(varying_length)[0]
        for row in res.observed:
            predicted = float(np.exp(-res.fit.rate_per_step * row["L"]))
            assert abs(predicted - row["accuracy"]) < 0.05

    def test_accuracy_decays_with_length(self, varying_length) -> None:
        acc = [r["accuracy"] for r in run_p5(varying_length)[0].observed]
        assert acc[0] > acc[-1]

    def test_too_few_lengths_raises(self) -> None:
        z = np.random.default_rng(0).pareto(2.0, 5000) + 1.0
        with pytest.raises(ValueError, match="at least 3 distinct lengths"):
            fit_length_law({3: (90, 100), 4: (80, 100)}, z)

    def test_a_pinned_theta_rescales_tau_not_the_rate(self) -> None:
        z = np.random.default_rng(0).pareto(2.0, 20000) + 1.0
        counts = {length: (int(100 * np.exp(-0.02 * length)), 100) for length in range(3, 13)}
        loose = fit_length_law(counts, z, theta=1.0)
        tight = fit_length_law(counts, z, theta=0.3)
        assert loose.rate_per_step == pytest.approx(tight.rate_per_step, rel=1e-6)
        assert tight.tau < loose.tau, "a smaller theta needs a lower tolerance for the same rate"
