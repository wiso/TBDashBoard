# TB2026 Monitoring — Offline Dashboard

Offline monitoring dashboard for the Dual-Readout calorimeter test beam at CERN SPS.
Reads ROOT ntuples produced by the DAQ and displays counters, histograms, and channel
maps in a web browser.

## Quick start

```bash
# 1. Install uv (if not already installed)
# https://docs.astral.sh/uv/getting-started/installation/

# 2. Install dependencies and create the virtual environment
uv sync

# 3. Run the dashboard
uv run tb-monitor --data-dir /path/to/root/files
```

Then open <http://localhost:8050> in your browser.

## Command-line options

| Option | Default | Description |
|---|---|---|
| `--config` | auto-detected `config.toml` | Path to TOML configuration file |
| `--data-dir` | from config | Directory containing ROOT files |
| `--port` | `8050` | HTTP port |
| `--host` | `0.0.0.0` | Bind address |
| `--debug` | off | Enable Dash debug mode and verbose logging |

Example:

```bash
uv run tb-monitor --data-dir /eos/experiment/dualreadout/data/merged --port 9090 --debug
```

## What it shows

The dashboard has six tabs:

- **Overview** — Trigger mask distribution, event rate vs time, events per spill.
- **ADC Channels** — Mean ADC per channel (scintillation & Cherenkov separately) and a 2D channel × ADC heatmap.
- **Aux Counters** — Beam counters (PS, Veto, Tail Catcher) and leakage counters (mean ± std).
- **Muon Counter** — Muon counter ADC distribution (all events + pedestal overlay).
- **Cherenkov Counters** — ADC distributions for beam-line Cherenkov counters (Cher1–3).
- **SiPM** — Mean SiPM high-gain per channel.

A run selector dropdown at the top scans the data directory for ROOT run files.

## Configuration

All tuneable parameters live in `config.toml` (TOML format). Sections:

- `[server]` — `data_dir`, `host`, `port`
- `[processing]` — `step_size`, `run_file_pattern`
- `[detector]` — channel counts, ADC range, channel ranges, special channel map

CLI flags override config file values. See `config.toml` for the full set of options.

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
├── app.py                          # Entry point, CLI, Dash app factory
├── settings.py                     # Frozen Settings dataclass + TOML loader
├── themes.py                       # Light/dark theme dicts
├── backend/
│   ├── channel_map.py              # Function-based channel mapping API
│   ├── data_loader.py              # uproot batch iteration + metadata reader
│   ├── file_scanner.py             # Directory scanning for run files
│   └── histograms.py               # Histogram filling (process_run → RunResults)
├── components/
│   ├── base.py                     # Component ABC
│   ├── __init__.py                 # COMPONENTS registry (tab order)
│   ├── overview.py                 # Trigger mask, event rate, events per spill
│   ├── adc.py                      # Calorimeter ADC channel maps, 2D heatmap
│   ├── aux.py                      # Beam + leakage counters (mean ± std)
│   ├── muon.py                     # Muon counter ADC distribution
│   ├── cherenkov_counter.py        # Cherenkov counter ADC distributions
│   └── sipm.py                     # SiPM high-gain per-channel mean
└── frontend/
    ├── layout.py                   # Dash HTML layout (tabs, dropdowns, spinner)
    └── callbacks.py                # Dash callbacks wiring everything together
```

## Development

```bash
# Install all dependencies (including dev group)
uv sync

# Run linter
uv run ruff check src/ tests/

# Format code
uv run ruff format src/ tests/

# Run tests (48 tests)
uv run pytest
```

## Tech stack

- **Python** ≥ 3.10 — managed with [uv](https://docs.astral.sh/uv/)
- [Dash](https://dash.plotly.com/) + [Plotly](https://plotly.com/python/) — web UI
- [uproot](https://github.com/scikit-hep/uproot5) — ROOT file I/O (no PyROOT needed)
- [hist](https://github.com/scikit-hep/hist) — histogram objects with named axes
- [awkward](https://github.com/scikit-hep/awkward) — columnar array operations
- [hatchling](https://hatch.pypa.io/) — build backend
