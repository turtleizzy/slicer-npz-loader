# Agent instructions — slicer_npz_loader

## Before you edit

1. **Read** [`.memory/PROJECT_KNOWHOW.md`](.memory/PROJECT_KNOWHOW.md) first. It summarizes architecture, data conventions (NumPy vs Slicer axes, LPS→RAS), module layout, where logic lives (`NpzLoader.py` vs `SliceViewingTool.py`), and **Qt patterns** for the load-plan tree (splitter/stretch, `blockSignals`, multi-select batch checkboxes).
2. Treat **[`README.md`](README.md)** as the user-facing feature list and supported key names; align behavior and docs when you change detection or loading rules.
3. This is a **3D Slicer scripted module**: validate non-trivial UI, geometry, or segmentation changes in **Slicer**, not only by static review.

## Scope discipline

- Prefer **minimal, targeted** changes; do not refactor unrelated code or add unsolicited documentation files.
- **`NpzLoader.py`** holds module entry, widget, **`NpzLoaderLogic`**, and tests. **`SliceViewingTool.py`** is the optional slice interaction controller; avoid duplicating slice logic across files.

## Safety and compatibility

- Keep **`np.load(..., allow_pickle=False)`** for NPZ/NPY.
- Be careful changing **`_applyGeometry`**, **`_resolveSpacingOrigin`**, **`_resolveDirection`**, or **`_directionsToSlicer`** — they affect clinical alignment with the rest of the scene. Direction is ITK 3×3 (columns = IJK axes), LPS by default: `Slicer = diag(-1,-1,1) @ D`. Unsuffixed spacing/origin stay `(z,y,x)`; `spacing_xyz` / `origin_lps` are xyz, with LPS origin flipped to RAS.

## After changes

- If you touch load/analysis logic, consider whether **`NpzLoaderTest`** should be extended (same file as the module).
- CMake lists must stay in sync if you add/remove Python scripts or resources under `NpzLoader/`.
