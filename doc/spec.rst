.. _spec-ts:

********************************
Timestream Format Specifications
********************************

The timestream format is a way of structuring image files that allows for
simple, time-indexed, access to images in an image series. Traditionally (i.e.
in version 1 timestreams) this has been a simple folder hierarchy. Moving
forward (i.e. version 2 timestreams), timestreams will be stored in
`BagIt <https://en.wikipedia.org/wiki/BagIt>`_ objects. This will allow more
scalable storage of long time series.



.. _spec-ts-v1:

The Timestream Format (Version 1)
=================================

A timestream refers to the root directory containing the folder hierarchy
detailed below. A timestream may optionally contain a single file --
``timestream.json`` -- containing the "manifest", a data structure defining
certain timestream metadata.



.. _spec-ts-v1-folders:

Timestream Version 1 Folder Hierarchy
-------------------------------------

In the following diagram, folder levels are on different lines, parseable
keywords are enclosed in ``< >``, and ``strptime``/``strftime`` date format
specifiers are used to represent date components. All other characters are
literal.

::

    <name>/
    .     /%Y/
    .        /%Y_%m/
    .              /%Y_%m_%d/
    .                       /%Y_%m_%d/
    .                                /%Y_%m_%d_%H/
    .                                            /<name>_%Y_%m_%d_%H_%M_%S_<n>.<ext>

Named timestream parameters:

* ``<name>``: Timestream name. May contain any ASCII character except ' '
  (space) and '_' and any character which requires escaping on NTFS or EXT4
  filesystems (mostly these: ``/\$()[]{}^"'```) and all non-printing
  characters.
* ``<n>``: A sub-second counter. Valid values are ``00``-``99``. Use ``printf``
  specifier ``%02d`` or similar to format this field.
* ``<ext>``: File extension of files in timestream. This must be uniform across
  all images in timestream. It must be three alphanumeric characters. It may be
  capitalised, and parsers should be case insensitive. Examples of valid
  formats include ``JPG``, ``png``, and ``CR2``.



.. _spec-ts-manifests:

Timestream Manifests
====================

The timestream manifest file is a file containing a, valid, parsable JSON
object. The fields of this object are layed out below. All fields are required.
Additionally, all fields must contain a valid value unless otherwise specified.

==================  ==========  ===============================================
Key                 JSON Type   Description
==================  ==========  ===============================================
``name``            ``string``  The name of the timestream. May contain any
                                ASCII character except ' ' and '_' and any
                                character which requires escaping on NTFS or
                                EXT4 filesystems (mostly these:
                                ``/\$()[]{}^"'```) and all non-printing
                                characters.
``version``         ``string``  The timestreams' version. Valid values are "1"
                                and "2".
``start_datetime``  ``string``  The first timepoint in the time series.
                                This is encoded as a string using the following
                                ISO 8601 format string: ``%Y-%m-%dT%H:%M:%S%z``
``end_datetime``    ``string``  The final timepoint in the time series.
                                Encoded as a string per ``start_datetime``
                                above.
``image_type``      ``string``  The image type of timestreams. This
                                corresponds to the ``<ext>`` field discussed in
                                :ref:`spec-ts-v1-folders` .
``missing_images``  ``array``   An array of timepoints at which no image
                                exists, encoded as a string per
                                ``start_datetime`` above. This array may be
                                empty.
``bookmarks``       ``array``   An array of objects containing descriptions of
                                the bookmarks within the timestream. The format
                                of these objects is described in
                                :ref:`spec-ts-manifests-bookmarks`.
``numeric_data``    ``array``   An array of objects that describe optional
                                numeric data files. The format of these objects
                                is described in
                                :ref:`spec-ts-manifests-numericdata`.
==================  ==========  ===============================================


.. _spec-ts-manifests-bookmarks:

Bookmark Objects
----------------

The format of a timestream bookmark object within the timestream manifest
object is detailed below. All fields are required. Additionally, all fields
must contain a valid value unless otherwise specified.



.. _spec-ts-manifests-numericdata: 

Numeric Data Objects
--------------------

The format of a timestream numeric data object within the timestream manifest
object is detailed below. All fields are required. Additionally, all fields
must contain a valid value unless otherwise specified.

* TODO



.. _spec-webapi:

********************
Timestream Flask API
********************

In the future, there will be a web API to access timestreams. This section will
provide the specification for this, once written.
