import os
import re
import json
import tempfile
import zipfile
from dataclasses import dataclass, field
from typing import Optional

import ctk
import numpy as np
import numpy.lib.format as npyfmt
import qt
import slicer
from SliceViewingTool import ensureGlobalSliceViewingTool, getGlobalSliceViewingTool
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
        ensureGlobalSliceViewingTool(os.path.dirname(__file__))


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


@dataclass
class ReviewDataItem:
    data_id: str
    source_type: str  # "npz" | "paired"
    npz_path: Optional[str] = None
    img_path: Optional[str] = None
    seg_paths: list[str] = field(default_factory=list)


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
        self._currentDataItems: list[ReviewDataItem] = []
        self._currentDataItem: Optional[ReviewDataItem] = None
        self._pairedSegSuffixSelection: dict[str, bool] = {}
        self._segSingleModeIndex = 0
        self._segAllModeIndex = 0
        self._shortcuts: list[qt.QShortcut] = []
        self._sliceViewingTool = None

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
        self.ui.imgDirectorySelector.filters = ctk.ctkPathLineEdit.Dirs
        self.ui.segDirectorySelector.filters = ctk.ctkPathLineEdit.Dirs
        self.ui.directorySelector.connect("currentPathChanged(QString)", self.onDirectoryChanged)
        self.ui.imgDirectorySelector.connect("currentPathChanged(QString)", self.onPairedPathChanged)
        self.ui.segDirectorySelector.connect("currentPathChanged(QString)", self.onPairedPathChanged)
        self.ui.sourceTypeComboBox.connect("currentIndexChanged(int)", self.onSourceTypeChanged)
        self.ui.scanButton.connect("clicked()", self.onScanPairedDirectories)
        self.ui.onlyWithSegCheckBox.connect("toggled(bool)", self.onOnlyWithSegToggled)
        self.ui.fileList.connect("currentRowChanged(int)", self.onFileSelected)
        self._loadReviewSourceSettings()

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
        self._loadFloatSegSettings()
        self.ui.floatSegAutoThresholdCheckBox.connect(
            "toggled(bool)", self._onFloatSegAutoThresholdToggled
        )
        self.ui.floatSegThresholdDoubleSpinBox.connect(
            "valueChanged(double)", self._onFloatSegThresholdChanged
        )
        self._loadShortcutSettings()
        self.ui.wlPresetF1LineEdit.connect("editingFinished()", self._saveShortcutSettings)
        self.ui.wlPresetF2LineEdit.connect("editingFinished()", self._saveShortcutSettings)
        self.ui.wlPresetF3LineEdit.connect("editingFinished()", self._saveShortcutSettings)

        self.layout.addStretch(1)
        self._setupShortcuts()
        self._setupSliceTool()

        self._updateSourceUi()
        self._refreshDataListFromSource()

    def cleanup(self):
        for shortcut in self._shortcuts:
            shortcut.disconnect("activated()")
        self._shortcuts.clear()
        if self._sliceViewingTool:
            self._sliceViewingTool.status_callback = None
            self._sliceViewingTool = None

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

    def _loadReviewSourceSettings(self):
        settings = qt.QSettings()
        sourceIdx = int(settings.value("NpzLoader/SourceTypeIndex", 0))
        self.ui.sourceTypeComboBox.currentIndex = max(0, min(sourceIdx, 1))
        self.ui.directorySelector.currentPath = settings.value("NpzLoader/RootDirectory", "")
        self.ui.imgDirectorySelector.currentPath = settings.value("NpzLoader/ImgDirectory", "")
        self.ui.segDirectorySelector.currentPath = settings.value("NpzLoader/SegDirectory", "")
        self.ui.onlyWithSegCheckBox.checked = self._toBool(
            settings.value("NpzLoader/OnlyWithSeg", False)
        )
        rawSuffixSelection = settings.value("NpzLoader/PairedSegSuffixSelection", "{}")
        try:
            parsed = json.loads(str(rawSuffixSelection))
            self._pairedSegSuffixSelection = {
                str(k): bool(v) for k, v in parsed.items()
            } if isinstance(parsed, dict) else {}
        except Exception:
            self._pairedSegSuffixSelection = {}

    def _saveReviewSourceSettings(self):
        settings = qt.QSettings()
        settings.setValue("NpzLoader/SourceTypeIndex", int(self.ui.sourceTypeComboBox.currentIndex))
        settings.setValue("NpzLoader/RootDirectory", self.ui.directorySelector.currentPath)
        settings.setValue("NpzLoader/ImgDirectory", self.ui.imgDirectorySelector.currentPath)
        settings.setValue("NpzLoader/SegDirectory", self.ui.segDirectorySelector.currentPath)
        settings.setValue("NpzLoader/OnlyWithSeg", bool(self.ui.onlyWithSegCheckBox.checked))
        settings.setValue(
            "NpzLoader/PairedSegSuffixSelection",
            json.dumps(self._pairedSegSuffixSelection, ensure_ascii=True),
        )

    @staticmethod
    def _toBool(value) -> bool:
        # qt.QSettings may return QVariant / string depending on PythonQt build.
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "y", "on")

    def _loadFloatSegSettings(self):
        settings = qt.QSettings()
        autoThresholdVal = settings.value("NpzLoader/FloatSegAutoThreshold", True)
        thresholdVal = settings.value("NpzLoader/FloatSegThreshold", 0.5)

        self.ui.floatSegAutoThresholdCheckBox.checked = self._toBool(autoThresholdVal)
        self.ui.floatSegThresholdDoubleSpinBox.value = float(thresholdVal)
        self.ui.floatSegThresholdDoubleSpinBox.setEnabled(
            self.ui.floatSegAutoThresholdCheckBox.checked
        )

        # Sync to logic
        if self.logic:
            self.logic.floatSegAutoThreshold = self.ui.floatSegAutoThresholdCheckBox.checked
            self.logic.floatSegThreshold = float(self.ui.floatSegThresholdDoubleSpinBox.value)

    def _saveFloatSegSettings(self):
        settings = qt.QSettings()
        settings.setValue(
            "NpzLoader/FloatSegAutoThreshold",
            bool(self.ui.floatSegAutoThresholdCheckBox.checked),
        )
        settings.setValue(
            "NpzLoader/FloatSegThreshold",
            float(self.ui.floatSegThresholdDoubleSpinBox.value),
        )

        # Sync to logic
        if self.logic:
            self.logic.floatSegAutoThreshold = bool(self.ui.floatSegAutoThresholdCheckBox.checked)
            self.logic.floatSegThreshold = float(self.ui.floatSegThresholdDoubleSpinBox.value)

    def _onFloatSegAutoThresholdToggled(self, _checked: bool):
        self.ui.floatSegThresholdDoubleSpinBox.setEnabled(_checked)
        self._saveFloatSegSettings()

    def _onFloatSegThresholdChanged(self, _value: float):
        self._saveFloatSegSettings()

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
        addShortcut("T", self._toggleLoadedSegmentationsDisplayMode)
        addShortcut("Shift+T", self._toggleSceneSegmentationsDisplayMode)
        addShortcut("S", self._toggleSliceDragTool)

    def _setupSliceTool(self):
        moduleDir = os.path.dirname(__file__)
        ensureGlobalSliceViewingTool(moduleDir)
        self._sliceViewingTool = getGlobalSliceViewingTool()
        if self._sliceViewingTool:
            self._sliceViewingTool.status_callback = (
                lambda text: setattr(self.ui.statusLabel, "text", text)
            )

    def _toggleSliceDragTool(self):
        if self._sliceViewingTool:
            self._sliceViewingTool.toggle()

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

    def _toggleLoadedSegmentationsDisplayMode(self):
        if not self._isModuleActive():
            return
        if not self._loadedSegmentationNodeIds:
            return
        self._segSingleModeIndex = (self._segSingleModeIndex + 1) % 3
        modeName = ["fill", "contour", "hide"][self._segSingleModeIndex]
        count = 0
        for nodeId in self._loadedSegmentationNodeIds:
            segNode = slicer.mrmlScene.GetNodeByID(nodeId)
            if not segNode:
                continue
            self._applySegDisplayMode(segNode, self._segSingleModeIndex)
            count += 1
        if count > 0:
            self.ui.statusLabel.text = (
                f"Loaded segmentations display mode: {modeName} ({count} nodes)"
            )

    def _toggleSceneSegmentationsDisplayMode(self):
        if not self._isModuleActive():
            return
        allSegNodes = slicer.util.getNodesByClass("vtkMRMLSegmentationNode")
        if not allSegNodes:
            return
        self._segAllModeIndex = (self._segAllModeIndex + 1) % 3
        modeName = ["fill", "contour", "hide"][self._segAllModeIndex]
        count = 0
        for segNode in allSegNodes:
            self._applySegDisplayMode(segNode, self._segAllModeIndex)
            count += 1
        if count > 0:
            self.ui.statusLabel.text = (
                f"All scene segmentations display mode: {modeName} ({count} nodes)"
            )

    # ---- Directory & file list ---------------------------------------------

    def _isNpzSourceMode(self) -> bool:
        return int(self.ui.sourceTypeComboBox.currentIndex) == 0

    def _updateSourceUi(self):
        isNpz = self._isNpzSourceMode()
        self.ui.directoryLabel.visible = isNpz
        self.ui.directorySelector.visible = isNpz
        self.ui.imgDirectoryLabel.visible = not isNpz
        self.ui.imgDirectorySelector.visible = not isNpz
        self.ui.segDirectoryLabel.visible = not isNpz
        self.ui.segDirectorySelector.visible = not isNpz
        self.ui.scanButton.visible = not isNpz
        self.ui.onlyWithSegCheckBox.visible = not isNpz
        self.ui.keyInfoLabel.visible = isNpz
        self.ui.keyInfoTable.visible = isNpz
        self.ui.loadPlanLabel.visible = True
        self.ui.loadPlanTree.visible = True
        self.ui.addGroupButton.visible = isNpz
        self.ui.removeGroupButton.visible = isNpz
        self.ui.loadPlanCollapsible.text = (
            "NPZ Key Analysis & Load Plan" if isNpz else "Paired Load Plan"
        )
        self.ui.loadPlanLabel.text = (
            "Load Plan (check groups to load, edit key mappings):"
            if isNpz else
            "Load Plan (check image/seg items to load):"
        )
        self.ui.loadPlanTree.setColumnCount(2)
        if isNpz:
            self.ui.loadPlanTree.setHeaderLabels(["Property", "Value"])
        else:
            self.ui.loadPlanTree.setHeaderLabels(["Item", "Suffix"])

    def _setDataItems(self, items: list[ReviewDataItem]):
        self._currentDataItems = items
        self._currentDataItem = None
        self.ui.fileList.clear()
        for item in items:
            self.ui.fileList.addItem(item.data_id)

    def _clearPlanUi(self):
        self._currentKeys = []
        self._loadPlanGroups = []
        self.ui.keyInfoTable.clearContents()
        self.ui.keyInfoTable.setRowCount(0)
        self.ui.loadPlanTree.clear()

    def _refreshDataListFromSource(self):
        if self._isNpzSourceMode():
            self.onDirectoryChanged(self.ui.directorySelector.currentPath)
        else:
            self.onScanPairedDirectories()

    def onSourceTypeChanged(self, _index: int):
        self._saveReviewSourceSettings()
        self._updateSourceUi()
        self._clearPlanUi()
        self.ui.statusLabel.text = "No data selected."
        self._refreshDataListFromSource()

    def onDirectoryChanged(self, dirPath):
        if not self._isNpzSourceMode():
            return
        self._saveReviewSourceSettings()
        self._clearPlanUi()
        if not dirPath or not os.path.isdir(dirPath):
            self._setDataItems([])
            self.ui.statusLabel.text = "Select a valid NPZ root directory."
            return
        items = self.logic.scanNpzDirectory(dirPath)
        self._setDataItems(items)
        self.ui.statusLabel.text = f"Found {len(items)} NPZ/NPY items."

    def onPairedPathChanged(self, _path: str):
        self._saveReviewSourceSettings()

    def onOnlyWithSegToggled(self, _checked: bool):
        self._saveReviewSourceSettings()
        if not self._isNpzSourceMode():
            self.onScanPairedDirectories()

    def onScanPairedDirectories(self):
        if self._isNpzSourceMode():
            return
        self._saveReviewSourceSettings()
        self._clearPlanUi()
        imgDir = self.ui.imgDirectorySelector.currentPath
        segDir = self.ui.segDirectorySelector.currentPath
        validImgDir = bool(imgDir and os.path.isdir(imgDir))
        validSegDir = bool(segDir and os.path.isdir(segDir))
        if not validImgDir and not validSegDir:
            self._setDataItems([])
            self.ui.statusLabel.text = "Select at least one valid IMG or SEG directory."
            return
        onlyWithSeg = bool(self.ui.onlyWithSegCheckBox.checked)
        items, totalItems, withSegCount, unmatchedSegCount = self.logic.scanPairedDirectory(
            imgDir if validImgDir else None,
            segDir if validSegDir else None,
            onlyWithSeg=onlyWithSeg,
        )
        self._setDataItems(items)
        self.ui.statusLabel.text = (
            f"Scanned paired directories: total={totalItems}, with_seg={withSegCount}, "
            f"listed={len(items)}, unmatched_seg_files={unmatchedSegCount}"
        )

    def onFileSelected(self, row):
        if row < 0:
            return
        if row >= len(self._currentDataItems):
            return
        item = self._currentDataItems[row]
        self._currentDataItem = item
        self.ui.statusLabel.text = f"Selected: {item.data_id}"
        if item.source_type == "npz" and item.npz_path:
            self._analyzeAndBuildPlan(item.npz_path)
        else:
            self._clearPlanUi()
            self._populatePairedLoadPlanTree(item)
            self.ui.statusLabel.text = (
                f"Selected: {item.data_id} (paired image, seg count={len(item.seg_paths)})"
            )

    def _extractSegSuffix(self, dataId: str, segPath: str) -> str:
        base = os.path.basename(segPath)
        if not base.lower().endswith("-seg.nii.gz"):
            return ""
        stem = base[:-len("-seg.nii.gz")]
        if stem.startswith(dataId):
            return stem[len(dataId):]
        return ""

    def _populatePairedLoadPlanTree(self, item: ReviewDataItem):
        tree = self.ui.loadPlanTree
        tree.clear()
        tree.setColumnCount(2)
        tree.setHeaderLabels(["Item", "Suffix"])
        self.ui.loadPlanTree.visible = True

        imgItem = qt.QTreeWidgetItem(tree)
        imgItem.setText(0, "image")
        imgItem.setText(1, os.path.basename(item.img_path) if item.img_path else "(none)")
        imgItem.setData(0, qt.Qt.UserRole, "image")
        imgItem.setFlags(imgItem.flags() | qt.Qt.ItemIsUserCheckable)
        imgItem.setCheckState(0, qt.Qt.Checked if item.img_path else qt.Qt.Unchecked)

        for segPath in item.seg_paths:
            suffix = self._extractSegSuffix(item.data_id, segPath)
            isEnabled = self._pairedSegSuffixSelection.get(suffix, True)
            segItem = qt.QTreeWidgetItem(tree)
            segItem.setText(0, f"seg: {os.path.basename(segPath)}")
            segItem.setText(1, suffix if suffix else "(empty)")
            segItem.setData(0, qt.Qt.UserRole, "seg")
            segItem.setData(1, qt.Qt.UserRole, segPath)
            segItem.setData(1, qt.Qt.UserRole + 1, suffix)
            segItem.setFlags(segItem.flags() | qt.Qt.ItemIsUserCheckable)
            segItem.setCheckState(0, qt.Qt.Checked if isEnabled else qt.Qt.Unchecked)
        tree.resizeColumnToContents(0)

    def _readPairedLoadPlanSelection(self) -> tuple[bool, list[str]]:
        tree = self.ui.loadPlanTree
        loadImage = True
        selectedSegPaths: list[str] = []
        for i in range(tree.topLevelItemCount):
            item = tree.topLevelItem(i)
            role = item.data(0, qt.Qt.UserRole)
            checked = (item.checkState(0) == qt.Qt.Checked)
            if role == "image":
                loadImage = checked
            elif role == "seg":
                segPath = item.data(1, qt.Qt.UserRole)
                suffix = item.data(1, qt.Qt.UserRole + 1) or ""
                self._pairedSegSuffixSelection[str(suffix)] = checked
                if checked and segPath:
                    selectedSegPaths.append(str(segPath))
        self._saveReviewSourceSettings()
        return loadImage, selectedSegPaths

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
        dialog.setModal(True)
        dialog.setMinimumWidth(360)

        mainLayout = qt.QVBoxLayout()
        nameEdit = qt.QLineEdit()
        typeCombo = qt.QComboBox()
        typeCombo.addItems(["volume", "seg_labelmap", "seg_sparse"])
        formLayout = qt.QFormLayout()
        formLayout.addRow("Name:", nameEdit)
        formLayout.addRow("Type:", typeCombo)
        mainLayout.addLayout(formLayout)

        # QDialogButtonBox is unreliable in some PythonQt builds (empty / invisible buttons).
        btnRow = qt.QHBoxLayout()
        btnRow.addStretch(1)
        okBtn = qt.QPushButton("OK")
        cancelBtn = qt.QPushButton("Cancel")
        okBtn.setDefault(True)
        okBtn.setAutoDefault(True)
        btnRow.addWidget(okBtn)
        btnRow.addWidget(cancelBtn)
        mainLayout.addLayout(btnRow)
        dialog.setLayout(mainLayout)

        okBtn.connect("clicked()", dialog.accept)
        cancelBtn.connect("clicked()", dialog.reject)

        if dialog.exec_() != qt.QDialog.Accepted:
            return
        name = str(nameEdit.text).strip()
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
        if not self._currentDataItem:
            slicer.util.warningDisplay("No data selected.")
            return
        if self._currentDataItem.source_type == "npz":
            self._loadCurrentNpzItem()
        else:
            self._loadCurrentPairedItem()

    def _loadCurrentNpzItem(self):
        if not self._currentDataItem or not self._currentDataItem.npz_path:
            slicer.util.warningDisplay("No NPZ/NPY item selected.")
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

        baseName = self._currentDataItem.data_id

        try:
            npzData = self.logic.loadFile(self._currentDataItem.npz_path)
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
        if self._sliceViewingTool:
            self._sliceViewingTool.onDataLoaded()

    def _loadCurrentPairedItem(self):
        if not self._currentDataItem:
            slicer.util.warningDisplay("No paired data item selected.")
            return

        self._clearNodes()
        self._segSingleModeIndex = 0
        self._segAllModeIndex = 0

        item = self._currentDataItem
        warnings: list[str] = []
        loadedCount = 0
        loadImage, selectedSegPaths = self._readPairedLoadPlanSelection()

        if not loadImage and not selectedSegPaths:
            slicer.util.warningDisplay("No paired items are enabled in load plan.")
            return

        if loadImage and item.img_path:
            try:
                volumeNodeId = self.logic.loadPairedImage(item.img_path, item.data_id)
                self._loadedNodeIds.append(volumeNodeId)
                self._loadedVolumeNodeIds.append(volumeNodeId)
                loadedCount += 1
            except Exception as e:
                slicer.util.errorDisplay(f"Failed to load paired image for '{item.data_id}':\n{e}")
                return

        segNodeIds, segWarnings = self.logic.loadPairedSegmentations(selectedSegPaths, item.data_id)
        self._loadedNodeIds.extend(segNodeIds)
        self._loadedSegmentationNodeIds.extend(segNodeIds)
        loadedCount += len(segNodeIds)
        warnings.extend(segWarnings)

        if warnings:
            slicer.util.warningDisplay("\n".join(warnings))
        self.ui.statusLabel.text = (
            f"Loaded paired item: {item.data_id} ({loadedCount} nodes, seg={len(segNodeIds)})"
        )
        if self._sliceViewingTool:
            self._sliceViewingTool.onDataLoaded()

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
        # Controls how float dense labelmaps are converted into vtkMRMLLabelMapVolumeNode.
        # Some pipelines export seg as int-like values in float arrays; others export 0-1 probability masks.
        self.floatSegAutoThreshold: bool = True
        self.floatSegThreshold: float = 0.5
        self.floatSegNearIntTolerance: float = 1e-2
        self.floatSegNearIntFraction: float = 0.95
        self.floatSegIn01Fraction: float = 0.9
        self._supportedImageExtensions = (".nii", ".nii.gz", ".nrrd", ".mhd")

    # ---- Key analysis ------------------------------------------------------

    _VOLUME_PATTERN = re.compile(r"^(img|vol|volume|image)$", re.IGNORECASE)
    # Accept both prefix/suffix forms:
    # - origin* or *origin
    # - spacing* or *spacing
    _SPACING_PATTERN = re.compile(r"(^spacing|spacing$)", re.IGNORECASE)
    _ORIGIN_PATTERN = re.compile(r"(^origin|origin$)", re.IGNORECASE)
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
        # Dense seg: name matches seg; allow non-integer dtypes (e.g. float masks) — load casts to int16.
        if self._SEG_PATTERN.search(name) and len(shape) == 3:
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

    # ---- Data source scanning ----------------------------------------------

    @staticmethod
    def _stripKnownImageSuffix(name: str) -> str:
        lower = name.lower()
        if lower.endswith(".nii.gz"):
            return name[:-7]
        for suffix in (".nii", ".nrrd", ".mhd", ".npz", ".npy"):
            if lower.endswith(suffix):
                return name[: -len(suffix)]
        return name

    def scanNpzDirectory(self, dirPath: str) -> list[ReviewDataItem]:
        items: list[ReviewDataItem] = []
        for fname in sorted(os.listdir(dirPath)):
            if not fname.lower().endswith((".npz", ".npy")):
                continue
            dataId = self._stripKnownImageSuffix(fname)
            items.append(ReviewDataItem(
                data_id=dataId,
                source_type="npz",
                npz_path=os.path.join(dirPath, fname),
            ))
        return items

    def scanPairedDirectory(
        self, imgDir: Optional[str], segDir: Optional[str], onlyWithSeg: bool = False
    ) -> tuple[list[ReviewDataItem], int, int, int]:
        itemsById: dict[str, ReviewDataItem] = {}

        if imgDir and os.path.isdir(imgDir):
            for entry in sorted(os.listdir(imgDir)):
                entryPath = os.path.join(imgDir, entry)
                if os.path.isdir(entryPath):
                    itemsById[entry] = ReviewDataItem(
                        data_id=entry,
                        source_type="paired",
                        img_path=entryPath,
                    )
                    continue
                lower = entry.lower()
                if lower.endswith(self._supportedImageExtensions):
                    dataId = self._stripKnownImageSuffix(entry)
                    itemsById[dataId] = ReviewDataItem(
                        data_id=dataId,
                        source_type="paired",
                        img_path=entryPath,
                    )

        segEntries: list[tuple[str, str, str]] = []
        if segDir and os.path.isdir(segDir):
            for f in sorted(os.listdir(segDir)):
                fullPath = os.path.join(segDir, f)
                if not os.path.isfile(fullPath) or not f.lower().endswith("-seg.nii.gz"):
                    continue
                segStem = f[:-len("-seg.nii.gz")]
                segEntries.append((f, fullPath, segStem))

        matchedSegFiles: set[str] = set()
        if itemsById:
            for dataId, item in itemsById.items():
                segPaths: list[str] = []
                for segName, segPath, _segStem in segEntries:
                    if segName.startswith(dataId):
                        matchedSegFiles.add(segName)
                        segPaths.append(segPath)
                item.seg_paths = segPaths
        else:
            # SEG-only mode: build data items from seg stems.
            for segName, segPath, segStem in segEntries:
                dataId = segStem
                item = itemsById.get(dataId)
                if item is None:
                    item = ReviewDataItem(
                        data_id=dataId,
                        source_type="paired",
                        img_path=None,
                        seg_paths=[],
                    )
                    itemsById[dataId] = item
                item.seg_paths.append(segPath)
                matchedSegFiles.add(segName)

        allItems = [itemsById[k] for k in sorted(itemsById.keys())]
        withSegCount = sum(1 for item in allItems if item.seg_paths)
        listedItems = [item for item in allItems if (item.seg_paths or not onlyWithSeg)]

        unmatchedSegCount = len(segEntries) - len(matchedSegFiles)
        return listedItems, len(allItems), withSegCount, unmatchedSegCount

    # ---- File loading ------------------------------------------------------

    @staticmethod
    def loadFile(filePath: str):
        """Load an NPZ or NPY file and return a dict-like object."""
        ext = os.path.splitext(filePath)[1].lower()
        if ext == ".npy":
            arr = np.load(filePath, allow_pickle=False)
            return _NpyWrapper(arr)
        return np.load(filePath, allow_pickle=False)

    def loadPairedImage(self, imgPath: str, baseName: str) -> str:
        if os.path.isdir(imgPath):
            return self._loadDicomSeriesFromDirectory(imgPath, baseName)
        success, volumeNode = slicer.util.loadVolume(imgPath, returnNode=True)
        if not success or volumeNode is None:
            raise ValueError(f"Failed to load image file: {imgPath}")
        volumeNode.SetName(baseName)
        slicer.util.setSliceViewerLayers(background=volumeNode, fit=True)
        return volumeNode.GetID()

    @staticmethod
    def _loadDicomSeriesFromDirectory(dicomDir: str, baseName: str) -> str:
        try:
            from DICOMLib import DICOMUtils
        except Exception as e:
            raise RuntimeError(f"DICOM support is unavailable: {e}") from e

        beforeIds = {n.GetID() for n in slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")}
        with DICOMUtils.TemporaryDICOMDatabase(tempfile.mkdtemp(prefix="npzloader_dicomdb_")) as db:
            DICOMUtils.importDicom(dicomDir, db)
            patientUIDs = db.patients()
            if not patientUIDs:
                raise ValueError(f"No DICOM patient found under directory: {dicomDir}")
            for patientUid in patientUIDs:
                DICOMUtils.loadPatientByUID(patientUid)

        newNodes = [
            node for node in slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
            if node.GetID() not in beforeIds
        ]
        if not newNodes:
            raise RuntimeError("No scalar volume node was loaded from DICOM directory.")
        volumeNode = newNodes[-1]
        volumeNode.SetName(baseName)
        slicer.util.setSliceViewerLayers(background=volumeNode, fit=True)
        return volumeNode.GetID()

    @staticmethod
    def loadPairedSegmentations(segPaths: list[str], baseName: str) -> tuple[list[str], list[str]]:
        segNodeIds: list[str] = []
        warnings: list[str] = []
        for segPath in segPaths:
            segStem = NpzLoaderLogic._stripKnownImageSuffix(os.path.basename(segPath))
            nodeName = f"{baseName}_{segStem}"
            try:
                success, segNode = slicer.util.loadSegmentation(segPath, returnNode=True)
                if not success or segNode is None:
                    warnings.append(f"Failed to load segmentation: {segPath}")
                    continue
                segNode.SetName(nodeName)
                segNode.CreateClosedSurfaceRepresentation()
                segNode.CreateDefaultDisplayNodes()
                segDisplayNode = segNode.GetDisplayNode()
                if segDisplayNode:
                    segDisplayNode.SetPreferredDisplayRepresentationName3D("Closed surface")
                    segDisplayNode.SetVisibility(True)
                    segDisplayNode.SetVisibility3D(True)
                segNodeIds.append(segNode.GetID())
            except Exception as e:
                warnings.append(f"Failed to load segmentation '{segPath}': {e}")
        return segNodeIds, warnings

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

    def _convertFloatSegToLabelmap(self, segData: np.ndarray, threshold: float) -> tuple[np.ndarray, str]:
        """
        Convert float seg data into int16 labelmap.

        Returns:
          (labelmap_int16, mode)
          - 'multilabel_from_near_integers'
          - 'binary_threshold'
          - 'fallback_round'
        """
        segFloat = np.asarray(segData)
        if segFloat.size == 0:
            return np.zeros(segFloat.shape, dtype=np.int16), "empty"

        flat = segFloat.ravel()
        finiteMask = np.isfinite(flat)
        flat = flat[finiteMask]
        if flat.size == 0:
            return np.zeros(segFloat.shape, dtype=np.int16), "non_finite_only"
        # Robustly detect whether there are values beyond the binary range at all.
        # (Using full-array max avoids missing rare >1 voxels due to sampling.)
        flatMax = float(np.max(flat))

        # Sample for fast statistics on large volumes.
        maxSamples = 200000
        if flat.size > maxSamples:
            idx = np.linspace(0, flat.size - 1, num=maxSamples, dtype=np.int64)
            sample = flat[idx]
        else:
            sample = flat

        # How close are values to nearest integers?
        rounded = np.rint(sample)
        nearInt = np.abs(sample - rounded) <= self.floatSegNearIntTolerance
        nearIntFraction = float(np.mean(nearInt))

        # How often are values within [0, 1] (with tolerance)?
        in01 = (sample >= -self.floatSegNearIntTolerance) & (sample <= 1.0 + self.floatSegNearIntTolerance)
        in01Fraction = float(np.mean(in01))

        # Multi-label conversion is only safe when the float seg actually contains
        # label values > 1 (otherwise it is often a 0/1 mask exported as float).
        if nearIntFraction >= self.floatSegNearIntFraction and flatMax >= (2.0 - self.floatSegNearIntTolerance):
            # Treat as multi-label (0,1,2,...) even if stored as float.
            return np.rint(segFloat).astype(np.int16), "multilabel_from_near_integers"

        if in01Fraction >= self.floatSegIn01Fraction:
            thr = float(threshold)
            thr = max(0.0, min(1.0, thr))
            return (segFloat >= thr).astype(np.int16), "binary_threshold"

        # Fallback: round to nearest integer labels.
        return np.rint(segFloat).astype(np.int16), "fallback_round"

    # ---- Seg-labelmap loading ----------------------------------------------

    def loadSegLabelmap(self, npzData, group: LoadPlanGroup, baseName: str,
                        volumeShape=None, volumeSpacing=None, volumeOrigin=None):
        dataKey = group.mappings.get("data")
        if not dataKey:
            raise ValueError("No data key specified for seg_labelmap group.")

        segDataRaw = np.array(npzData[dataKey])
        if segDataRaw.ndim != 3:
            raise ValueError(f"Seg labelmap '{dataKey}' must be 3-D, got shape {segDataRaw.shape}")

        # Determine whether seg has its own spacing/origin
        hasOwnGeometry = (volumeShape is None or segDataRaw.shape != volumeShape)
        if hasOwnGeometry:
            spacing_xyz, origin_xyz = self._resolveSpacingOrigin(npzData, group.mappings)
        else:
            spacing_xyz, origin_xyz = self._resolveSpacingOrigin(
                npzData, group.mappings, volumeSpacing, volumeOrigin
            )

        if np.issubdtype(segDataRaw.dtype, np.floating) and self.floatSegAutoThreshold:
            segData, mode = self._convertFloatSegToLabelmap(segDataRaw, threshold=self.floatSegThreshold)
            if mode == "binary_threshold":
                slicer.util.warningDisplay(
                    f"Float seg '{dataKey}' detected. Converted to binary labelmap using threshold={self.floatSegThreshold:g}."
                )
            elif mode == "fallback_round":
                slicer.util.warningDisplay(
                    f"Float seg '{dataKey}' detected, but not clearly 0-1 mask or integer-like. Converted by rounding to int16 labels."
                )
            else:
                slicer.util.infoDisplay(
                    f"Float seg '{dataKey}' detected. Treated as integer-like dense labelmap (rounded to int16)."
                )
        else:
            segData = self._coerceDtype(segDataRaw.astype(np.int16))

        labelmapName = f"{baseName}_{group.name}_labelmap"
        labelmapNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", labelmapName)
        self._applyGeometry(labelmapNode, spacing_xyz, origin_xyz, segData.shape)
        slicer.util.updateVolumeFromArray(labelmapNode, segData)

        segNodeName = f"{baseName}_{group.name}"
        segNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", segNodeName)
        slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelmapNode, segNode)
        segNode.CreateClosedSurfaceRepresentation()
        segNode.CreateDefaultDisplayNodes()
        segDisplayNode = segNode.GetDisplayNode()
        if segDisplayNode:
            segDisplayNode.SetPreferredDisplayRepresentationName3D("Closed surface")
            segDisplayNode.SetVisibility(True)
            segDisplayNode.SetVisibility3D(True)

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
        segNode.CreateDefaultDisplayNodes()
        segDisplayNode = segNode.GetDisplayNode()
        if segDisplayNode:
            segDisplayNode.SetPreferredDisplayRepresentationName3D("Closed surface")
            segDisplayNode.SetVisibility(True)
            segDisplayNode.SetVisibility3D(True)

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
        self.test_ScanPairedDirectory()
        self.test_LoadVolume()
        self.test_FloatSegConversion()

    def test_AnalyzeKeys(self):
        self.delayDisplay("Testing key analysis")
        import tempfile

        vol = np.random.rand(10, 20, 30).astype(np.float32)
        seg = np.zeros((10, 20, 30), dtype=np.int16)
        seg[2:5, 3:8, 4:10] = 1
        seg_float = np.zeros((10, 20, 30), dtype=np.float32)
        spacing = np.array([0.5, 0.5, 0.5])
        origin = np.array([10.0, 20.0, 30.0])

        tmpFile = os.path.join(tempfile.gettempdir(), "test_npz_loader.npz")
        np.savez(tmpFile, img=vol, seg_organ=seg, seg=seg_float, spacing=spacing, origin=origin)

        logic = NpzLoaderLogic()
        keys = logic.analyzeNpzKeys(tmpFile)
        roles = {k.name: k.role for k in keys}
        assert roles["img"] == "volume", f"Expected volume, got {roles['img']}"
        assert roles["seg_organ"] == "seg_labelmap", f"Expected seg_labelmap, got {roles['seg_organ']}"
        assert roles["seg"] == "seg_labelmap", f"Expected seg_labelmap for float seg key, got {roles['seg']}"
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

    def test_ScanPairedDirectory(self):
        self.delayDisplay("Testing paired directory scan")
        import shutil
        import tempfile

        rootDir = tempfile.mkdtemp(prefix="npz_loader_paired_")
        imgDir = os.path.join(rootDir, "img")
        segDir = os.path.join(rootDir, "seg")
        os.makedirs(imgDir)
        os.makedirs(segDir)

        try:
            # IMG entries: one volume file + one dicom folder
            open(os.path.join(imgDir, "case_a.nii.gz"), "a", encoding="utf-8").close()
            os.makedirs(os.path.join(imgDir, "case_b"))
            open(os.path.join(imgDir, "notes.txt"), "a", encoding="utf-8").close()

            # SEG entries (root-level only)
            open(os.path.join(segDir, "case_a-lesion-seg.nii.gz"), "a", encoding="utf-8").close()
            open(os.path.join(segDir, "case_b-main-seg.nii.gz"), "a", encoding="utf-8").close()
            open(os.path.join(segDir, "case_b-alt-seg.nii.gz"), "a", encoding="utf-8").close()
            open(os.path.join(segDir, "orphan-seg.nii.gz"), "a", encoding="utf-8").close()
            os.makedirs(os.path.join(segDir, "nested"))
            open(os.path.join(segDir, "nested", "case_a-nested-seg.nii.gz"), "a", encoding="utf-8").close()

            logic = NpzLoaderLogic()
            items, totalCount, withSegCount, unmatchedSeg = logic.scanPairedDirectory(
                imgDir, segDir, onlyWithSeg=False
            )
            assert totalCount == 2, f"Expected 2 data items, got {totalCount}"
            assert len(items) == 2
            assert withSegCount == 2
            assert unmatchedSeg == 1

            byId = {item.data_id: item for item in items}
            assert "case_a" in byId
            assert "case_b" in byId
            assert len(byId["case_a"].seg_paths) == 1
            assert len(byId["case_b"].seg_paths) == 2

            filteredItems, _, _, _ = logic.scanPairedDirectory(imgDir, segDir, onlyWithSeg=True)
            assert len(filteredItems) == 2

            # IMG-only scan still returns image items.
            imgOnlyItems, imgOnlyTotal, imgOnlyWithSeg, imgOnlyUnmatched = logic.scanPairedDirectory(
                imgDir, None, onlyWithSeg=False
            )
            assert imgOnlyTotal == 2
            assert len(imgOnlyItems) == 2
            assert imgOnlyWithSeg == 0
            assert imgOnlyUnmatched == 0

            # SEG-only scan builds items directly from seg stems.
            segOnlyItems, segOnlyTotal, segOnlyWithSeg, segOnlyUnmatched = logic.scanPairedDirectory(
                None, segDir, onlyWithSeg=False
            )
            assert segOnlyTotal == 4, f"Expected 4 seg-only items, got {segOnlyTotal}"
            assert len(segOnlyItems) == 4
            assert segOnlyWithSeg == 4
            assert segOnlyUnmatched == 0
        finally:
            shutil.rmtree(rootDir, ignore_errors=True)
        self.delayDisplay("Paired scan test passed!")

    def test_FloatSegConversion(self):
        logic = NpzLoaderLogic()

        rng = np.random.default_rng(0)
        # Case 1: float values close to {0,1,2} -> multi-label
        segIntLike = rng.choice([0.0, 1.0, 2.0], size=(6, 7, 8)).astype(np.float32)
        segIntLike += rng.normal(0.0, 1e-3, size=segIntLike.shape).astype(np.float32)
        label1, mode1 = logic._convertFloatSegToLabelmap(segIntLike, threshold=0.5)
        assert mode1 == "multilabel_from_near_integers", f"Unexpected mode1: {mode1}"
        u1 = set(np.unique(label1).tolist())
        assert u1.issubset({0, 1, 2}), f"Unexpected labels1: {u1}"

        # Case 2: random float in [0,1] -> binary threshold
        seg01 = rng.random((6, 7, 8), dtype=np.float32)
        label2, mode2 = logic._convertFloatSegToLabelmap(seg01, threshold=0.5)
        assert mode2 == "binary_threshold", f"Unexpected mode2: {mode2}"
        u2 = set(np.unique(label2).tolist())
        assert u2.issubset({0, 1}), f"Unexpected labels2: {u2}"

        # Case 3: float values near {0,1} -> should prefer binary threshold
        seg01IntLike = rng.choice([0.0, 1.0], size=(6, 7, 8)).astype(np.float32)
        seg01IntLike += rng.normal(0.0, 1e-3, size=seg01IntLike.shape).astype(np.float32)
        label3, mode3 = logic._convertFloatSegToLabelmap(seg01IntLike, threshold=0.5)
        assert mode3 == "binary_threshold", f"Unexpected mode3: {mode3}"
        u3 = set(np.unique(label3).tolist())
        assert u3.issubset({0, 1}), f"Unexpected labels3: {u3}"
