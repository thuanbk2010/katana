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

import stat
from twisted.internet import defer
from buildbot.process import buildstep
from buildbot.status.results import SUCCESS, FAILURE
from buildbot.interfaces import BuildSlaveTooOldError

class SlaveBuildStep(buildstep.BuildStep):
    def describe(self, done=False):
        description = self.descriptionDone if done else self.description
        return description or [self.name]

class SetPropertiesFromEnv(SlaveBuildStep):
    """
    Sets properties from envirionment variables on the slave.

    Note this is transfered when the slave first connects
    """
    name='SetPropertiesFromEnv'
    description=['Setting']
    descriptionDone=['Set']

    def __init__(self, variables, source="SlaveEnvironment", **kwargs):
        buildstep.BuildStep.__init__(self, **kwargs)
        self.variables = variables
        self.source = source

    def start(self):
        # on Windows, environment variables are case-insensitive, but we have
        # a case-sensitive dictionary in slave_environ.  Fortunately, that
        # dictionary is also folded to uppercase, so we can simply fold the
        # variable names to uppercase to duplicate the case-insensitivity.
        fold_to_uppercase = (self.buildslave.slave_system == 'win32')

        properties = self.build.getProperties()
        environ = self.buildslave.slave_environ
        variables = self.variables
        log = []
        if isinstance(variables, str):
            variables = [self.variables]
        for variable in variables:
            key = variable
            if fold_to_uppercase:
                key = variable.upper()
            value = environ.get(key, None)
            if value:
                # note that the property is not uppercased
                properties.setProperty(variable, value, self.source,
                                       runtime=True)
                log.append("%s = %r" % (variable, value))
        self.addCompleteLog("properties", "\n".join(log))
        self.step_status.setText(self.describe(done=True))
        self.finished(SUCCESS)

class FileExists(SlaveBuildStep):
    """
    Check for the existence of a file on the slave.
    """
    name='FileExists'
    description='Checking'
    descriptionDone='Checked'

    renderables = [ 'file' ]

    haltOnFailure = True
    flunkOnFailure = True


    def __init__(self, file, **kwargs):
        buildstep.BuildStep.__init__(self, **kwargs)
        self.file = file

    def start(self):
        slavever = self.slaveVersion('stat')
        if not slavever:
            raise BuildSlaveTooOldError("slave is too old, does not know "
                                        "about stat")
        cmd = buildstep.RemoteCommand('stat', {'file': self.file })
        d = self.runCommand(cmd)
        d.addCallback(lambda res: self.commandComplete(cmd))
        d.addErrback(self.failed)

    def commandComplete(self, cmd):
        if cmd.didFail():
            self.step_status.setText(["File not found."])
            self.finished(FAILURE)
            return
        s = cmd.updates["stat"][-1]
        if stat.S_ISREG(s[stat.ST_MODE]):
            self.step_status.setText(["File found."])
            self.finished(SUCCESS)
        else:
            self.step_status.setText(["Not a file."])
            self.finished(FAILURE)

class CopyDirectory(SlaveBuildStep):
    """
    Copy a directory tree on the slave.
    """
    name='CopyDirectory'
    description=['Copying']
    descriptionDone=['Copied']

    renderables = [ 'src', 'dest' ]

    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, src, dest, timeout=None, maxTime=None, **kwargs):
        buildstep.BuildStep.__init__(self, **kwargs)
        self.src = src
        self.dest = dest
        self.timeout = timeout
        self.maxTime = maxTime

    def start(self):
        slavever = self.slaveVersion('cpdir')
        if not slavever:
            raise BuildSlaveTooOldError("slave is too old, does not know "
                                        "about cpdir")

        args = {'fromdir': self.src, 'todir': self.dest }
        if self.timeout:
            args['timeout'] = self.timeout
        if self.maxTime:
            args['maxTime'] = self.maxTime

        cmd = buildstep.RemoteCommand('cpdir', args)
        d = self.runCommand(cmd)
        d.addCallback(lambda res: self.commandComplete(cmd))
        d.addErrback(self.failed)

    def commandComplete(self, cmd):
        if cmd.didFail():
            self.step_status.setText(["Copying", self.src, "to", self.dest, "failed."])
            self.finished(FAILURE)
            return
        self.step_status.setText(self.describe(done=True))
        self.finished(SUCCESS)

    def describe(self, done=False):
        desc = self.descriptionDone if done else self.description
        desc = desc[:]
        desc.extend([self.src, "to", self.dest])
        return desc
        
class RemoveDirectory(SlaveBuildStep):
    """
    Remove a directory tree on the slave.
    """
    name='RemoveDirectory'
    description=None
    descriptionDone=None

    renderables = [ 'dir' ]

    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, dir, description=None, descriptionDone=None, **kwargs):
        self.description = description
        if isinstance(self.description, str):
            self.description = [self.description]

        self.descriptionDone = descriptionDone
        if isinstance(self.descriptionDone, str):
            self.descriptionDone = [self.descriptionDone]

        buildstep.BuildStep.__init__(self, **kwargs)
        self.dir = dir


    def start(self):
        slavever = self.slaveVersion('rmdir')
        if not slavever:
            raise BuildSlaveTooOldError("slave is too old, does not know "
                                        "about rmdir")
        cmd = buildstep.RemoteCommand('rmdir', {'dir': self.dir })
        d = self.runCommand(cmd)
        d.addCallback(lambda res: self.commandComplete(cmd))
        d.addErrback(self.failed)

    def commandComplete(self, cmd):
        description = self.describe(done=True) or ['rmdir', self.dir]
        if cmd.didFail():
            self.step_status.setText(description + ["failed"])
            self.finished(FAILURE)
            return

        self.step_status.setText(description)
        self.finished(SUCCESS)

    def describe(self, done=False):
        description = self.descriptionDone if done else self.description
        return  description or ['rmdir', self.dir]


class MakeDirectory(SlaveBuildStep):
    """
    Create a directory on the slave.
    """
    name='MakeDirectory'
    description=['Creating']
    descriptionDone=['Created']

    renderables = [ 'dir' ]

    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, dir, **kwargs):
        buildstep.BuildStep.__init__(self, **kwargs)
        self.dir = dir

    def start(self):
        slavever = self.slaveVersion('mkdir')
        if not slavever:
            raise BuildSlaveTooOldError("slave is too old, does not know "
                                        "about mkdir")
        cmd = buildstep.RemoteCommand('mkdir', {'dir': self.dir })
        d = self.runCommand(cmd)
        d.addCallback(lambda res: self.commandComplete(cmd))
        d.addErrback(self.failed)

    def commandComplete(self, cmd):
        if cmd.didFail():
            self.step_status.setText(["Create failed."])
            self.finished(FAILURE)
            return
        self.step_status.setText(self.describe(done=True))
        self.finished(SUCCESS)


class RequestGracefulDisconnect(buildstep.LoggingBuildStep):
    name='Request Graceful Disconnect'
    description='Requesting the slave to disconnect gracefully'
    descriptionDone='Slave gracefully disconnected'

    def __init__(self, **kwargs):
        buildstep.LoggingBuildStep.__init__(self, **kwargs)

    def start(self):
        self.build.slavebuilder.slave.slave_status.setGraceful(True)
        self.finished(SUCCESS)
        return

class CompositeStepMixin():
    """I define utils for composite steps, factorizing basic remote commands"""
    def addLogForRemoteCommands(self, logname):
        """This method must be called by user classes
        composite steps could create several logs, this mixin functions will write
        to the last one.
        """
        self.rc_log = self.addLog(logname)
        return self.rc_log

    def runRemoteCommand(self, cmd, args, abandonOnFailure=True):
        """generic RemoteCommand boilerplate"""
        cmd = buildstep.RemoteCommand(cmd, args)
        cmd.useLog(self.rc_log, False)
        d = self.runCommand(cmd)
        def commandComplete(cmd):
            if abandonOnFailure and cmd.didFail():
                raise buildstep.BuildStepFailed()
            return cmd.didFail()
        d.addCallback(lambda res: commandComplete(cmd))
        return d

    def runRmdir(self, dir, **kwargs):
        """ remove a directory from the slave """
        return self.runRemoteCommand('rmdir',
                                     {'dir': dir, 'logEnviron': self.logEnviron },
                                     **kwargs)

    @defer.inlineCallbacks
    def pathExists(self, path):
        """ test whether path exists"""
        res = yield self.runRemoteCommand('stat', {'file': path,
                                                   'logEnviron': self.logEnviron,},
                                          abandonOnFailure=False)
        defer.returnValue(not res)

    def runMkdir(self, _dir, **kwargs):
        """ create a directory and its parents"""
        return self.runRemoteCommand('mkdir', {'dir': _dir,
                                               'logEnviron': self.logEnviron,},
                                     **kwargs)
