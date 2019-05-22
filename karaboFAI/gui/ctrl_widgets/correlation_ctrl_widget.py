"""
Offline and online data analysis and visualization tool for azimuthal
integration of different data acquired with various detectors at
European XFEL.

CorrelationCtrlWidget.

Author: Jun Zhu <jun.zhu@xfel.eu>, Ebad Kamil <ebad.kamil@xfel.eu>
Copyright (C) European X-Ray Free-Electron Laser Facility GmbH.
All rights reserved.
"""
from collections import OrderedDict
import functools

from ..pyqtgraph import Qt, QtCore, QtGui

from .base_ctrl_widgets import AbstractCtrlWidget
from ..misc_widgets import SmartLineEdit
from ...config import CorrelationFom


class CorrelationCtrlWidget(AbstractCtrlWidget):
    """Widget for setting up the correlation analysis parameters."""

    class CorrelationParam:
        def __init__(self, device_ids=None, properties=None):
            if device_ids is None:
                self.device_ids = []
            else:
                self.device_ids = device_ids

            if properties is None:
                self.properties = []
            else:
                self.properties = properties

    _n_params = 4  # maximum number of correlated parameters

    # Leave the default device ID empty since the available devices
    # in different instruments are different.
    #
    # TODO: move this to a separate config file
    _available_categories = OrderedDict({
        "": CorrelationParam(),
        "XGM": CorrelationParam(
            device_ids=[
                "",
                "SA1_XTD2_XGM/DOOCS/MAIN",
                "SPB_XTD9_XGM/DOOCS/MAIN",
                "SA3_XTD10_XGM/XGM/DOOCS",
                "SCS_BLU_XGM/XGM/DOOCS"
            ],
            properties=["data.intensityTD"],
        ),
        "MonoChromator": CorrelationParam(
            device_ids=[
                "",
                "SA3_XTD10_MONO/MDL/PHOTON_ENERGY"
            ],
            properties=["actualEnergy"],
        ),
        "Digitizer": CorrelationParam(
            device_ids=[
                "",
                "SCS_UTC1_ADQ/ADC/1"
            ],
            properties=["MCP1", "MCP2", "MCP3", "MCP4"],
        ),
        "Motor": CorrelationParam(
            device_ids=[
                "",
                "FXE_SMS_USR/MOTOR/UM01",
                "FXE_SMS_USR/MOTOR/UM02",
                "FXE_SMS_USR/MOTOR/UM04",
                "FXE_SMS_USR/MOTOR/UM05",
                "FXE_SMS_USR/MOTOR/UM13",
                "FXE_AUXT_LIC/DOOCS/PPLASER",
            ],
            properties=["actualPosition"],
        ),
        "Train ID": CorrelationParam(
            device_ids=["", "Any"],
            properties=["timestamp.tid"]
        ),
        "User defined": CorrelationParam()
    })

    _available_foms = OrderedDict({
        "": CorrelationFom.UNDEFINED,
        "pump-probe FOM": CorrelationFom.PUMP_PROBE_FOM,
        "ROI1 - ROI2": CorrelationFom.ROI_SUB,
        "ROI1": CorrelationFom.ROI1,
        "ROI2": CorrelationFom.ROI2,
        "ROI1 + ROI2": CorrelationFom.ROI_SUM,
        "azimuthal integ mean": CorrelationFom.AZIMUTHAL_INTEG_MEAN,
    })

    def __init__(self, *args, **kwargs):
        super().__init__("Correlation analysis setup", *args, **kwargs)

        self._fom_type_cb = QtGui.QComboBox()
        for v in self._available_foms:
            self._fom_type_cb.addItem(v)

        self._reset_btn = QtGui.QPushButton("Reset")

        self._table = QtGui.QTableWidget()

        self.initUI()
        self.initConnections()

        self.setFixedHeight(self.minimumSizeHint().height())

    def initUI(self):
        """Overload."""
        layout = QtGui.QGridLayout()
        AR = QtCore.Qt.AlignRight

        layout.addWidget(QtGui.QLabel("FOM type: "), 0, 0, AR)
        layout.addWidget(self._fom_type_cb, 0, 1)
        layout.addWidget(self._reset_btn, 0, 3)
        layout.addWidget(self._table, 1, 0, 1, 4)

        self.setLayout(layout)

        self.initParamTable()

    def initConnections(self):
        mediator = self._mediator

        self._fom_type_cb.currentTextChanged.connect(
            lambda x: mediator.onCorrelationFomChange(
                self._available_foms[x]))
        self._fom_type_cb.currentTextChanged.emit(
            self._fom_type_cb.currentText())

        self._reset_btn.clicked.connect(mediator.onCorrelationReset)

    def initParamTable(self):
        """Initialize the correlation parameter table widget."""
        table = self._table

        n_row = self._n_params
        n_col = 4

        table.setColumnCount(n_col)
        table.setRowCount(n_row)
        table.setHorizontalHeaderLabels([
            'Category', 'Karabo Device ID', 'Property Name', 'Resolution'])
        table.setVerticalHeaderLabels(['1', '2', '3', '4'])
        for i_row in range(self._n_params):
            combo = QtGui.QComboBox()
            for t in self._available_categories.keys():
                combo.addItem(t)
            table.setCellWidget(i_row, 0, combo)
            combo.currentTextChanged.connect(
                functools.partial(self.onCategoryChange, i_row))

            for i_col in range(1, n_col):
                widget = QtGui.QLineEdit()
                table.setCellWidget(i_row, i_col, widget)
                widget.setReadOnly(True)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, Qt.QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, Qt.QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(2, Qt.QtWidgets.QHeaderView.Stretch)

        header = table.verticalHeader()
        for i in range(n_row):
            header.setSectionResizeMode(i, Qt.QtWidgets.QHeaderView.Stretch)

        header_height = self._table.horizontalHeader().height()
        self._table.setMinimumHeight(header_height * (self._n_params + 2))
        self._table.setMaximumHeight(header_height * (self._n_params + 3))

    @QtCore.pyqtSlot(str)
    def onCategoryChange(self, i_row, text):
        resolution_le = SmartLineEdit("0.0")
        resolution_le.setValidator(QtGui.QDoubleValidator(0.0, 99999.9, 6))
        # i_row is the row number in the QTableWidget
        if not text or text == "User defined":
            # '' or 'User defined'
            device_id_le = SmartLineEdit()
            property_le = SmartLineEdit()

            if not text:
                device_id_le.setReadOnly(True)
                property_le.setReadOnly(True)
                resolution_le.setReadOnly(True)
                resolution_le.setText("")
            else:
                device_id_le.returnPressed.connect(functools.partial(
                    self.onCorrelationParamChangeLe, i_row))
                property_le.returnPressed.connect(functools.partial(
                    self.onCorrelationParamChangeLe, i_row))
                resolution_le.returnPressed.connect(functools.partial(
                    self.onCorrelationParamChangeLe, i_row))

            self._table.setCellWidget(i_row, 1, device_id_le)
            self._table.setCellWidget(i_row, 2, property_le)
            self._table.setCellWidget(i_row, 3, resolution_le)
        else:
            combo_device_ids = QtGui.QComboBox()
            for device_id in self._available_categories[text].device_ids:
                combo_device_ids.addItem(device_id)
            combo_device_ids.currentTextChanged.connect(functools.partial(
                self.onCorrelationParamChangeCb, i_row))
            self._table.setCellWidget(i_row, 1, combo_device_ids)

            combo_properties = QtGui.QComboBox()
            for ppt in self._available_categories[text].properties:
                combo_properties.addItem(ppt)
            combo_properties.currentTextChanged.connect(functools.partial(
                self.onCorrelationParamChangeCb, i_row))
            self._table.setCellWidget(i_row, 2, combo_properties)

            resolution_le.returnPressed.connect(functools.partial(
                self.onCorrelationParamChangeCb, i_row))
            self._table.setCellWidget(i_row, 3, resolution_le)

        # we always have invalid (empty) input when the category changes
        self._mediator.onCorrelationParamChange((i_row+1, '', '', 0.0))

    @QtCore.pyqtSlot()
    def onCorrelationParamChangeLe(self, i_row):
        device_id = self._table.cellWidget(i_row, 1).text()
        ppt = self._table.cellWidget(i_row, 2).text()
        res = float(self._table.cellWidget(i_row, 3).text())

        self._mediator.onCorrelationParamChange(
            (i_row+1, device_id, ppt, res))

    @QtCore.pyqtSlot(str)
    def onCorrelationParamChangeCb(self, i_row):
        device_id = self._table.cellWidget(i_row, 1).currentText()
        ppt = self._table.cellWidget(i_row, 2).currentText()
        res = float(self._table.cellWidget(i_row, 3).text())

        self._mediator.onCorrelationParamChange(
            (i_row+1, device_id, ppt, res))

    def updateSharedParameters(self):
        # TODO: emit signals for each row
        return True
