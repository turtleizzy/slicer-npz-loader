# Agent instructions — slicer_npz_loader

## Before you edit

1. **Read** [`.memory/PROJECT_KNOWHOW.md`](.memory/PROJECT_KNOWHOW.md) first. It summarizes architecture, data conventions (NumPy vs Slicer axes, LPS→RAS), module layout, and where logic lives (`NpzLoader.py` vs `SliceViewingTool.py`).
2. Treat **[`README.md`](README.md)** as the user-facing feature list and supported key names; align behavior and docs when you change detection or loading rules.
3. This is a **3D Slicer scripted module**: validate non-trivial UI, geometry, or segmentation changes in **Slicer**, not only by static review.

## Scope discipline

- Prefer **minimal, targeted** changes; do not refactor unrelated code or add unsolicited documentation files.
- **`NpzLoader.py`** holds module entry, widget, **`NpzLoaderLogic`**, and tests. **`SliceViewingTool.py`** is the optional slice interaction controller; avoid duplicating slice logic across files.

## Safety and compatibility

- Keep **`np.load(..., allow_pickle=False)`** for NPZ/NPY.
- Be careful changing **`_applyGeometry`**, **`_resolveSpacingOrigin`**, or **`_IJK_DIRECTIONS_LPS_TO_RAS`** — they affect clinical alignment with the rest of the scene.

## After changes

- If you touch load/analysis logic, consider whether **`NpzLoaderTest`** should be extended (same file as the module).
- CMake lists must stay in sync if you add/remove Python scripts or resources under `NpzLoader/`.
