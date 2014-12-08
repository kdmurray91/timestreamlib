#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2014
# Author(s): Chuong Nguyen <chuong.v.nguyen@gmail.com>
#            Joel Granados <joel.granados@gmail.com>
#            Kevin Murray <kevin@kdmurray.id.au>
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

from __future__ import absolute_import, division, print_function

from timestream.manipulate import PCException

import sys
import os
import timestream
import logging
import timestream.manipulate.configuration as pipeconf
import timestream.manipulate.pipeline as pipeline
import datetime
from docopt import (docopt, DocoptExit)

HAVE_QT = False
try:
    from PyQt4 import (QtGui, QtCore, uic)
    from _pipeline_gui import PipelineRunnerGUI, maingui
    HAVE_QT = True
except ImportError:
    HAVE_QT = False


def genConfig(opts):
    # Pipeline configuration
    if opts['-p'] is not None:
        plConfPath = opts['-p']
    elif opts['-i'] is not None:
        plConfPath = os.path.join(opts['-i'], '_data', 'pipeline.yml')
    else:
        raise RuntimeError("Invalid argument configuration")
    if not os.path.isfile(plConfPath):
        raise RuntimeError("%s is not a file" % plConfPath)

    plConf = pipeconf.PCFGConfig(plConfPath, 2)
    plConf.setVal("general.plConfPath", plConfPath)

    # override general.inputRootPath in opts['-p'] if any.
    if opts['-i'] is not None:
        if os.path.isfile(opts['-i']):
            raise RuntimeError("%s is a file. Expected a dir" % opts['-i'])
        if not os.path.exists(opts['-i']):
            raise RuntimeError("%s does not exists" % opts['-i'])
        plConf.general.setVal("inputRootPath", opts['-i'])

    # Add timestream configuration if we find one
    if opts['-t']:
        tsConfPath = opts['-t']
    else:
        tsConfPath = os.path.join(plConf.general.inputRootPath,
                                  '_data', 'timestream.yml')
    if os.path.isfile(tsConfPath):
        # 2 is the depth of the configuration file
        plConf.append(tsConfPath, 2)
        plConf.general.setVal("tsConfPath", tsConfPath)

    # Add whatever came in the command line
    if opts['--set']:
        for setelem in opts["--set"].split(','):
            try:
                cName, cVal = setelem.split("=")
                plConf.setVal(cName, cVal)
            except:
                raise RuntimeError("Error in the --set string")

    if opts['-o']:
        if os.path.isfile(opts['-o']):
            raise RuntimeError("%s is a file" % opts["-o"])
        plConf.general.setVal("outputRootPath", opts["-o"])

    plConf.autocomplete()
    plConf.validate()
    plConf.lock()

    return plConf


def createOutputs(plConf):
    if not plConf.hasSubSecName("general") \
            or not plConf.general.hasSubSecName("outputRootPath"):
        raise RuntimeError("Configuration missing outputRootPath")
    if not os.path.exists(plConf.general.outputRootPath):
        os.makedirs(plConf.general.outputRootPath)


def initlogging(opts):
    # 1. We init verbosity. log to console by default.
    if opts["-v"] == 0 or opts["-v"] == 1:
        vbsty = timestream.LOGV.V
    elif opts["-v"] == 2:
        vbsty = timestream.LOGV.VV
    elif opts["-v"] == 3:
        vbsty = timestream.LOGV.VVV
    if opts["-s"]:  # Silent will trump all
        vbsty = timestream.LOGV.S
        return

    outlog = timestream.add_log_handler(verbosity=vbsty)
    if outlog is os.devnull:
        raise RuntimeError("Error setting up output to console")

    if "--logfile" in opts.keys():
        f = opts["--logfile"]
        outlog = timestream.add_log_handler(stream=f, verbosity=vbsty)
        if outlog is os.devnull:
            raise RuntimeError("Error setting log to file {}".format(f))


def genContext(plConf):
    if not plConf.hasSubSecName("outstreams") \
            or not plConf.hasSubSecName("general"):
        raise RuntimeError("Error while generating context")

    # Initialize the context
    ctx = pipeconf.PCFGSection("--")

    # create new timestream for output data
    for k, outstream in plConf.outstreams.asDict().iteritems():
        ts_out = timestream.TimeStream()
        ts_out.data["settings"] = plConf.asDict()
        # ts_out.data["settingPath"] = os.path.dirname(settingFile)
        ts_out.data["sourcePath"] = plConf.general.inputRootPath
        ts_out.name = outstream["name"]

        # timeseries output input path plus a suffix
        tsoutpath = os.path.abspath(plConf.general.outputPrefixPath) \
            + outstream["name"]
        if "outpath" in outstream.keys():
            tsoutpath = outstream["outpath"]
        if not os.path.exists(tsoutpath) \
                or len(os.listdir(os.path.join(tsoutpath, '_data'))) == 0:
            ts_out.create(tsoutpath)
        else:
            ts_out.load(tsoutpath)
        ctx.setVal("outts."+outstream["name"], ts_out)

    ctx.setVal("outputPrefixPath", plConf.general.outputPrefixPath)
    ctx.setVal("outputPrefix", plConf.general.outputPrefix)

    if not ctx.hasSubSecName("outts"):
        raise RuntimeError("Could not identify output timestreams")

    return ctx


def genExistingTS(ctx):
    existing_ts = []
    for tsname in ctx.outts.listSubSecNames():
        ts_out = ctx.outts.getVal(tsname)
        existing_ts.append(ts_out.image_data.keys())

    existing_ts = list(set([item for sl in existing_ts for item in sl]))
    return existing_ts


def genInputTimestream(plConf, existing_ts):
    # FIXME: This should not go here. It should be in the genConfig method.
    sd = plConf.general.startDate
    if sd is not None:
        sd = datetime.datetime(sd.year, sd.month, sd.day,
                               sd.hour, sd.minute, sd.second)
    ed = plConf.general.endDate
    if ed is not None:
        ed = datetime.datetime(ed.year, ed.month, ed.day,
                               ed.hour, ed.minute, ed.second)

    # FIXME: This should not go here. It should be in the genConfig method.
    sr = plConf.general.startHourRange
    if sr is not None:
        sr = datetime.time(sr.hour, sr.minute, sr.second)
    er = plConf.general.endHourRange
    if er is not None:
        er = datetime.time(er.hour, er.minute, er.second)
    # initialise input timestream for processing
    ts = timestream.TimeStreamTraverser(
        ts_path=plConf.general.inputRootPath,
        interval=plConf.general.timeInterval,
        start=sd,
        end=ed,
        start_hour=sr,
        end_hour=er,
        existing_ts=existing_ts,
        err_on_access=True)
    # FIXME: asDict because it cannot be handled by json.
    ts.data["settings"] = plConf.asDict()
    return ts


# Avoid repeating code in cli and gui
def initPipeline(LOG, opts):
    # configuration
    plConf = genConfig(opts)
    createOutputs(plConf)
    LOG.info(str(plConf))

    # context
    ctx = genContext(plConf)
    for tsname in ctx.outts.listSubSecNames():
        ts_out = ctx.outts.getVal(tsname)
        LOG.info("Output timestream instance:")
        LOG.info("   ts_out.path: {}".format(ts_out.path))

    # Skiping
    existing_ts = []
    if not opts["--recalculate"]:
        existing_ts = genExistingTS(ctx)
    LOG.info("Skipping time stamps {}".format(existing_ts))

    # initialise input timestream for processing
    ts = genInputTimestream(plConf, existing_ts)
    ctx.setVal("ints", ts)
    LOG.info(str(ts))

    # initialise processing pipeline
    pl = pipeline.ImagePipeline(plConf.pipeline, ctx)

    return (plConf, ctx, pl, ts)


# Enclose in a class to be able to stop it
class PipelineRunner(object):

    def __init__(self):
        self.running = False

    def runPipeline(self, plConf, ctx, ts, pl, LOG, prsig=None, stsig=None):
        self.running = True
        for i in range(len(ts.timestamps)):
            if prsig is not None:
                prsig.emit(i)
            timestamp = ts.timestamps[i]
            try:
                img = ts.getImgByTimeStamp(timestamp, update_index=True)
                # Detach img from timestream. We don't need it!
                img.parent_timestream = None
                LOG.info("Process {} ...".format(img.path))
            except PCException as pcex:
                # Propagate PCException to components.
                img = pcex

            try:
                pl.process(ctx, [img], plConf.general.visualise)
            except PCException as bip:
                LOG.info(bip.message)
                continue

            if not self.running:
                break
        LOG.info("Done")
        if stsig is not None:
            stsig.emit()


def maincli(opts):
    try:
        # logging, re-initialize with user options.
        initlogging(opts)
        LOG = logging.getLogger("timestreamlib")

        plConf, ctx, pl, ts = initPipeline(LOG, opts)

        pr = PipelineRunner()
        pr.runPipeline(plConf, ctx, ts, pl, LOG)
    except RuntimeError as re:
        raise DocoptExit(str(re))


def maindoc(opts):
    if opts["--conf"]:
        print(pipeconf.PCFGConfig.info())

    if opts["--comp"]:
        for cname, ccomp in pipeline.ImagePipeline.complist.iteritems():
            print(ccomp.info())

OPTS = """
USAGE:
    run-pipeline (-i IN | -p YML | -i IN -p YML)
                 [-o OUT] [-t YML]
                 [-v | -vv | -vvv | -s] [--logfile=FILE]
                 [--recalculate] [--set=CONFIG]
    run-pipeline (-d | --doc) [--conf] [--comp]
    run-pipeline (-g | --gui)
    run-pipeline (-h | --help)

OPTIONS:
    -h --help   Show this screen.
    -g --gui    Open the QT Graphical User Interface
    -d --doc    Output documentation of components or configuration file.
    -i IN       Input timestream directory. IN will take precedence over any
                input directory in pipeline yaml configuration. If not
                defined, we search for IN in the pipeline yaml configuration.
    -o OUT      Output root. Where results will be created.
    -p YML      Path to pipeline yaml configuration. Defaults to
                IN/_data/pipeline.yml
    -t YML      Path to timestream yaml configuration. Defaults to
                IN/_data/timestream.yml
    -v          Level 1 verbosity: Simple process information
    -vv         Level 2 verbosity: same as -v but with timestamps
    -vvv        Level 3 verbosity: for  debugging. Will output file, function
                name, timestamps and additional debuggin information.
    -s          Silent verbosity: Remove all output logging.
    --logfile=FILE   If given, log to FILE with given verbosity.
    --set=CONFIG     Overwrite any configuration value. CONFIG is a coma (,)
                     separated string of name=value pairs.
                     E.g: --set=a.b=value,c.d.e=val2
    --recalculate    By default we don't re-calculate images. Passing this
                     option forces recalculation
    --conf           If set we output the documentation for the configuration
                     files.
    --comp           If set we output the documentation for all active
                     components.
"""


def main():
    opts = docopt(OPTS)
    if opts["-i"] is not None or opts["-p"] is not None:
        maincli(opts)
    elif opts["--gui"]:
        if HAVE_QT:
            maingui(opts)
        else:
            raise ImportError("Couldn't import PyQT4. Please install it")
    elif opts["--doc"]:
        maindoc(opts)
    else:
        raise DocoptExit()

if __name__ == "__main__":
    main()
