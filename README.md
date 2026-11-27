# sparkplot

Terminal sparklines, histograms, box plots and horizontal bar charts from CLI arguments, stdin, CSV or JSON. Zero dependencies.

## Install

```bash
pip install .
```

Or run directly without installing:

```bash
python3 -m sparkplot --help
```

## Usage

### Sparkline + summary stats

```bash
sparkplot spark 12 18 25 21 34 49 38 29 15 19
# ▁▂▃▃▅█▆▄▂▂
# n=10  min=12  median=23  mean=26  p95=44.05  max=49  stdev=11.56

sparkplot spark --file metrics.csv --col latency_ms
```

### Frequency histogram

```bash
printf "1\n2\n2\n3\n3\n3\n4\n5\n8\n9\n" | sparkplot hist --bins 5 --width 30
```

### Box-and-whisker plot (single or grouped)

```bash
sparkplot box 10 12 14 15 18 19 22 25 48
sparkplot box --file results.csv --col score --group method --width 45
```

### Horizontal bar chart

```bash
printf "api,42\nworker,27\ncache,13\ndb,58\n" | sparkplot bar --sort desc
```

All commands also support `--ascii` (plain ASCII rendering) and `--json` (machine-readable statistics and bin data).

## Run tests

```bash
python3 -m unittest discover -s tests
```

## License

MIT
