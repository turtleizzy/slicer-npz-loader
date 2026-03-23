import os
import re
import zipfile
from dataclasses import dataclass, field
from typing import Optional

import ctk
import numpy as np
import numpy.lib.format as npyfmt
import qt
import slicer
from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleLogic,
    ScriptedLoadableModuleTest,
    ScriptedLoadableModuleWidget,
)


# ---------------------------------------------------------------------------
# Module
# ---------------------------------------------------------------------------

class NpzLoader(ScriptedLoadableModule):

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "NPZ Loader"
        self.parent.categories = ["Informatics"]
        self.parent.dependencies = []
        self.parent.contributors = ["NpzLoader Contributors"]
        self.parent.helpText = (
            "Load volume and segmentation data from NPZ/NPY files. "
            "Supports labelmap and sparse-index segmentation formats."
        )
        self.parent.acknowledgementText = ""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class KeyInfo:
    name: str
    shape: tuple
    dtype: str
    role: str  # "volume", "spacing", "origin", "seg_labelmap", "seg_sparse_ind", "seg_sparse_color", "unknown"


@dataclass
class LoadPlanGroup:
    name: str
    group_type: str  # "volume" | "seg_labelmap" | "seg_sparse"
    enabled: bool = True
    mappings: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class NpzLoaderWidget(ScriptedLoadableModuleWidget):

    def __init__(self, parent=None):
        ScriptedLoadableModuleWidget.__init__(self, parent)
        self.logic = None
        self._currentKeys: list[KeyInfo] = []
        self._loadPlanGroups: list[LoadPlanGroup] = []
        self._loadedNodeIds: list[str] = []
        self._loadedVolumeNodeIds: list[str] = []
        self._loadedSegmentationNodeIds: list[str] = []
        self._currentFilePath: Optional[str] = None
        self._segSingleModeIndex = 0
        self._segAllModeIndex = 0
        self._shortcuts: list[qt.QShortcut] = []

    # ---- setup -------------------------------------------------------------

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)
        self.logic = NpzLoaderLogic()

        uiPath = os.path.join(os.path.dirname(__file__), "Resources", "UI", "NpzLoader.ui")
        uiWidget = slicer.util.loadUI(uiPath)
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # --- Section 1: Directory & File Selection ---
        self.ui.directorySelector.filters = ctk.ctkPathLineEdit.Dirs
        self.ui.directorySelector.settingKey = "NpzLoader/RootDirectory"
        self.ui.directorySelector.connect("currentPathChanged(QString)", self.onDirectoryChanged)
        self.ui.fileList.connect("currentRowChanged(int)", self.onFileSelected)

        # --- Section 2: Load plan tree ---
        self.ui.loadPlanTree.setHeaderLabels(["Property", "Value"])
        self.ui.loadPlanTree.setColumnCount(2)
        self.ui.addGroupButton.connect("clicked()", self.onAddGroup)
        self.ui.removeGroupButton.connect("clicked()", self.onRemoveGroup)

        # --- Section 3: Load / Close ---
        self.ui.loadButton.connect("clicked()", self.onLoad)
        self.ui.closeButton.connect("clicked()", self.onClose)

        # --- Section 4: Settings ---
        self.ui.autoDetectCheckBox.checked = True
        self.ui.reuseplanCheckBox.checked = True
        self._loadShortcutSettings()
        self.ui.wlPresetF1LineEdit.connect("editingFinished()", self._saveShortcutSettings)
        self.ui.wlPresetF2LineEdit.connect("editingFinished()", self._saveShortcutSettings)
        self.ui.wlPresetF3LineEdit.connect("editingFinished()", self._saveShortcutSettings)

        self.layout.addStretch(1)
        self._setupShortcuts()

        # Populate if a directory was restored from settings
        if self.ui.directorySelector.currentPath:
            self.onDirectoryChanged(self.ui.directorySelector.currentPath)

    def cleanup(self):
        for shortcut in self._shortcuts:
            shortcut.disconnect("activated()")
        self._shortcuts.clear()

    # ---- shortcut settings -------------------------------------------------

    @staticmethod
    def _defaultWlPresetStrings() -> dict[str, str]:
        return {
            "F1": "400,40",
            "F2": "1500,-600",
            "F3": "2500,500",
        }

    def _loadShortcutSettings(self):
        settings = qt.QSettings()
        defaults = self._defaultWlPresetStrings()
        self.ui.wlPresetF1LineEdit.text = settings.value("NpzLoader/WLPresetF1", defaults["F1"])
        self.ui.wlPresetF2LineEdit.text = settings.value("NpzLoader/WLPresetF2", defaults["F2"])
        self.ui.wlPresetF3LineEdit.text = settings.value("NpzLoader/WLPresetF3", defaults["F3"])

    def _saveShortcutSettings(self):
        settings = qt.QSettings()
        settings.setValue("NpzLoader/WLPresetF1", self.ui.wlPresetF1LineEdit.text.strip())
        settings.setValue("NpzLoader/WLPresetF2", self.ui.wlPresetF2LineEdit.text.strip())
        settings.setValue("NpzLoader/WLPresetF3", self.ui.wlPresetF3LineEdit.text.strip())

    def _setupShortcuts(self):
        mainWindow = slicer.util.mainWindow()
        if not mainWindow:
            return

        def addShortcut(key, callback):
            sc = qt.QShortcut(qt.QKeySequence(key), mainWindow)
            sc.setContext(qt.Qt.ApplicationShortcut)
            sc.connect("activated()", callback)
            self._shortcuts.append(sc)

        addShortcut("F1", lambda: self._onWindowLevelShortcut("F1"))
        addShortcut("F2", lambda: self._onWindowLevelShortcut("F2"))
        addShortcut("F3", lambda: self._onWindowLevelShortcut("F3"))
        addShortcut("T", self._toggleLatestSegmentationDisplayMode)
        addShortcut("Shift+T", self._toggleAllSegmentationsDisplayMode)

    @staticmethod
    def _isModuleActive() -> bool:
        mainWindow = slicer.util.mainWindow()
        if not mainWindow:
            return False
        moduleSelector = mainWindow.moduleSelector()
        if not moduleSelector:
            return False
        selectedModule = None
        if hasattr(moduleSelector, "selectedModule"):
            selectedModule = moduleSelector.selectedModule
        elif hasattr(moduleSelector, "selectedModuleName"):
            selectedModule = moduleSelector.selectedModuleName
        return selectedModule == "NpzLoader"

    @staticmethod
    def _parseWlPreset(text: str) -> Optional[tuple[float, float]]:
        parts = [p.strip() for p in text.split(",")]
        if len(parts) != 2:
            return None
        try:
            return float(parts[0]), float(parts[1])
        except ValueError:
            return None

    def _onWindowLevelShortcut(self, presetKey: str):
        if not self._isModuleActive():
            return
        if presetKey == "F1":
            presetText = self.ui.wlPresetF1LineEdit.text
        elif presetKey == "F2":
            presetText = self.ui.wlPresetF2LineEdit.text
        else:
            presetText = self.ui.wlPresetF3LineEdit.text

        wl = self._parseWlPreset(presetText)
        if wl is None:
            slicer.util.warningDisplay(
                f"Invalid {presetKey} preset format. Use 'window,level' (e.g. 400,40)."
            )
            return
        self._applyWindowLevelToLoadedVolumes(*wl)

    def _applyWindowLevelToLoadedVolumes(self, window: float, level: float):
        appliedCount = 0
        for nodeId in self._loadedVolumeNodeIds:
            volumeNode = slicer.mrmlScene.GetNodeByID(nodeId)
            if not volumeNode:
                continue
            displayNode = volumeNode.GetDisplayNode()
            if not displayNode:
                volumeNode.CreateDefaultDisplayNodes()
                displayNode = volumeNode.GetDisplayNode()
            if not displayNode:
                continue
            displayNode.AutoWindowLevelOff()
            displayNode.SetWindow(window)
            displayNode.SetLevel(level)
            appliedCount += 1

        if appliedCount > 0:
            self.ui.statusLabel.text = (
                f"Applied WL preset: window={window:g}, level={level:g} "
                f"to {appliedCount} volume(s)"
            )

    @staticmethod
    def _applySegDisplayMode(segNode, modeIndex: int):
        displayNode = segNode.GetDisplayNode()
        if not displayNode:
            segNode.CreateDefaultDisplayNodes()
            displayNode = segNode.GetDisplayNode()
        if not displayNode:
            return

        # 0=fill, 1=contour, 2=hide
        if modeIndex == 0:
            displayNode.SetVisibility2DFill(True)
            displayNode.SetVisibility2DOutline(False)
        elif modeIndex == 1:
            displayNode.SetVisibility2DFill(False)
            displayNode.SetVisibility2DOutline(True)
        else:
            displayNode.SetVisibility2DFill(False)
            displayNode.SetVisibility2DOutline(False)

    def _toggleLatestSegmentationDisplayMode(self):
        if not self._isModuleActive():
            return
        if not self._loadedSegmentationNodeIds:
            return
        segNode = slicer.mrmlScene.GetNodeByID(self._loadedSegmentationNodeIds[-1])
        if not segNode:
            return
        self._segSingleModeIndex = (self._segSingleModeIndex + 1) % 3
        self._applySegDisplayMode(segNode, self._segSingleModeIndex)
        modeName = ["fill", "contour", "hide"][self._segSingleModeIndex]
        self.ui.statusLabel.text = f"Latest segmentation display mode: {modeName}"

    def _toggleAllSegmentationsDisplayMode(self):
        if not self._isModuleActive():
            return
        if not self._loadedSegmentationNodeIds:
            return
        self._segAllModeIndex = (self._segAllModeIndex + 1) % 3
        modeName = ["fill", "contour", "hide"][self._segAllModeIndex]
        count = 0
        for nodeId in self._loadedSegmentationNodeIds:
            segNode = slicer.mrmlScene.GetNodeByID(nodeId)
            if not segNode:
                continue
            self._applySegDisplayMode(segNode, self._segAllModeIndex)
            count += 1
        if count > 0:
            self.ui.statusLabel.text = f"All segmentations display mode: {modeName} ({count} nodes)"

    # ---- Directory & file list ---------------------------------------------

    def onDirectoryChanged(self, dirPath):
        self.ui.fileList.clear()
        if not dirPath or not os.path.isdir(dirPath):
            return
        for fname in sorted(os.listdir(dirPath)):
            if fname.lower().endswith((".npz", ".npy")):
                self.ui.fileList.addItem(fname)

    def onFileSelected(self, row):
        if row < 0:
            return
        dirPath = self.ui.directorySelector.currentPath
        fname = self.ui.fileList.item(row).text()
        filePath = os.path.join(dirPath, fname)
        self._currentFilePath = filePath

        baseName = os.path.splitext(fname)[0]
        self.ui.statusLabel.text = f"Selected: {baseName}"

        self._analyzeAndBuildPlan(filePath)

    # ---- Key analysis & plan building --------------------------------------

    def _analyzeAndBuildPlan(self, filePath):
        try:
            self._currentKeys = self.logic.analyzeNpzKeys(filePath)
        except Exception as e:
            slicer.util.errorDisplay(f"Failed to analyze file:\n{e}")
            return

        self._populateKeyInfoTable()

        reuse = self.ui.reuseplanCheckBox.checked
        signature = self.logic.computeKeySignature(self._currentKeys)
        if reuse and signature in self.logic.stickyPlans:
            self._loadPlanGroups = self.logic.clonePlanGroups(self.logic.stickyPlans[signature])
        else:
            self._loadPlanGroups = self.logic.generateLoadPlan(self._currentKeys)

        self._populateLoadPlanTree()

    def _populateKeyInfoTable(self):
        table = self.ui.keyInfoTable
        table.setRowCount(len(self._currentKeys))
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Key", "Shape", "Dtype", "Role"])
        for i, ki in enumerate(self._currentKeys):
            table.setItem(i, 0, qt.QTableWidgetItem(ki.name))
            table.setItem(i, 1, qt.QTableWidgetItem(str(ki.shape)))
            table.setItem(i, 2, qt.QTableWidgetItem(ki.dtype))
            table.setItem(i, 3, qt.QTableWidgetItem(ki.role))
        table.resizeColumnsToContents()

    # ---- Load Plan Tree UI -------------------------------------------------

    def _populateLoadPlanTree(self):
        tree = self.ui.loadPlanTree
        tree.clear()
        allKeyNames = ["(none)"] + [k.name for k in self._currentKeys]

        for group in self._loadPlanGroups:
            groupItem = qt.QTreeWidgetItem(tree)
            groupItem.setText(0, f"{group.group_type}: {group.name}")
            groupItem.setFlags(groupItem.flags() | qt.Qt.ItemIsUserCheckable)
            groupItem.setCheckState(0, qt.Qt.Checked if group.enabled else qt.Qt.Unchecked)

            for mappingKey, mappingVal in group.mappings.items():
                childItem = qt.QTreeWidgetItem(groupItem)
                childItem.setText(0, mappingKey)

                combo = qt.QComboBox()
                combo.addItems(allKeyNames)
                idx = combo.findText(mappingVal) if mappingVal else 0
                combo.setCurrentIndex(max(idx, 0))
                tree.setItemWidget(childItem, 1, combo)

            groupItem.setExpanded(True)

        tree.resizeColumnToContents(0)

    def _readLoadPlanFromTree(self):
        """Sync the UI tree state back into self._loadPlanGroups."""
        tree = self.ui.loadPlanTree
        for groupIdx in range(tree.topLevelItemCount):
            groupItem = tree.topLevelItem(groupIdx)
            group = self._loadPlanGroups[groupIdx]
            group.enabled = groupItem.checkState(0) == qt.Qt.Checked

            for childIdx in range(groupItem.childCount()):
                childItem = groupItem.child(childIdx)
                mappingKey = childItem.text(0)
                combo = tree.itemWidget(childItem, 1)
                val = combo.currentText if combo else "(none)"
                group.mappings[mappingKey] = val if val != "(none)" else None

    # ---- Add / Remove groups -----------------------------------------------

    def onAddGroup(self):
        dialog = qt.QDialog(slicer.util.mainWindow())
        dialog.setWindowTitle("Add Load Plan Group")
        layout = qt.QFormLayout(dialog)

        nameEdit = qt.QLineEdit()
        typeCombo = qt.QComboBox()
        typeCombo.addItems(["volume", "seg_labelmap", "seg_sparse"])
        layout.addRow("Name:", nameEdit)
        layout.addRow("Type:", typeCombo)

        buttons = qt.QDialogButtonBox(qt.QDialogButtonBox.Ok | qt.QDialogButtonBox.Cancel)
        buttons.connect("accepted()", dialog.accept)
        buttons.connect("rejected()", dialog.reject)
        layout.addRow(buttons)

        if dialog.exec_() != qt.QDialog.Accepted:
            return
        name = nameEdit.text.strip()
        if not name:
            return

        gtype = typeCombo.currentText
        mappings = self.logic.defaultMappingsForType(gtype)
        newGroup = LoadPlanGroup(name=name, group_type=gtype, enabled=True, mappings=mappings)
        self._loadPlanGroups.append(newGroup)
        self._populateLoadPlanTree()

    def onRemoveGroup(self):
        tree = self.ui.loadPlanTree
        item = tree.currentItem()
        if item is None:
            return
        # Find top-level index
        parent = item.parent()
        if parent is not None:
            item = parent
        idx = tree.indexOfTopLevelItem(item)
        if 0 <= idx < len(self._loadPlanGroups):
            del self._loadPlanGroups[idx]
            self._populateLoadPlanTree()

    # ---- Load / Close ------------------------------------------------------

    def onLoad(self):
        if not self._currentFilePath:
            slicer.util.warningDisplay("No file selected.")
            return

        self._readLoadPlanFromTree()

        enabledGroups = [g for g in self._loadPlanGroups if g.enabled]
        if not enabledGroups:
            slicer.util.warningDisplay("No load plan groups enabled.")
            return

        # Clear previously loaded nodes before loading new ones
        self._clearNodes()
        self._segSingleModeIndex = 0
        self._segAllModeIndex = 0

        baseName = os.path.splitext(os.path.basename(self._currentFilePath))[0]

        try:
            npzData = self.logic.loadFile(self._currentFilePath)
        except Exception as e:
            slicer.util.errorDisplay(f"Failed to load file:\n{e}")
            return

        volumeShape = None
        volumeSpacing = None
        volumeOrigin = None

        # First pass: load volumes to determine shape/spacing/origin for segs
        for group in enabledGroups:
            if group.group_type == "volume":
                try:
                    nodeIds, vShape, vSpacing, vOrigin = self.logic.loadVolume(
                        npzData, group, baseName
                    )
                    self._loadedNodeIds.extend(nodeIds)
                    self._loadedVolumeNodeIds.extend(nodeIds)
                    if volumeShape is None:
                        volumeShape = vShape
                        volumeSpacing = vSpacing
                        volumeOrigin = vOrigin
                except Exception as e:
                    slicer.util.errorDisplay(f"Error loading volume '{group.name}':\n{e}")

        # Second pass: load segmentations
        for group in enabledGroups:
            if group.group_type == "seg_labelmap":
                try:
                    nodeIds = self.logic.loadSegLabelmap(
                        npzData, group, baseName, volumeShape, volumeSpacing, volumeOrigin
                    )
                    self._loadedNodeIds.extend(nodeIds)
                    self._loadedSegmentationNodeIds.extend(nodeIds)
                except Exception as e:
                    slicer.util.errorDisplay(f"Error loading seg '{group.name}':\n{e}")
            elif group.group_type == "seg_sparse":
                try:
                    nodeIds = self.logic.loadSegSparse(
                        npzData, group, baseName, volumeShape, volumeSpacing, volumeOrigin
                    )
                    self._loadedNodeIds.extend(nodeIds)
                    self._loadedSegmentationNodeIds.extend(nodeIds)
                except Exception as e:
                    slicer.util.errorDisplay(f"Error loading sparse seg '{group.name}':\n{e}")

        if hasattr(npzData, "close"):
            npzData.close()

        # Save sticky plan
        signature = self.logic.computeKeySignature(self._currentKeys)
        self.logic.stickyPlans[signature] = self.logic.clonePlanGroups(self._loadPlanGroups)

        self.ui.statusLabel.text = f"Loaded: {baseName} ({len(self._loadedNodeIds)} nodes)"

    def onClose(self):
        self._clearNodes()
        self.ui.statusLabel.text = "Scene cleared."

    def _clearNodes(self):
        for nodeId in self._loadedNodeIds:
            node = slicer.mrmlScene.GetNodeByID(nodeId)
            if node:
                slicer.mrmlScene.RemoveNode(node)
        self._loadedNodeIds.clear()
        self._loadedVolumeNodeIds.clear()
        self._loadedSegmentationNodeIds.clear()


# ---------------------------------------------------------------------------
# NPY wrapper (makes a single array behave like NpzFile)
# ---------------------------------------------------------------------------

class _NpyWrapper:
    """Thin dict-like wrapper so a single .npy array can be used
    with the same code paths as NpzFile objects."""

    def __init__(self, arr: np.ndarray):
        self._data = {"data": arr}
        self.files = ["data"]

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def get(self, key, default=None):
        return self._data.get(key, default)

    def close(self):
        pass


# ---------------------------------------------------------------------------
# Logic
# ---------------------------------------------------------------------------

class NpzLoaderLogic(ScriptedLoadableModuleLogic):

    def __init__(self):
        ScriptedLoadableModuleLogic.__init__(self)
        self.stickyPlans: dict[str, list[LoadPlanGroup]] = {}

    # ---- Key analysis ------------------------------------------------------

    _VOLUME_PATTERN = re.compile(r"^(img|vol|volume|image)$", re.IGNORECASE)
    _SPACING_PATTERN = re.compile(r"^spacing$", re.IGNORECASE)
    _ORIGIN_PATTERN = re.compile(r"^origin$", re.IGNORECASE)
    _SEG_PATTERN = re.compile(r"(^seg|seg$)", re.IGNORECASE)
    _SPARSE_IND_PATTERN = re.compile(r"(?:^|_)(inds?)$", re.IGNORECASE)
    _SPARSE_COLOR_PATTERN = re.compile(r"color_point|color_points|colorpoint|colorpoints", re.IGNORECASE)

    @staticmethod
    def _readNpyHeaderShapeDtype(fileobj) -> tuple[tuple, str]:
        """Read only the .npy header (magic + dict); does not read array data."""
        version = npyfmt.read_magic(fileobj)
        if version == (1, 0):
            shape, _fortran, dtype = npyfmt.read_array_header_1_0(fileobj)
        elif version == (2, 0):
            shape, _fortran, dtype = npyfmt.read_array_header_2_0(fileobj)
        elif version == (3, 0):
            shape, _fortran, dtype = npyfmt._read_array_header(fileobj, version)
        else:
            raise ValueError(f"Unsupported numpy .npy format version {version}")
        return tuple(shape), str(dtype)

    def analyzeNpzKeys(self, filePath: str) -> list[KeyInfo]:
        """Classify arrays using only each member's .npy header (no full array I/O)."""
        ext = os.path.splitext(filePath)[1].lower()
        if ext == ".npy":
            with open(filePath, "rb") as f:
                shape, dtype = self._readNpyHeaderShapeDtype(f)
            return [KeyInfo(name="data", shape=shape, dtype=dtype, role="volume")]

        keys: list[KeyInfo] = []
        with zipfile.ZipFile(filePath, "r") as zf:
            for member in sorted(zf.namelist()):
                if not member.endswith(".npy"):
                    continue
                array_key = os.path.splitext(os.path.basename(member))[0]
                with zf.open(member, "r") as raw:
                    shape, dtype = self._readNpyHeaderShapeDtype(raw)
                role = self._classifyKey(array_key, shape, dtype)
                keys.append(KeyInfo(name=array_key, shape=shape, dtype=dtype, role=role))
        return keys

    def _classifyKey(self, name: str, shape: tuple, dtype: str) -> str:
        if self._SPACING_PATTERN.match(name):
            return "spacing"
        if self._ORIGIN_PATTERN.match(name):
            return "origin"
        if self._VOLUME_PATTERN.match(name) and len(shape) == 3:
            return "volume"
        if self._SPARSE_IND_PATTERN.search(name) and len(shape) == 2 and shape[1] == 3:
            return "seg_sparse_ind"
        if self._SPARSE_COLOR_PATTERN.search(name) and len(shape) == 1:
            return "seg_sparse_color"
        if self._SEG_PATTERN.search(name) and len(shape) == 3 and np.issubdtype(np.dtype(dtype), np.integer):
            return "seg_labelmap"
        if len(shape) == 3 and self._VOLUME_PATTERN.match(name) is None and self._SEG_PATTERN.search(name) is None:
            return "unknown"
        return "unknown"

    # ---- Plan generation ---------------------------------------------------

    def generateLoadPlan(self, keys: list[KeyInfo]) -> list[LoadPlanGroup]:
        groups: list[LoadPlanGroup] = []

        spacingKey = next((k.name for k in keys if k.role == "spacing"), None)
        originKey = next((k.name for k in keys if k.role == "origin"), None)

        # Volumes
        for k in keys:
            if k.role == "volume":
                groups.append(LoadPlanGroup(
                    name=k.name,
                    group_type="volume",
                    enabled=True,
                    mappings={"data": k.name, "spacing": spacingKey, "origin": originKey},
                ))

        # Labelmap segmentations
        for k in keys:
            if k.role == "seg_labelmap":
                groups.append(LoadPlanGroup(
                    name=k.name,
                    group_type="seg_labelmap",
                    enabled=True,
                    mappings={"data": k.name, "spacing": spacingKey, "origin": originKey},
                ))

        # Sparse segmentations: pair ind with color_point
        indKeys = [k for k in keys if k.role == "seg_sparse_ind"]
        colorKeys = [k for k in keys if k.role == "seg_sparse_color"]

        for ik in indKeys:
            prefix = re.sub(r"(_{0,1})(inds?|ind)$", "", ik.name, flags=re.IGNORECASE)
            matched_color = None
            for ck in colorKeys:
                cprefix = re.sub(r"(_{0,1})(color_?points?|colorpoints?)$", "", ck.name, flags=re.IGNORECASE)
                if cprefix.lower() == prefix.lower():
                    matched_color = ck.name
                    break

            sparseGroupName = prefix if prefix else ik.name
            groups.append(LoadPlanGroup(
                name=sparseGroupName,
                group_type="seg_sparse",
                enabled=True,
                mappings={
                    "ind": ik.name,
                    "color_point": matched_color,
                    "spacing": spacingKey,
                    "origin": originKey,
                },
            ))

        # If no volume was detected, pick first 3-D array as volume
        if not any(g.group_type == "volume" for g in groups):
            for k in keys:
                if len(k.shape) == 3 and k.role == "unknown":
                    groups.insert(0, LoadPlanGroup(
                        name=k.name,
                        group_type="volume",
                        enabled=True,
                        mappings={"data": k.name, "spacing": spacingKey, "origin": originKey},
                    ))
                    break

        return groups

    def computeKeySignature(self, keys: list[KeyInfo]) -> str:
        return ",".join(sorted(k.name for k in keys))

    def clonePlanGroups(self, groups: list[LoadPlanGroup]) -> list[LoadPlanGroup]:
        return [
            LoadPlanGroup(
                name=g.name,
                group_type=g.group_type,
                enabled=g.enabled,
                mappings=dict(g.mappings),
            )
            for g in groups
        ]

    def defaultMappingsForType(self, groupType: str) -> dict:
        if groupType == "volume":
            return {"data": None, "spacing": None, "origin": None}
        elif groupType == "seg_labelmap":
            return {"data": None, "spacing": None, "origin": None}
        elif groupType == "seg_sparse":
            return {"ind": None, "color_point": None, "spacing": None, "origin": None}
        return {}

    # ---- File loading ------------------------------------------------------

    @staticmethod
    def loadFile(filePath: str):
        """Load an NPZ or NPY file and return a dict-like object."""
        ext = os.path.splitext(filePath)[1].lower()
        if ext == ".npy":
            arr = np.load(filePath, allow_pickle=False)
            return _NpyWrapper(arr)
        return np.load(filePath, allow_pickle=False)

    # ---- Loading helpers ---------------------------------------------------

    _VTK_COMPATIBLE_DTYPES = {
        np.float16: np.float32,
        np.float128: np.float64 if hasattr(np, "float128") else np.float64,
    }

    @classmethod
    def _coerceDtype(cls, arr: np.ndarray) -> np.ndarray:
        """Upcast dtypes that VTK cannot handle (e.g. float16) to the nearest supported type."""
        target = cls._VTK_COMPATIBLE_DTYPES.get(arr.dtype.type)
        if target is not None:
            return arr.astype(target)
        if not np.issubdtype(arr.dtype, np.bool_) and not np.issubdtype(arr.dtype, np.integer) and not np.issubdtype(arr.dtype, np.floating):
            return arr.astype(np.float64)
        return arr

    # LPS → RAS: Slicer uses RAS (Right, Anterior, Superior).  DICOM / many
    # numpy pipelines use LPS (Left, Posterior, Superior) with voxel indices
    # increasing along +L, +P, +S.  Map I,J,K to RAS directions by negating
    # the in-plane axes (L→R, P→A); keep +S along K (typical axial stack).
    # Rows are I, J, K axis directions in RAS (same order as SetIJKToRASDirections).
    _IJK_DIRECTIONS_LPS_TO_RAS = [
        [-1, 0, 0],
        [0, -1, 0],
        [0, 0, 1],
    ]

    @staticmethod
    def _resolveSpacingOrigin(npzData, mappings, volumeSpacing=None, volumeOrigin=None):
        """Return (spacing_xyz, origin_xyz) tuples in Slicer (x,y,z) order."""
        spacingKey = mappings.get("spacing")
        originKey = mappings.get("origin")

        if spacingKey and spacingKey in npzData:
            sp = tuple(float(v) for v in npzData[spacingKey])  # (z, y, x)
        elif volumeSpacing is not None:
            sp = volumeSpacing  # already (z, y, x)
        else:
            sp = (1.0, 1.0, 1.0)

        if originKey and originKey in npzData:
            og = tuple(float(v) for v in npzData[originKey])  # (z, y, x)
        elif volumeOrigin is not None:
            og = volumeOrigin  # already (z, y, x)
        else:
            og = (0.0, 0.0, 0.0)

        # Reverse from (z, y, x) to (x, y, z) for Slicer
        spacing_xyz = (sp[2], sp[1], sp[0])
        origin_xyz = (og[2], og[1], og[0])
        return spacing_xyz, origin_xyz

    @classmethod
    def _applyGeometry(cls, node, spacing_xyz, origin_xyz, shape):
        """Set spacing, LPS→RAS directions, and origin on a volume node.

        Numpy array is (K, J, I) = (D, H, W).  For each axis whose RAS direction
        is negated vs identity, shift origin so the same voxel grid maps to the
        same physical extent (corner of index space stays consistent).
        """
        node.SetSpacing(*spacing_xyz)
        # I and J negated → compensate X and Y; K unchanged → no Z shift.
        # shape[2]=I extent, shape[1]=J extent, shape[0]=K extent.
        adjusted_origin = (
            origin_xyz[0], # + (shape[2] - 1) * spacing_xyz[0
            origin_xyz[1], # + (shape[1] - 1) * spacing_xyz[1],
            origin_xyz[2],
        )
        node.SetOrigin(*adjusted_origin)
        d = cls._IJK_DIRECTIONS_LPS_TO_RAS
        node.SetIJKToRASDirections(
            d[0][0], d[0][1], d[0][2],
            d[1][0], d[1][1], d[1][2],
            d[2][0], d[2][1], d[2][2],
        )

    # ---- Volume loading ----------------------------------------------------

    def loadVolume(self, npzData, group: LoadPlanGroup, baseName: str):
        dataKey = group.mappings.get("data")
        if not dataKey:
            raise ValueError("No data key specified for volume group.")

        data = self._coerceDtype(np.array(npzData[dataKey]))
        if data.ndim != 3:
            raise ValueError(f"Volume array '{dataKey}' must be 3-D, got shape {data.shape}")

        spacing_xyz, origin_xyz = self._resolveSpacingOrigin(npzData, group.mappings)

        nodeName = f"{baseName}_{group.name}"
        volumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", nodeName)
        self._applyGeometry(volumeNode, spacing_xyz, origin_xyz, data.shape)
        slicer.util.updateVolumeFromArray(volumeNode, data)
        volumeNode.CreateDefaultDisplayNodes()

        slicer.util.setSliceViewerLayers(background=volumeNode, fit=True)

        # Retrieve raw spacing/origin in (z,y,x) for downstream seg use
        spKey = group.mappings.get("spacing")
        rawSpacing = tuple(float(v) for v in npzData[spKey]) if (spKey and spKey in npzData) else (1.0, 1.0, 1.0)
        ogKey = group.mappings.get("origin")
        rawOrigin = tuple(float(v) for v in npzData[ogKey]) if (ogKey and ogKey in npzData) else (0.0, 0.0, 0.0)

        return [volumeNode.GetID()], data.shape, rawSpacing, rawOrigin

    # ---- Seg-labelmap loading ----------------------------------------------

    def loadSegLabelmap(self, npzData, group: LoadPlanGroup, baseName: str,
                        volumeShape=None, volumeSpacing=None, volumeOrigin=None):
        dataKey = group.mappings.get("data")
        if not dataKey:
            raise ValueError("No data key specified for seg_labelmap group.")

        segData = np.array(npzData[dataKey])
        if segData.ndim != 3:
            raise ValueError(f"Seg labelmap '{dataKey}' must be 3-D, got shape {segData.shape}")

        # Determine whether seg has its own spacing/origin
        hasOwnGeometry = (volumeShape is None or segData.shape != volumeShape)
        if hasOwnGeometry:
            spacing_xyz, origin_xyz = self._resolveSpacingOrigin(npzData, group.mappings)
        else:
            spacing_xyz, origin_xyz = self._resolveSpacingOrigin(
                npzData, group.mappings, volumeSpacing, volumeOrigin
            )

        segData = self._coerceDtype(segData.astype(np.int16))

        labelmapName = f"{baseName}_{group.name}_labelmap"
        labelmapNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", labelmapName)
        self._applyGeometry(labelmapNode, spacing_xyz, origin_xyz, segData.shape)
        slicer.util.updateVolumeFromArray(labelmapNode, segData)

        segNodeName = f"{baseName}_{group.name}"
        segNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", segNodeName)
        slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelmapNode, segNode)
        segNode.CreateClosedSurfaceRepresentation()

        slicer.mrmlScene.RemoveNode(labelmapNode)

        return [segNode.GetID()]

    # ---- Seg-sparse loading ------------------------------------------------

    def loadSegSparse(self, npzData, group: LoadPlanGroup, baseName: str,
                      volumeShape=None, volumeSpacing=None, volumeOrigin=None):
        indKey = group.mappings.get("ind")
        if not indKey:
            raise ValueError("No ind key specified for seg_sparse group.")

        indices = np.array(npzData[indKey])
        if indices.ndim != 2 or indices.shape[1] != 3:
            raise ValueError(f"Sparse index array '{indKey}' must be (N,3), got shape {indices.shape}")

        colorKey = group.mappings.get("color_point")
        colorPoints = None
        if colorKey and colorKey in npzData:
            colorPoints = np.array(npzData[colorKey])

        targetShape = volumeShape
        if targetShape is None:
            maxIdx = indices.max(axis=0)
            targetShape = (int(maxIdx[0]) + 1, int(maxIdx[1]) + 1, int(maxIdx[2]) + 1)

        labelmap = np.zeros(targetShape, dtype=np.int16)
        if colorPoints is not None:
            labelmap[indices[:, 0], indices[:, 1], indices[:, 2]] = colorPoints.astype(np.int16)
        else:
            labelmap[indices[:, 0], indices[:, 1], indices[:, 2]] = 1

        spacing_xyz, origin_xyz = self._resolveSpacingOrigin(
            npzData, group.mappings, volumeSpacing, volumeOrigin
        )

        labelmapName = f"{baseName}_{group.name}_sparse_labelmap"
        labelmapNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", labelmapName)
        self._applyGeometry(labelmapNode, spacing_xyz, origin_xyz, labelmap.shape)
        slicer.util.updateVolumeFromArray(labelmapNode, labelmap)

        segNodeName = f"{baseName}_{group.name}"
        segNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", segNodeName)
        slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelmapNode, segNode)
        segNode.CreateClosedSurfaceRepresentation()

        slicer.mrmlScene.RemoveNode(labelmapNode)

        return [segNode.GetID()]


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

class NpzLoaderTest(ScriptedLoadableModuleTest):

    def setUp(self):
        slicer.mrmlScene.Clear(0)

    def runTest(self):
        self.setUp()
        self.test_AnalyzeKeys()
        self.test_LoadVolume()

    def test_AnalyzeKeys(self):
        self.delayDisplay("Testing key analysis")
        import tempfile

        vol = np.random.rand(10, 20, 30).astype(np.float32)
        seg = np.zeros((10, 20, 30), dtype=np.int16)
        seg[2:5, 3:8, 4:10] = 1
        spacing = np.array([0.5, 0.5, 0.5])
        origin = np.array([10.0, 20.0, 30.0])

        tmpFile = os.path.join(tempfile.gettempdir(), "test_npz_loader.npz")
        np.savez(tmpFile, img=vol, seg_organ=seg, spacing=spacing, origin=origin)

        logic = NpzLoaderLogic()
        keys = logic.analyzeNpzKeys(tmpFile)
        roles = {k.name: k.role for k in keys}
        assert roles["img"] == "volume", f"Expected volume, got {roles['img']}"
        assert roles["seg_organ"] == "seg_labelmap", f"Expected seg_labelmap, got {roles['seg_organ']}"
        assert roles["spacing"] == "spacing"
        assert roles["origin"] == "origin"

        plan = logic.generateLoadPlan(keys)
        assert any(g.group_type == "volume" for g in plan)
        assert any(g.group_type == "seg_labelmap" for g in plan)

        os.remove(tmpFile)
        self.delayDisplay("Key analysis test passed!")

    def test_LoadVolume(self):
        self.delayDisplay("Testing volume loading")
        import tempfile

        vol = np.random.rand(10, 20, 30).astype(np.float32)
        spacing = np.array([2.0, 1.0, 0.5])
        origin = np.array([10.0, 20.0, 30.0])

        tmpFile = os.path.join(tempfile.gettempdir(), "test_npz_loader_vol.npz")
        np.savez(tmpFile, img=vol, spacing=spacing, origin=origin)

        logic = NpzLoaderLogic()
        keys = logic.analyzeNpzKeys(tmpFile)
        plan = logic.generateLoadPlan(keys)

        npzData = np.load(tmpFile, allow_pickle=False)
        volGroup = [g for g in plan if g.group_type == "volume"][0]
        nodeIds, shape, sp, og = logic.loadVolume(npzData, volGroup, "test")
        npzData.close()

        assert len(nodeIds) == 1
        node = slicer.mrmlScene.GetNodeByID(nodeIds[0])
        assert node is not None
        assert node.GetClassName() == "vtkMRMLScalarVolumeNode"

        nodeSp = node.GetSpacing()
        assert abs(nodeSp[0] - 0.5) < 1e-6
        assert abs(nodeSp[1] - 1.0) < 1e-6
        assert abs(nodeSp[2] - 2.0) < 1e-6

        slicer.mrmlScene.RemoveNode(node)
        os.remove(tmpFile)
        self.delayDisplay("Volume loading test passed!")
