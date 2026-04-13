# TB2026 Monitoring — Offline Dashboard

Offline monitoring dashboard for the Dual-Readout calorimeter test beam at CERN SPS.
Reads ROOT ntuples produced by the DAQ and displays counters, histograms, and channel
maps in a web browser.

## Quick start

```bash
# 1. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate      # fish: source .venv/bin/activate.fish

# 2. Install the package
pip install -e .

# 3. Run the dashboard
tb-monitor --data-dir /path/to/root/files
```

Then open <http://localhost:8050> in your browser.

## Command-line options

| Option | Default | Description |
|---|---|---|
| `--data-dir` | `/home/turra/TB2025_H8/mergedNtuples` | Directory containing ROOT files |
| `--port` | `8050` | HTTP port |
| `--host` | `0.0.0.0` | Bind address |
| `--debug` | off | Enable Dash hot-reload and debug output |

Example:

```bash
tb-monitor --data-dir /eos/experiment/dualreadout/data/merged --port 9090 --debug
```

## What it shows

The dashboard has three tabs:

- **Overview** — Trigger mask distribution, event rate vs time, events per spill.
- **ADC Channels** — Mean ADC per channel (with error bars) and a 2D channel × ADC heatmap.
- **SiPM** — Mean SiPM high-gain per channel.

A run selector dropdown at the top scans the data directory for `*run*.root` files.

## Data format

The ROOT files must contain these TTrees:

| TTree | Key branches |
|---|---|
| `CERNSPS2025` | `ADCs[224]`, `TDCsval[48]`, `TDCscheck[48]`, `TriggerMask`, `EventNumber`, `EventSpill`, `EventTime` |
| `SiPM_rawTree_aligned` | `SiPM_HG[1024]`, `SiPM_LG[1024]`, `SiPM_ToA[1024]`, `SiPM_ToT[1024]`, `TrigID` |
| `RunMetaData` | `runNumber`, `dataFormat`, `software`, `boardType`, `acqMode`, `acqTime` |

Data is read in batches via `uproot.iterate()` — files of any size can be processed
without loading the full TTree into memory.

## Project layout

```
src/tb_monitor/
├── app.py                     # Entry point, CLI, Dash app factory
├── backend/
│   ├── data_loader.py         # uproot batch iteration + metadata reader
│   ├── histograms.py          # Histogram filling (process_run → RunResults)
│   └── file_scanner.py        # Directory scanning for run files
└── frontend/
    ├── layout.py              # Dash HTML layout (tabs, dropdowns, graphs)
    ├── plots.py               # hist → Plotly figure conversions
    └── callbacks.py           # Dash callbacks wiring everything together
```

## Development

```bash
pip install -e ".[dev]"

# Run linter
ruff check src/

# Run tests
pytest
```

## Tech stack

- [Dash](https://dash.plotly.com/) + [Plotly](https://plotly.com/python/) — web UI
- [uproot](https://github.com/scikit-hep/uproot5) — ROOT file I/O (no PyROOT needed)
- [hist](https://github.com/scikit-hep/hist) — histogram objects
- [awkward](https://github.com/scikit-hep/awkward) — columnar array operations
