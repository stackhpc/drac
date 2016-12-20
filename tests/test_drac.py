#!/usr/bin/env python

import unittest

import mock

import drac


class FakeSetting(object):
    """Fake BIOS setting object."""

    def __init__(self, current, pending=None, possible=None):
        self.current_value = current
        self.pending_value = pending
        if possible is not None:
            self.possible_values = possible


class FakeJob(object):
    """Fake DRAC job object."""

    def __init__(self, name='ConfigBIOS'):
        self.name = name


class FailJSON(Exception):
    """Dummy exception for mocking module.fail_json behaviour."""
    pass


class TestDRACBIOS(unittest.TestCase):
    """Test case for Ansible drac module."""

    def setUp(self):
        self.module = mock.MagicMock()
        self.module.fail_json.side_effect = FailJSON
        self.bmc = mock.MagicMock()

    def test_has_committed_config_job_no_jobs(self):
        self.bmc.list_jobs.return_value = []
        has_job = drac.has_committed_config_job(self.module, self.bmc)
        self.assertFalse(has_job)

    def test_has_committed_config_job_non_config_jobs(self):
        self.bmc.list_jobs.return_value = [FakeJob('ADifferentJob')]
        has_job = drac.has_committed_config_job(self.module, self.bmc)
        self.assertFalse(has_job)

    def test_has_committed_config_job_with_config_jobs(self):
        self.bmc.list_jobs.return_value = [FakeJob('ConfigBIOS')]
        has_job = drac.has_committed_config_job(self.module, self.bmc)
        self.assertTrue(has_job)

    def test_has_committed_config_job_with_config_prefixed_jobs(self):
        self.bmc.list_jobs.return_value = [FakeJob('ConfigBIOS:suffix')]
        has_job = drac.has_committed_config_job(self.module, self.bmc)
        self.assertTrue(has_job)

    def test_has_committed_config_job_list_jobs_failure(self):
        self.bmc.list_jobs.side_effect = Exception
        self.assertRaises(FailJSON, drac.has_committed_config_job,
                          self.module, self.bmc)

    def test_check_change_one_with_reboot(self):
        self.bmc.list_bios_settings.return_value = {
            'setting1': FakeSetting('value')
        }
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'config': {
                'setting1': 'new value'
            },
            'reboot': True,
        }
        changing, applying, actions = drac.check(self.module, self.bmc)
        self.bmc.list_bios_settings.assert_called_once_with()
        self.assertDictEqual(changing, {'setting1': 'new value'})
        self.assertDictEqual(applying, {'setting1': 'new value'})
        self.assertEqual(actions,
                         drac.BIOSActions(False, False, True, True))

    def test_check_change_one_without_reboot(self):
        self.bmc.list_bios_settings.return_value = {
            'setting1': FakeSetting('value')
        }
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'config': {
                'setting1': 'new value'
            },
            'reboot': False,
        }
        changing, applying, actions = drac.check(self.module, self.bmc)
        self.bmc.list_bios_settings.assert_called_once_with()
        self.assertDictEqual(changing, {'setting1': 'new value'})
        self.assertDictEqual(applying, {'setting1': 'new value'})
        self.assertEqual(actions,
                         drac.BIOSActions(False, False, True, True))

    def test_check_change_one_uncommitted_pending_with_reboot(self):
        self.bmc.list_bios_settings.return_value = {
            'setting1': FakeSetting('value', 'new value')
        }
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'config': {
                'setting1': 'new value'
            },
            'reboot': True,
        }
        changing, applying, actions = drac.check(self.module, self.bmc)
        self.bmc.list_bios_settings.assert_called_once_with()
        self.bmc.list_jobs.assert_called_once_with(only_unfinished=True)
        self.assertDictEqual(changing, {})
        self.assertDictEqual(applying, {})
        self.assertEqual(actions,
                         drac.BIOSActions(False, False, False, True))

    def test_check_change_one_uncommitted_pending_without_reboot(self):
        self.bmc.list_bios_settings.return_value = {
            'setting1': FakeSetting('value', 'new value')
        }
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'config': {
                'setting1': 'new value'
            },
            'reboot': False,
        }
        changing, applying, actions = drac.check(self.module, self.bmc)
        self.bmc.list_bios_settings.assert_called_once_with()
        self.bmc.list_jobs.assert_called_once_with(only_unfinished=True)
        self.assertDictEqual(changing, {})
        self.assertDictEqual(applying, {})
        self.assertEqual(actions,
                         drac.BIOSActions(False, False, False, True))

    def test_check_change_one_committed_pending_with_reboot(self):
        self.bmc.list_bios_settings.return_value = {
            'setting1': FakeSetting('value', 'new value')
        }
        self.bmc.list_jobs.return_value = [FakeJob()]
        self.module.params = {
            'config': {
                'setting1': 'new value'
            },
            'reboot': True,
        }
        changing, applying, actions = drac.check(self.module, self.bmc)
        self.bmc.list_bios_settings.assert_called_once_with()
        self.bmc.list_jobs.assert_called_once_with(only_unfinished=True)
        self.assertDictEqual(changing, {})
        self.assertDictEqual(applying, {})
        self.assertEqual(actions,
                         drac.BIOSActions(False, True, False, False))

    def test_check_change_one_committed_pending_without_reboot(self):
        self.bmc.list_bios_settings.return_value = {
            'setting1': FakeSetting('value', 'new value')
        }
        self.bmc.list_jobs.return_value = [FakeJob()]
        self.module.params = {
            'config': {
                'setting1': 'new value'
            },
            'reboot': False,
        }
        changing, applying, actions = drac.check(self.module, self.bmc)
        self.bmc.list_bios_settings.assert_called_once_with()
        self.bmc.list_jobs.assert_called_once_with(only_unfinished=True)
        self.assertDictEqual(changing, {})
        self.assertDictEqual(applying, {})
        self.assertEqual(actions,
                         drac.BIOSActions(False, False, False, False))

    def test_check_change_one_uncommitted_conflict_with_reboot(self):
        self.bmc.list_bios_settings.return_value = {
            'setting1': FakeSetting('value', 'new value'),
            'setting2': FakeSetting('value'),
            'setting3': FakeSetting('value', 'new value')
        }
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'config': {
                'setting1': 'newer value'
            },
            'reboot': True,
        }
        changing, applying, actions = drac.check(self.module, self.bmc)
        self.bmc.list_bios_settings.assert_called_once_with()
        self.bmc.list_jobs.assert_called_once_with(only_unfinished=True)
        self.assertDictEqual(changing, {'setting1': 'newer value'})
        self.assertDictEqual(applying, {'setting1': 'newer value',
                                        'setting3': 'new value'})
        self.assertEqual(actions,
                         drac.BIOSActions(True, False, True, True))

    def test_check_change_one_uncommitted_conflict_without_reboot(self):
        self.bmc.list_bios_settings.return_value = {
            'setting1': FakeSetting('value', 'new value'),
            'setting2': FakeSetting('value'),
            'setting3': FakeSetting('value', 'new value')
        }
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'config': {
                'setting1': 'newer value'
            },
            'reboot': False,
        }
        changing, applying, actions = drac.check(self.module, self.bmc)
        self.bmc.list_bios_settings.assert_called_once_with()
        self.bmc.list_jobs.assert_called_once_with(only_unfinished=True)
        self.assertDictEqual(changing, {'setting1': 'newer value'})
        self.assertDictEqual(applying, {'setting1': 'newer value',
                                        'setting3': 'new value'})
        self.assertEqual(actions,
                         drac.BIOSActions(True, False, True, True))

    def test_check_change_one_committed_conflict_with_reboot(self):
        self.bmc.list_bios_settings.return_value = {
            'setting1': FakeSetting('value', 'new value'),
            'setting2': FakeSetting('value'),
            'setting3': FakeSetting('value', 'new value')
        }
        self.bmc.list_jobs.return_value = [FakeJob()]
        self.module.params = {
            'config': {
                'setting1': 'newer value'
            },
            'reboot': True,
        }
        changing, applying, actions = drac.check(self.module, self.bmc)
        self.bmc.list_bios_settings.assert_called_once_with()
        self.bmc.list_jobs.assert_called_once_with(only_unfinished=True)
        self.assertDictEqual(changing, {'setting1': 'newer value'})
        self.assertDictEqual(applying, {'setting1': 'newer value'})
        self.assertEqual(actions,
                         drac.BIOSActions(False, True, True, True))

    def test_check_change_one_committed_conflict_without_reboot(self):
        self.bmc.list_bios_settings.return_value = {
            'setting1': FakeSetting('value', 'new value'),
            'setting2': FakeSetting('value'),
            'setting3': FakeSetting('value', 'new value')
        }
        self.bmc.list_jobs.return_value = [FakeJob()]
        self.module.params = {
            'config': {
                'setting1': 'newer value'
            },
            'reboot': False,
        }
        self.assertRaises(FailJSON, drac.check, self.module, self.bmc)
        self.bmc.list_bios_settings.assert_called_once_with()
        self.bmc.list_jobs.assert_called_once_with(only_unfinished=True)

    def test_check_list_settings_failure(self):
        self.bmc.list_bios_settings.side_effect = Exception
        self.assertRaises(FailJSON, drac.check, self.module, self.bmc)


if __name__ == "__main__":
    unittest.main()
