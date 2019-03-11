"""
Offline and online data analysis and visualization tool for azimuthal
integration of different data acquired with various detectors at
European XFEL.

Data models for analysis and visualization.

Author: Jun Zhu <jun.zhu@xfel.eu>
Copyright (C) European X-Ray Free-Electron Laser Facility GmbH.
All rights reserved.
"""
import abc

import numpy as np

from cached_property import cached_property

from ..algorithms import nanmean_axis0_para
from ..logger import logger
from ..config import config, ImageMaskChange


class TrainData:
    """Store the history train data.

    Each data point is pair of data: (x, value), where x can be a
    train ID for time series analysis or a correlated data for
    correlation analysis.
    """
    MAX_LENGTH = 1000000

    def __init__(self, **kwargs):
        # We need to have a 'x' for each sub-dataset due to the
        # concurrency of data processing.
        self._x = []
        self._values = []
        # for now it is used in CorrelationData to store device ID and
        # property information
        self._info = kwargs

    def __get__(self, instance, instance_type):
        if instance is None:
            return self
        return self._x, self._values, self._info

    def __set__(self, instance, pair):
        x, value = pair
        self._x.append(x)
        self._values.append(value)

        # TODO: improve, e.g., cache
        if len(self._x) > self.MAX_LENGTH:
            self.__delete__(instance)

    def __delete__(self, instance):
        del self._x[0]
        del self._values[0]

    def clear(self):
        self._x.clear()
        self._values.clear()
        # do not clear _info here!


class AbstractData(abc.ABC):
    @classmethod
    def clear(cls):
        for attr in cls.__dict__.values():
            if isinstance(attr, TrainData):
                # descriptor protocol will not be triggered here
                attr.clear()


class RoiData(AbstractData):
    """A class which stores ROI data."""

    # value (integration/mean/median) histories of ROI1 and ROI2
    values1 = TrainData()
    values2 = TrainData()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.roi1 = None  # (w, h, px, py)
        self.roi2 = None  # (w, h, px, py)


class LaserOnOffData(AbstractData):
    """A class which stores Laser on-off data."""

    # FOM history
    foms = TrainData()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_pulse = None
        self.off_pulse = None
        self.diff = None


class CorrelationData(AbstractData):
    """A class which stores Laser on-off data."""

    @classmethod
    def add_param(cls, idx, device_id, ppt):
        setattr(cls, f'param{idx}', TrainData(device_id=device_id,
                                              property=ppt))

    @classmethod
    def remove_param(cls, idx):
        name = f'param{idx}'
        if hasattr(cls, name):
            delattr(cls, name)

    @classmethod
    def get_params(cls):
        params = []
        for kls in cls.__dict__:
            if isinstance(cls.__dict__[kls], TrainData):
                params.append(kls)

        return params


class ImageData:
    """A class that manages the detector images.

    Operation flow:

    remove background -> cropping -> calculate mean image -> apply mask

    Attributes:
        pixel_size (float): detector pixel size.
        _images (numpy.ndarray): detector images for all the pulses in
            a train. shape = (pulse_id, y, x) for pulse-resolved
            detectors and shape = (y, x) for train-resolved detectors.
        _threshold_mask (tuple): (min, max) threshold of the pixel value.
        _image_mask (numpy.ndarray): an image mask, default = None.
            Shape = (y, x)
        _crop_area (tuple): (x, y, w, h) of the cropped image.
        _poni (tuple): (Cx, Cy), where Cx is the coordinate of the point
            of normal incidence along the detector's second dimension,
            in pixels, and Cy is the coordinate of the point of normal
            incidence along the detector's first dimension, in pixels.
            default = (0, 0)
    """
    class RawImageData:
        def __init__(self):
            self._images = None  # moving average (original data)
            self._ma_window = 1
            self._ma_count = 0

            self._bkg = 0.0  # current background value

        def _invalid_image_cached(self):
            try:
                del self.__dict__['images']
            except KeyError:
                pass

        @property
        def background(self):
            return self._bkg

        @background.setter
        def background(self, v):
            if self._bkg != v:
                self._bkg = v
                self._invalid_image_cached()

        @cached_property
        def images(self):
            if self._images is None:
                return None
            # return a new constructed array
            return self._images - self._bkg

        def set(self, imgs):
            """Set new image train data."""
            if self._images is None:
                self._images = imgs
                self._ma_count = 1
            else:
                if imgs.shape != self._images.shape:
                    logger.error(f"The shape {imgs.shape} of the new image is "
                                 f"different from the current one "
                                 f"{self._images.shape}!")
                    return

                elif self._ma_window > 1:
                    if self._ma_count < self._ma_window:
                        self._ma_count += 1
                        self._images += (imgs - self._images) / self._ma_count
                    else:  # self._ma_count == self._ma_window
                        # here is an approximation
                        self._images += (imgs - self._images) / self._ma_window

                else:  # self._ma_window == 1
                    self._images = imgs
                    self._ma_count = 1

            self._invalid_image_cached()

        @property
        def moving_average_window(self):
            return self._ma_window

        @moving_average_window.setter
        def moving_average_window(self, v):
            if not isinstance(v, int) or v < 0:
                v = 1

            if v < self._ma_window:
                # if the new window size is smaller than the current one,
                # we reset the original image sum and count
                self._ma_window = v
                self._ma_count = 0
                self._images = None
                self._invalid_image_cached()

            self._ma_window = v

        @property
        def moving_average_count(self):
            return self._ma_count

    class ImageMaskData:
        def __init__(self, shape):
            """Initialization.

            :param shape: shape of the mask.
            """
            self._assembled = np.zeros(shape, dtype=bool)

        def get(self):
            """Return the assembled mask."""
            return self._assembled

        def set(self, mask):
            """Set the current mask."""
            self._assembled[:] = mask

        def add(self, x, y, w, h, flag):
            """Update an area in the mask.

            :param bool flag: True for masking the new area and False for
                unmasking.
            """
            self._assembled[y:y + h, x:x + w] = flag

        def clear(self):
            """Unmask all."""
            self._assembled[:] = False

    class ThresholdMaskData:
        def __init__(self, lb=None, ub=None):
            self._lower = lb
            self._upper = ub

        def get(self):
            lower = -np.inf if self._lower is None else self._lower
            upper = np.inf if self._upper is None else self._upper
            return lower, upper

        def set(self, lb, ub):
            self._lower = lb
            self._upper = ub

    class CropAreaData:
        def __init__(self):
            self._rect = None

        def get(self):
            return self._rect

        def set(self, x, y, w, h):
            self._rect = (x, y, w, h)

        def clear(self):
            self._rect = None

    __raw = RawImageData()
    __threshold_mask = None
    __image_mask = None
    __crop_area = CropAreaData()

    pixel_size = None

    def __init__(self, images, *, poni=None):
        """Initialization."""
        if self.pixel_size is None:
            self.__class__.pixel_size = config["PIXEL_SIZE"]

        if not isinstance(images, np.ndarray):
            raise TypeError(r"Images must be numpy.ndarray!")

        if images.ndim <= 1 or images.ndim > 3:
            raise ValueError(
                f"The shape of images must be (y, x) or (n_pulses, y, x)!")

        if self.__image_mask is None:
            self.__class__.__image_mask = self.ImageMaskData(images.shape[-2:])
        if self.__threshold_mask is None:
            self.__class__.__threshold_mask = self.ThresholdMaskData(
                *config['MASK_RANGE'])

        # update moving average
        self._set_images(images)

        # Instance attributes should be "frozen" after created. Otherwise,
        # the data used in different plot widgets could be different.
        self._images = self.__raw.images
        self._image_mask = np.copy(self.__image_mask.get())
        self._threshold_mask = self.__threshold_mask.get()
        self._crop_area = self.__crop_area.get()

        self._poni = (0, 0) if poni is None else poni

        # cache these two properties
        self.ma_window
        self.ma_count

        self._registered_ops = set()

    @property
    def n_images(self):
        if self._images.ndim == 3:
            return self._images.shape[0]
        return 1

    @property
    def shape(self):
        return self._images.shape[-2:]

    @property
    def background(self):
        return self.__raw.background

    @property
    def threshold_mask(self):
        return self._threshold_mask

    @cached_property
    def ma_window(self):
        # Updating ma_window could set __raw._images to None. Since there
        # is no cache being deleted. '_images' in this instance will not
        # be set to None. Note: '_images' is not allowed to be None.
        return self.__raw.moving_average_window

    @cached_property
    def ma_count(self):
        # Updating ma_window could reset ma_count. Therefore, 'ma_count'
        # should both be a cached property
        return self.__raw.moving_average_count

    def pos(self, x, y):
        """Return the position in the original image."""
        if self._crop_area is None:
            return x, y
        x0, y0, _, _, = self._crop_area
        return x + x0, y + y0

    def _set_images(self, imgs):
        self.__raw.set(imgs)

    def set_ma_window(self, v):
        self.__raw.moving_average_window = v

    def set_background(self, v):
        self.__raw.background = v
        self._registered_ops.add("background")

    def set_crop_area(self, flag, x, y, w, h):
        if flag:
            self.__crop_area.set(x, y, w, h)
        else:
            self.__crop_area.clear()

        self._registered_ops.add("crop")

    def set_image_mask(self, flag, x, y, w, h):
        if flag == ImageMaskChange.MASK:
            self.__image_mask.add(x, y, w, h, True)
        elif flag == ImageMaskChange.UNMASK:
            self.__image_mask.add(x, y, w, h, False)
        elif flag == ImageMaskChange.CLEAR:
            self.__image_mask.clear()
        elif flag == ImageMaskChange.REPLACE:
            self.__image_mask.set(x)

        self._registered_ops.add("image_mask")

    def set_threshold_mask(self, lb, ub):
        self.__threshold_mask.set(lb, ub)
        self._registered_ops.add("threshold_mask")

    @cached_property
    def image_mask(self):
        if self._crop_area is not None:
            x, y, w, h = self._crop_area
            return self._image_mask[y:y+h, x:x+w]

        return self._image_mask

    @cached_property
    def images(self):
        """Return the cropped, background-subtracted images.

        Warning: it shares the memory space with self._images
        """
        if self._crop_area is None:
            return self._images

        x, y, w, h = self._crop_area
        return self._images[..., y:y+h, x:x+w]

    @cached_property
    def mean(self):
        """Return the average of images over pulses in a train.

        The image is cropped and background-subtracted.

        :return numpy.ndarray: a single image, shape = (y, x)
        """
        if self._images.ndim == 3:
            # pulse resolved
            return nanmean_axis0_para(self.images,
                                      max_workers=8, chunk_size=20)
        # train resolved
        return self.images

    @cached_property
    def masked_mean(self):
        """Return the masked average image.

        The image is cropped and background-subtracted before applying
        the mask.
        """
        # keep both mean image and masked mean image so that we can
        # recalculate the masked image
        mean_image = np.copy(self.mean)

        # Convert 'nan' to '-inf' and it will later be converted to the
        # lower range of mask, which is usually 0.
        # We do not convert 'nan' to 0 because: if the lower range of
        # mask is a negative value, 0 will be converted to a value
        # between 0 and 255 later.
        mean_image[np.isnan(mean_image)] = -np.inf
        # clip the array, which now will contain only numerical values
        # within the mask range
        np.clip(mean_image, *self._threshold_mask, out=mean_image)

        return mean_image

    @property
    def poni(self):
        """Return the PONI in the original image."""
        poni1 = self._poni[0]
        poni2 = self._poni[1]
        if self._crop_area is not None:
            x, y, _, _ = self._crop_area
            poni1 -= y
            poni2 -= x

        return poni1, poni2

    @poni.setter
    def poni(self, v):
        self._poni = v

    def update(self):
        invalid_caches = set()
        if "background" in self._registered_ops:
            self._images = self.__raw.images
            invalid_caches.update({"images", "mean", "masked_mean"})
        if "crop" in self._registered_ops:
            self._crop_area = self.__crop_area.get()
            invalid_caches.update(
                {"images", "mean", "masked_mean", "image_mask"})
        if "image_mask" in self._registered_ops:
            self._image_mask = np.copy(self.__image_mask.get())
            invalid_caches.add("image_mask")
        if "threshold_mask" in self._registered_ops:
            self._threshold_mask = self.__threshold_mask.get()
            invalid_caches.add("masked_mean")

        for cache in invalid_caches:
            try:
                del self.__dict__[cache]
            except KeyError:
                pass

        self._registered_ops.clear()

    @classmethod
    def reset(cls):
        """Reset all the class attributes.

        Used in unittest only.
        """
        cls.__raw = cls.RawImageData()
        cls.__threshold_mask = None
        cls.__image_mask = None
        cls.__crop_area = cls.CropAreaData()


class ProcessedData:
    """A class which stores the processed data.

    ProcessedData also provide interface for manipulating the other node
    dataset, e.g. RoiData, CorrelationData, LaserOnOffData.

    Attributes:
        tid (int): train ID.
        momentum (numpy.ndarray): x-axis of azimuthal integration result.
            Shape = (momentum,)
        intensities (numpy.ndarray): y-axis of azimuthal integration result.
            Shape = (pulse_id, intensity)
        intensity_mean (numpy.ndarray): average of the y-axis of azimuthal
            integration result over pulses. Shape = (intensity,)
        roi (RoiData): stores ROI related data.
        on_off (LaserOnOffData): stores laser on-off related data.
        correlation (CorrelationData): correlation related data.
    """

    def __init__(self, tid, images=None, **kwargs):
        """Initialization."""
        if not isinstance(tid, int):
            raise ValueError("Train ID must be an integer!")

        self._tid = tid  # current Train ID
        if images is None:
            self._image_data = None
        else:
            self._image_data = ImageData(images, **kwargs)

        self.momentum = None
        self.intensities = None
        self.intensity_mean = None

        self.sample_degradation_foms = None

        self.roi = RoiData()
        self.on_off = LaserOnOffData()
        self.correlation = CorrelationData()

    @property
    def tid(self):
        return self._tid

    @property
    def image(self):
        return self._image_data

    @property
    def n_pulses(self):
        if self._image_data is None:
            return 0

        return self._image_data.n_images

    @classmethod
    def clear_roi_hist(cls):
        RoiData.clear()

    @classmethod
    def clear_onoff_hist(cls):
        LaserOnOffData.clear()

    @classmethod
    def clear_correlation_hist(cls):
        CorrelationData.clear()

    @staticmethod
    def add_correlator(idx, device_id, ppt):
        """Add a correlated parameter.

        :param int idx: index
        :param str device_id: device ID
        :param str ppt: property
        """
        if device_id and ppt:
            CorrelationData.add_param(idx, device_id, ppt)
        else:
            CorrelationData.remove_param(idx)

    @staticmethod
    def get_correlators():
        return CorrelationData.get_params()

    def empty(self):
        """Check the goodness of the data."""
        logger.debug("Deprecated! use self.n_pulses!")
        if self.image is None:
            return True
        return False


class Data4Visualization:
    """Data shared between all the windows and widgets.

    The internal data is only modified in MainGUI.updateAll()
    """
    def __init__(self):
        self.__value = ProcessedData(-1)

    def get(self):
        return self.__value

    def set(self, value):
        self.__value = value
