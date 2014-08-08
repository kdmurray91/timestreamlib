#!/usr/bin/python
#coding=utf-8
# Copyright (C) 2014
# Author(s): Joel Granados <joel.granados@gmail.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import numpy as np
import matplotlib.pyplot as plt
import timestream.manipulate.plantSegmenter as tm_ps

class ImagePotRectangle(object):
    def __init__(self, rectDesc, imgSize, growM=100):
        """ Handles all logic to do with rectangles in images.

        Attribures:
          rectDesc([x,y,x',y'])*: This is the total description of the rectangle:
            upper left corner and lower right corner.
          rectDesc([x,y]): This is the center of a rectangle. We will grow it by
            growM in every direction.
          imgSize([height, width]): Size of the image containing the rectangle.
            Whatever img.shape returns.
          growM(int): The maximum amount (in pixels) when we receive a coordinate.
          * y is vertical | x is horizontal.

        Raises:
          TypeError: When we don't receive a list for a rectangle descriptor.
        """
        self._rect = np.array([-1,-1,-1,-1])

        if not isinstance(imgSize, tuple) or len(imgSize) < 2:
            raise TypeError("ImgSize must be a tuple of at least len 2")
        if True in (np.array(imgSize[0:2])<1):
            raise TypeError("ImgSize elements must be >0")
        self._imgwidth = imgSize[1]
        self._imgheight = imgSize[0]

        if not (isinstance(rectDesc, list) or isinstance(rectDesc, np.array))\
                or (len(rectDesc) != 2 and len(rectDesc) != 4 ):
            raise TypeError("Rectangle Descriptor must be a list of len 2 or 4")

        elif len(rectDesc) == 4:
            self._rect = np.array(rectDesc)

        elif len(rectDesc) == 2:
            pt1 = np.array(rectDesc) - growM
            pt2 = np.array(rectDesc) + growM
            self._rect = np.concatenate((pt1, pt2))

        # Check to see if rect is within size.
        if sum(self._rect < 0) > 0 \
                or sum(self._rect[[1,3]] > self._imgheight) > 0 \
                or sum(self._rect[[0,2]] > self._imgwidth) > 0:
            raise TypeError("Rectangle is outside containing image dims.")

    def __getitem__(self, item):
        if item > 4 or item < 0:
            raise IndexError("Rectangle index should be [0,3]")
        return self._rect[int(item)]

    def asList(self):
        return self._rect

    @property
    def width(self):
        return abs(self._rect[2]-self._rect[0])

    @property
    def height(self):
        return abs(self._rect[3]-self._rect[1])

class ImagePotHandler(object):
    def __init__(self, potID, rect, superImage, \
            metaids=None, ps=None, iphPrev=None):
        """ImagePotHandler: a class for individual pot images.

        Args:
          potID (object): Should be unique between pots. Is given by the
            potMatrix. Is not changeable.
          rect (ImagePotRectangle): [x,y,x`,y`]: (x,y) and (x`,y`)* are reciprocal corners
          superImage (ndarray): Image in which the image pot is located
          ps (PotSegmenter): It can be any child class from PotSegmenter. Its
            instance that has a segment method.
          iphPrev (ImagePotHandler): The previous ImagePotHandler for this pot
            position.
          metaids (dict): info that might be used by the pot image in
            other contexts (e.g {chamberID:#, universalID:#...}). We can only
            bind to a numeric or character value.
          * y is vertical | x is horizontal.

        Attributes:
          image: Return the cropped image (with rect) of superImage
          maskedImage: Return the segmented cropped image.
          features: Return the calculated features

        Raises:
          TypeError: When the Args is of an unexpected type.
        """
        self._id = potID

        # FIXME: This check for ndarray should be for TimestreamImage
        if isinstance(superImage, np.ndarray):
            self.si = superImage
        else:
            raise TypeError("superImate must be an ndarray")

        if not isinstance(rect, ImagePotRectangle):
            raise TypeError("rect must be an instance of ImagePotRectangle")

        self._rect = rect

        if ps == None:
            self._ps = None
        elif isinstance(ps, tm_ps.PotSegmenter):
            self._ps = ps
        else:
            raise TypeError("ps must be an instance of PotSegmenter")

        if iphPrev == None:
            self._iphPrev = None
        elif isinstance(iphPrev, ImagePotHandler):
            self._iphPrev = iphPrev
            # avoid a run on memory
            self._iphPrev.iphPrev = None

            # Don't let previous pot run segmentation code
            self._iphPrev.ps = None
        else:
            raise TypeError("iphPrev must be an instance of ImagePotHandler")

        self._fc = tm_ps.StatParamCalculator()
        self._features = {}
        self._mask = np.zeros( [self._rect.height, self._rect.width], \
                                dtype=np.dtype("float64")) - 1

        if metaids is None:
            self._mids = {}
        elif not isinstance(metaids, dict):
            raise TypeError("Metaids must be dictionary")
        elif len(metaids) < 1:
            self._mids = {}
        else:
            self._mids = metaids
        # Check all metaids are (int, long, float, complex, str)
        for key, val in self._mids.iteritems():
            if not isinstance(val, (int, long, float, complex, str)):
                raise TypeError("Metaids must be of type"\
                        + "int, long, float, complex or string")

    @property
    def iphPrev(self):
        return self._iphPrev

    @iphPrev.setter
    def iphPrev(self, v):
        if v == None:
            self._iphPrev = None
        elif isinstance(v, ImagePotHandler):
            self._iphPrev = v
            # avoid a run on memory
            self._iphPrev.iphPrev = None

            # Don't let previous pot run segmentation code
            self._iphPrev.ps = None
        else:
            raise TypeError("iphPrev must be an instance of ImagePotHandler")

    @property
    def ps(self):
        return self._ps

    @ps.setter
    def ps(self, ps):
        self._ps = ps

    @ps.deleter
    def ps(self):
        self._ps = None

    @property
    def id(self):
        return self._id

    @property # not settable nor delettable
    def image(self):
        return ( self.si[self._rect[1]:self._rect[3],
                            self._rect[0]:self._rect[2], :] )

    def getSegmented(self):
        """Does not change internals of instance

            This method is used to parallelize the pot segmentation
            calculation so we should avoid changing the inner struct
            of the instance.
        """
        # FIXME: here we loose track of the hints
        msk, hint = self._ps.segment(self.image, {})

        # if bad segmentation
        if 1 not in msk and self._iphPrev is not None:
            # We try previous mask. This is tricky because we need to fit the
            # previous mask size into msk
            pm = self._iphPrev.mask

            vDiff = msk.shape[0] - pm.shape[0]
            if vDiff < 0: # reduce pm vertically
                side = True
                for i in range(abs(vDiff)):
                    if side:
                        pm = pm[1:,:]
                    else:
                        pm = pm[:-1,:]
                    side = not side

            if vDiff > 0: # grow pm vertically
                padS = np.array([1,0])
                for i in range(abs(vDiff)):
                    pm = np.lib.pad(pm, (padS.tolist(), (0,0)), 'constant', \
                            constant_values = 0)
                    padS = -(padS-1) # other side

            hDiff = msk.shape[1] - pm.shape[1]
            if hDiff < 0: # reduce pm horizontally
                side = True
                for i in range(abs(hDiff)):
                    if side:
                        pm = pm[:,1:]
                    else:
                        pm = pm[:,:-1]
                    side = not side

            if hDiff > 0: # grow pm horizontally
                padS = np.array([1,0])
                for i in range(abs(hDiff)):
                    pm = np.lib.pad(pm, ((0,0), padS.tolist()), 'constant', \
                            constant_values = 0)
                    padS = -(padS-1) # other side

            msk = pm

        return msk

    @property
    def mask(self):
        if -1 not in self._mask:
            return self._mask

        if self._ps == None:
            return np.zeros(self._mask.shape, np.dtype("float64"))

        self._mask = self.getSegmented()
        return (self._mask)

    @mask.setter
    def mask(self, m):
        if ( not isinstance(m, np.ndarray) \
                or m.dtype != np.dtype("float64") \
                or m.shape != self._mask.shape ):
            raise ValueError("Invalid mask assigment")
        self._mask = m

    @property # not deletable
    def rect(self):
        return (self._rect)

    @rect.setter
    def rect(self, r):
        if isinstance(r, list):
            if len(r) != 4:
                raise TypeError("Pass a list of len 4 to set a rectangle")
            else:
                self._rect = ImagePotRectangle(r, self.si.shape)

        elif isinstance(ImagePotRectangle):
            # The write thing to do here is to create a new Imagepotrectangle so
            # we are sure we relate it to the correct image shape.
            self._rect = ImagePotRectangle(r.asList(), self.si.shape)

        else:
            raise TypeError("To set rectangle must pass list or"
                    + "ImagePotRectangle")


        self._mask = np.zeros( [self._rect.height, self._rect.width],
                                dtype=np.dtype("float64")) - 1
        #FIXME: Reset everything that depends on self._mask

    def maskedImage(self, inSuper=False):
        """Returns segmented pixels on a black background

        inSuper: When True we return the segmentation in the totality of
                 self.si. When False we return it in the rect.
        """
        # We use the property to trigger creation if needed.
        msk = self.mask
        img = self.image

        height, width, dims = img.shape
        msk = np.reshape(msk, (height*width, 1), order="F")
        img = np.reshape(img, (height*width, dims), order="F")

        retVal = np.zeros((height, width, dims), dtype=img.dtype)
        retVal = np.reshape(retVal, (height*width, dims), order="F")

        Ind = np.where(msk)[0]
        retVal[Ind,:] = img[Ind,:]
        retVal = np.reshape(retVal, (height, width, dims), order="F")

        if inSuper:
            superI = self.si.copy()
            superI[self._rect[1]:self._rect[3], \
                       self._rect[0]:self._rect[2], :] = retVal
            retVal = superI

        return (retVal)

    def increaseRect(self, by=5):
        # Using property to trigger assignment, checks and cleanup
        r = self._rect.asList() + np.array([-by, -by, by, by])
        self.rect = r

    def reduceRect(self, by=5):
        # Using property to trigger assignment, checks and cleanup
        r = self._rect.asList() + np.array([by, by, -by, -by])
        self.rect = r

    def calcFeatures(self, feats):
        # Calc all the possible features when feats not specfied
        if not isinstance(feats, list):
            raise TypeError("feats should be a list")

        if "all" in feats:
            feats = tm_ps.StatParamCalculator.statParamMethods()

        for featName in feats:
            # calc not-indexed feats
            if not featName in self._features.keys():
                featFunc = getattr(self._fc, featName)
                self._features[featName] = featFunc(self._mask)

    def getCalcedFeatures(self):
        return self._features

    def getMetaIdKeys(self):
        return self._mids.keys()

    def getMetaId(self, mKey):
        if mkey not in self._mids.keys():
            raise IndexError("%s is not a meta key."%mKey)
        else:
            return self._mids[mKey]
    def setMetaId(self, mKey, mValue):
        if not isinstance(mValue, (int, long, float, complex, str)):
            raise TypeError("Metaids values must be of type"\
                    + "int, long, float, complex or string")
        else:
            self._mids[mKey] = mValue

class ImagePotMatrix(object):
    def __init__(self, image, pots=[], growM=100, ipmPrev = None):
        """ImagePotMatrix: To house all the ImagePotHandlers

        We make sure that their IDs are unique inside the ImagePotMatrix
        instance. If there are two equal ids, one will overwrite the other
        without warning.

        Args:
          image (ndarray): Image in which everything is located
          pots (list): It can be a list of ImagePotHandler instances, of 4
            elment lists or of 2 elment list
          growM (int): The amount of pixels that containing plots should grow if
            they are initialized by a center.
          rects (list): list of tray lists. Each tray list is a list of two
            element sets. The reciprocal corners of the pot rectangle
          ipmPrev (ImagePotMatrix): The previous ImagePotMatrix object.

        Attributes:
          its: Dictionary of image tray instances.
          _pots: Dictionary of pots indexed by pot IDs.
        """
        if ipmPrev == None:
            self.ipmPrev = None
        elif isinstance(ipmPrev, ImagePotMatrix):
            self.ipmPrev = ipmPrev
            # avoid a run on memory
            self.ipmPrev.ipmPrev = None
        else:
            raise TypeError("ipmPrev must be an instance of ImagePotMatrix")

        # We make ImagePotHandler instances with whatever we find.
        if not isinstance(pots, list):
            raise TypeError("pots must be a list")
        potIndex = -1 # Used when creating from rect
        self._pots = {}
        for p in pots:
            if isinstance(p, ImagePotMatrix):
                self._pots[p.id] = p

            elif isinstance(p, list) and (len(p)==2 or len(p)==4):
                iphPrev = None
                if self.ipmPrev is not None:
                    iphPrev = self.ipmPrev.getPot(potIndex)
                r = ImagePotRectangle(pot, image.shape, growM=growM)
                self._pots[potIndex] = ImagePotHandler(potIndex, r, image,
                        iphPrev=iphPrev)
                potIndex -= 1

            else:
                TypeError("Elements in pots must be ImagePotHandler, list" \
                        + " of 2 or 4 elments")

    def getPot(self, potId):
        if potId not in self._pots.keys():
            raise IndexError("No pot id %d found"%potNum)

        return self._pots[potId]

    def addPot(self, pot):
        if not isinstance(pot, ImagePotHandler):
            raise TypeError("Pot must be of type ImagePotHandler")
        iphPrev = None
        if self.ipmPrev is not None:
            iphPrev = self.ipmPrev.getPot(pot.id)
        pot.iphPrev = iphPrev
        self._pots[pot.id] = pot

    @property
    def potIds(self):
        """Returns a list of pot ids"""
        return self._pots.keys()

    def iter_through_pots(self):
        for key, pot in self._pots.iteritems():
            yield(key, pot)

    @property
    def potFeatures(self):
        """ Return a feature name list with all possible features in pots """
        featureNames = []
        for key, pot in self._pots.iteritems():
            for featName in pot.getCalcedFeatures():
                if featName not in featureNames:
                    featureNames.append(featName)

        return (featureNames)

    def show(self):
        """ Show segmented image with the plot squares on top. """
        sImage = self.image
        for key, pot in self._pots.iteritems():
            sImage = sImage & pot.maskedImage(inSuper=True)

        plt.figure()
        plt.imshow(sImage.astype(np.uint8))
        plt.hold(True)

        for key, pot in self._pots.iteritems():
            r = pot.rect
            plt.plot([r[0], r[2], r[2], r[0], r[0]],
                     [r[1], r[1], r[3], r[3], r[1]],
                     linestyle="-", color="r")

        plt.title('Pot Rectangles')
        plt.show()