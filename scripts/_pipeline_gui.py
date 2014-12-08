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
from PyQt4 import (QtGui, QtCore, uic)


class PipelineRunnerGUI(QtGui.QMainWindow):
    class TextEditStream:
        def __init__(self, sig):
            self._sig = sig

        def write(self, m):
            self._sig.emit(m)

    class TextEditSignal(QtCore.QObject):
        sig = QtCore.pyqtSignal(str)

    class ProgressSignal(QtCore.QObject):
        sig = QtCore.pyqtSignal(int)  # offset of progress

    class ThreadStopped(QtCore.QObject):
        sig = QtCore.pyqtSignal()

    class PipelineThread(QtCore.QThread):

        def __init__(self, plConf, ctx, ts, pl,
                     log, prsig, stsig, parent=None):
            QtCore.QThread.__init__(self, parent)
            self._plConf = plConf
            self._ctx = ctx
            self._ts = ts
            self._pl = pl
            self._log = log
            self._prsig = prsig
            self._stsig = stsig
            self._pr = None
            self._running = False

        def setRunning(self, val):
            self._running = val
            if self._pr is not None:
                self._pr.running = self._running

        def run(self):
            self._running = True
            self._pr = PipelineRunner()
            self._pr.runPipeline(self._plConf, self._ctx, self._ts,
                                 self._pl, self._log, prsig=self._prsig,
                                 stsig=self._stsig)

    def __init__(self, opts):
        QtGui.QMainWindow.__init__(self)
        self._ui = uic.loadUi("_pipeline_guiui")
        self._opts = opts
        self.tesig = PipelineRunnerGUI.TextEditSignal()
        self.tesig.sig.connect(self._outputLog)
        self.prsig = PipelineRunnerGUI.ProgressSignal()
        self.prsig.sig.connect(self._updateProgress)
        self.stsig = PipelineRunnerGUI.ThreadStopped()
        self.stsig.sig.connect(self._threadstopped)

        # Hide the progress bar stuff
        self._ui.pbpl.setVisible(False)
        self._ui.bCancel.setVisible(False)

        # buttons
        self._ui.bCancel.clicked.connect(self._cancelRunPipeline)
        self._ui.bRunPipe.clicked.connect(self._runPipeline)
        self._ui.bAddInput.clicked.connect(self._addInput)
        self._ui.bAddOutput.clicked.connect(self._addOutput)
        self._ui.bPipeConfig.clicked.connect(self._addPipeline)
        self._ui.bTSConfig.clicked.connect(self._addTimeStream)

        # pipeline thread
        self._plthread = None
        self._ui.show()

    def _addDir(self):
        D = QtGui.QFileDialog.getExistingDirectory(
            self, "Select Directory", "",
            QtGui.QFileDialog.ShowDirsOnly
            | QtGui.QFileDialog.DontResolveSymlinks)
        if D == "":  # Handle the cancel
            return ""

        D = os.path.realpath(str(D))
        if not os.path.isdir(D):
            errmsg = QtGui.QErrorMessage(self)
            errmsg.showMessage("Directory {} does not exist".format(D))
            return ""
        else:
            return D

    def _addFile(self):
        F = QtGui.QFileDialog.getOpenFileName(
            self, "Select YAML configuration", "", "CSV (*.yml *.yaml)")
        if F == "":
            return ""

        if not os.path.isfile(F):
            errmsg = QtGui.QErrorMessage(self)
            errmsg.showMessage("{} is not a file".format(F))
            return ""
        else:
            return F

    def _addInput(self):
        tsdir = self._addDir()
        if tsdir != "":
            self._opts["-i"] = str(tsdir)
            self._ui.leInput.setText(str(tsdir))
        else:
            del(self._opts["-i"])
            self._ui.leInput.setText("")
        return tsdir

    def _addOutput(self):
        outdir = self._addDir()
        if outdir != "":
            self._opts["-o"] = str(outdir)
            self._ui.leOutput.setText(str(outdir))
        else:
            del(self._opts["-o"])
            self._ui.leOutput.setText("Default")
        return outdir

    def _addPipeline(self):
        plfile = self._addFile()
        if plfile != "":
            self._opts["-p"] = str(plfile)
            self._ui.lePipeConfig.setText(str(plfile))
        else:
            del(self._opts["-p"])
            self._ui.lePipeConfig.setText("Default")
        return plfile

    def _addTimeStream(self):
        tsfile = self._addFile()
        if tsfile != "":
            self._opts["-t"] = str(tsfile)
            self._ui.leTSConfig.setText(str(tsfile))
        else:
            del(self._opts["-t"])
            self._ui.leTSConfig.setText("Default")
        return tsfile

    def _cancelRunPipeline(self):
        if self._plthread is not None:
            self._plthread.setRunning(False)

    def _threadstopped(self):
        self._ui.pbpl.setValue(self._ui.pbpl.maximum())
        self._ui.pbpl.setVisible(False)
        self._ui.bCancel.setVisible(False)

    def _outputLog(self, m):
        self._ui.teOutput.append(QtCore.QString(m))

    def _updateProgress(self, i):
        self._ui.pbpl.setValue(i)
        QtGui.qApp.processEvents()

    def _runPipeline(self):
        if self._plthread is not None and self._plthread._running:
            return

        if "-i" not in self._opts.keys() or self._opts["-i"] is None:
            retVal = self._addInput()
            if retVal == "":
                return

        # log to QTextEdit
        stream = PipelineRunnerGUI.TextEditStream(self.tesig.sig)
        outlog = timestream.add_log_handler(
            stream=stream,
            verbosity=timestream.LOGV.VV)
        if outlog is os.devnull:
            errmsg = QtGui.QErrorMessage(self)
            errmsg.showMessage("Error setting up output to TextEdit")
            return
        LOG = logging.getLogger("timestreamlib")

        plConf, ctx, pl, ts = initPipeline(LOG, self._opts)

        self._ui.pbpl.setVisible(True)
        self._ui.bCancel.setVisible(True)
        self._ui.pbpl.setMinimum(0)
        self._ui.pbpl.setMaximum(len(ts.timestamps))
        self._ui.pbpl.reset()

        self._plthread = PipelineRunnerGUI.PipelineThread(
            plConf, ctx, ts, pl, LOG, self.prsig.sig,
            self.stsig.sig, parent=self)
        self._plthread.start()


def maingui(opts):
    app = QtGui.QApplication(sys.argv)
    PipelineRunnerGUI(opts)
    app.exec_()
    app.deleteLater()
    sys.exit()
