# Copyright 2014 Kevin Murray
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
.. module:: timestream
    :platform: Unix, Windows
    :synopsis: A python library to manipulate TimeStreams

.. moduleauthor:: Kevin Murray <spam@kdmurray.id.au>
"""

from copy import deepcopy
import cv2
import datetime as dt
import json
import logging
import numpy as np
import os
from os import path
from sys import stderr
from timestream.manipulate.pot import ImagePotMatrix
import cPickle

from timestream.parse.validate import (
    validate_timestream_manifest,
)
from timestream.parse import (
    _is_ts_v1,
    _is_ts_v2,
    _ts_date_to_path,
    ts_guess_manifest_v1,
    all_files_with_ext,
    ts_parse_date_path,
    ts_parse_date,
    ts_format_date,
    iter_date_range,
)
from timestream.parse.validate import (
    IMAGE_EXT_TO_TYPE,
    TS_MANIFEST_KEYS,
)
from timestream.util.imgmeta import (
    get_exif_date,
)


# versioneer
from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

LOG = logging.getLogger("timestreamlib")
NOW = dt.datetime.now()


def setup_module_logging(level=logging.DEBUG, handler=logging.StreamHandler,
                         stream=stderr):
    """Setup debug console logging. Designed for interactive use."""
    log = logging.getLogger("timestreamlib")
    fmt = logging.Formatter('%(asctime)s: %(message)s', '%H:%M:%S')
    if stream is None:
        stream = open("/dev/null", "w")
    cons = handler(stream=stream)
    cons.setLevel(level)
    cons.setFormatter(fmt)
    log.addHandler(cons)
    log.setLevel(level)


class TimeStream(object):

    def __init__(self, version=None):
        """A TimeStream, including metadata and parsers"""
        # Store version
        self._version = None
        if version:
            self.version = version
        self._path = None
        self._name = None
        self.start_datetime = None
        self.end_datetime = None
        self.image_type = None
        self.extension = None
        self.interval = None
        self.image_data = {}
        self.data = {}
        self.image_db_path = None
        self.db_path = None
        self.data_dir = None

    def __str__(self):
        ret = "TimeStream "
        if self._name:
            ret += "called {}\n".format(self._name)
        if self._path:
            ret += "\tpath: {}\n".format(self._path)
        for key in TS_MANIFEST_KEYS:
            ret += "\t{}: {}\n".format(key, getattr(self, key))
        return ret

    @property
    def version(self):
        return self._version

    @version.setter
    def version(self, version):
        if not isinstance(version, int) or version < 1 or version > 2:
            msg = "Invalid TimeStream version {}.".format(repr(version))
            msg += " Must be an int, 1 or 2"
            LOG.error(msg)
            raise ValueError(msg)
        self._version = version

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        if not isinstance(name, str):
            msg = "Timestream name must be a str"
            LOG.error(msg)
            raise TypeError(msg)
        if '_' in name:
            msg = "Timestream name can't contain _. '{}' does".format(name)
            LOG.error(msg)
            raise ValueError(msg)
        self._name = name

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, ts_path):
        """Store the root path of this timestream"""
        # Store root path
        if not isinstance(ts_path, str):
            msg = "Timestream path must be a str"
            LOG.error(msg)
            raise TypeError(msg)
        ts_path = ts_path.rstrip(os.sep)
        # This is required to ensure that path.dirname() of timestreams with
        # relative paths rooted at the current directory returns ".", not "",
        # or the timestream itself.
        dotslash = ".{}".format(os.sep)
        if not ts_path.startswith(os.sep):
            if not ts_path.startswith(dotslash):
                ts_path = "{}{}".format(dotslash, ts_path)
        self._path = ts_path
        self.data_dir = path.join(self._path, "_data")
        if (not path.isdir(self.data_dir)) and path.isdir(ts_path):
            os.mkdir(self.data_dir)

        self.image_db_path = path.join(self.data_dir, "image_data.json")
        self.db_path = path.join(self.data_dir, "timestream_data.json")

    @path.deleter
    def path(self):
        del self._path

    def load(self, ts_path):
        """Load a timestream from ``ts_path``, reading metadata"""
        self.path = ts_path
        if not path.exists(self.path):
            msg = "Timestream at {} does not exsit".format(self.path)
            LOG.error(msg)
            raise ValueError(msg)
        try:
            with open(self.image_db_path) as db_fh:
                self.image_data = json.load(db_fh)
        except IOError:
            self.image_data = {}
        try:
            with open(self.db_path) as db_fh:
                self.data = json.load(db_fh)
        except IOError:
            self.data = {}
        self.read_metadata()

    def create(self, ts_path, version=1, ext="png", type=None, start=NOW,
               end=NOW, name=None):
        self.version = version
        if not isinstance(ts_path, str):
            msg = "Timestream path must be a str"
            LOG.error(msg)
            raise TypeError(msg)
        # Basename will trip over the trailing slash, if given.
        ts_path = ts_path.rstrip(os.sep)
        # This is required to ensure that path.dirname() of timestreams with
        # relative paths rooted at the current directory returns ".", not "",
        # or the timestream itself.
        dotslash = ".{}".format(os.sep)
        if not ts_path.startswith(os.sep):
            if not ts_path.startswith(dotslash):
                ts_path = "{}{}".format(dotslash, ts_path)
        if not path.exists(path.dirname(ts_path)):
            msg = "Cannot create {}. Parent dir doesn't exist".format(ts_path)
            LOG.error(msg)
            raise ValueError(msg)
        if not path.exists(ts_path):
            if self.version == 1:
                os.mkdir(ts_path)
        self.path = ts_path
        self.extension = ext
        self.start_datetime = start
        self.end_datetime = end
        if name is None:
            self.name = path.basename(ts_path)
        if type:
            self.image_type = type
        else:
            try:
                self.image_type = IMAGE_EXT_TO_TYPE[ext]
            except KeyError:
                msg = "Invalid image ext {}".format(ext)
                LOG.error(msg)
                raise ValueError(msg)

    def write_image(self, image, overwrite_mode="skip"):
        if not self.name:
            msg = "write_image() must be called on instance with valid name"
            LOG.error(msg)
            raise RuntimeError(msg)
        if not self.path:
            msg = "write_image() must be called on instance with valid path"
            LOG.error(msg)
            raise RuntimeError(msg)
        if not isinstance(image, TimeStreamImage):
            msg = "write_image() must be given an instance of TimeStreamImage"
            LOG.error(msg)
            raise TypeError(msg)
        if not isinstance(overwrite_mode, str):
            msg = "overwrite_mode must be a str"
            LOG.error(msg)
            raise TypeError(msg)
        if overwrite_mode not in {"skip", "increment", "overwrite", "raise"}:
            msg = "Invalid overwrite_mode {}.".format(overwrite_mode)
            LOG.error(msg)
            raise ValueError(msg)
        if image.pixels is None:
            msg = "Image must have pixels to be able to be written"
            LOG.error(msg)
            raise ValueError(msg)

        if self.version == 1:
            fpath = _ts_date_to_path(self.name, self.extension,
                                     image.datetime, 0)
            fpath = path.join(self.path, fpath)
            if path.exists(fpath):
                if overwrite_mode == "skip":
                    return
                elif overwrite_mode == "increment":
                    subsec = 0
                    while path.exists(fpath) and subsec < 100:
                        subsec += 1
                        fpath = _ts_date_to_path(self.name, image.datetime,
                                                 subsec)
                    if path.exists(fpath):
                        msg = "Too many images at timepoint {}".format(
                            ts_format_date(image.datetime))
                        LOG.error(msg)
                        raise ValueError(msg)
                elif overwrite_mode == "overwrite":
                    # We don't do anything here if we want to overwrite
                    pass
                elif overwrite_mode == "raise":
                    msg = "Image already exists at {}".format(fpath)
                    LOG.error(msg)
                    raise ValueError(msg)
            # Update timestream if required
            if image.datetime > self.end_datetime:
                self.end_datetime = image.datetime
            if image.datetime < self.start_datetime:
                self.start_datetime = image.datetime
            self.image_data[ts_format_date(image.datetime)] = image.data
            self.write_metadata()
            # FIXME: pass the overwrite_mode
            image.write(fpath=fpath, overwrite=True)
            self.write_pickled_image(image, overwrite=True)

        else:
            raise NotImplementedError("v2 timestreams not implemented yet")

    def write_pickled_image(self, image, overwrite=False):
        if not isinstance(image, TimeStreamImage):
            msg = "image must be instance of TimeStreamImage"
            LOG.error(msg)
            raise TypeError(msg)

        pPath = path.join(self.data_dir,
                          _ts_date_to_path(self.name, "p", image.datetime, 0))

        if path.isfile(pPath) and not overwrite:
            msg = "File {} exists and overwrite is {}".format(pPath, overwrite)
            LOG.error(msg)
            raise RuntimeError(msg)

        # lose all the unnecessaries
        image.strip()

        if not path.exists(path.dirname(pPath)):
            os.makedirs(path.dirname(pPath))

        f = file(pPath, "w")
        cPickle.dump(image, f)
        f.close()

    def load_pickled_image(self, datetime):
        retImg = None
        pPath = path.join(self.data_dir,
                          _ts_date_to_path(self.name, "p", datetime, 0))
        if path.isfile(pPath):
            f = file(pPath, "r")
            retImg = cPickle.load(f)
            f.close()

            if not isinstance(retImg, TimeStreamImage):
                retImg = None

        return retImg

    def write_metadata(self):
        if not self.path:
            msg = "write_metadata() must be called on instance with valid path"
            LOG.error(msg)
            raise RuntimeError(msg)
        if self.version == 1:
            with open(self.image_db_path, "w") as db_fh:
                json.dump(self.image_data, db_fh)
            with open(self.db_path, "w") as db_fh:
                json.dump(self.data, db_fh)
        else:
            raise NotImplementedError("v2 metadata not implemented")

    def read_metadata(self):
        """Guesses the metadata fields of a timestream, v1 or v2."""
        if not self.path:
            msg = "read_metadata() must be called on instance with valid path"
            LOG.error(msg)
            raise RuntimeError(msg)
        # Detect version
        if self.version is None:
            if _is_ts_v1(self.path):
                self.version = 1
            elif _is_ts_v2(self.path):
                self.version = 2
            else:
                msg = "{} is neither a v1 nor v2 timestream.".format(self.path)
                LOG.error(msg)
                raise ValueError(msg)
        if self.version == 1:
            manifest = ts_guess_manifest_v1(self.path)
            self._set_metadata(**manifest)
            for key in TS_MANIFEST_KEYS:
                self.data[key] = manifest[key]
        elif self.version == 2:
            raise NotImplementedError(
                "No OOP interface to timestream v2 format")
        else:
            msg = "{} is neither a v1 nor v2 timestream.".format(self.path)
            LOG.error(msg)
            raise ValueError(msg)

    def _set_metadata(self, **metadata):
        """Sets class members from ``metadata`` dict, first validating it."""
        metadata = validate_timestream_manifest(metadata)
        for datum, value in metadata.items():
            setattr(self, datum, value)

    def iter_by_files(self, ignored_timestamps=[]):
        for fpath in all_files_with_ext(
                self.path, self.extension, cs=False):
            img = TimeStreamImage()
            img.parent_timestream = self
            img.path = fpath
            img_date = ts_format_date(img.datetime)

            # skip images in ignored_timestamps
            if img_date in ignored_timestamps:
                LOG.info("Skip processing data at {}".format(img.datetime))
                continue

            try:
                img.data = self.image_data[img_date]
            except KeyError:
                img.data = {}
            yield img

    def iter_by_timepoints(self, remove_gaps=True, start=None, end=None,
                           interval=None, start_hour=None, end_hour=None,
                           ignored_timestamps=[]):
        """
        Iterate over a TimeStream in chronological order, yielding a
        TimeStreamImage instance for each timepoint. If ``remove_gaps`` is
        False, yield None for missing images.
        """
        if not start or start < self.start_datetime:
            start = self.start_datetime
        if not end or end > self.end_datetime:
            end = self.end_datetime
        if not interval:
            interval = self.interval

        # fix hour range if given
        if start_hour is not None:
            start = dt.datetime.combine(start.date(), start_hour)
        if end_hour is not None:
            end = dt.datetime.combine(end.date(), end_hour)

        # iterate thru times
        for time in iter_date_range(start, end, interval):
            # skip images in ignored_timestamps
            if ts_format_date(time) in ignored_timestamps:
                LOG.info("Skip processing data at {}".format(time))
                continue

            # apply hour range if given
            if start_hour is not None:
                hrstart = dt.datetime.combine(time.date(), start_hour)
                if time < hrstart:
                    continue
            if end_hour is not None:
                hrend = dt.datetime.combine(time.date(), end_hour)
                if time > hrend:
                    continue

            # Format the path below the ts root
            relpath = _ts_date_to_path(self.name, self.extension, time, 0)
            # Join to make "absolute" path, i.e. path including ts_path
            img_path = path.join(self.path, relpath)
            # not-so-silently fail if we can't find the image
            if path.exists(img_path):
                LOG.debug("Image at {} in {} is {}.".format(time, self.path,
                                                            img_path))
            else:
                LOG.debug("Expected image {} at {} did not exist.".format(
                    img_path, time, self.path))
                img_path = None
            if remove_gaps and img_path is None:
                continue
            elif img_path is None:
                img = TimeStreamImage(dt=time)
                img.pixels = np.array([])
                yield img
            else:
                img = self.load_pickled_image(time)
                if img is None:
                    img = TimeStreamImage(dt=time)
                img.parent_timestream = self
                img.path = img_path

                try:
                    img_date = ts_format_date(img.datetime)
                    img.data = self.image_data[img_date]
                except KeyError:
                    img.data = {}
                yield img


class TimeStreamTraverser(TimeStream):

    def __init__(self, ts_path=None, version=None, interval=None,
                 start=None, end=None, start_hour=None, end_hour=None,
                 ignored_timestamps=[]):
        """Class to got back and forth on a TimeStream

        Use This class when you need to traverse the timestream both forwards
        and backwards in time.

        Args:
          version(int): Passed directly to TimeStream
          interval(int): Interval between time stamps
          start(datetime): Start of time stream
          end(datetime): End of time stream
          start_hour(datetime): Starting hour within every day of time stream
          end_hour(datetime): Ending hour within every day of time stream
          ignored_timestamps(list): List of ignore time stamps.0

        Attributes:
          _timestamps(list): List of strings that index all existing image files
            in this timestream
          _offset(int): Current offset within _timestamps.

        """
        super(TimeStreamTraverser, self).__init__(version=version)
        self.load(ts_path)

        self._offset = 0
        self._timestamps = []
        # FIXME: Following is practically equal to
        # TimeStream.iter_by_timepoints.
        if not start or start < self.start_datetime:
            start = self.start_datetime
        if not end or end > self.end_datetime:
            end = self.end_datetime
        if not interval:
            interval = self.interval

        # fix hour range if given
        if start_hour is not None:
            start = dt.datetime.combine(start.date(), start_hour)
        if end_hour is not None:
            end = dt.datetime.combine(end.date(), end_hour)

        # iterate thru times
        for time in iter_date_range(start, end, interval):
            # skip images in ignored_timestamps
            if ts_format_date(time) in ignored_timestamps:
                continue

            # apply hour range if given
            if start_hour is not None:
                hrstart = dt.datetime.combine(time.date(), start_hour)
                if time < hrstart:
                    continue
            if end_hour is not None:
                hrend = dt.datetime.combine(time.date(), end_hour)
                if time > hrend:
                    continue

            # If path exists add index to _timestamps
            relpath = _ts_date_to_path(self.name, self.extension, time, 0)
            img_path = path.join(self.path, relpath)
            if path.exists(img_path):
                self._timestamps.append(time)

    def next(self):
        if self._offset == len(self._timestamps) - 1:
            self._offset = 0

        return self.curr()

    def prev(self):
        if self._offset == 0:
            self._offset = len(self._timestamps) - 1

        return self.curr()

    def curr(self):
        time = self._timestamps[self._offset]
        relpath = _ts_date_to_path(self.name, self.extension, time, 0)
        img_path = path.join(self.path, relpath)

        img = self.load_pickled_image(time)
        if img is None:
            img = TimeStreamImage(dt=time)

        img.parent_timestream = self
        img.path = img_path

        try:
            img_date = ts_format_date(img.datetime)
            img.data = self.image_data[img_date]
        except KeyError:
            img.data = {}

        return img


class TimeStreamImage(object):
    """Class to represent an image in a TimeSeries.

       Attributes:
          datetime(datetime): The timestamp for this image
          timestream(TimeStream): The stream that this image is related to.
          path(str): This class is driven by _path. _path should be valid at
            end of all methods.!!
          pixels(ndarray): The actual image.
          ipm(ImagePotMatrix): The ImagePotMatrix instance should contain all
            the pot specific data for this image.
          data(dict): related data.
    """

    def __init__(self, dt=None):
        """Initialise a TimeStreamImage

        :param dt: The timestamp for this image.
        :type dt: datetime.datetime object
        """
        self._datetime = None
        if dt:
            self._datetime = ts_parse_date(dt)
        self._timestream = None
        self._path = None
        self._pixels = None
        self._ipm = None
        self.data = {}

    def clone(self, copy_pixels=False, copy_path=False, copy_timestream=False):
        """Make an exact copy of ``self`` in a new instance.

        By default, the members pixels, path and timestream are not copied. All
        members are copied by value, not by reference, so can be changed.

        :param copy_pixels: Should we copy pixels?
        :type copy_pixels: Boolean
        :param copy_path: Should we copy path?
        :type copy_path: Boolean
        :param copy_timestream: Should we copy timestream?
        :type copy_timestream: Boolean
        :returns: A copy of self.
        :rtype: TimeStreamInstance
        """
        new = TimeStreamImage()
        new._datetime = deepcopy(self._datetime)
        new.data = deepcopy(self.data)
        if copy_pixels and self.pixels is not None:
            new._pixels = self._pixels.copy()
        if copy_timestream:
            new._timestream = self._timestream
        if copy_path:
            new._path = self._path
        return new

    def write(self, fpath=None, overwrite=False):
        # Don't let _pixels auto-reset in this method.
        if fpath is not None and not isinstance(fpath, str):
            msg = "fpath must be string"
            LOG.error(msg)
            raise TypeError(msg)
        # We default to whatever we have in _path
        if fpath is None and self._path is None:
            msg = "There is no default path to write to"
            LOG.error(msg)
            raise RuntimeError(msg)
        if not fpath:
            fpath = self._path
        # We assume that there is something in _pixels to write
        if self._pixels is None:
            msg = "Image pixels must be set to write"
            LOG.error(msg)
            raise RuntimeError(msg)

        if path.exists(fpath) and not overwrite:
            msg = "Path {} exists and overwrite is {}".format(fpath, overwrite)
            LOG.error(msg)
            raise RuntimeError(msg)

        # from this point we are overwriting
        if path.isfile(fpath):
            os.remove(fpath)

        if not path.exists(path.dirname(fpath)):
            os.makedirs(path.dirname(fpath))

        cv2.imwrite(fpath, self._pixels[:, :, ::-1])

        # Once we have written its ok to set property
        self.path = fpath

    def read(self, fpath=None):
        """This will refresh pixels

        It differers from pixels in that it always replaces _pixels.
        """
        if fpath is None:
            fpath = self._path

        if not path.isfile(fpath):
            msg = "No file exists at {}. ".format(fpath) + \
                  "``path`` of TimeStreamImage must point to existing file"
            LOG.error(msg)
            raise ValueError(msg)

        try:
            import skimage.io
            try:
                self._pixels = skimage.io.imread(fpath, plugin="freeimage")
            except (RuntimeError, ValueError) as exc:
                LOG.error(str(exc))
                self._pixels = None
        except ImportError:
            LOG.warn("Couln't load scikit image io module. " +
                     "Raw images will not be loaded correctly")
            self._pixels = cv2.imread(fpath)[:, :, ::-1]

        self.path = fpath

    @property
    def path(self):
        if self._path:
            return self._path
        if self._timestream:
            ts_path = None
            try:
                if self._timestream.version == 1:
                    ts_path = self._timestream.path
            except AttributeError:
                pass
            if not ts_path or not self._datetime:
                return None
            subpath = _ts_date_to_path(self._timestream.name,
                                       self._timestream.extension,
                                       self._datetime)
            self._path = path.join(ts_path, subpath)
            return self._path
        return None

    @path.setter
    def path(self, img_path):
        # Set image path
        if not isinstance(img_path, str):
            msg = "Image path must be an instance of str."
            LOG.error(msg)
            raise TypeError(msg)
        # FIXME: breaks relation with _datetime and _timestream
        self._path = img_path

    @property
    def ipm(self):
        return self._ipm

    @ipm.setter
    def ipm(self, ipm):
        if not isinstance(ipm, ImagePotMatrix):
            msg = "ipm should be an instance of ImagePotMatrix"
            LOG.error(msg)
            raise TypeError(msg)

        # for consistency, self and ipm.image be the same instance
        if self is not ipm.image:
            msg = "The TimeStreamImage needs to be the same as ipm.image"
            LOG.error(msg)
            raise RuntimeError(msg)

        self._ipm = ipm

    @property
    def parent_timestream(self):
        return self._timestream

    @parent_timestream.setter
    def parent_timestream(self, ts):
        if not isinstance(ts, TimeStream) and ts is not None:
            msg = "Parent timestream must be an instance of TimeStream."
            LOG.error(msg)
            raise TypeError(msg)

        # Special case where we want to leave TimeStreamImage without a
        # _timestream. When ts==None, we leave evertying (_*) untouched
        if ts is not None:
            # If _timestream changes, _path changes.
            self._path = None

        self._timestream = ts

    @property
    def datetime(self):
        if self._datetime:
            return self._datetime

        if not self._path:
            return None
        try:
            self._datetime = ts_parse_date_path(self._path)
        except ValueError:
            self._datetime = get_exif_date(self._path)

        return self._datetime

    @datetime.setter
    def datetime(self, dte):
        self._datetime = ts_parse_date(dte)
        self._path = None

    @datetime.deleter
    def datetime(self):
        del self._datetime

    @property
    def pixels(self):
        """
        Lazy-loading pixel property.

        The path of the image must be set before the pixels property is
        accessed, or things will error out with RuntimeError.

        The colour dimension maps to:
            [:,:,RGB]
        not what OpenCV gives us, which is:
            [:,:,BGR]
        So we convert OpenCV back to reality and sanity.
        """
        if self._pixels is None:
            if not self.path:
                msg = "``path`` member of TimeStreamImage must be set " + \
                      "before ``pixels`` member is accessed."
                LOG.error(msg)
                raise RuntimeError(msg)

            self.read(self._path)
        return self._pixels

    @pixels.setter
    def pixels(self, value):
        if not isinstance(value, np.ndarray):
            msg = "Cant set TimeStreamImage.pixels to something not an ndarray"
            LOG.error(msg)
            raise TypeError(msg)

        self._pixels = value

    @pixels.deleter
    def pixels(self):
        del self._pixels

    def strip(self):
        """Used to strip before pickling"""
        self._pixels = None
        if self._ipm:
            self._ipm.strip()

    @classmethod
    def pickledump(cls, tsi, filepath, overwrite=False):
        if not isinstance(tsi, TimeStreamImage):
            msg = "Object must be instance of TimeStreamImage"
            LOG.error(msg)
            raise TypeError(msg)
        if not isinstance(filepath, str):
            msg = "Filepath should be a string"
            LOG.error(msg)
            raise TypeError(msg)
        if path.exists(filepath) and not overwrite:
            msg = "File {} exists and we should not overwrite".format(filepath)
            LOG.error(msg)
            raise RuntimeError(msg)

        # make sure we strip away everythin that is unneeded.
        tsi.strip()

        f = file(filepath, "w")
        cPickle.dump(tsi, f)
        f.close()

    @classmethod
    def pickleload(cls, filepath):
        if not isinstance(filepath, str):
            msg = "Filepath should be a string"
            LOG.error(msg)
            raise TypeError(msg)
        if not path.exists(filepath):
            msg = "File {} not found".format(filepath)
            LOG.error(msg)
            raise RuntimeError(msg)

        f = file(filepath, "w")
        tsi = cPickle.load(f)
        f.close()

        if not isinstance(tsi, TimeStreamImage):
            msg = "Object must be instance of TimeStreamImage"
            LOG.error(msg)
        return tsi
