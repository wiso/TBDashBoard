---
description: "Add a new monitoring component or plot to the dashboard"
---

# Add a New Monitoring Component

Each monitoring component is self-contained in one file under
`src/tb_monitor/components/`. It handles its own data needs, histogram
filling, Dash layout, and callbacks.

## To add a new component

1. Create `src/tb_monitor/components/my_thing.py` with a class that
   subclasses `Component` from `tb_monitor.components.base`.
2. Implement the required methods:
   - `name` / `label` — unique ID and tab label.
   - `tree_branches()` — which TTree branches you need.
   - `create_state(path)` — create empty accumulators.
     Call `get_settings()` here for detector parameters (never at module level).
   - `fill_batch(state, tree_name, batch)` — accumulate one batch.
   - `finalize(state)` — compute final results.
   - `tab_layout()` — return `html.Div(...)` with `dcc.Graph` elements.
   - `register_callbacks(app, get_results)` — wire `get_results(path)`
     to Plotly figures via Dash callbacks.
3. Register it in `src/tb_monitor/components/__init__.py` by adding an
   instance to the `COMPONENTS` list.
4. If you need new configurable parameters, add fields to `Settings` in
   `settings.py` and corresponding entries in `config.toml`.

See `overview.py`, `adc.py`, `muon.py`, `cherenkov_counter.py`, or `sipm.py` for examples.

## To add a plot to an existing component

1. Add a `dcc.Graph(id="...")` to the component's `tab_layout()`.
2. Add a new `@app.callback` in the component's `register_callbacks()`.
3. If new branches are needed, update `tree_branches()`.
4. Update `fill_batch()` and `finalize()` to produce the new data.
