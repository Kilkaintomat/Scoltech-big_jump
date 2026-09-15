"""Rendering Tables 1 and 2. A cell the run did not produce must stay visibly unfilled."""

from __future__ import annotations

from pathlib import Path

from onebigjump.reporting.tables import (
    PLACEHOLDER,
    render_table1,
    render_table2,
    to_latex,
    to_markdown,
    write_table,
)


class _P1:
    def rows(self):
        return [
            {
                "model": "m",
                "layer": 8,
                "statistic": "whitened",
                "subset": "verified",
                "m_traces": 120,
                "hill": 0.21,
                "hill_lo": 0.18,
                "hill_hi": 0.25,
                "moment": 0.19,
                "moment_lo": 0.14,
                "moment_hi": 0.24,
                "gpd": 0.20,
                "gpd_lo": 0.15,
                "gpd_hi": 0.26,
            },
            {
                "model": "m",
                "layer": 8,
                "statistic": "whitened",
                "subset": "refuted_post",
                "m_traces": 40,
                "hill": 0.44,
                "hill_lo": 0.31,
                "hill_hi": 0.58,
                "moment": None,
                "moment_lo": None,
                "moment_hi": None,
                "gpd": float("nan"),
                "gpd_lo": None,
                "gpd_hi": None,
            },
        ]


class _P2:
    def row(self):
        return {
            "model": "m",
            "layer": 8,
            "statistic": "whitened",
            "top1": 0.62,
            "top3": 0.88,
            "chance": 0.07,
            "surprisal_top1": 0.31,
            "perm_mean": 0.07,
            "perm_sd": 0.02,
            "perm_p": 0.0005,
        }


class TestPrimitives:
    def test_markdown_columns_are_aligned(self) -> None:
        out = to_markdown(["a", "bbbb"], [["1", "2"]])
        lines = out.strip().split("\n")
        assert len(lines) == 3
        assert all(line.count("|") == 3 for line in lines)

    def test_latex_uses_booktabs(self) -> None:
        out = to_latex(["a", "b"], [["1", "2"]], caption="c", label="tab:x")
        for token in (r"\toprule", r"\midrule", r"\bottomrule", r"\caption{c}", r"\label{tab:x}"):
            assert token in out

    def test_a_group_column_inserts_midrules(self) -> None:
        rows = [["A", "1"], ["A", "2"], ["B", "3"]]
        assert to_latex(["g", "v"], rows, group_column=0).count(r"\midrule") == 2


class TestTable1:
    def test_estimates_render_with_their_intervals(self) -> None:
        _, rows = render_table1([_P1()])
        assert rows[0][3] == "0.21 [0.18, 0.25]"
        assert rows[0][2] == "120"

    def test_missing_values_use_the_papers_placeholder(self) -> None:
        _, rows = render_table1([_P1()])
        assert rows[1][4] == PLACEHOLDER, "a None estimate"
        assert rows[1][5] == PLACEHOLDER, "a NaN estimate"

    def test_subset_labels_match_the_paper(self) -> None:
        _, rows = render_table1([_P1()])
        assert rows[1][1] == r"refuted, $t \geq t^*$"


class TestTable2:
    def test_the_chance_column_is_present(self) -> None:
        headers, rows = render_table2([_P2()])
        assert "chance" in headers
        assert rows[0][4] == "0.07"

    def test_the_permutation_null_shows_mean_and_spread(self) -> None:
        _, rows = render_table2([_P2()])
        assert rows[0][6] == r"0.07 $\pm$ 0.02"

    def test_the_p_value_keeps_three_digits(self) -> None:
        _, rows = render_table2([_P2()])
        assert rows[0][7] == "0.001"


class TestWriting:
    def test_both_formats_are_written(self, tmp_path: Path) -> None:
        headers, rows = render_table1([_P1()])
        paths = write_table(headers, rows, tmp_path, "table1", caption="Tail index")
        assert {p.suffix for p in paths} == {".md", ".tex"}
        assert all(p.stat().st_size > 0 for p in paths)
        assert "Tail index" in (tmp_path / "table1.tex").read_text(encoding="utf-8")
