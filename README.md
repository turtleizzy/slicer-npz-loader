# NpzLoader for 3D Slicer

`NpzLoader` is a scripted 3D Slicer extension module for data review workflows in Slicer.

It supports both NumPy archives (`.npz` / `.npy`) and paired image/segmentation directory layouts.

## Features

- Loads scalar volumes from `.npz` or single-array `.npy` files.
- Supports two data source modes:
  - `NPZ Directory` (legacy mode, same behavior as before),
  - `IMG+SEG Paired Directory` (new data review mode).
- Loads segmentations from:
  - dense 3D labelmaps (`seg_*` style keys), and
  - sparse index format (`*_ind` / `*_inds` with optional `*_color_point(s)`).
- Auto-analyzes file keys and generates an editable load plan.
- Supports reusable load plans for files with matching key signatures.
- Applies geometry using spacing/origin metadata when available.
- Includes a custom Slice Viewing Tool and useful keyboard shortcuts.

## Supported Data Conventions

### File types

- `.npz`: multiple arrays (volume, segmentation, metadata, etc.).
- `.npy`: single array, treated as one `volume` group with key `data`.

### Common recognized keys (auto-detection)

- Volume: `img`, `vol`, `volume`, `image` (3D arrays).
- Spacing: keys that start or end with `spacing`.
- Origin: keys that start or end with `origin`.
- Dense segmentation: keys that start or end with `seg` and are integer 3D arrays.
- Sparse segmentation indices: keys ending with `ind` / `inds` with shape `(N, 3)`.
- Sparse segmentation labels: keys containing `color_point`, `color_points`, `colorpoint`, or `colorpoints`.

### Axis and geometry assumptions

- Arrays are interpreted in NumPy order `(z, y, x)` for voxel data.
- `spacing` and `origin` values are expected in `(z, y, x)` and converted internally to Slicer axis order.
- Default spacing/origin are `(1, 1, 1)` and `(0, 0, 0)` if metadata is missing.

## Installation

## Option 1 (Simplest): Clone and drag into Slicer

1. Clone this repository:
   - `git clone https://github.com/turtleizzy/slicer-npz-loader.git`
2. Open 3D Slicer.
3. Drag the cloned project folder (or the `NpzLoader` module folder) into the Slicer window.
4. Confirm adding/loading the scripted module, then restart/reload if Slicer prompts.

This is the fastest way to start using the module locally for development and testing.

## Option 2: Build as a Slicer extension (CMake)

1. Clone this repository.
2. Configure and build with CMake against your Slicer build/environment.
3. Install the built extension package into Slicer.

Top-level CMake metadata:
- Project: `NpzLoader`
- Category: `Informatics`
- Homepage: <https://github.com/turtleizzy/slicer-npz-loader>

## Option 3: Developer workflow (scripted module iteration)

If you are developing the module, place this repository where Slicer can load scripted extension modules, or build in your local Slicer extension workflow and restart/reload as needed.

## Usage

1. Open **NPZ Loader** in Slicer.
2. In **Directory & File Selection**, choose a data source mode:
   - `NPZ Directory`, or
   - `IMG+SEG Paired Directory`.
3. Build/select the data list:
   - NPZ mode: choose root directory and select a data item from the list.
   - Paired mode: choose IMG directory + SEG directory, optionally enable `Only show data with seg`, then click `Scan`.
4. If using NPZ mode, review detected keys in **NPZ Key Analysis & Load Plan**.
5. If using NPZ mode, adjust the generated load plan if needed:
   - enable/disable groups,
   - remap keys (data / spacing / origin / sparse fields),
   - add or remove plan groups.
6. Click **Load** to import selected data item into the scene.
7. Click **Close / Clear** to remove nodes loaded by the current file.

## IMG+SEG Paired Directory Convention

- `IMG directory` is scanned at top level (non-recursive):
  - If entry is a file with extension `.nii`, `.nii.gz`, `.nrrd`, or `.mhd`, it is one image item and `data_id` is the file basename.
  - If entry is a directory, it is treated as one DICOM series item and `data_id` is the directory name.
- `SEG directory` supports two scan modes:
  - **Flat mode (legacy):** if root-level files matching `-seg.nii.gz` exist, only those root files are used.
  - **Nested mode:** if no root `-seg.nii.gz` file exists and the root contains subdirectories, each first-level subdirectory name is treated as `data_id`, and `-seg.nii.gz` files are collected recursively from that subdirectory.
- Matching rule in flat mode: seg filename must `start with data_id` and `end with -seg.nii.gz`.
- One `data_id` may match multiple segmentation files.
- Items without segmentation can still be listed, and can be filtered out via `Only show data with seg`.

### Paired Load Plan Preference Persistence

- In paired mode, load plan check states are persisted when switching `data_id` (not only when clicking `Load`).
- Persisted preferences include:
  - image row enabled/disabled state,
  - segmentation row enabled/disabled state keyed by seg suffix.
- For nested SEG mode where seg filenames may not start with `data_id`, suffix falls back to filename stem (without `-seg.nii.gz`) to provide stable per-seg preference keys.

## Keyboard Shortcuts (module-focused workflow)

When NPZ Loader is active:

- `F1`, `F2`, `F3`: apply configured window/level presets to loaded volumes.
- `T`: cycle display mode for segmentations loaded by this module (`fill -> contour -> hide`).
- `Shift+T`: cycle display mode for all segmentation nodes in the current scene.
- `S`: toggle the custom Slice Viewing Tool.

## Sparse Segmentation Format

For `seg_sparse` groups:

- `ind` (required): integer array of shape `(N, 3)` with voxel coordinates.
- `color_point` (optional): per-point integer labels.

Behavior:
- If `color_point` is provided, those values become label values.
- Otherwise, foreground value `1` is used.
- If no reference volume shape is available, target shape is inferred from the max sparse index.

## Notes

- Data is loaded with `allow_pickle=False` for NumPy file safety.
- Unsupported/awkward dtypes are coerced to VTK-compatible types when needed.
- The module ships with generic scripted module tests through Slicer CMake macros.

## AI Tool Usage

This project is developed with an AI-assisted workflow.

- Most of the code in this repository was generated by AI tools.
- The human author is responsible for:
  - architecture and feature design,
  - requirement definition and review,
  - manual testing and validation in 3D Slicer,
  - debugging and final quality decisions.

Recommended workflow for contributors:

1. Define or refine the requirement first (input format, expected behavior, edge cases).
2. Use an AI coding tool to generate an initial implementation.
3. Run tests and perform real interactive checks in Slicer.
4. Debug and adjust geometry, UI behavior, and segmentation correctness.
5. Review the final patch manually before merging.

Please treat AI output as draft code: always verify correctness, safety, and maintainability before release.

## Repository Structure

- `CMakeLists.txt`: extension-level configuration.
- `NpzLoader/CMakeLists.txt`: module packaging (scripts/resources/tests).
- `NpzLoader/NpzLoader.py`: main module UI + loading logic.
- `NpzLoader/SliceViewingTool.py`: custom slice interaction controller.
- `NpzLoader/Resources/UI/NpzLoader.ui`: Qt UI layout.

