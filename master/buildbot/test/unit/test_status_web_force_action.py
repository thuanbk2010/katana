import mock

from twisted.internet import defer
from twisted.web.test.requesthelper import DummyRequest
from twisted.trial import unittest

from buildbot.schedulers.base import BaseScheduler
from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.status.web.builder import ForceAction
from buildbot.test.fake.fakemaster import FakeBuilderStatus, FakeMaster


class TestForceAction(unittest.TestCase):

    def setUp(self):
        self.builder_name = 'proj0-test-builder'
        self.project = 'proj0'

        self.builder_status = FakeBuilderStatus(
            buildername=self.builder_name, project=self.project,
        )
        self.master = FakeMaster()
        self.request = DummyRequest([])
        self.request.site = mock.Mock(
            buildbot_service=mock.Mock(master=self.master),
        )

        self.force_action_resource = ForceAction()
        self.force_action_resource.builder_status = self.builder_status

    @defer.inlineCallbacks
    def test_forcescheduler_form_param(self):
        first_scheduler = mock.Mock(spec=ForceScheduler)
        first_scheduler.name = 'test-scheduler-0+[force]'

        selected_scheduler = mock.Mock(spec=ForceScheduler)
        selected_scheduler.name = 'test-scheduler-1+[force]'

        self.master.scheduler_manager.addService(first_scheduler)
        self.master.scheduler_manager.addService(selected_scheduler)

        self.request.addArg('forcescheduler', selected_scheduler.name)

        yield self.force_action_resource.force(self.request, [self.builder_name])

        selected_scheduler.force.assert_called_once()
        first_scheduler.force.assert_not_called()

    @defer.inlineCallbacks
    def test_forcescheduler_form_param_empty(self):
        first_scheduler = mock.Mock(spec=ForceScheduler, builderNames=[])
        first_scheduler.name = 'test-scheduler-0+[force]'

        selected_scheduler = mock.Mock(spec=ForceScheduler, builderNames=[self.builder_name])
        selected_scheduler.name = 'test-scheduler-1+[force]'

        self.master.scheduler_manager.addService(first_scheduler)
        self.master.scheduler_manager.addService(selected_scheduler)

        yield self.force_action_resource.force(self.request, [self.builder_name])

        selected_scheduler.force.assert_called_once()
        first_scheduler.force.assert_not_called()

    @defer.inlineCallbacks
    def test_forcescheduler_form_param_empty_only_force_schedulers_allowed(self):
        first_scheduler = mock.Mock(spec=BaseScheduler, builderNames=[self.builder_name])
        first_scheduler.name = 'test-scheduler-0+[force]'

        selected_scheduler = mock.Mock(spec=ForceScheduler, builderNames=[self.builder_name])
        selected_scheduler.name = 'test-scheduler-1+[force]'

        self.master.scheduler_manager.addService(first_scheduler)
        self.master.scheduler_manager.addService(selected_scheduler)

        yield self.force_action_resource.force(self.request, [self.builder_name])

        selected_scheduler.force.assert_called_once()

    @defer.inlineCallbacks
    def test_forcescheduler_form_param_empty_scheduler_not_found(self):
        scheduler = mock.Mock(spec=ForceScheduler, builderNames=[])
        scheduler.name = 'test-scheduler-0+[force]'

        self.master.scheduler_manager.addService(scheduler)

        result = yield self.force_action_resource.force(self.request, [self.builder_name])

        self.assertEqual(
            result,
            (
                'projects/{}/builders/{}'.format(self.project, self.builder_name),
                'forcescheduler arg not found, and could not find a default force scheduler for builderName',
            ),
        )

    def test_decode_request_arguments(self):
        self.request.args['checkbox'] = ['checkbox-selected-1', 'checkbox-selected-2']

        args = ForceAction.decode_request_arguments(self.request)

        self.assertEqual(args, {'checkbox-selected-1': True, 'checkbox-selected-2': True})
