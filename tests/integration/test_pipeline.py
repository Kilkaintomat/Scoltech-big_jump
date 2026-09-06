"""The loop that was missing: labelled traces plus a model, to the deviations table.

Driven with GPT-2 on the handwritten Lean fixtures. The science is meaningless -- GPT-2 is not a
prover -- but every joint in the chain is real: real kernel labels, real activations, the real
calibration split, and the real table the predictions read.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.ml, pytest.mark.slow]

REPO = Path(__file__).resolve().parents[2]
TRACES = REPO / "results" / "pilot" / "lean" / "traces.jsonl"


@pytest.fixture(scope="module")
def model_and_tokenizer():
    transformers = pytest.importorskip("transformers")
    try:
        model = transformers.AutoModelForCausalLM.from_pretrained("gpt2")
        tok = transformers.AutoTokenizer.from_pretrained("gpt2")
    except Exception as exc:  # pragma: no cover - offline or no cached weights
        pytest.skip(f"gpt2 is not available: {exc}")
    model.eval()
    return model, tok


@pytest.fixture(scope="module")
def traces():
    from onebigjump.models.extraction import read_traces

    if not TRACES.is_file():
        pytest.skip(f"{TRACES} is absent; run `make lean-verify` first")
    return read_traces(TRACES)


class TestAlignment:
    def test_every_labelled_trace_aligns(self, traces, model_and_tokenizer) -> None:
        from onebigjump.models.extraction import trace_alignment

        _, tok = model_and_tokenizer
        for trace in traces:
            if not trace.labelled:
                continue
            assert trace_alignment(trace, tok) is not None, trace.trace_id

    def test_the_readout_lands_on_the_last_token_of_each_step(
        self, traces, model_and_tokenizer
    ) -> None:
        from onebigjump.models.extraction import trace_alignment

        _, tok = model_and_tokenizer
        trace = next(t for t in traces if t.trace_id == "ok-addcomm")
        text, alignment = trace_alignment(trace, tok)
        ids = tok(text, add_special_tokens=True)["input_ids"]
        assert alignment.complete
        assert tok.decode([ids[alignment.step_end_tokens[0]]]) == "]"

    def test_an_unlabelled_trace_is_not_aligned(self, traces, model_and_tokenizer) -> None:
        from onebigjump.models.extraction import trace_alignment

        _, tok = model_and_tokenizer
        discarded = next(t for t in traces if not t.labelled)
        assert trace_alignment(discarded, tok) is None or not discarded.steps


class TestExtractTable:
    @pytest.fixture(scope="class")
    def result(self, traces, model_and_tokenizer):
        from onebigjump.models.extraction import extract_table, stratified_calibration_split

        model, tok = model_and_tokenizer
        calibration = stratified_calibration_split(traces, frac=0.4, seed=0)
        return extract_table(
            traces,
            model,
            tok,
            calibration_problems=calibration,
            layer_fractions=(0.25, 0.5, 0.75),
            model_name="gpt2",
        )

    def test_unlabelled_traces_are_counted_not_analysed(self, result, traces) -> None:
        assert result.skipped["unlabelled"] == sum(not t.labelled for t in traces)
        assert result.n_extracted + result.skipped["unlabelled"] <= result.n_traces

    def test_the_calibration_split_is_disjoint_from_the_analysis(self, result) -> None:
        """Appendix B.1 fits on a disjoint *problem* split; a shared problem would leak."""
        assert not set(result.calibration_problems) & set(result.analysis_problems)

    def test_calibration_traces_never_enter_the_table(self, result) -> None:
        assert not set(result.table["prompt_id"]) & set(result.calibration_problems)

    def test_the_table_validates(self, result) -> None:
        from onebigjump.experiments.dataset import validate_table

        validate_table(result.table)

    def test_all_requested_layers_are_present(self, result) -> None:
        assert sorted(result.table["layer"].unique().tolist()) == result.layers
        assert result.layers == [3, 6, 9]

    def test_deviations_are_positive_and_finite(self, result) -> None:
        z = result.table["z"].to_numpy()
        assert (z > 0).all()
        assert result.table["z"].notna().all()

    def test_an_underdetermined_calibration_degrades_to_raw_only(self, result) -> None:
        """Three increments in 768 dimensions: refused, and the table says so by omission."""
        assert set(result.table["statistic"].unique()) == {"raw"}
        assert result.calibrations == {}

    def test_the_summary_is_serialisable(self, result) -> None:
        json.loads(json.dumps(result.summary()))


class TestRunExtraction:
    @pytest.fixture(scope="class")
    def run(self, tmp_path_factory, traces):
        from onebigjump.experiments.pipeline import run_extraction

        out = tmp_path_factory.mktemp("activations")
        payload = run_extraction(
            TRACES,
            "gpt2",
            out,
            layer_fractions=(0.5,),
            calibration_frac=0.4,
            device="cpu",
            dtype="float32",
            analyse=True,
        )
        return payload, out

    def test_the_table_is_written_and_readable(self, run) -> None:
        import pandas as pd

        _, out = run
        table = pd.read_parquet(out / "deviations.parquet")
        assert len(table) > 0
        assert "z" in table.columns

    def test_the_manifest_records_the_run(self, run) -> None:
        _, out = run
        man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        assert man["status"] == "ok"
        assert man["kind"] == "activations"
        assert "table" in {o["role"] for o in man["outputs"]}

    def test_missing_statistics_are_noted_not_hidden(self, run) -> None:
        _, out = run
        man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        assert any("whitened" in note for note in man["notes"])

    def test_the_analysis_runs_on_the_extracted_table(self, run) -> None:
        payload, _ = run
        assert "analysis" in payload
        assert payload["analysis"]["n_rows"] == payload["extraction"]["rows"]

    def test_predictions_the_table_cannot_support_are_named(self, run) -> None:
        payload, _ = run
        assert set(payload["analysis"]["not_run"]) <= {"P1", "P2", "P3", "P5"}
