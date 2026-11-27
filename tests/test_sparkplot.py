import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from sparkplot.cli import main
from sparkplot.core import (
    SparkPlotError,
    compute_histogram,
    compute_stats,
    render_bar_chart,
    render_box_plot,
    render_histogram,
    render_sparkline,
)


class TestSparkPlotCore(unittest.TestCase):
    def test_sparkline_basic_and_constant(self) -> None:
        s = render_sparkline([0, 50, 100])
        self.assertEqual(len(s), 3)
        self.assertEqual(s[0], "▁")
        self.assertEqual(s[-1], "█")
        self.assertEqual(render_sparkline([7, 7, 7], ascii_only=True), "===")

    def test_stats_and_outliers(self) -> None:
        st = compute_stats([10, 11, 12, 13, 14, 15, 50])
        self.assertEqual(st.count, 7)
        self.assertEqual(st.median, 13.0)
        self.assertEqual(st.outliers, (50.0,))
        self.assertEqual(st.whisker_high, 15.0)

    def test_histogram_counts_sum(self) -> None:
        vals = [1, 2, 2, 3, 5, 7, 8, 9, 10]
        bins = compute_histogram(vals, bins=4)
        self.assertEqual(len(bins), 4)
        self.assertEqual(sum(b.count for b in bins), len(vals))
        rendered = render_histogram(vals, bins=4, width=20, ascii_only=True)
        self.assertIn("#", rendered)

    def test_box_plot_multi_series(self) -> None:
        chart = render_box_plot(
            [("fast", [10, 12, 14, 15, 18]), ("slow", [30, 35, 40, 42, 65])],
            width=30,
            ascii_only=True,
        )
        lines = chart.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertIn("fast", lines[0])
        self.assertIn("slow", lines[1])

    def test_bar_chart_sorting(self) -> None:
        chart = render_bar_chart([("b", 10), ("a", 30), ("c", 20)], sort_order="desc", ascii_only=True)
        lines = chart.splitlines()
        self.assertTrue(lines[0].strip().startswith("a"))
        self.assertTrue(lines[-1].strip().startswith("b"))

    def test_empty_raises(self) -> None:
        with self.assertRaises(SparkPlotError):
            compute_stats([])


class TestSparkPlotCLI(unittest.TestCase):
    def test_cli_json_and_csv_group(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["--json", "spark", "1", "2", "3", "4"])
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["stats"]["count"], 4)
        self.assertEqual(payload["stats"]["median"], 2.5)

        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as tmp:
            tmp.write("group,val\nA,10\nA,12\nA,14\nB,20\nB,25\nB,30\n")
            tmp_path = tmp.name
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = main(["--json", "box", "--file", tmp_path, "--col", "val", "--group", "group"])
            self.assertEqual(code, 0)
            grouped = json.loads(buf.getvalue())
            self.assertEqual(grouped["A"]["median"], 12.0)
            self.assertEqual(grouped["B"]["median"], 25.0)
        finally:
            os.unlink(tmp_path)

    def test_cli_bad_number(self) -> None:
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(["spark", "1", "oops"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
