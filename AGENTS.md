# TB2026 Monitoring Offline — AI Agent Instructions

## Project Overview
Offline monitoring dashboard for CERN SPS test beam detector data (Dual-Readout calorimeter).
Reads ROOT ntuples produced by the DAQ, displays counters, histograms, and channel maps via a web dashboard.

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
│   ├── base.py         # Component ABC (name, label, tree_branches, create_state, fill_batch, finalize, tab_layout, register_callbacks)
│   ├── __init__.py     # COMPONENTS list — registry of active components
│   ├── overview.py     # Trigger mask, event rate, events per spill
│   ├── adc.py          # Calorimeter ADC channel maps (S & C separately), 2D heatmap
│   ├── aux.py          # Beam counters + leakage counters (mean ± std)
│   ├── muon.py         # Muon counter ADC distribution (all + pedestal overlay)
│   ├── cherenkov_counter.py  # Cherenkov counter ADC distributions (Cher1–3)
│   └── sipm.py         # SiPM high-gain per-channel mean
└── frontend/
    ├── layout.py       # make_layout() — run selector dropdown, tabs, theme toggle, loading spinner
    └── callbacks.py    # Generic callbacks: theme, run loading, tab routing, per-component dispatch
```

- **Backend** (`backend/`): Data loading (uproot), histogram filling (hist library), file scanning.
  All backend modules use Python `logging` for diagnostics.
  - Data is read via `uproot.iterate()` in batches — never load full TTrees into memory.
  - `histograms.process_run()` dispatches batches to all registered components in one pass.
- **Frontend** (`frontend/`): Dash web app, Plotly figures, callbacks.
  - `dcc.Loading` wraps `tab-content` with a hidden trigger span for spinner visibility.
- **Components** (`components/`): Each component is self-contained (data → histograms → layout → callbacks).
- **Settings** (`settings.py`): All tuneable parameters live in a frozen `Settings` dataclass.
  Loaded from `config.toml` (TOML), overridable via CLI flags.
  Accessed at runtime via `get_settings()` singleton.
- Separation allows swapping the data source (files → streaming) without touching the UI.

## Configuration System
- `config.toml` at project root holds defaults (server, processing, detector sections).
- `Settings` dataclass (`settings.py`): frozen, with derived properties (leakage_channels, beam_channels, scintillation_channels, cherenkov_channels). `replace(**kwargs)` creates a new instance with overrides.
- `load_settings(path)` reads TOML → `Settings`. `set_settings(s)` sets the singleton.
- `channel_map.py` exposes function-based API (`special_channels()`, `beam_channels()`, `leakage_channels()`, `scintillation_channels()`, `cherenkov_channels()`, `aux_channel_set()`) — each calls `get_settings()` internally.
- Components call `get_settings()` in `create_state()` / `fill_batch()` — never at module level.

## Tech Stack
- Python ≥ 3.10 (developed on 3.14)
- **uv** for dependency management and virtualenv (`uv sync`, `uv run`)
- **hatchling** as the build backend
- **uproot** for reading ROOT files (never PyROOT)
- **hist** (scikit-hep) for all histograms — do not use numpy histogramming directly
- **Dash + Plotly** for the web UI
- **awkward** arrays as the intermediate data format from uproot
- **tomllib** (stdlib ≥ 3.11) for config loading

## Data Format
ROOT files contain these TTrees:
- `CERNSPS2025`: Main detector tree (ADCs[224], TDCsval[48], TDCscheck[48], TriggerMask, EventNumber, EventSpill, EventTime, counters)
- `SiPM_rawTree_aligned`: SiPM subsystem (SiPM_HG[1024], SiPM_LG[1024], SiPM_ToA[1024], SiPM_ToT[1024], TrigID, timestamps)
- `RunMetaData`: Single-entry metadata (runNumber, dataFormat, software, boardType, acqMode, acqTime)

## Coding Conventions
- Type hints on all function signatures.
- `hist.Hist` with named axes for **all** histograms. `hist.axis.Integer` for ADC values, `IntCategory(growth=True)` for triggers/spills.
- Prefer explicit HTML/CSS in Dash layout over JavaScript DOM post-processing.
- Keep backend functions pure: take arrays/data in, return hist objects or dicts out.
- Never load a full TTree into memory. Use `uproot.iterate()` to process data in batches.
- Plotly figures should be built from hist objects (via `.to_numpy()`), not raw arrays.
- No global mutable state — pass data through function arguments or Dash stores.
  Exception: `settings.py` singleton set once at startup.
- All hardcoded detector parameters come from `get_settings()`, not module-level constants.
- Line length ≤ 100 characters. Format with ruff (`ruff check --fix`, `ruff format`).

## File Naming
- snake_case for all Python files and variables.
- Descriptive module names (e.g., `data_loader.py`, not `utils.py`).

## Testing
- Tests go in `tests/` directory (48 tests as of last count).
- Use pytest. Test backend functions with small synthetic data, not real ROOT files.
- `conftest.py` provides `rng`, `cernsps_batch`, `sipm_batch` fixtures.
- Run: `uv run pytest`
