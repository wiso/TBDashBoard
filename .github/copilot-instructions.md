# Copilot Instructions for TB2026 Monitoring

## Context
This is a particle physics test beam monitoring application. It reads ROOT ntuples
with uproot, fills histograms using the `hist` library, and serves a Dash web dashboard.

## Rules
- Always use `uproot` for ROOT I/O (never PyROOT or root_numpy).
- Always use `hist.Hist` with named axes for histograms.
- Build Plotly figures from `hist` objects using their `.to_numpy()` or axis info.
- Use `awkward` arrays as intermediate data; convert to numpy only at plot time.
- Never load a full TTree at once. Use `uproot.iterate()` to fill histograms in batches.
- Use `growth=True` on category axes when the set of values is not known ahead of time.
- Dash callbacks must not have side effects on module-level state.
- Prefer `dcc.Store` for sharing data between callbacks.
- Type-annotate all public functions.
- Keep imports sorted (ruff isort).
- Target Python 3.10+.
