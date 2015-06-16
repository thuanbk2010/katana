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
# Copyright Buildbot Team Members

from email.Utils import formatdate
import time
import re

from twisted.python import log
from twisted.internet import defer

from buildbot.process import buildstep
from buildbot.steps.shell import StringFileWriter
from buildbot.steps.source.base import Source
from buildbot.interfaces import BuildSlaveTooOldError

class CVS(Source):

    name = "cvs"

    renderables = [ "cvsroot" ]

    def __init__(self, cvsroot=None, cvsmodule='', mode='incremental',
                 method=None, branch=None, global_options=[], extra_options=[],
                 login=None, **kwargs):

        self.cvsroot = cvsroot
        self.cvsmodule = cvsmodule
        self.branch = branch
        self.global_options = global_options
        self.extra_options = extra_options
        self.login = login
        self.mode = mode
        self.method = method
        self.srcdir = 'source'
        Source.__init__(self, **kwargs)

    def startVC(self, branch, revision, patch):
        self.branch = branch
        self.revision = revision

        self.method = self._getMethod()
        d = self.checkCvs()
        def checkInstall(cvsInstalled):
            if not cvsInstalled:
                raise BuildSlaveTooOldError("CVS is not installed on slave")
            return 0
        d.addCallback(checkInstall)
        d.addCallback(self.checkLogin)

        if self.mode == 'incremental':
            d.addCallback(lambda _: self.incremental())
        elif self.mode == 'full':
            d.addCallback(lambda _: self.full())

        d.addCallback(self.parseGotRevision)
        d.addCallback(self.finish)
        d.addErrback(self.failed)
        return d

    @defer.inlineCallbacks
    def incremental(self):
        updatable = yield self._sourcedirIsUpdatable()
        if updatable:
            rv = yield self.doUpdate()
        else:
            rv = yield self.clobber()
        defer.returnValue(rv)

    @defer.inlineCallbacks
    def full(self):
        if self.method == 'clobber':
            rv = yield self.clobber()
            defer.returnValue(rv)
            return

        elif self.method == 'copy':
            rv = yield self.copy()
            defer.returnValue(rv)
            return

        updatable = yield self._sourcedirIsUpdatable()
        if not updatable:
            log.msg("CVS repo not present, making full checkout")
            rv = yield self.doCheckout(self.workdir)
        elif self.method == 'clean':
            rv = yield self.clean()
        elif self.method == 'fresh':
            rv = yield self.fresh()
        else:
            raise ValueError("Unknown method, check your configuration")
        defer.returnValue(rv)

    def clobber(self):
        cmd = buildstep.RemoteCommand('rmdir', {'dir': self.workdir,
                                                'logEnviron': self.logEnviron})
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)
        def checkRemoval(res):
            if res != 0:
                raise RuntimeError("Failed to delete directory")
            return res
        d.addCallback(lambda _: checkRemoval(cmd.rc))
        d.addCallback(lambda _: self.doCheckout(self.workdir))
        return d

    def fresh(self, ):
        d = self.purge(True)
        d.addCallback(lambda _: self.doUpdate())
        return d

    def clean(self, ):
        d = self.purge(False)
        d.addCallback(lambda _: self.doUpdate())
        return d

    def copy(self):
        cmd = buildstep.RemoteCommand('rmdir', {'dir': self.workdir,
                                                'logEnviron': self.logEnviron})
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)        
        self.workdir = 'source'
        d.addCallback(lambda _: self.incremental())
        def copy(_):
            cmd = buildstep.RemoteCommand('cpdir',
                                          {'fromdir': 'source',
                                           'todir':'build',
                                           'logEnviron': self.logEnviron,})
            cmd.useLog(self.stdio_log, False)
            d = self.runCommand(cmd)
            return d
        d.addCallback(copy)
        def resetWorkdir(_):
            self.workdir = 'build'
            return 0
        d.addCallback(resetWorkdir)
        return d
        
    def purge(self, ignore_ignores):
        command = ['cvsdiscard']
        if ignore_ignores:
            command += ['--ignore']
        cmd = buildstep.RemoteShellCommand(self.workdir, command,
                                           env=self.env,
                                           logEnviron=self.logEnviron,
                                           timeout=self.timeout)
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)
        def evaluate(cmd):
            if cmd.didFail():
                raise buildstep.BuildStepFailed()
            return cmd.rc
        d.addCallback(evaluate)
        return d
        
    def doCheckout(self, dir):
        command = ['-d', self.cvsroot, '-z3', 'checkout', '-d', dir ]
        command = self.global_options + command + self.extra_options
        if self.branch:
            command += ['-r', self.branch]
        if self.revision:
            command += ['-D', self.revision]
        command += [ self.cvsmodule ]
        d = self._dovccmd(command, '')
        return d

    def doUpdate(self):
        command = ['-z3', 'update', '-dP']
        branch = self.branch
        # special case. 'cvs update -r HEAD -D today' gives no files; see #2351
        if branch == 'HEAD' and self.revision:
            branch = None
        if branch:
            command += ['-r', self.branch]
        if self.revision:
            command += ['-D', self.revision]
        d = self._dovccmd(command)
        return d

    def finish(self, res):
        d = defer.succeed(res)
        def _gotResults(results):
            self.setStatus(self.cmd, results)
            return results
        d.addCallback(_gotResults)
        d.addCallbacks(self.finished, self.checkDisconnect)
        return d

    def checkLogin(self, _):
        if self.login:
            d = defer.succeed(0)
        else:
            d = self._dovccmd(['-d', self.cvsroot, 'login'])
            def setLogin(res):
                # this happens only if the login command succeeds.
                self.login = True
                return res
            d.addCallback(setLogin)

        return d

    def _dovccmd(self, command, workdir=None):
        if workdir is None:
            workdir = self.workdir
        if not command:
            raise ValueError("No command specified")
        cmd = buildstep.RemoteShellCommand(workdir, ['cvs'] +
                                           command,
                                           env=self.env,
                                           timeout=self.timeout,
                                           logEnviron=self.logEnviron)
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)
        def evaluateCommand(cmd):
            if cmd.rc != 0:
                log.msg("Source step failed while running command %s" % cmd)
                raise buildstep.BuildStepFailed()
            return cmd.rc
        d.addCallback(lambda _: evaluateCommand(cmd))
        return d

    @defer.inlineCallbacks
    def _sourcedirIsUpdatable(self):
        myFileWriter = StringFileWriter()
        args = {
                'workdir': self.build.path_module.join(self.workdir, 'CVS'),
                'writer': myFileWriter,
                'maxsize': None,
                'blocksize': 32*1024,
                }

        cmd = buildstep.RemoteCommand('uploadFile',
                dict(slavesrc='Root', **args),
                ignore_updates=True)
        yield self.runCommand(cmd)
        if cmd.rc is not None and cmd.rc != 0:
            defer.returnValue(False)
            return

        # on Windows, the cvsroot may not contain the password, so compare to
        # both
        cvsroot_without_pw = re.sub("(:pserver:[^:]*):[^@]*(@.*)",
                                    r"\1\2", self.cvsroot)
        if myFileWriter.buffer.strip() not in (self.cvsroot,
                                               cvsroot_without_pw):
            defer.returnValue(False)
            return

        myFileWriter.buffer = ""
        cmd = buildstep.RemoteCommand('uploadFile',
                dict(slavesrc='Repository', **args),
                ignore_updates=True)
        yield self.runCommand(cmd)
        if cmd.rc is not None and cmd.rc != 0:
            defer.returnValue(False)
            return
        if myFileWriter.buffer.strip() != self.cvsmodule:
            defer.returnValue(False)
            return

        defer.returnValue(True)

    def parseGotRevision(self, res):
        revision = time.strftime("%Y-%m-%d %H:%M:%S +0000", time.gmtime())
        self.updateSourceProperty('got_revision', revision)
        return res

    def checkCvs(self):
        d = self._dovccmd(['--version'])
        def check(res):
            if res == 0:
                return True
            return False
        d.addCallback(check)
        return d

    def _getMethod(self):
        if self.method is not None and self.mode != 'incremental':
            return self.method
        elif self.mode == 'incremental':
            return None
        elif self.method is None and self.mode == 'full':
            return 'fresh'

    def computeSourceRevision(self, changes):
        if not changes:
            return None
        lastChange = max([c.when for c in changes])
        lastSubmit = max([br.submittedAt for br in self.build.requests])
        when = (lastChange + lastSubmit) / 2
        return formatdate(when)
