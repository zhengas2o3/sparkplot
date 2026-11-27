"""Core statistical summaries and terminal chart renderers."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Sequence, Tuple

_UNICODE_SPARK = "▁▂▃▄▅▆▇█"
_ASCII_SPARK = " .:-=+*#"


class SparkPlotError(ValueError):
    """Raised on empty or malformed numeric inputs."""


@dataclass(frozen=True)
class SummaryStats:
    count: int
    minimum: float
    q1: float
    median: float
    q3: float
    p95: float
    maximum: float
    mean: float
    stdev: float
    whisker_low: float
    whisker_high: float
    outliers: Tuple[float, ...]

    def to_dict(self) -> Dict[str, object]:
        return {
            "count": self.count,
            "min": self.minimum,
            "q1": self.q1,
            "median": self.median,
            "q3": self.q3,
            "p95": self.p95,
            "max": self.maximum,
            "mean": self.mean,
            "stdev": self.stdev,
            "whisker_low": self.whisker_low,
            "whisker_high": self.whisker_high,
            "outliers": list(self.outliers),
        }


@dataclass(frozen=True)
class HistogramBin:
    low: float
    high: float
    count: int

    def to_dict(self) -> Dict[str, object]:
        return {"low": self.low, "high": self.high, "count": self.count}


def fmt_num(value: float) -> str:
    """Compact human-readable number formatting."""
    if math.isnan(value) or math.isinf(value):
        return str(value)
    if abs(value - round(value)) < 1e-9 and abs(value) < 1e12:
        return str(int(round(value)))
    if abs(value) >= 1000 or (0 < abs(value) < 0.01):
        return f"{value:.4g}"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _percentile(sorted_vals: Sequence[float], pct: float) -> float:
    """Linear-interpolated percentile (R-7 method, matching NumPy default)."""
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    pos = (n - 1) * (pct / 100.0)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    frac = pos - lo
    return sorted_vals[lo] + frac * (sorted_vals[hi] - sorted_vals[lo])


def compute_stats(values: Sequence[float]) -> SummaryStats:
    """Compute descriptive statistics and Tukey 1.5*IQR whiskers/outliers."""
    clean = [float(v) for v in values if not math.isnan(v) and not math.isinf(v)]
    if not clean:
        raise SparkPlotError("No finite numeric values provided")

    ordered = sorted(clean)
    n = len(ordered)
    mean = sum(ordered) / n
    if n > 1:
        variance = sum((x - mean) ** 2 for x in ordered) / (n - 1)
        stdev = math.sqrt(variance)
    else:
        stdev = 0.0

    q1 = _percentile(ordered, 25.0)
    median = _percentile(ordered, 50.0)
    q3 = _percentile(ordered, 75.0)
    p95 = _percentile(ordered, 95.0)

    iqr = q3 - q1
    fence_low = q1 - 1.5 * iqr
    fence_high = q3 + 1.5 * iqr

    inliers = [x for x in ordered if fence_low <= x <= fence_high]
    whisker_low = inliers[0] if inliers else ordered[0]
    whisker_high = inliers[-1] if inliers else ordered[-1]
    outliers = tuple(x for x in ordered if x < fence_low or x > fence_high)

    return SummaryStats(
        count=n,
        minimum=ordered[0],
        q1=q1,
        median=median,
        q3=q3,
        p95=p95,
        maximum=ordered[-1],
        mean=mean,
        stdev=stdev,
        whisker_low=whisker_low,
        whisker_high=whisker_high,
        outliers=outliers,
    )


def render_sparkline(values: Sequence[float], *, ascii_only: bool = False) -> str:
    """Render a one-line sparkline for a sequence of numbers."""
    clean = [float(v) for v in values if not math.isnan(v) and not math.isinf(v)]
    if not clean:
        raise SparkPlotError("No finite numeric values provided")

    glyphs = _ASCII_SPARK if ascii_only else _UNICODE_SPARK
    lo, hi = min(clean), max(clean)
    span = hi - lo
    if span == 0:
        mid = glyphs[len(glyphs) // 2]
        return mid * len(clean)

    levels = len(glyphs) - 1
    out = []
    for v in clean:
        idx = int(round(((v - lo) / span) * levels))
        idx = max(0, min(levels, idx))
        out.append(glyphs[idx])
    return "".join(out)


def compute_histogram(values: Sequence[float], *, bins: int = 10) -> List[HistogramBin]:
    """Bucket values into equal-width histogram bins."""
    if bins < 1:
        raise SparkPlotError("bins must be >= 1")
    clean = [float(v) for v in values if not math.isnan(v) and not math.isinf(v)]
    if not clean:
        raise SparkPlotError("No finite numeric values provided")

    lo, hi = min(clean), max(clean)
    if lo == hi:
        return [HistogramBin(low=lo, high=hi, count=len(clean))]

    step = (hi - lo) / bins
    counts = [0] * bins
    for v in clean:
        idx = int((v - lo) / step)
        if idx >= bins:
            idx = bins - 1
        counts[idx] += 1

    return [
        HistogramBin(low=lo + i * step, high=lo + (i + 1) * step, count=counts[i])
        for i in range(bins)
    ]


def render_histogram(
    values: Sequence[float],
    *,
    bins: int = 10,
    width: int = 36,
    ascii_only: bool = False,
) -> str:
    """Render a horizontal terminal frequency histogram."""
    if width < 4:
        raise SparkPlotError("width must be >= 4")
    hist_bins = compute_histogram(values, bins=bins)
    max_count = max(b.count for b in hist_bins) or 1
    bar_char = "#" if ascii_only else "█"

    labels = [f"[{fmt_num(b.low)}, {fmt_num(b.high)})" for b in hist_bins]
    if labels:
        labels[-1] = f"[{fmt_num(hist_bins[-1].low)}, {fmt_num(hist_bins[-1].high)}]"
    label_w = max(len(lbl) for lbl in labels)

    lines: List[str] = []
    for lbl, b in zip(labels, hist_bins):
        bar_len = int(round((b.count / max_count) * width))
        if b.count > 0 and bar_len == 0:
            bar_len = 1
        bar = bar_char * bar_len
        lines.append(f"{lbl.rjust(label_w)} | {bar.ljust(width)} {b.count}")
    return "\n".join(lines)


def render_box_plot(
    series: Sequence[Tuple[str, Sequence[float]]],
    *,
    width: int = 44,
    ascii_only: bool = False,
) -> str:
    """Render one or more aligned horizontal box-and-whisker plots on a shared axis."""
    if width < 12:
        raise SparkPlotError("width must be >= 12")
    if not series:
        raise SparkPlotError("No series provided")

    stats_list: List[Tuple[str, SummaryStats]] = [
        (name, compute_stats(vals)) for name, vals in series
    ]
    global_min = min(st.minimum for _, st in stats_list)
    global_max = max(st.maximum for _, st in stats_list)
    span = global_max - global_min

    def _pos(x: float) -> int:
        if span == 0:
            return width // 2
        idx = int(round(((x - global_min) / span) * (width - 1)))
        return max(0, min(width - 1, idx))

    whisk_ch = "-" if ascii_only else "─"
    box_ch = "=" if ascii_only else "█"
    med_ch = "|" if ascii_only else "┃"
    cap_ch = "|" if ascii_only else "├"
    cap_r = "|" if ascii_only else "┤"
    out_ch = "o" if ascii_only else "●"

    label_w = max(len(name) for name, _ in stats_list)
    lines: List[str] = []

    for name, st in stats_list:
        canvas = [" "] * width
        p_wl = _pos(st.whisker_low)
        p_q1 = _pos(st.q1)
        p_med = _pos(st.median)
        p_q3 = _pos(st.q3)
        p_wh = _pos(st.whisker_high)

        for i in range(p_wl, p_wh + 1):
            canvas[i] = whisk_ch
        canvas[p_wl] = cap_ch
        canvas[p_wh] = cap_r
        for i in range(p_q1, p_q3 + 1):
            canvas[i] = box_ch
        canvas[p_med] = med_ch
        for out_val in st.outliers:
            canvas[_pos(out_val)] = out_ch

        row = "".join(canvas)
        summary = f"med={fmt_num(st.median)} (n={st.count})"
        lines.append(f"{name.rjust(label_w)} | {row} | {summary}")

    # Shared scale footer
    left_lbl = fmt_num(global_min)
    mid_lbl = fmt_num((global_min + global_max) / 2.0)
    right_lbl = fmt_num(global_max)
    axis = [" "] * width
    for i, ch in enumerate(left_lbl):
        if i < width:
            axis[i] = ch
    mid_start = max(len(left_lbl) + 1, (width - len(mid_lbl)) // 2)
    if mid_start + len(mid_lbl) < width - len(right_lbl):
        for i, ch in enumerate(mid_lbl):
            axis[mid_start + i] = ch
    right_start = max(0, width - len(right_lbl))
    for i, ch in enumerate(right_lbl):
        if right_start + i < width:
            axis[right_start + i] = ch

    prefix = " " * (label_w + 3)
    lines.append(f"{prefix}{''.join(axis)}")
    return "\n".join(lines)


def render_bar_chart(
    items: Sequence[Tuple[str, float]],
    *,
    width: int = 36,
    sort_order: Optional[str] = None,
    ascii_only: bool = False,
) -> str:
    """Render a horizontal bar chart for (label, value) pairs."""
    if width < 4:
        raise SparkPlotError("width must be >= 4")
    if not items:
        raise SparkPlotError("No label/value pairs provided")

    rows = [(str(lbl), float(val)) for lbl, val in items]
    if sort_order == "asc":
        rows.sort(key=lambda pair: pair[1])
    elif sort_order == "desc":
        rows.sort(key=lambda pair: pair[1], reverse=True)

    max_val = max(abs(v) for _, v in rows) or 1.0
    bar_char = "#" if ascii_only else "█"
    label_w = max(len(lbl) for lbl, _ in rows)

    lines: List[str] = []
    for lbl, val in rows:
        bar_len = int(round((abs(val) / max_val) * width))
        if val != 0 and bar_len == 0:
            bar_len = 1
        bar = bar_char * bar_len
        lines.append(f"{lbl.rjust(label_w)} | {bar.ljust(width)} {fmt_num(val)}")
    return "\n".join(lines)
