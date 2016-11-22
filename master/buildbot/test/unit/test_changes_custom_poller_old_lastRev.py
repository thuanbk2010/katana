from twisted.internet import defer
import test_changes_custom_poller

class TestCustomPollerOldLastRev(test_changes_custom_poller.TestCustomPoller):

    def setup_lastRev(self, poller):
        poller.lastRev = {"1.0/dev": "1:835be7494fb4", "stable": "3:05bbe2605e10"}

    def add_expected_commands_for_processBranches(self):
        self.expected_commands.append({'command': ['log', '-b', 'trunkbookmark', '-r',
                                                   '70fc4de2ff3828a587d80f7528c1b5314c51550e7:' +
                                                   '70fc4de2ff3828a587d80f7528c1b5314c51550e7',
                                                   '--template={node}\\n'],
                                       'stdout': defer.succeed('70fc4de2ff3828a587d80f7528c1b5314c51550e7')})

        self.expected_commands.append({'command': ['log', '-b', '1.0/dev', '-r',
                                                   '835be7494fb4:117b9a27b5bf65d7e7b5edb48f7fd59dc4170486',
                                                   '--template={node}\\n'],
                                       'stdout': defer.succeed('5553a6194a6393dfbec82f96654d52a76ddf844d\n' +
                                                               'b2e48cbab3f0753f99db833acff6ca18096854bd\n' +
                                                               '117b9a27b5bf65d7e7b5edb48f7fd59dc4170486\n')})


