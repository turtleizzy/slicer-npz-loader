# NPZ Loader — project know-how

## What this is

A **scripted 3D Slicer extension** (`Informatics` → **NPZ Loader**) that loads `.npz` / `.npy` NumPy archives into the MRML scene as scalar volumes and segmentations. Goal: fast inspection of Python pipeline output in Slicer with minimal manual setup.

## Layout and build

- **Root** `CMakeLists.txt`: Slicer extension metadata; `add_subdirectory(NpzLoader)`.
- **`NpzLoader/`**: single scripted module.
  - `NpzLoader.py`: module class, widget, `NpzLoaderLogic`, tests (`ScriptedLoadableModule*` pattern).
  - `SliceViewingTool.py`: optional slice interaction helper (separate from load logic).
  - `Resources/UI/NpzLoader.ui`, `Resources/Icons/*.png`, `SliceViewingTool.svg`.
- **`NpzLoader/CMakeLists.txt`**: `slicerMacroBuildScriptedModule` with `WITH_GENERIC_TESTS`; lists both Python scripts and resources.

## Data model (code)

- **`KeyInfo`**: per-array name, shape, dtype, **role** (`volume`, `spacing`, `origin`, `seg_labelmap`, `seg_sparse_ind`, `seg_sparse_color`, `unknown`).
- **`LoadPlanGroup`**: `group_type` ∈ `volume` | `seg_labelmap` | `seg_sparse`, `enabled`, **`mappings`** (which NPZ keys feed `data`, `spacing`, `origin`, or for sparse `ind` / `color_point`).

## Axis and geometry (critical)

- Voxel arrays are **NumPy `(z, y, x)`** (comments in code use K,J,I ↔ depth, height, width).
- **`spacing` / `origin` in files are `(z, y, x)`**; logic reverses to **`(x, y, z)`** for Slicer (`_resolveSpacingOrigin`).
- **`_applyGeometry`**: sets spacing, origin, and **`SetIJKToRASDirections`** via **`_IJK_DIRECTIONS_LPS_TO_RAS`** — assumes a **LPS-style** numpy grid mapped into Slicer’s **RAS** frame (negated I and J). Changing this matrix affects alignment with other DICOM/native Slicer data; test visually when touching geometry.

## Analysis vs load

- **`.npz`**: `analyzeNpzKeys` walks the zip, reads **only each member’s `.npy` header** (no full tensor read) via `numpy.lib.format` / `_readNpyHeaderShapeDtype`.
- **`.npy`**: single array exposed as key `data`, wrapped by **`_NpyWrapper`** so downstream code matches NPZ dict-like access.
- **`loadFile`**: `np.load(..., allow_pickle=False)`.

## Classification (`NpzLoaderLogic._classifyKey`)

Regex-driven: volume names `img|vol|volume|image` (3D); `spacing` / `origin` by substring; dense seg by `seg` in name (3D, dtype-agnostic: integer or float masks); sparse by `ind`/`inds` suffix `(N,3)` and optional `color_point(s)` 1D. Unknown 3D arrays can be promoted to a volume group in **`generateLoadPlan`** if no volume was found.

## Float dense seg handling

- When loading dense `seg_labelmap` from a **float** array, the logic auto-converts into `int16` labelmap:
  - If values are mostly **near integers** (e.g. 0/1/2 with tolerance), treat as multi-label (rounded to nearest integer).
    - Multi-label is only triggered when float data also contains label values beyond the binary range (i.e. `>= 2` within tolerance).
  - If values are mostly **in [0,1]**, treat as a probability/score mask and binarize with a configurable threshold (default `0.5`).

## Load plan and sticky reuse

- **`generateLoadPlan`**: builds groups; pairs sparse `ind` with `color_*` by **stripped name prefix**; shares global `spacing`/`origin` keys when present.
- **`computeKeySignature`**: sorted comma-separated key names — used to **reuse** edited plans when “reuse plan” is on (`stickyPlans` dict on logic).

## Load pipeline (widget `onLoad`)

1. Read tree → `_loadPlanGroups`; clear prior module nodes.
2. **`loadFile`** once.
3. **First pass**: all enabled **`volume`** groups → `loadVolume` (tracks first volume shape + raw z,y,x spacing/origin for segs).
4. **Second pass**: **`seg_labelmap`** and **`seg_sparse`** using that geometry when shapes match.

## Volume / segmentation implementation

- **Volume**: `updateVolumeFromArray`, default display nodes, `setSliceViewerLayers(background=..., fit=True)`.
- **Dense seg**: numpy → **labelmap volume** → `ImportLabelmapToSegmentationNode` → closed surface; temporary labelmap node removed.
- **Sparse seg**: scatter into dense `labelmap` (infer shape from max index if no volume); same import path. Optional per-voxel labels from `color_point`.
- **`_coerceDtype`**: VTK-incompatible dtypes (e.g. float16) upcast; non-numeric types coerced to float64.

## UI / shortcuts

- Qt UI from **`NpzLoader.ui`**; load plan edited via tree + combos (`(none)` = unmapped).
- **Shortcuts** (only when module **NpzLoader** is selected, for WL/seg): `F1`–`F3` window/level from settings; `T` / `Shift+T` seg fill/contour/hide; `S` toggles slice tool.
- **`SliceViewingTool`**: global singleton via **`ensureGlobalSliceViewingTool`** (created at main window or `startupCompleted`); adds toolbar action on mouse mode bar; custom interactor observers for slice drag, WL, pan, zoom; `status_callback` can drive module status label. **`onDataLoaded`** refreshes observers and can auto-enable the tool.
- Qt/PythonQt dialog pitfall: **`QDialogButtonBox` may render empty/invisible in some builds**. Prefer explicit `QPushButton` ("OK"/"Cancel") laid out with `QHBoxLayout` + `addStretch` and connect `clicked()` to `dialog.accept()/reject()`.

## Slice viewing crosshair/plane linkage (Slicer)

- `vtkMRMLCrosshairNode.SetCrosshairRAS(...)` 通常只更新“十字光标”的可视交线位置；**不保证**所有 slice view 的“slice plane（offset）”会随之跳转。
- 当自定义交互（例如在 `MouseMoveEvent` 里 `return True` 并拦截了原生 interactor 链路）时，更要避免依赖 Slicer 内置“crosshair->slice plane”自动处理。
- 若你需要在 RAS 坐标下让所有（linked）slice planes 同步，使用：`slicer.vtkMRMLSliceNode.JumpAllSlices(slicer.mrmlScene, r, a, s, jumpMode)`
- `jumpMode` 可用 `vtkMRMLSliceNode.CenteredJumpSlice`（强制居中）或 `DefaultJumpSlice`（跟随 slice node 的默认 jump 行为，具体取决于 Slicer 版本/配置）。
- 记忆点：遇到“crosshair 联动了但 plane 没动”，优先检查是否少了 `JumpAllSlices`，而不是只改 crosshair 的行为。

## Tests

- `NpzLoaderTest` in same file: `analyzeNpzKeys` / `generateLoadPlan` and `loadVolume` against temp NPZ files (requires Slicer runtime).

## Conventions for changes

- Preserve **`allow_pickle=False`** for security.
- Match existing **regex and naming** conventions when extending key detection.
- Geometry changes deserve **Slicer visual checks** (alignment with reference volumes).
- Keep **SliceViewingTool** decoupled from loading logic unless integrating new hooks.

## Local Slicer environment (for API lookup / testing)

Local Slicer installation/build path:

- `/wr/Slicer-5.11.0-2025-11-17-linux-amd64/Slicer`

When you need to test behavior or inspect Slicer APIs (python modules/classes, MRML helpers, segmentations/volumes logic, etc.), run/view them in this local Slicer environment first (for example, using its Python interpreter / ensuring matching versions).

## 2026-03 data review expansion notes

### Data source architecture

- The module now supports two review sources in one workflow:
  - `NPZ Directory` (legacy behavior),
  - `IMG+SEG Paired Directory`.
- New shared item model: `ReviewDataItem` (`data_id`, `source_type`, `npz_path`, `img_path`, `seg_paths`).
- UI list now represents generic **data items** (`data_id`) instead of only NPZ filenames.

### Paired scan rules (current contract)

- IMG scan is top-level only:
  - file entries (`.nii/.nii.gz/.nrrd/.mhd`) -> one item, `data_id = basename`,
  - directory entries -> one DICOM-series item, `data_id = folder name`.
- SEG scan is top-level only, matching files ending with `-seg.nii.gz`.
- In paired mode, list generation supports all three scenarios:
  - IMG+SEG available,
  - IMG-only,
  - SEG-only.
- SEG-only behavior: each seg file stem (filename without `-seg.nii.gz`) becomes one `data_id`.

### Paired load plan behavior

- Paired mode reuses the existing load-plan tree area but with a paired-specific plan:
  - one checkable `image` row (may be unchecked when `img_path` missing),
  - multiple checkable `seg` rows.
- Seg suffix preference is persisted across reviews via QSettings:
  - key: `NpzLoader/PairedSegSuffixSelection`,
  - format: JSON dict `suffix -> bool`.
- `Only show data with seg` remains a filtering option over scanned paired items.

### Source switching and state reset

- Important: when switching source type, stale plan/list state must be reset.
- Current reset flow clears:
  - `_currentDataItem`, `_currentDataItems`,
  - `fileList` content/selection,
  - key table and load plan tree content,
  - status text.
- Tree headers should match source mode (`Property/Value` for NPZ, `Item/Suffix` for paired) to avoid confusing leftovers.

### Paired load execution

- Paired loading now supports:
  - image + seg,
  - image-only,
  - seg-only (if user checks seg rows).
- DICOM folder image loading uses `DICOMLib.DICOMUtils` with a temporary DICOM DB.
- Seg loading failures are non-fatal per file; warnings are accumulated.

### "Show 3D" gotcha (segmentation tab semantics)

- Simply calling `SetVisibility3D(True)` may be insufficient for what users expect as segmentation-tab `Show 3D`.
- Robust sequence after seg import/load:
  1. `CreateClosedSurfaceRepresentation()`
  2. `CreateDefaultDisplayNodes()`
  3. `displayNode.SetPreferredDisplayRepresentationName3D("Closed surface")`
  4. `displayNode.SetVisibility(True)`
  5. `displayNode.SetVisibility3D(True)`
- Apply this consistently to NPZ labelmap seg, NPZ sparse seg, and paired seg file loading paths.
