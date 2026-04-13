# TB2026 Monitoring Offline — AI Agent Instructions

## Project Overview
Offline monitoring dashboard for CERN SPS test beam detector data (Dual-Readout calorimeter).
Reads ROOT ntuples produced by the DAQ, displays counters, histograms, and channel maps via a web dashboard.

## Architecture
- **Backend** (`src/tb_monitor/backend/`): Data loading (uproot), histogram filling (hist library), file scanning.
  - Data is read via `uproot.iterate()` in batches — never load full TTrees into memory.
  - `histograms.process_run()` does all filling in one pass, returning a `RunResults` dataclass.
- **Frontend** (`src/tb_monitor/frontend/`): Dash web app, Plotly figures, callbacks.
- Separation allows swapping the data source (files → streaming) without touching the UI.

## Tech Stack
- Python ≥ 3.10
- **uproot** for reading ROOT files (never PyROOT)
- **hist** (scikit-hep) for all histograms — do not use numpy histogramming directly
- **Dash + Plotly** for the web UI
- **awkward** arrays as the intermediate data format from uproot

## Data Format
ROOT files contain these TTrees:
- `CERNSPS2025`: Main detector tree (ADCs[224], TDCsval[48], TDCscheck[48], TriggerMask, EventNumber, EventSpill, EventTime, counters)
- `SiPM_rawTree_aligned`: SiPM subsystem (SiPM_HG[1024], SiPM_LG[1024], SiPM_ToA[1024], SiPM_ToT[1024], TrigID, timestamps)
- `RunMetaData`: Single-entry metadata (runNumber, dataFormat, software, boardType, acqMode, acqTime)

## Coding Conventions
- Use type hints on all function signatures.
- Prefer explicit HTML/CSS in Dash layout over JavaScript DOM post-processing.
- Keep backend functions pure: take arrays/data in, return hist objects or dicts out.
- Use `hist.Hist` with named axes for all histograms.
- Never load a full TTree into memory. Use `uproot.iterate()` to process data in batches.
- Use `growth=True` on IntCategory axes when the set of values is not known upfront.
- Plotly figures should be built from hist objects, not raw arrays.
- No global mutable state — pass data through function arguments or Dash stores.
- Line length ≤ 100 characters. Format with ruff.

## File Naming
- snake_case for all Python files and variables.
- Descriptive module names (e.g., `data_loader.py`, not `utils.py`).

## Testing
- Tests go in `tests/` directory.
- Use pytest. Test backend functions with small synthetic data, not real ROOT files.
