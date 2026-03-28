# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'NpzLoader.ui'
##
## Created by: Qt User Interface Compiler version 6.6.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox,
    QDoubleSpinBox, QFormLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QSizePolicy, QSpacerItem, QTableWidget,
    QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget)
class Ui_NpzLoader(object):
    def setupUi(self, NpzLoader):
        if not NpzLoader.objectName():
            NpzLoader.setObjectName(u"NpzLoader")
        self.verticalLayout = QVBoxLayout(NpzLoader)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.fileSelectionCollapsible = ctkCollapsibleButton(NpzLoader)
        self.fileSelectionCollapsible.setObjectName(u"fileSelectionCollapsible")
        self.fileSelectionLayout = QVBoxLayout(self.fileSelectionCollapsible)
        self.fileSelectionLayout.setObjectName(u"fileSelectionLayout")
        self.dirFormLayout = QFormLayout()
        self.dirFormLayout.setObjectName(u"dirFormLayout")
        self.sourceTypeLabel = QLabel(self.fileSelectionCollapsible)
        self.sourceTypeLabel.setObjectName(u"sourceTypeLabel")

        self.dirFormLayout.setWidget(0, QFormLayout.LabelRole, self.sourceTypeLabel)

        self.sourceTypeComboBox = QComboBox(self.fileSelectionCollapsible)
        self.sourceTypeComboBox.addItem("")
        self.sourceTypeComboBox.addItem("")
        self.sourceTypeComboBox.setObjectName(u"sourceTypeComboBox")

        self.dirFormLayout.setWidget(0, QFormLayout.FieldRole, self.sourceTypeComboBox)

        self.directoryLabel = QLabel(self.fileSelectionCollapsible)
        self.directoryLabel.setObjectName(u"directoryLabel")

        self.dirFormLayout.setWidget(1, QFormLayout.LabelRole, self.directoryLabel)

        self.directorySelector = ctkPathLineEdit(self.fileSelectionCollapsible)
        self.directorySelector.setObjectName(u"directorySelector")

        self.dirFormLayout.setWidget(1, QFormLayout.FieldRole, self.directorySelector)

        self.imgDirectoryLabel = QLabel(self.fileSelectionCollapsible)
        self.imgDirectoryLabel.setObjectName(u"imgDirectoryLabel")

        self.dirFormLayout.setWidget(2, QFormLayout.LabelRole, self.imgDirectoryLabel)

        self.imgDirectorySelector = ctkPathLineEdit(self.fileSelectionCollapsible)
        self.imgDirectorySelector.setObjectName(u"imgDirectorySelector")

        self.dirFormLayout.setWidget(2, QFormLayout.FieldRole, self.imgDirectorySelector)

        self.segDirectoryLabel = QLabel(self.fileSelectionCollapsible)
        self.segDirectoryLabel.setObjectName(u"segDirectoryLabel")

        self.dirFormLayout.setWidget(3, QFormLayout.LabelRole, self.segDirectoryLabel)

        self.segDirectorySelector = ctkPathLineEdit(self.fileSelectionCollapsible)
        self.segDirectorySelector.setObjectName(u"segDirectorySelector")

        self.dirFormLayout.setWidget(3, QFormLayout.FieldRole, self.segDirectorySelector)

        self.enableCompareCheckBox = QCheckBox(self.fileSelectionCollapsible)
        self.enableCompareCheckBox.setObjectName(u"enableCompareCheckBox")
        self.enableCompareCheckBox.setChecked(False)

        self.dirFormLayout.setWidget(4, QFormLayout.FieldRole, self.enableCompareCheckBox)

        self.segDirectoryALabel = QLabel(self.fileSelectionCollapsible)
        self.segDirectoryALabel.setObjectName(u"segDirectoryALabel")

        self.dirFormLayout.setWidget(5, QFormLayout.LabelRole, self.segDirectoryALabel)

        self.segDirectoryASelector = ctkPathLineEdit(self.fileSelectionCollapsible)
        self.segDirectoryASelector.setObjectName(u"segDirectoryASelector")

        self.dirFormLayout.setWidget(5, QFormLayout.FieldRole, self.segDirectoryASelector)

        self.segDirectoryBLabel = QLabel(self.fileSelectionCollapsible)
        self.segDirectoryBLabel.setObjectName(u"segDirectoryBLabel")

        self.dirFormLayout.setWidget(6, QFormLayout.LabelRole, self.segDirectoryBLabel)

        self.segDirectoryBSelector = ctkPathLineEdit(self.fileSelectionCollapsible)
        self.segDirectoryBSelector.setObjectName(u"segDirectoryBSelector")

        self.dirFormLayout.setWidget(6, QFormLayout.FieldRole, self.segDirectoryBSelector)

        self.pairedControlsLayout = QHBoxLayout()
        self.pairedControlsLayout.setObjectName(u"pairedControlsLayout")
        self.onlyWithSegCheckBox = QCheckBox(self.fileSelectionCollapsible)
        self.onlyWithSegCheckBox.setObjectName(u"onlyWithSegCheckBox")
        self.onlyWithSegCheckBox.setChecked(False)

        self.pairedControlsLayout.addWidget(self.onlyWithSegCheckBox)

        self.scanButton = QPushButton(self.fileSelectionCollapsible)
        self.scanButton.setObjectName(u"scanButton")

        self.pairedControlsLayout.addWidget(self.scanButton)


        self.dirFormLayout.setLayout(7, QFormLayout.FieldRole, self.pairedControlsLayout)


        self.fileSelectionLayout.addLayout(self.dirFormLayout)

        self.fileListLabel = QLabel(self.fileSelectionCollapsible)
        self.fileListLabel.setObjectName(u"fileListLabel")

        self.fileSelectionLayout.addWidget(self.fileListLabel)

        self.fileList = QListWidget(self.fileSelectionCollapsible)
        self.fileList.setObjectName(u"fileList")
        self.fileList.setMaximumSize(QSize(16777215, 160))

        self.fileSelectionLayout.addWidget(self.fileList)


        self.verticalLayout.addWidget(self.fileSelectionCollapsible)

        self.loadPlanCollapsible = ctkCollapsibleButton(NpzLoader)
        self.loadPlanCollapsible.setObjectName(u"loadPlanCollapsible")
        self.loadPlanLayout = QVBoxLayout(self.loadPlanCollapsible)
        self.loadPlanLayout.setObjectName(u"loadPlanLayout")
        self.keyInfoLabel = QLabel(self.loadPlanCollapsible)
        self.keyInfoLabel.setObjectName(u"keyInfoLabel")

        self.loadPlanLayout.addWidget(self.keyInfoLabel)

        self.keyInfoTable = QTableWidget(self.loadPlanCollapsible)
        self.keyInfoTable.setObjectName(u"keyInfoTable")
        self.keyInfoTable.setMaximumSize(QSize(16777215, 140))
        self.keyInfoTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.keyInfoTable.setSelectionMode(QAbstractItemView.NoSelection)

        self.loadPlanLayout.addWidget(self.keyInfoTable)

        self.loadPlanLabel = QLabel(self.loadPlanCollapsible)
        self.loadPlanLabel.setObjectName(u"loadPlanLabel")

        self.loadPlanLayout.addWidget(self.loadPlanLabel)

        self.loadPlanTree = QTreeWidget(self.loadPlanCollapsible)
        self.loadPlanTree.setObjectName(u"loadPlanTree")
        self.loadPlanTree.setMinimumSize(QSize(0, 0))
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.loadPlanTree.sizePolicy().hasHeightForWidth())
        self.loadPlanTree.setSizePolicy(sizePolicy)
        self.loadPlanTree.setSelectionMode(QAbstractItemView.ExtendedSelection)

        self.loadPlanLayout.addWidget(self.loadPlanTree)

        self.groupButtonLayout = QHBoxLayout()
        self.groupButtonLayout.setObjectName(u"groupButtonLayout")
        self.addGroupButton = QPushButton(self.loadPlanCollapsible)
        self.addGroupButton.setObjectName(u"addGroupButton")

        self.groupButtonLayout.addWidget(self.addGroupButton)

        self.removeGroupButton = QPushButton(self.loadPlanCollapsible)
        self.removeGroupButton.setObjectName(u"removeGroupButton")

        self.groupButtonLayout.addWidget(self.removeGroupButton)

        self.groupButtonSpacer = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.groupButtonLayout.addItem(self.groupButtonSpacer)


        self.loadPlanLayout.addLayout(self.groupButtonLayout)


        self.verticalLayout.addWidget(self.loadPlanCollapsible)

        self.loadActionsCollapsible = ctkCollapsibleButton(NpzLoader)
        self.loadActionsCollapsible.setObjectName(u"loadActionsCollapsible")
        self.loadActionsLayout = QVBoxLayout(self.loadActionsCollapsible)
        self.loadActionsLayout.setObjectName(u"loadActionsLayout")
        self.actionButtonLayout = QHBoxLayout()
        self.actionButtonLayout.setObjectName(u"actionButtonLayout")
        self.loadButton = QPushButton(self.loadActionsCollapsible)
        self.loadButton.setObjectName(u"loadButton")

        self.actionButtonLayout.addWidget(self.loadButton)

        self.closeButton = QPushButton(self.loadActionsCollapsible)
        self.closeButton.setObjectName(u"closeButton")

        self.actionButtonLayout.addWidget(self.closeButton)


        self.loadActionsLayout.addLayout(self.actionButtonLayout)

        self.statusLabel = QLabel(self.loadActionsCollapsible)
        self.statusLabel.setObjectName(u"statusLabel")

        self.loadActionsLayout.addWidget(self.statusLabel)


        self.verticalLayout.addWidget(self.loadActionsCollapsible)

        self.settingsCollapsible = ctkCollapsibleButton(NpzLoader)
        self.settingsCollapsible.setObjectName(u"settingsCollapsible")
        self.settingsCollapsible.setCollapsed(True)
        self.settingsLayout = QVBoxLayout(self.settingsCollapsible)
        self.settingsLayout.setObjectName(u"settingsLayout")
        self.autoDetectCheckBox = QCheckBox(self.settingsCollapsible)
        self.autoDetectCheckBox.setObjectName(u"autoDetectCheckBox")
        self.autoDetectCheckBox.setChecked(True)

        self.settingsLayout.addWidget(self.autoDetectCheckBox)

        self.reuseplanCheckBox = QCheckBox(self.settingsCollapsible)
        self.reuseplanCheckBox.setObjectName(u"reuseplanCheckBox")
        self.reuseplanCheckBox.setChecked(True)

        self.settingsLayout.addWidget(self.reuseplanCheckBox)

        self.autoShowSeg3DCheckBox = QCheckBox(self.settingsCollapsible)
        self.autoShowSeg3DCheckBox.setObjectName(u"autoShowSeg3DCheckBox")
        self.autoShowSeg3DCheckBox.setChecked(True)

        self.settingsLayout.addWidget(self.autoShowSeg3DCheckBox)

        self.floatSegAutoThresholdCheckBox = QCheckBox(self.settingsCollapsible)
        self.floatSegAutoThresholdCheckBox.setObjectName(u"floatSegAutoThresholdCheckBox")
        self.floatSegAutoThresholdCheckBox.setChecked(True)

        self.settingsLayout.addWidget(self.floatSegAutoThresholdCheckBox)

        self.floatSegThresholdFormLayout = QFormLayout()
        self.floatSegThresholdFormLayout.setObjectName(u"floatSegThresholdFormLayout")
        self.floatSegThresholdLabel = QLabel(self.settingsCollapsible)
        self.floatSegThresholdLabel.setObjectName(u"floatSegThresholdLabel")

        self.floatSegThresholdFormLayout.setWidget(0, QFormLayout.LabelRole, self.floatSegThresholdLabel)

        self.floatSegThresholdDoubleSpinBox = QDoubleSpinBox(self.settingsCollapsible)
        self.floatSegThresholdDoubleSpinBox.setObjectName(u"floatSegThresholdDoubleSpinBox")
        self.floatSegThresholdDoubleSpinBox.setMinimum(0.000000000000000)
        self.floatSegThresholdDoubleSpinBox.setMaximum(1.000000000000000)
        self.floatSegThresholdDoubleSpinBox.setSingleStep(0.050000000000000)
        self.floatSegThresholdDoubleSpinBox.setDecimals(3)
        self.floatSegThresholdDoubleSpinBox.setValue(0.500000000000000)

        self.floatSegThresholdFormLayout.setWidget(0, QFormLayout.FieldRole, self.floatSegThresholdDoubleSpinBox)


        self.settingsLayout.addLayout(self.floatSegThresholdFormLayout)

        self.wlPresetTitleLabel = QLabel(self.settingsCollapsible)
        self.wlPresetTitleLabel.setObjectName(u"wlPresetTitleLabel")

        self.settingsLayout.addWidget(self.wlPresetTitleLabel)

        self.wlPresetFormLayout = QFormLayout()
        self.wlPresetFormLayout.setObjectName(u"wlPresetFormLayout")
        self.wlPresetF1Label = QLabel(self.settingsCollapsible)
        self.wlPresetF1Label.setObjectName(u"wlPresetF1Label")

        self.wlPresetFormLayout.setWidget(0, QFormLayout.LabelRole, self.wlPresetF1Label)

        self.wlPresetF1LineEdit = QLineEdit(self.settingsCollapsible)
        self.wlPresetF1LineEdit.setObjectName(u"wlPresetF1LineEdit")

        self.wlPresetFormLayout.setWidget(0, QFormLayout.FieldRole, self.wlPresetF1LineEdit)

        self.wlPresetF2Label = QLabel(self.settingsCollapsible)
        self.wlPresetF2Label.setObjectName(u"wlPresetF2Label")

        self.wlPresetFormLayout.setWidget(1, QFormLayout.LabelRole, self.wlPresetF2Label)

        self.wlPresetF2LineEdit = QLineEdit(self.settingsCollapsible)
        self.wlPresetF2LineEdit.setObjectName(u"wlPresetF2LineEdit")

        self.wlPresetFormLayout.setWidget(1, QFormLayout.FieldRole, self.wlPresetF2LineEdit)

        self.wlPresetF3Label = QLabel(self.settingsCollapsible)
        self.wlPresetF3Label.setObjectName(u"wlPresetF3Label")

        self.wlPresetFormLayout.setWidget(2, QFormLayout.LabelRole, self.wlPresetF3Label)

        self.wlPresetF3LineEdit = QLineEdit(self.settingsCollapsible)
        self.wlPresetF3LineEdit.setObjectName(u"wlPresetF3LineEdit")

        self.wlPresetFormLayout.setWidget(2, QFormLayout.FieldRole, self.wlPresetF3LineEdit)


        self.settingsLayout.addLayout(self.wlPresetFormLayout)

        self.shortcutHintLabel = QLabel(self.settingsCollapsible)
        self.shortcutHintLabel.setObjectName(u"shortcutHintLabel")
        self.shortcutHintLabel.setWordWrap(True)

        self.settingsLayout.addWidget(self.shortcutHintLabel)


        self.verticalLayout.addWidget(self.settingsCollapsible)


        self.retranslateUi(NpzLoader)

        QMetaObject.connectSlotsByName(NpzLoader)
    # setupUi

    def retranslateUi(self, NpzLoader):
        self.fileSelectionCollapsible.setText(QCoreApplication.translate("NpzLoader", u"Directory & File Selection", None))
        self.sourceTypeLabel.setText(QCoreApplication.translate("NpzLoader", u"Data Source:", None))
        self.sourceTypeComboBox.setItemText(0, QCoreApplication.translate("NpzLoader", u"NPZ Directory", None))
        self.sourceTypeComboBox.setItemText(1, QCoreApplication.translate("NpzLoader", u"IMG+SEG Paired Directory", None))

        self.directoryLabel.setText(QCoreApplication.translate("NpzLoader", u"Root Directory:", None))
#if QT_CONFIG(tooltip)
        self.directorySelector.setToolTip(QCoreApplication.translate("NpzLoader", u"Select root directory containing NPZ/NPY files", None))
#endif // QT_CONFIG(tooltip)
        self.imgDirectoryLabel.setText(QCoreApplication.translate("NpzLoader", u"IMG Directory:", None))
#if QT_CONFIG(tooltip)
        self.imgDirectorySelector.setToolTip(QCoreApplication.translate("NpzLoader", u"Select image directory for paired mode", None))
#endif // QT_CONFIG(tooltip)
        self.segDirectoryLabel.setText(QCoreApplication.translate("NpzLoader", u"SEG Directory:", None))
#if QT_CONFIG(tooltip)
        self.segDirectorySelector.setToolTip(QCoreApplication.translate("NpzLoader", u"Select segmentation directory for paired mode", None))
#endif // QT_CONFIG(tooltip)
        self.enableCompareCheckBox.setText(QCoreApplication.translate("NpzLoader", u"Enable Compare Mode", None))
#if QT_CONFIG(tooltip)
        self.enableCompareCheckBox.setToolTip(QCoreApplication.translate("NpzLoader", u"Switch paired mode UI to compare one image with two segmentation roots", None))
#endif // QT_CONFIG(tooltip)
        self.segDirectoryALabel.setText(QCoreApplication.translate("NpzLoader", u"SEG A Directory:", None))
#if QT_CONFIG(tooltip)
        self.segDirectoryASelector.setToolTip(QCoreApplication.translate("NpzLoader", u"Select segmentation directory A for compare mode", None))
#endif // QT_CONFIG(tooltip)
        self.segDirectoryBLabel.setText(QCoreApplication.translate("NpzLoader", u"SEG B Directory:", None))
#if QT_CONFIG(tooltip)
        self.segDirectoryBSelector.setToolTip(QCoreApplication.translate("NpzLoader", u"Select segmentation directory B for compare mode", None))
#endif // QT_CONFIG(tooltip)
        self.onlyWithSegCheckBox.setText(QCoreApplication.translate("NpzLoader", u"Only show data with seg", None))
        self.scanButton.setText(QCoreApplication.translate("NpzLoader", u"Scan", None))
#if QT_CONFIG(tooltip)
        self.scanButton.setToolTip(QCoreApplication.translate("NpzLoader", u"Scan img/seg directories and build data list", None))
#endif // QT_CONFIG(tooltip)
        self.fileListLabel.setText(QCoreApplication.translate("NpzLoader", u"Data List:", None))
#if QT_CONFIG(tooltip)
        self.fileList.setToolTip(QCoreApplication.translate("NpzLoader", u"Select a file to analyze and load", None))
#endif // QT_CONFIG(tooltip)
        self.loadPlanCollapsible.setText(QCoreApplication.translate("NpzLoader", u"NPZ Key Analysis & Load Plan", None))
        self.keyInfoLabel.setText(QCoreApplication.translate("NpzLoader", u"Detected Keys:", None))
        self.loadPlanLabel.setText(QCoreApplication.translate("NpzLoader", u"Load Plan (check groups to load, edit key mappings):", None))
#if QT_CONFIG(tooltip)
        self.loadPlanTree.setToolTip(QCoreApplication.translate("NpzLoader", u"Configure which data to load and key mappings. Ctrl/Shift+click for multi-select; toggling one checkbox applies to all selected rows.", None))
#endif // QT_CONFIG(tooltip)
        self.addGroupButton.setText(QCoreApplication.translate("NpzLoader", u"Add Group", None))
#if QT_CONFIG(tooltip)
        self.addGroupButton.setToolTip(QCoreApplication.translate("NpzLoader", u"Add a new load plan group", None))
#endif // QT_CONFIG(tooltip)
        self.removeGroupButton.setText(QCoreApplication.translate("NpzLoader", u"Remove Group", None))
#if QT_CONFIG(tooltip)
        self.removeGroupButton.setToolTip(QCoreApplication.translate("NpzLoader", u"Remove the selected load plan group", None))
#endif // QT_CONFIG(tooltip)
        self.loadActionsCollapsible.setText(QCoreApplication.translate("NpzLoader", u"Load Actions", None))
        self.loadButton.setText(QCoreApplication.translate("NpzLoader", u"Load", None))
#if QT_CONFIG(tooltip)
        self.loadButton.setToolTip(QCoreApplication.translate("NpzLoader", u"Load enabled plan groups into the scene", None))
#endif // QT_CONFIG(tooltip)
        self.closeButton.setText(QCoreApplication.translate("NpzLoader", u"Close / Clear", None))
#if QT_CONFIG(tooltip)
        self.closeButton.setToolTip(QCoreApplication.translate("NpzLoader", u"Remove all nodes loaded from the current file", None))
#endif // QT_CONFIG(tooltip)
        self.statusLabel.setText(QCoreApplication.translate("NpzLoader", u"No file loaded.", None))
        self.settingsCollapsible.setText(QCoreApplication.translate("NpzLoader", u"Settings", None))
        self.autoDetectCheckBox.setText(QCoreApplication.translate("NpzLoader", u"Auto-detect load plan for each file", None))
        self.reuseplanCheckBox.setText(QCoreApplication.translate("NpzLoader", u"Reuse last load plan for files with matching keys", None))
        self.autoShowSeg3DCheckBox.setText(QCoreApplication.translate("NpzLoader", u"Automatically enable segmentation Show 3D after load", None))
#if QT_CONFIG(tooltip)
        self.autoShowSeg3DCheckBox.setToolTip(QCoreApplication.translate("NpzLoader", u"When checked, loaded segmentations are shown in the 3D view (Segmentations module Show 3D). When unchecked, 3D visibility stays off.", None))
#endif // QT_CONFIG(tooltip)
        self.floatSegAutoThresholdCheckBox.setText(QCoreApplication.translate("NpzLoader", u"Auto-convert float seg masks (0-1 -> threshold)", None))
        self.floatSegThresholdLabel.setText(QCoreApplication.translate("NpzLoader", u"Float seg threshold (0-1):", None))
#if QT_CONFIG(tooltip)
        self.floatSegThresholdDoubleSpinBox.setToolTip(QCoreApplication.translate("NpzLoader", u"Used when float seg is detected as a 0-1 probability mask", None))
#endif // QT_CONFIG(tooltip)
        self.wlPresetTitleLabel.setText(QCoreApplication.translate("NpzLoader", u"Window/Level Presets (WW,WL):", None))
        self.wlPresetF1Label.setText(QCoreApplication.translate("NpzLoader", u"F1 preset:", None))
        self.wlPresetF1LineEdit.setPlaceholderText(QCoreApplication.translate("NpzLoader", u"e.g. 400,40", None))
#if QT_CONFIG(tooltip)
        self.wlPresetF1LineEdit.setToolTip(QCoreApplication.translate("NpzLoader", u"Format: window,level", None))
#endif // QT_CONFIG(tooltip)
        self.wlPresetF2Label.setText(QCoreApplication.translate("NpzLoader", u"F2 preset:", None))
        self.wlPresetF2LineEdit.setPlaceholderText(QCoreApplication.translate("NpzLoader", u"e.g. 1500,-600", None))
#if QT_CONFIG(tooltip)
        self.wlPresetF2LineEdit.setToolTip(QCoreApplication.translate("NpzLoader", u"Format: window,level", None))
#endif // QT_CONFIG(tooltip)
        self.wlPresetF3Label.setText(QCoreApplication.translate("NpzLoader", u"F3 preset:", None))
        self.wlPresetF3LineEdit.setPlaceholderText(QCoreApplication.translate("NpzLoader", u"e.g. 2500,500", None))
#if QT_CONFIG(tooltip)
        self.wlPresetF3LineEdit.setToolTip(QCoreApplication.translate("NpzLoader", u"Format: window,level", None))
#endif // QT_CONFIG(tooltip)
        self.shortcutHintLabel.setText(QCoreApplication.translate("NpzLoader", u"Shortcuts (active only in NPZ Loader): F1/F2/F3 apply W/L presets, T toggles latest segmentation (fill/contour/hide), Shift+T toggles all loaded segmentations.", None))
        pass
    # retranslateUi

