"""Command-line interface and input loaders for sparkplot."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from typing import Dict, List, Optional, Tuple

from . import __version__
from .core import (
    SparkPlotError,
    compute_histogram,
    compute_stats,
    fmt_num,
    render_bar_chart,
    render_box_plot,
    render_histogram,
    render_sparkline,
)


def _parse_float(token: str) -> float:
    try:
        return float(token.strip())
    except ValueError as exc:
        raise SparkPlotError(f"Not a valid number: '{token}'") from exc


def _load_numbers(
    positional: List[str],
    file_path: Optional[str],
    col: Optional[str],
) -> List[float]:
    if file_path:
        return _load_numbers_from_file(file_path, col)
    if positional:
        return [_parse_float(x) for x in positional]
    if not sys.stdin.isatty():
        text = sys.stdin.read().strip()
        if not text:
            return []
        if text.startswith("["):
            return _extract_numbers_from_json(text, col)
        if col:
            return _extract_column_from_csv(text.splitlines(), col)
        tokens = [tok for tok in text.replace(",", " ").split() if tok]
        return [_parse_float(tok) for tok in tokens]
    return []


def _extract_numbers_from_json(text: str, col: Optional[str]) -> List[float]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SparkPlotError(f"Invalid JSON input: {exc}") from exc
    if not isinstance(data, list):
        raise SparkPlotError("JSON input must be a list of numbers or objects")
    out: List[float] = []
    for item in data:
        if isinstance(item, (int, float)):
            out.append(float(item))
        elif isinstance(item, dict):
            if not col:
                raise SparkPlotError("JSON array of objects requires --col")
            if col in item and item[col] is not None and str(item[col]).strip() != "":
                out.append(_parse_float(str(item[col])))
        else:
            raise SparkPlotError(f"Unsupported JSON element: {type(item).__name__}")
    return out


def _extract_column_from_csv(lines: List[str], col: str) -> List[float]:
    reader = csv.DictReader(lines)
    if not reader.fieldnames or col not in reader.fieldnames:
        raise SparkPlotError(f"Column '{col}' not found in CSV header {reader.fieldnames}")
    vals: List[float] = []
    for row in reader:
        cell = (row.get(col) or "").strip()
        if cell:
            vals.append(_parse_float(cell))
    return vals


def _load_numbers_from_file(path: str, col: Optional[str]) -> List[float]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read().strip()
    except OSError as exc:
        raise SparkPlotError(f"Cannot read '{path}': {exc}") from exc

    if not text:
        return []
    if path.endswith(".json") or text.startswith("["):
        return _extract_numbers_from_json(text, col)
    if col:
        return _extract_column_from_csv(text.splitlines(), col)
    tokens = [tok for tok in text.replace(",", " ").split() if tok]
    return [_parse_float(tok) for tok in tokens]


def _load_grouped_series(
    file_path: Optional[str],
    col: str,
    group_col: str,
) -> List[Tuple[str, List[float]]]:
    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except OSError as exc:
            raise SparkPlotError(f"Cannot read '{file_path}': {exc}") from exc
    elif not sys.stdin.isatty():
        lines = sys.stdin.read().splitlines()
    else:
        raise SparkPlotError("--group requires --file or piped CSV stdin")

    reader = csv.DictReader(lines)
    if not reader.fieldnames:
        raise SparkPlotError("Empty CSV input")
    for required in (col, group_col):
        if required not in reader.fieldnames:
            raise SparkPlotError(f"Column '{required}' not found in CSV header {reader.fieldnames}")

    grouped: Dict[str, List[float]] = {}
    for row in reader:
        g = (row.get(group_col) or "").strip() or "(empty)"
        cell = (row.get(col) or "").strip()
        if cell:
            grouped.setdefault(g, []).append(_parse_float(cell))
    return list(grouped.items())


def _load_pairs(
    positional: List[str],
    file_path: Optional[str],
    label_col: Optional[str],
    value_col: Optional[str],
) -> List[Tuple[str, float]]:
    if positional:
        pairs: List[Tuple[str, float]] = []
        for item in positional:
            sep = "=" if "=" in item else (":" if ":" in item else None)
            if not sep:
                raise SparkPlotError(f"Expected label=value pair, got '{item}'")
            lbl, raw_val = item.split(sep, 1)
            pairs.append((lbl.strip(), _parse_float(raw_val)))
        return pairs

    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                text = fh.read().strip()
        except OSError as exc:
            raise SparkPlotError(f"Cannot read '{file_path}': {exc}") from exc
    elif not sys.stdin.isatty():
        text = sys.stdin.read().strip()
    else:
        return []

    if not text:
        return []

    if text.startswith("{"):
        data = json.loads(text)
        return [(str(k), _parse_float(str(v))) for k, v in data.items()]

    lines = [line for line in text.splitlines() if line.strip()]
    if label_col and value_col:
        reader = csv.DictReader(lines)
        if not reader.fieldnames:
            raise SparkPlotError("Empty CSV input")
        return [
            ((row.get(label_col) or "").strip(), _parse_float(row.get(value_col) or ""))
            for row in reader
            if (row.get(value_col) or "").strip()
        ]

    pairs = []
    for row in csv.reader(lines):
        if len(row) < 2:
            raise SparkPlotError(f"Expected at least 2 columns per row, got {row}")
        pairs.append((row[0].strip(), _parse_float(row[1])))
    return pairs


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sparkplot",
        description="Terminal sparklines, histograms, box plots and bar charts.",
    )
    parser.add_argument("--version", action="version", version=f"sparkplot {__version__}")
    parser.add_argument("--ascii", action="store_true", help="Use plain ASCII glyphs")
    parser.add_argument("--json", action="store_true", help="Output JSON")

    sub = parser.add_subparsers(dest="command", required=True)

    p_spark = sub.add_parser("spark", help="Render a sparkline and summary stats")
    p_spark.add_argument("values", nargs="*", help="Numeric values (reads stdin if omitted)")
    p_spark.add_argument("--file", default=None, help="Read numbers from a file (txt, CSV, JSON)")
    p_spark.add_argument("--col", default=None, help="Column/key name for CSV or JSON objects")
    p_spark.add_argument("--no-stats", action="store_true", help="Print only the sparkline")

    p_hist = sub.add_parser("hist", help="Render a horizontal frequency histogram")
    p_hist.add_argument("values", nargs="*", help="Numeric values (reads stdin if omitted)")
    p_hist.add_argument("--file", default=None, help="Read numbers from a file")
    p_hist.add_argument("--col", default=None, help="Column/key name for CSV or JSON objects")
    p_hist.add_argument("--bins", type=int, default=8, help="Number of bins (default: 8)")
    p_hist.add_argument("--width", type=int, default=36, help="Max bar width (default: 36)")

    p_box = sub.add_parser("box", help="Render a box-and-whisker plot")
    p_box.add_argument("values", nargs="*", help="Numeric values (reads stdin if omitted)")
    p_box.add_argument("--file", default=None, help="Read numbers from a file")
    p_box.add_argument("--col", default=None, help="Column/key name for CSV or JSON objects")
    p_box.add_argument("--group", default=None, help="Group column in CSV for multi-series comparison")
    p_box.add_argument("--label", default="data", help="Series label for single-series mode")
    p_box.add_argument("--width", type=int, default=44, help="Plot axis width (default: 44)")

    p_bar = sub.add_parser("bar", help="Render a horizontal bar chart from label/value pairs")
    p_bar.add_argument("pairs", nargs="*", help="Pairs formatted as label=value")
    p_bar.add_argument("--file", default=None, help="Read CSV or JSON object from a file")
    p_bar.add_argument("--label-col", default=None, help="Label column name for CSV with header")
    p_bar.add_argument("--value-col", default=None, help="Value column name for CSV with header")
    p_bar.add_argument("--sort", choices=["asc", "desc"], default=None, help="Sort bars by value")
    p_bar.add_argument("--width", type=int, default=36, help="Max bar width (default: 36)")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "spark":
            vals = _load_numbers(args.values, args.file, args.col)
            line = render_sparkline(vals, ascii_only=args.ascii)
            stats = compute_stats(vals)
            if args.json:
                print(json.dumps({"sparkline": line, "stats": stats.to_dict()}, indent=2))
            else:
                print(line)
                if not args.no_stats:
                    print(
                        f"n={stats.count}  min={fmt_num(stats.minimum)}  "
                        f"median={fmt_num(stats.median)}  mean={fmt_num(stats.mean)}  "
                        f"p95={fmt_num(stats.p95)}  max={fmt_num(stats.maximum)}  "
                        f"stdev={fmt_num(stats.stdev)}"
                    )
            return 0

        if args.command == "hist":
            vals = _load_numbers(args.values, args.file, args.col)
            bins = compute_histogram(vals, bins=args.bins)
            if args.json:
                print(
                    json.dumps(
                        {
                            "bins": [b.to_dict() for b in bins],
                            "stats": compute_stats(vals).to_dict(),
                        },
                        indent=2,
                    )
                )
            else:
                print(render_histogram(vals, bins=args.bins, width=args.width, ascii_only=args.ascii))
            return 0

        if args.command == "box":
            if args.group:
                if not args.col:
                    raise SparkPlotError("--group requires --col")
                series = _load_grouped_series(args.file, args.col, args.group)
            else:
                vals = _load_numbers(args.values, args.file, args.col)
                series = [(args.label, vals)]
            if args.json:
                payload = {name: compute_stats(vals).to_dict() for name, vals in series}
                print(json.dumps(payload, indent=2))
            else:
                print(render_box_plot(series, width=args.width, ascii_only=args.ascii))
            return 0

        if args.command == "bar":
            pairs = _load_pairs(args.pairs, args.file, args.label_col, args.value_col)
            if args.json:
                rows = list(pairs)
                if args.sort == "asc":
                    rows.sort(key=lambda p: p[1])
                elif args.sort == "desc":
                    rows.sort(key=lambda p: p[1], reverse=True)
                print(json.dumps([{"label": k, "value": v} for k, v in rows], indent=2))
            else:
                print(
                    render_bar_chart(
                        pairs,
                        width=args.width,
                        sort_order=args.sort,
                        ascii_only=args.ascii,
                    )
                )
            return 0

    except SparkPlotError as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
