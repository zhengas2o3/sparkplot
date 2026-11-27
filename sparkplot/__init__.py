"""Zero-dependency terminal sparklines, histograms, box plots and bar charts."""

from .core import (
    HistogramBin,
    SparkPlotError,
    SummaryStats,
    compute_histogram,
    compute_stats,
    render_bar_chart,
    render_box_plot,
    render_histogram,
    render_sparkline,
)

__all__ = [
    "HistogramBin",
    "SparkPlotError",
    "SummaryStats",
    "compute_histogram",
    "compute_stats",
    "render_bar_chart",
    "render_box_plot",
    "render_histogram",
    "render_sparkline",
]
__version__ = "0.1.0"
