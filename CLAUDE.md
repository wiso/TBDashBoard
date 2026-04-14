# CLAUDE.md — Project Context for Claude

## What This Is
Offline monitoring dashboard for CERN SPS 2025 test beam (Dual-Readout calorimeter).
Python + Dash/Plotly web app. Reads ROOT ntuples via uproot, fills histograms with `hist`,
displays them as interactive plots.

## Quick Reference

### Run the App
```bash
uv run tb-monitor --config config.toml --data-dir /path/to/root/files
```

### Run Tests
```bash
uv run pytest              # all 48 tests
uv run pytest -x -q        # stop on first failure
```

### Lint / Format
```bash
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
```

## Architecture

```
src/tb_monitor/
├── app.py              # Dash entry point, CLI (--config, --data-dir, --port, --host, --debug)
├── settings.py         # Frozen Settings dataclass + TOML loader + get_settings()/set_settings()
├── themes.py           # Light/dark theme dicts
├── backend/
│   ├── channel_map.py  # Function-based API: special_channels(), beam_channels(), etc.
│   ├── data_loader.py  # iter_tree() wraps uproot.iterate(); load_metadata()
│   ├── file_scanner.py # Scans directory for ROOT run files using settings pattern
│   └── histograms.py   # process_run() dispatches batches to components; logging
├── components/
│   ├── base.py         # Component ABC
│   ├── __init__.py     # COMPONENTS list — registry of active components
│   ├── overview.py     # Trigger mask, event rate, events per spill
│   ├── adc.py          # Calorimeter ADC channel maps (S & C separately), 2D heatmap
│   ├── aux.py          # Beam counters + leakage counters (mean ± std)
│   ├── muon.py         # Muon counter ADC distribution (all + pedestal overlay)
│   ├── cherenkov_counter.py  # Cherenkov counter ADC distributions (Cher1–3)
│   └── sipm.py         # SiPM high-gain per-channel mean
└── frontend/
    ├── layout.py       # make_layout() — run selector dropdown, tabs, theme toggle, loading spinner
    └── callbacks.py    # Generic callbacks: theme, run loading, tab routing, dispatch
```

## Key Patterns

### Settings Singleton
All configurable values live in the frozen `Settings` dataclass (`settings.py`).
Loaded from `config.toml` at startup, overridable via CLI. Access via `get_settings()`.
**Never use module-level constants for detector parameters.**

### Component ABC
Each monitoring subsystem is a `Component` subclass with:
- `name` / `label` — identity
- `tree_branches()` — which TTree branches it reads
- `create_state(path)` — create empty accumulators (calls `get_settings()` here)
- `fill_batch(state, tree_name, batch)` — accumulate one batch
- `finalize(state)` — compute final results
- `tab_layout()` — Dash HTML layout
- `register_callbacks(app, get_results)` — wire Dash callbacks

### Channel Map
`backend/channel_map.py` exposes functions (not constants):
`special_channels()`, `beam_channels()`, `leakage_channels()`,
`scintillation_channels()`, `cherenkov_channels()`, `aux_channel_set()`.
Each calls `get_settings()` internally.

### Batch Processing
`histograms.process_run()` iterates each TTree once, dispatching batches to all
components that declared interest. Only one batch lives in memory at a time.

## Coding Rules
- **uproot** for ROOT I/O (never PyROOT).
- **hist.Hist** with named axes for all histograms.
  `hist.axis.Integer` for ADC values, `IntCategory(growth=True)` for triggers/spills.
- **awkward** arrays from uproot → numpy only at plot time.
- Never load a full TTree. Always `uproot.iterate()`.
- Plotly figures from hist objects (`.to_numpy()`), not raw arrays.
- Type-annotate all function signatures.
- No global mutable state (exception: settings singleton, set once).
- Prefer explicit HTML/CSS over JS DOM post-processing.
- Line length ≤ 100. Format with ruff.
- Python 3.10+ (developed on 3.14).

## Data Format
ROOT files contain TTrees:
- `CERNSPS2025`: ADCs[224], TDCsval[48], TDCscheck[48], TriggerMask, EventNumber, EventSpill, EventTime
- `SiPM_rawTree_aligned`: SiPM_HG[1024], SiPM_LG[1024], SiPM_ToA[1024], SiPM_ToT[1024], TrigID
- `RunMetaData`: runNumber, dataFormat, software, boardType, acqMode, acqTime

## Testing
- 48 tests in `tests/` using pytest.
- Synthetic data only — no real ROOT files needed.
- `conftest.py` provides `rng`, `cernsps_batch` (100 events × 224 ch), `sipm_batch` (80 × 1024) fixtures.
- Components tested via create_state → fill_batch → finalize cycle.
- `process_run()` tested with mock patching (no file I/O).
- `conftest.py` provides `rng`, `cernsps_batch` (100 events × 224 ch), `sipm_batch` (80 × 1024) fixtures.
- Components tested via create_state → fill_batch → finalize cycle.
- `process_run()` tested with mock patching (no file I/O).
