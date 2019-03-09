"""
Offline and online data analysis and visualization tool for azimuthal
integration of different data acquired with various detectors at
European XFEL.

Mediator class.

Author: Jun Zhu <jun.zhu@xfel.eu>
Copyright (C) European X-Ray Free-Electron Laser Facility GmbH.
All rights reserved.
"""
from .pyqtgraph import QtCore


class Mediator(QtCore.QObject):
    vip_pulse_id1_sgn = QtCore.pyqtSignal(int)
    vip_pulse_id2_sgn = QtCore.pyqtSignal(int)

    roi_displayed_range_sgn = QtCore.pyqtSignal(int)

    __instance = None

    def __new__(cls, *args, **kwargs):
        """Create a singleton."""
        if cls.__instance is None:
            cls.__instance = super().__new__(cls, *args, **kwargs)
            cls.__instance.__initialized = False
        return cls.__instance

    def __init__(self, processor=None, *args, **kwargs):
        if self.__initialized:
            return
        self.__initialized = True

        super().__init__(*args, **kwargs)

        self._proc = processor

    @QtCore.pyqtSlot(int)
    def onPulseID1Updated(self, v):
        self.vip_pulse_id1_sgn.emit(v)

    @QtCore.pyqtSlot(int)
    def onPulseID2Updated(self, v):
        self.vip_pulse_id2_sgn.emit(v)

    @QtCore.pyqtSlot()
    def onRoiDisplayedRangeChange(self):
        v = int(self.sender().text())
        self.roi_displayed_range_sgn.emit(v)

    @QtCore.pyqtSlot()
    def onRoiHistClear(self):
        self._proc.clear_roi_hist()

    @QtCore.pyqtSlot(object)
    def onRoiValueTypeChange(self, state):
        self._proc.update_roi_value_type(state)

    @QtCore.pyqtSlot(bool, int, int, int, int)
    def onRoi1Change(self, activated, w, h, px, py):
        self._proc.update_roi1_region(activated, w, h, px, py)

    @QtCore.pyqtSlot(bool, int, int, int, int)
    def onRoi2Change(self, activated, w, h, px, py):
        self._proc.update_roi2_region(activated, w, h, px, py)

    @QtCore.pyqtSlot()
    def onBkgChange(self):
        self._proc.update_background(float(self.sender().text()))

    @QtCore.pyqtSlot(bool, int, int, int, int)
    def onCropAreaChange(self, restore, w, h, px, py):
        self._proc.update_crop_area(restore, w, h, px, py)

    @QtCore.pyqtSlot(int)
    def onMovingAvgWindowChange(self, v):
        self._proc.update_moving_avg_window(v)

    @QtCore.pyqtSlot(float, float)
    def onThresholdMaskChange(self, lb, ub):
        self._proc.update_threshold_mask(lb, ub)

    @QtCore.pyqtSlot(object, int, int, int, int)
    def onMaskRegionChange(self, tp, x, y, w, h):
        self._proc.update_image_mask(tp, x, y, w, h)
