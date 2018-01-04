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

import mock
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.schedulers import manager, base
from buildbot import config


class SchedulerManager(unittest.TestCase):

    def setUp(self):
        self.next_objectid = 13
        self.objectids = {}

        self.master = mock.Mock()
        def getObjectId(sched_name, class_name):
            k = (sched_name, class_name)
            try:
                rv = self.objectids[k]
            except:
                rv = self.objectids[k] = self.next_objectid
                self.next_objectid += 1
            return defer.succeed(rv)
        self.master.db.state.getObjectId = getObjectId

        self.new_config = mock.Mock()

        self.sm = manager.SchedulerManager(self.master)
        self.sm.startService()

    def tearDown(self):
        if self.sm.running:
            return self.sm.stopService()

    class Sched(base.BaseScheduler):

        # changing sch.attr should make a scheduler look "updated"
        compare_attrs = ( 'attr', )
        already_started = False
        reconfig_count = 0

        def startService(self):
            assert not self.already_started
            assert self.master is not None
            assert self.objectid is not None
            self.already_started = True
            base.BaseScheduler.startService(self)

        def stopService(self):
            d = base.BaseScheduler.stopService(self)
            def still_set(_):
                assert self.master is not None
                assert self.objectid is not None
            d.addCallback(still_set)
            return d

    class ReconfigSched(config.ReconfigurableServiceMixin, Sched):

        def reconfigService(self, new_config):
            self.reconfig_count += 1
            new_sched = self.findNewSchedulerInstance(new_config)
            self.attr = new_sched.attr
            return config.ReconfigurableServiceMixin.reconfigService(self,
                                                        new_config)

    class ReconfigSched2(ReconfigSched):
        pass

    def makeSched(self, cls, name, attr='alpha'):
        sch = cls(name=name, builderNames=['x'], properties={})
        sch.attr = attr
        return sch

    # tests

    @defer.inlineCallbacks
    def test_reconfigService_add_and_change_and_remove(self):
        sch1 = self.makeSched(self.ReconfigSched, 'sch1', attr='alpha')
        self.new_config.schedulers = dict(sch1=sch1)

        yield self.sm.reconfigService(self.new_config)

        self.assertIdentical(sch1.parent, self.sm)
        self.assertIdentical(sch1.master, self.master)
        self.assertEqual(sch1.reconfig_count, 1)

        sch1_new = self.makeSched(self.ReconfigSched, 'sch1', attr='beta')
        sch2 = self.makeSched(self.ReconfigSched, 'sch2', attr='alpha')
        self.new_config.schedulers = dict(sch1=sch1_new, sch2=sch2)

        yield self.sm.reconfigService(self.new_config)

        # sch1 is still the active scheduler, and has been reconfig'd,
        # and has the correct attribute
        self.assertIdentical(sch1.parent, self.sm)
        self.assertIdentical(sch1.master, self.master)
        self.assertEqual(sch1.attr, 'beta')
        self.assertEqual(sch1.reconfig_count, 2)
        self.assertIdentical(sch1_new.parent, None)
        self.assertIdentical(sch1_new.master, None)

        self.assertIdentical(sch2.parent, self.sm)
        self.assertIdentical(sch2.master, self.master)

        self.new_config.schedulers = {}

        yield self.sm.reconfigService(self.new_config)

        self.assertIdentical(sch1.parent, None)
        self.assertIdentical(sch1.master, None)

    @defer.inlineCallbacks
    def test_reconfigService_class_name_change(self):
        sch1 = self.makeSched(self.ReconfigSched, 'sch1')
        self.new_config.schedulers = dict(sch1=sch1)

        yield self.sm.reconfigService(self.new_config)

        self.assertIdentical(sch1.parent, self.sm)
        self.assertIdentical(sch1.master, self.master)
        self.assertEqual(sch1.reconfig_count, 1)

        sch1_new = self.makeSched(self.ReconfigSched2, 'sch1')
        self.new_config.schedulers = dict(sch1=sch1_new)

        yield self.sm.reconfigService(self.new_config)

        # sch1 had its class name change, so sch1_new is now the active
        # instance
        self.assertIdentical(sch1_new.parent, self.sm)
        self.assertIdentical(sch1_new.master, self.master)

    @defer.inlineCallbacks
    def test_reconfigService_add_and_change_and_remove_no_reconfig(self):
        sch1 = self.makeSched(self.Sched, 'sch1', attr='alpha')
        self.new_config.schedulers = dict(sch1=sch1)

        yield self.sm.reconfigService(self.new_config)

        self.assertIdentical(sch1.parent, self.sm)
        self.assertIdentical(sch1.master, self.master)

        sch1_new = self.makeSched(self.Sched, 'sch1', attr='beta')
        sch2 = self.makeSched(self.Sched, 'sch2', attr='alpha')
        self.new_config.schedulers = dict(sch1=sch1_new, sch2=sch2)

        yield self.sm.reconfigService(self.new_config)

        # sch1 is not longer active, and sch1_new is
        self.assertIdentical(sch1.parent, None)
        self.assertIdentical(sch1.master, None)
        self.assertIdentical(sch1_new.parent, self.sm)
        self.assertIdentical(sch1_new.master, self.master)
        self.assertIdentical(sch2.parent, self.sm)
        self.assertIdentical(sch2.master, self.master)

    def test_finding_scheduler_by_name(self):
        scheduler_manager = manager.SchedulerManager(self.master)

        mocked_schedulers = [
            mock.Mock(spec=self.Sched),
            mock.Mock(spec=self.Sched),
            mock.Mock(spec=self.ReconfigSched),
            mock.Mock(spec=self.ReconfigSched),
        ]

        for index, scheduler in enumerate(mocked_schedulers):
            scheduler.name = 'scheduler-{}'.format(index)
            scheduler_manager.addService(scheduler)

        for scheduler in mocked_schedulers:
            self.assertEqual(scheduler_manager.findSchedulerByName(scheduler.name), scheduler)

        self.assertIsNone(scheduler_manager.findSchedulerByName('not-existing-scheduler'))

    def test_finding_scheduler_by_builder_name(self):
        scheduler_manager = manager.SchedulerManager(self.master)

        first_scheduler = mock.Mock(spec=self.Sched, builderNames=['builder_a', 'builder_b'])
        scheduler_manager.addService(first_scheduler)

        second_scheduler = mock.Mock(spec=self.Sched, builderNames=['builder_c', 'builder_d'])
        scheduler_manager.addService(second_scheduler)

        self.assertEqual(scheduler_manager.findSchedulerByBuilderName('builder_c'), second_scheduler)

    def test_finding_scheduler_by_builder_name_filter_by_scheduler_type(self):
        fake_scheduler_type = type('FakeScheduler', (base.BaseScheduler, ), {})

        scheduler_manager = manager.SchedulerManager(self.master)

        first_scheduler = mock.Mock(spec=self.Sched, builderNames=['builder_a', 'builder_b'])
        scheduler_manager.addService(first_scheduler)

        second_scheduler = mock.Mock(spec=fake_scheduler_type, builderNames=['builder_b', 'builder_c'])
        scheduler_manager.addService(second_scheduler)

        self.assertEqual(
            scheduler_manager.findSchedulerByBuilderName('builder_b', scheduler_type=self.Sched),
            first_scheduler,
        )

        self.assertEqual(
            scheduler_manager.findSchedulerByBuilderName('builder_b', scheduler_type=fake_scheduler_type),
            second_scheduler,
        )
