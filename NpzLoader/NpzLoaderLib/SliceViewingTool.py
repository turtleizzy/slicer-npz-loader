import math
import os

import qt
import slicer

_GLOBAL_SLICE_VIEWING_TOOL = None
_GLOBAL_STARTUP_HOOKED = False


class SliceViewingToolController:
    """Custom slice-view interaction tool independent from NpzLoader logic."""

    def __init__(self, module_dir: str, status_callback=None):
        self.module_dir = module_dir
        self.status_callback = status_callback

        self.enabled = False
        self.draggingSlice = False
        self.draggingWl = False
        self.draggingPan = False
        self.draggingZoom = False

        self.leftDown = False
        self.rightDown = False
        self.middleDown = False

        self.activeInteractor = None
        self.activeSliceLogic = None
        self.offsetRange = None

        self.startY = 0
        self.startOffset = 0.0

        self.wlStartX = 0
        self.wlStartY = 0
        self.wlStartWindow = 0.0
        self.wlStartLevel = 0.0
        self.wlScalarRange = (0.0, 1.0)

        self.panStartX = 0
        self.panStartY = 0
        self.panStartOrigin = (0.0, 0.0, 0.0)
        self.panStartFov = (1.0, 1.0, 1.0)

        self.zoomStartY = 0
        self.zoomStartFov = (1.0, 1.0, 1.0)

        self.observerTags = []
        self.sliceWidgetsPerInteractor = {}
        self.layoutManager = None

        self.toolbarAction = None
        self.originalActionStates = {}

    def setup(self):
        self.layoutManager = slicer.app.layoutManager() if slicer.app else None
        if not self.layoutManager:
            return
        self.layoutManager.connect("layoutChanged(int)", self._onLayoutChanged)
        self._setupToolbarAction()
        self.refreshObservers()
        self._applyToSliceViews()

    def cleanup(self):
        if self.toolbarAction:
            try:
                self.toolbarAction.disconnect("toggled(bool)", self._onToolbarToggled)
            except Exception:
                pass
            parent = self.toolbarAction.parent()
            if parent and hasattr(parent, "removeAction"):
                try:
                    parent.removeAction(self.toolbarAction)
                except Exception:
                    pass
            self.toolbarAction = None

        self._removeObservers()

        if self.layoutManager:
            try:
                self.layoutManager.disconnect("layoutChanged(int)", self._onLayoutChanged)
            except Exception:
                pass
            self.layoutManager = None

    def toggle(self):
        self.setEnabled(not self.enabled)

    def setEnabled(self, enabled: bool):
        self.enabled = bool(enabled)
        if self.toolbarAction:
            self.toolbarAction.blockSignals(True)
            self.toolbarAction.setChecked(self.enabled)
            self.toolbarAction.blockSignals(False)
        self._setStatus(f"Slice viewing tool: {'ON' if self.enabled else 'OFF'}")
        self._applyToSliceViews()

    def onDataLoaded(self):
        self.refreshObservers()
        if not self.enabled:
            self.setEnabled(True)

    def _setStatus(self, text: str):
        if self.status_callback:
            self.status_callback(text)

    def _onLayoutChanged(self, _layoutId):
        self.refreshObservers()
        self._applyToSliceViews()

    def _setupToolbarAction(self):
        mw = slicer.util.mainWindow()
        if not mw or self.toolbarAction:
            return
        mouseToolbar = None
        for tb in mw.findChildren("QToolBar"):
            if type(tb).__name__ == "qSlicerMouseModeToolBar":
                mouseToolbar = tb
                break
        if not mouseToolbar:
            return

        action = qt.QAction("Slice Viewing Tool", mouseToolbar)
        action.setCheckable(True)
        action.setChecked(self.enabled)
        action.setToolTip(
            "Left: slice, Right: WC/WL, Middle: zoom, Left+Right: pan, Wheel: slice."
        )
        iconPath = os.path.join(self.module_dir, "Resources", "Icons", "SliceViewingTool.svg")
        if os.path.exists(iconPath):
            action.setIcon(qt.QIcon(iconPath))

        for a in mouseToolbar.actions():
            if a.isCheckable() and a.actionGroup():
                a.actionGroup().addAction(action)
                break
        action.connect("toggled(bool)", self._onToolbarToggled)
        mouseToolbar.addAction(action)
        self.toolbarAction = action

    def _onToolbarToggled(self, checked: bool):
        self.enabled = bool(checked)
        self._setStatus(f"Slice viewing tool: {'ON' if self.enabled else 'OFF'}")
        self._applyToSliceViews()

    def _applyToSliceViews(self):
        lm = slicer.app.layoutManager() if slicer.app else None
        if not lm:
            return
        count = slicer.mrmlScene.GetNumberOfNodesByClass("vtkMRMLSliceNode")
        for i in range(count):
            sliceNode = slicer.mrmlScene.GetNthNodeByClass(i, "vtkMRMLSliceNode")
            if not sliceNode:
                continue
            sliceWidget = lm.sliceWidget(sliceNode.GetLayoutName())
            if not sliceWidget:
                continue
            try:
                style = sliceWidget.sliceView().sliceViewInteractorStyle()
            except Exception:
                continue
            if not style:
                continue
            mask = int(getattr(style, "AllActionsMask", 0))
            if mask <= 0:
                continue
            if self.enabled:
                styleId = id(style)
                if styleId not in self.originalActionStates:
                    bits = [1 << b for b in range(32) if (mask & (1 << b))]
                    states = [bool(style.GetActionEnabled(bit)) for bit in bits]
                    self.originalActionStates[styleId] = (bits, states)
                bits, _states = self.originalActionStates[id(style)]
                for bit in bits:
                    style.SetActionEnabled(bit, False)
            else:
                style.SetActionEnabled(mask, True)
        if not self.enabled:
            self.originalActionStates.clear()

    def _removeObservers(self):
        for observee, tag in self.observerTags:
            try:
                observee.RemoveObserver(tag)
            except Exception:
                pass
        self.observerTags.clear()
        self.sliceWidgetsPerInteractor.clear()
        self.draggingSlice = False
        self.draggingWl = False
        self.draggingPan = False
        self.draggingZoom = False
        self.leftDown = False
        self.rightDown = False
        self.middleDown = False

    def refreshObservers(self):
        self._removeObservers()
        lm = slicer.app.layoutManager() if slicer.app else None
        if not lm:
            return
        count = slicer.mrmlScene.GetNumberOfNodesByClass("vtkMRMLSliceNode")
        for i in range(count):
            sliceNode = slicer.mrmlScene.GetNthNodeByClass(i, "vtkMRMLSliceNode")
            if not sliceNode:
                continue
            sliceWidget = lm.sliceWidget(sliceNode.GetLayoutName())
            if not sliceWidget:
                continue
            interactor = sliceWidget.sliceView().interactor()
            if not interactor:
                continue
            self.sliceWidgetsPerInteractor[interactor] = sliceWidget
            for event in (
                "LeftButtonPressEvent",
                "LeftButtonReleaseEvent",
                "RightButtonPressEvent",
                "RightButtonReleaseEvent",
                "MiddleButtonPressEvent",
                "MiddleButtonReleaseEvent",
                "MouseWheelForwardEvent",
                "MouseWheelBackwardEvent",
                "MouseMoveEvent",
            ):
                tag = interactor.AddObserver(event, self._processEvent, 1.0)
                self.observerTags.append((interactor, tag))

    @staticmethod
    def _backgroundDisplayNode(sliceLogic):
        try:
            layer = sliceLogic.GetBackgroundLayer()
            volume = layer.GetVolumeNode() if layer else None
            if not volume:
                return None
            disp = volume.GetDisplayNode()
            if not disp:
                volume.CreateDefaultDisplayNodes()
                disp = volume.GetDisplayNode()
            return disp
        except Exception:
            return None

    @staticmethod
    def _backgroundScalarRange(sliceLogic):
        try:
            layer = sliceLogic.GetBackgroundLayer()
            volume = layer.GetVolumeNode() if layer else None
            imageData = volume.GetImageData() if volume else None
            scalarRange = imageData.GetScalarRange() if imageData else None
            if not scalarRange or scalarRange[1] <= scalarRange[0]:
                return (0.0, 1.0)
            return (float(scalarRange[0]), float(scalarRange[1]))
        except Exception:
            return (0.0, 1.0)

    @staticmethod
    def _offsetRange(sliceLogic):
        try:
            bounds = [0.0] * 6
            if hasattr(sliceLogic, "GetSliceBounds"):
                sliceLogic.GetSliceBounds(bounds)
            elif hasattr(sliceLogic, "GetBackgroundSliceBounds"):
                sliceLogic.GetBackgroundSliceBounds(bounds)
            else:
                return None
            return (min(float(bounds[4]), float(bounds[5])), max(float(bounds[4]), float(bounds[5])))
        except Exception:
            return None

    @staticmethod
    def _setSliceNodeOriginLinked(sliceLogic, sliceNode, x: float, y: float, z: float) -> None:
        """Pan: bracket origin updates so slice link broadcasts (SliceLinkLogic: flag 32 + SetSliceOrigin)."""
        try:
            sliceLogic.StartSliceNodeInteraction(32)  # XYZOriginFlag
            sliceNode.SetSliceOrigin(x, y, z)
            sliceLogic.EndSliceNodeInteraction()
        except Exception:
            try:
                sliceNode.SetSliceOrigin(x, y, z)
            except Exception:
                sliceNode.SetXYZOrigin(x, y, z)

    @staticmethod
    def _setSliceNodeFieldOfViewLinked(sliceLogic, sliceNode, fovX: float, fovY: float, fovZ: float) -> None:
        """Zoom: bracket FOV updates (SliceLinkLogic uses flag 2)."""
        try:
            sliceLogic.StartSliceNodeInteraction(2)  # FieldOfViewFlag
            sliceNode.SetFieldOfView(fovX, fovY, fovZ)
            sliceLogic.EndSliceNodeInteraction()
        except Exception:
            sliceNode.SetFieldOfView(fovX, fovY, fovZ)

    def _processEvent(self, interactor, event):
        if not self.enabled:
            return False
        sliceWidget = self.sliceWidgetsPerInteractor.get(interactor)
        if not sliceWidget:
            return False
        sliceLogic = sliceWidget.sliceLogic()
        if not sliceLogic:
            return False

        if event == "LeftButtonPressEvent":
            self.leftDown = True
            if self.rightDown:
                self.draggingSlice = False
                self.draggingWl = False
                self.draggingZoom = False
                self.draggingPan = True
                self.activeInteractor = interactor
                self.activeSliceLogic = sliceLogic
                pos = interactor.GetEventPosition()
                self.panStartX, self.panStartY = pos[0], pos[1]
                sliceNode = sliceLogic.GetSliceNode()
                origin = sliceNode.GetXYZOrigin()
                fov = sliceNode.GetFieldOfView()
                self.panStartOrigin = (float(origin[0]), float(origin[1]), float(origin[2]))
                self.panStartFov = (float(fov[0]), float(fov[1]), float(fov[2]))
                return True
            self.draggingSlice = True
            self.activeInteractor = interactor
            self.activeSliceLogic = sliceLogic
            self.startY = interactor.GetEventPosition()[1]
            self.startOffset = float(sliceLogic.GetSliceOffset())
            self.offsetRange = self._offsetRange(sliceLogic)
            sliceLogic.StartSliceOffsetInteraction()
            return True

        if event == "LeftButtonReleaseEvent":
            self.leftDown = False
            if self.draggingSlice and self.activeSliceLogic:
                self.activeSliceLogic.EndSliceOffsetInteraction()
            self.draggingSlice = False
            self.draggingZoom = False
            self.draggingPan = False
            self.draggingWl = False
            self.activeInteractor = None
            self.activeSliceLogic = None
            return True

        if event == "RightButtonPressEvent":
            self.rightDown = True
            if self.leftDown:
                if self.draggingSlice and self.activeSliceLogic:
                    self.activeSliceLogic.EndSliceOffsetInteraction()
                self.draggingSlice = False
                self.draggingWl = False
                self.draggingZoom = False
                self.draggingPan = True
                self.activeInteractor = interactor
                self.activeSliceLogic = sliceLogic
                pos = interactor.GetEventPosition()
                self.panStartX, self.panStartY = pos[0], pos[1]
                sliceNode = sliceLogic.GetSliceNode()
                origin = sliceNode.GetXYZOrigin()
                fov = sliceNode.GetFieldOfView()
                self.panStartOrigin = (float(origin[0]), float(origin[1]), float(origin[2]))
                self.panStartFov = (float(fov[0]), float(fov[1]), float(fov[2]))
            else:
                disp = self._backgroundDisplayNode(sliceLogic)
                if disp:
                    self.draggingZoom = False
                    self.draggingPan = False
                    self.draggingWl = True
                    self.activeInteractor = interactor
                    self.activeSliceLogic = sliceLogic
                    pos = interactor.GetEventPosition()
                    self.wlStartX, self.wlStartY = pos[0], pos[1]
                    self.wlStartWindow = float(disp.GetWindow())
                    self.wlStartLevel = float(disp.GetLevel())
                    self.wlScalarRange = self._backgroundScalarRange(sliceLogic)
            return True

        if event == "RightButtonReleaseEvent":
            self.rightDown = False
            self.draggingZoom = False
            self.draggingPan = False
            self.draggingWl = False
            if self.draggingSlice and self.activeSliceLogic:
                self.activeSliceLogic.EndSliceOffsetInteraction()
            self.draggingSlice = False
            self.activeInteractor = None
            self.activeSliceLogic = None
            return True

        if event == "MiddleButtonPressEvent":
            self.middleDown = True
            if self.draggingSlice and self.activeSliceLogic:
                self.activeSliceLogic.EndSliceOffsetInteraction()
            self.draggingSlice = False
            self.draggingPan = False
            self.draggingWl = False
            self.draggingZoom = True
            self.activeInteractor = interactor
            self.activeSliceLogic = sliceLogic
            self.zoomStartY = interactor.GetEventPosition()[1]
            fov = sliceLogic.GetSliceNode().GetFieldOfView()
            self.zoomStartFov = (float(fov[0]), float(fov[1]), float(fov[2]))
            return True

        if event == "MiddleButtonReleaseEvent":
            self.middleDown = False
            self.draggingZoom = False
            self.activeInteractor = None
            self.activeSliceLogic = None
            return True

        if event in ("MouseWheelForwardEvent", "MouseWheelBackwardEvent"):
            step = 1.0
            try:
                spacing = sliceLogic.GetBackgroundSliceSpacing()
                if spacing and len(spacing) >= 3:
                    step = abs(float(spacing[2]))
                elif spacing:
                    step = abs(float(spacing[-1]))
            except Exception:
                pass
            direction = 1.0 if event == "MouseWheelForwardEvent" else -1.0
            newOffset = float(sliceLogic.GetSliceOffset()) + direction * step
            offsetRange = self._offsetRange(sliceLogic)
            if offsetRange:
                newOffset = min(max(newOffset, offsetRange[0]), offsetRange[1])
            # Must bracket offset changes with slice-offset interaction so linked views
            # (slice link / hot link) receive the same broadcast as the native interactor.
            try:
                sliceLogic.StartSliceOffsetInteraction()
                sliceLogic.SetSliceOffset(newOffset)
                sliceLogic.EndSliceOffsetInteraction()
            except Exception:
                sliceLogic.SetSliceOffset(newOffset)
            return True

        if event != "MouseMoveEvent":
            return False

        # Keep crosshair synchronized with mouse position when Shift is held,
        # matching standard slice-view cross-reference behavior.
        if (interactor.GetShiftKey()
                and not self.leftDown
                and not self.rightDown
                and not self.middleDown):
            try:
                xy = interactor.GetEventPosition()
                ras = sliceWidget.sliceView().convertXYZToRAS(
                    sliceWidget.sliceView().convertDeviceToXYZ(xy)
                )
                crosshairNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLCrosshairNode")
                if crosshairNode:
                    r, a, s = float(ras[0]), float(ras[1]), float(ras[2])
                    crosshairNode.SetCrosshairRAS(r, a, s)
                    # Crosshair alone only moves the intersection lines; updating slice
                    # planes requires JumpAllSlices (see Slicer script repository / gui.md).
                    sliceNodeClass = slicer.vtkMRMLSliceNode
                    jump_mode = getattr(
                        sliceNodeClass,
                        "DefaultJumpSlice",
                        -1,
                    )
                    sliceNodeClass.JumpAllSlices(
                        slicer.mrmlScene,
                        r,
                        a,
                        s,
                        jump_mode,
                    )
                    return True
            except Exception:
                pass

        if interactor != self.activeInteractor or not self.activeSliceLogic:
            return False

        if self.draggingZoom:
            sliceNode = self.activeSliceLogic.GetSliceNode()
            currentY = interactor.GetEventPosition()[1]
            deltaY = currentY - self.zoomStartY
            viewHeight = max(1, sliceWidget.sliceView().height)
            scale = math.exp((deltaY / float(viewHeight)) * 1.5)
            fovX, fovY, fovZ = self.zoomStartFov
            self._setSliceNodeFieldOfViewLinked(
                self.activeSliceLogic,
                sliceNode,
                max(1e-3, fovX * scale),
                max(1e-3, fovY * scale),
                fovZ,
            )
            return True

        if self.draggingWl:
            disp = self._backgroundDisplayNode(self.activeSliceLogic)
            if not disp:
                return False
            currentX, currentY = interactor.GetEventPosition()
            deltaX = currentX - self.wlStartX
            deltaY = currentY - self.wlStartY
            low, high = self.wlScalarRange
            span = max(1e-3, high - low)
            viewWidth = max(1, sliceWidget.sliceView().width)
            viewHeight = max(1, sliceWidget.sliceView().height)
            windowDelta = (deltaX / float(viewWidth)) * span
            levelDelta = (-deltaY / float(viewHeight)) * span
            disp.AutoWindowLevelOff()
            disp.SetWindow(max(1e-3, self.wlStartWindow + windowDelta))
            disp.SetLevel(self.wlStartLevel + levelDelta)
            return True

        if self.draggingPan:
            sliceNode = self.activeSliceLogic.GetSliceNode()
            currentX, currentY = interactor.GetEventPosition()
            deltaX = currentX - self.panStartX
            deltaY = currentY - self.panStartY
            viewWidth = max(1, sliceWidget.sliceView().width)
            viewHeight = max(1, sliceWidget.sliceView().height)
            fovX, fovY, _ = self.panStartFov
            mmPerPixelX = fovX / float(viewWidth)
            mmPerPixelY = fovY / float(viewHeight)
            startX, startY, startZ = self.panStartOrigin
            self._setSliceNodeOriginLinked(
                self.activeSliceLogic,
                sliceNode,
                startX - deltaX * mmPerPixelX,
                startY - deltaY * mmPerPixelY,
                startZ,
            )
            return True

        if not self.draggingSlice:
            return False
        currentY = interactor.GetEventPosition()[1]
        deltaY = currentY - self.startY
        step = 1.0
        try:
            spacing = sliceLogic.GetBackgroundSliceSpacing()
            if spacing and len(spacing) >= 3:
                step = abs(float(spacing[2]))
            elif spacing:
                step = abs(float(spacing[-1]))
        except Exception:
            pass
        newOffset = self.startOffset + deltaY * step
        if self.offsetRange:
            newOffset = min(max(newOffset, self.offsetRange[0]), self.offsetRange[1])
        self.activeSliceLogic.SetSliceOffset(newOffset)
        return True


def getGlobalSliceViewingTool():
    return _GLOBAL_SLICE_VIEWING_TOOL


def ensureGlobalSliceViewingTool(module_dir: str):
    global _GLOBAL_SLICE_VIEWING_TOOL
    global _GLOBAL_STARTUP_HOOKED

    if _GLOBAL_SLICE_VIEWING_TOOL:
        return _GLOBAL_SLICE_VIEWING_TOOL

    def _create():
        global _GLOBAL_SLICE_VIEWING_TOOL
        if _GLOBAL_SLICE_VIEWING_TOOL:
            return
        controller = SliceViewingToolController(module_dir=module_dir, status_callback=None)
        controller.setup()
        _GLOBAL_SLICE_VIEWING_TOOL = controller

    if slicer.util.mainWindow():
        _create()
    elif not _GLOBAL_STARTUP_HOOKED and slicer.app:
        _GLOBAL_STARTUP_HOOKED = True

        def _onStartupCompleted():
            _create()

        slicer.app.connect("startupCompleted()", _onStartupCompleted)

    return _GLOBAL_SLICE_VIEWING_TOOL
