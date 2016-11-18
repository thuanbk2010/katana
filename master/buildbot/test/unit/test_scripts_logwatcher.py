# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Unity Technologies

import os

from twisted.python.failure import Failure

from buildbot.test.util import dirs
from twisted.trial import unittest

from buildbot.scripts.logwatcher import LogWatcher, BuildmasterTimeoutError


class TimeStepLogWatcher(LogWatcher):
    """Helper class for deterministically verifying timeout logic of the LogWatcher.

    Time is handled discretely by an integer, and timeout likewise. Every time the
    timeout is reset, the timeoutSteps is increased by the original amount of steps
    for a timeout. Each time a line is received, the time is increased by one.

    This is not a completely realistic test of LogWatcher, but it's the closest
    approximation that makes sense to unit test.
    """

    def __init__(self, logFile, timeoutSteps, finishedFunc):
        LogWatcher.__init__(self, logFile)
        self.origTimeoutSteps = timeoutSteps
        self.timeoutSteps = timeoutSteps
        self.time = 0
        self.finished = finishedFunc
        self.timer = None
        self.running = False

    def start(self):
        self.startTimer()
        self.running = True

    def startTimer(self):
        self.timer = object()

    def lineReceived(self, line):
        self.time += 1
        LogWatcher.lineReceived(self, line)
        if self.timer is None:
            self.timeoutSteps += self.origTimeoutSteps

    def __enter__(self):
        return self

    def __exit__(self, a, b, c):
        if self.isTimedOut():
            self.timeout()

    def timeout(self):
        self.finished(Failure(BuildmasterTimeoutError()))

    def isTimedOut(self):
        return self.timeoutSteps <= self.time


class TestLogwatcher(dirs.DirsMixin, unittest.TestCase):
    def setUp(self):
        self.setUpDirs('basedir')
        self.logFile = os.path.join('basedir', 'twistd.log')

    def test_buildmaster_running_success(self):
        results = []

        def finished(result):
            results.append(result)

        with TimeStepLogWatcher(self.logFile, 5, finished) as lw:
            lw.start()
            lw.lineReceived('BuildMaster is running')

        assert len(results) == 1
        assert results[0] == 'buildmaster'

    def test_buildmaster_running_timeout(self):
        results = []

        def finished(result):
            results.append(result)

        with TimeStepLogWatcher(self.logFile, 1, finished) as lw:
            lw.start()

            lw.lineReceived('y')
            lw.lineReceived('BuildMaster is running')

        assert len(results) == 2
        assert results[0] == 'buildmaster'
        assert results[1].type is BuildmasterTimeoutError

    def test_buildmaster_with_progress(self):
        results = []

        def finished(result):
            results.append(result)

        with TimeStepLogWatcher(self.logFile, 1, finished) as lw:
            lw.start()

            lw.lineReceived('added builder')
            lw.lineReceived('BuildMaster is running')

        assert len(results) == 1, results
        assert results[0] == 'buildmaster'

    def test_buildmaster_attach_is_progress(self):
        results = []

        def finished(result):
            results.append(result)

        with TimeStepLogWatcher(self.logFile, 1, finished) as lw:
            lw.start()

            lw.lineReceived('Buildslave foobarbaz attached to proj-quux')
            lw.lineReceived('BuildMaster is running')

        assert len(results) == 1, results
        assert results[0] == 'buildmaster'
