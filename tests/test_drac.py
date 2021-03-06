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

    def __init__(self, name):
        self.name = name


class FailJSON(Exception):
    """Dummy exception for mocking module.fail_json behaviour."""


class FakeDRACConfig(drac.DRACConfig):

    def __init__(self, committed_job, changing):
        super(FakeDRACConfig, self).__init__('Fake', committed_job)
        self.changing = changing

    def is_change_required(self):
        return self.changing


class DummyDRACException(Exception):
    """Dummy exception class raised by dracclient module."""


class BaseTestCase(unittest.TestCase):
    """Base test case for testing the drac module."""

    def setUp(self):
        self.module = mock.MagicMock()
        self.module.fail_json.side_effect = FailJSON
        self.bmc = mock.MagicMock()


class TestDRACConfig(BaseTestCase):
    """Test case for Ansible drac module DRACConfig object."""

    # Test set_initial_state:

    def test_drac_config_complete(self):
        config = FakeDRACConfig(False, False)
        config.set_initial_state(False, False, False)
        self.assertEqual(config.state, config.states.COMPLETE)

    def test_drac_config_complete_committed(self):
        config = FakeDRACConfig(True, False)
        config.set_initial_state(False, False, False)
        self.assertEqual(config.state, config.states.COMPLETE)

    def test_drac_config_uncommitted(self):
        config = FakeDRACConfig(False, True)
        config.set_initial_state(True, False, False)
        self.assertEqual(config.state, config.states.UNCOMMITTED)

    def test_drac_config_pre_committed(self):
        config = FakeDRACConfig(True, True)
        config.set_initial_state(True, False, False)
        self.assertEqual(config.state, config.states.PRE_COMMITTED)

    def test_drac_config_conflicting(self):
        config = FakeDRACConfig(False, True)
        config.set_initial_state(True, False, True)
        self.assertEqual(config.state, config.states.CONFLICTING)

    def test_drac_config_applied(self):
        config = FakeDRACConfig(False, False)
        config.set_initial_state(False, True, False)
        self.assertEqual(config.state, config.states.APPLIED)

    def test_drac_config_committed(self):
        config = FakeDRACConfig(True, False)
        config.set_initial_state(False, True, False)
        self.assertEqual(config.state, config.states.COMMITTED)

    # Test state transitions:

    def test_drac_config_conflicting_handle_reboot(self):
        config = FakeDRACConfig(False, False)
        config.state = config.states.CONFLICTING
        config.handle_reboot()
        self.assertEqual(config.state, config.states.CONFLICTING)

    def test_drac_config_conflicting_handle_abandon_no_changes(self):
        config = FakeDRACConfig(False, False)
        config.state = config.states.CONFLICTING
        config.handle_abandon()
        self.assertEqual(config.state, config.states.COMPLETE)

    def test_drac_config_conflicting_handle_abandon_with_changes(self):
        config = FakeDRACConfig(False, True)
        config.state = config.states.CONFLICTING
        config.handle_abandon()
        self.assertEqual(config.state, config.states.ABANDONED)

    def test_drac_config_conflicting_handle_invalid(self):
        config = FakeDRACConfig(False, False)
        config.state = config.states.CONFLICTING
        self.assertRaises(AssertionError, config.handle_apply)
        self.assertRaises(AssertionError, config.handle_commit)

    def test_drac_config_pre_committed_handle_reboot(self):
        config = FakeDRACConfig(False, False)
        config.state = config.states.PRE_COMMITTED
        config.handle_reboot()
        self.assertEqual(config.state, config.states.UNCOMMITTED)

    def test_drac_config_pre_committed_handle_invalid(self):
        config = FakeDRACConfig(False, False)
        config.state = config.states.PRE_COMMITTED
        self.assertRaises(AssertionError, config.handle_abandon)
        self.assertRaises(AssertionError, config.handle_apply)
        self.assertRaises(AssertionError, config.handle_commit)

    def test_drac_config_uncommitted_handle_reboot(self):
        config = FakeDRACConfig(False, False)
        config.state = config.states.UNCOMMITTED
        config.handle_reboot()
        self.assertEqual(config.state, config.states.UNCOMMITTED)

    def test_drac_config_uncommitted_handle_apply(self):
        config = FakeDRACConfig(False, False)
        config.state = config.states.UNCOMMITTED
        config.handle_apply()
        self.assertEqual(config.state, config.states.APPLIED)

    def test_drac_config_uncommitted_handle_invalid(self):
        config = FakeDRACConfig(False, False)
        config.state = config.states.UNCOMMITTED
        self.assertRaises(AssertionError, config.handle_abandon)
        self.assertRaises(AssertionError, config.handle_commit)

    def test_drac_config_applied_handle_reboot(self):
        config = FakeDRACConfig(False, False)
        config.state = config.states.APPLIED
        config.handle_reboot()
        self.assertEqual(config.state, config.states.APPLIED)

    def test_drac_config_applied_handle_commit(self):
        config = FakeDRACConfig(False, False)
        config.state = config.states.APPLIED
        config.handle_commit()
        self.assertEqual(config.state, config.states.COMMITTED)

    def test_drac_config_applied_handle_invalid(self):
        config = FakeDRACConfig(False, False)
        config.state = config.states.APPLIED
        self.assertRaises(AssertionError, config.handle_abandon)
        self.assertRaises(AssertionError, config.handle_apply)

    def test_drac_config_committed_handle_reboot(self):
        config = FakeDRACConfig(False, False)
        config.state = config.states.COMMITTED
        config.handle_reboot()
        self.assertEqual(config.state, config.states.COMPLETE)

    def test_drac_config_committed_handle_invalid(self):
        config = FakeDRACConfig(False, False)
        config.state = config.states.COMMITTED
        self.assertRaises(AssertionError, config.handle_abandon)
        self.assertRaises(AssertionError, config.handle_apply)
        self.assertRaises(AssertionError, config.handle_commit)

    def test_drac_config_complete_handle_reboot(self):
        config = FakeDRACConfig(False, False)
        config.state = config.states.COMPLETE
        config.handle_reboot()
        self.assertEqual(config.state, config.states.COMPLETE)

    def test_drac_config_complete_handle_invalid(self):
        config = FakeDRACConfig(False, False)
        config.state = config.states.COMPLETE
        self.assertRaises(AssertionError, config.handle_abandon)
        self.assertRaises(AssertionError, config.handle_apply)
        self.assertRaises(AssertionError, config.handle_commit)


class TestDRACBIOS(BaseTestCase):
    """Test case for Ansible drac module BIOS configuration."""

    def test_has_committed_bios_job_no_jobs(self):
        jobs = []
        has_job = drac.has_committed_bios_job(jobs)
        self.assertFalse(has_job)

    def test_has_committed_bios_job_non_bios_jobs(self):
        jobs = [FakeJob('ADifferentJob')]
        has_job = drac.has_committed_bios_job(jobs)
        self.assertFalse(has_job)

    def test_has_committed_bios_job_with_bios_jobs(self):
        jobs = [FakeJob('ConfigBIOS')]
        has_job = drac.has_committed_bios_job(jobs)
        self.assertTrue(has_job)

    def test_has_committed_bios_job_with_config_prefixed_jobs(self):
        jobs = [FakeJob('ConfigBIOS:suffix')]
        has_job = drac.has_committed_bios_job(jobs)
        self.assertTrue(has_job)

    @mock.patch.object(drac, 'drac_exc')
    def test_get_bios_config_list_settings_failure(self, mock_exc):
        mock_exc.BaseClientException = DummyDRACException
        self.bmc.list_bios_settings.side_effect = DummyDRACException
        self.assertRaises(FailJSON, drac.get_bios_config,
                          self.module, self.bmc)

    @mock.patch.object(drac, 'drac_exc')
    def test_get_bios_config_list_jobs_failure(self, mock_exc):
        mock_exc.BaseClientException = DummyDRACException
        self.bmc.list_jobs.side_effect = DummyDRACException
        self.assertRaises(FailJSON, drac.get_bios_config,
                          self.module, self.bmc)

    def test_get_bios_config_no_config(self):
        self.bmc.list_bios_settings.return_value = {
            'setting1': FakeSetting('value')
        }
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'bios_config': {}
        }
        config = drac.get_bios_config(self.module, self.bmc)
        self.bmc.list_bios_settings.assert_not_called()
        self.assertEqual(config.state, config.states.COMPLETE)
        applying = config.get_settings_to_apply()
        self.assertDictEqual(applying, {})

    def test_get_bios_config_no_changes(self):
        self.bmc.list_bios_settings.return_value = {
            'setting1': FakeSetting('value')
        }
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'bios_config': {
                'setting1': 'value'
            },
        }
        config = drac.get_bios_config(self.module, self.bmc)
        self.bmc.list_bios_settings.assert_called_once_with()
        self.assertEqual(config.state, config.states.COMPLETE)
        applying = config.get_settings_to_apply()
        self.assertDictEqual(applying, {})

    def test_get_bios_config_change_one(self):
        self.bmc.list_bios_settings.return_value = {
            'setting1': FakeSetting('value')
        }
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'bios_config': {
                'setting1': 'new value'
            },
        }
        config = drac.get_bios_config(self.module, self.bmc)
        self.bmc.list_bios_settings.assert_called_once_with()
        self.assertEqual(config.state, config.states.UNCOMMITTED)
        applying = config.get_settings_to_apply()
        self.assertDictEqual(applying, {'setting1': 'new value'})

    def test_get_bios_config_change_one_uncommitted_pending(self):
        self.bmc.list_bios_settings.return_value = {
            'setting1': FakeSetting('value', 'new value')
        }
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'bios_config': {
                'setting1': 'new value'
            },
        }
        config = drac.get_bios_config(self.module, self.bmc)
        self.bmc.list_bios_settings.assert_called_once_with()
        self.bmc.list_jobs.assert_called_once_with(only_unfinished=True)
        self.assertEqual(config.state, config.states.APPLIED)
        applying = config.get_settings_to_apply()
        self.assertDictEqual(applying, {})

    def test_get_bios_config_change_one_committed_pending(self):
        self.bmc.list_bios_settings.return_value = {
            'setting1': FakeSetting('value', 'new value')
        }
        self.bmc.list_jobs.return_value = [FakeJob('ConfigBIOS')]
        self.module.params = {
            'bios_config': {
                'setting1': 'new value'
            },
        }
        config = drac.get_bios_config(self.module, self.bmc)
        self.bmc.list_bios_settings.assert_called_once_with()
        self.bmc.list_jobs.assert_called_once_with(only_unfinished=True)
        self.assertEqual(config.state, config.states.COMMITTED)
        applying = config.get_settings_to_apply()
        self.assertDictEqual(applying, {})

    def test_get_bios_config_change_one_uncommitted_conflict(self):
        self.bmc.list_bios_settings.return_value = {
            'setting1': FakeSetting('value', 'new value'),
            'setting2': FakeSetting('value'),
            'setting3': FakeSetting('value', 'new value')
        }
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'bios_config': {
                'setting1': 'newer value'
            },
        }
        config = drac.get_bios_config(self.module, self.bmc)
        self.bmc.list_bios_settings.assert_called_once_with()
        self.bmc.list_jobs.assert_called_once_with(only_unfinished=True)
        self.assertEqual(config.state, config.states.CONFLICTING)
        config.handle_abandon()
        applying = config.get_settings_to_apply()
        self.assertDictEqual(applying, {'setting1': 'newer value',
                                        'setting3': 'new value'})

    def test_get_bios_config_change_one_committed_conflict(self):
        self.bmc.list_bios_settings.return_value = {
            'setting1': FakeSetting('value', 'new value'),
            'setting2': FakeSetting('value'),
            'setting3': FakeSetting('value', 'new value')
        }
        self.bmc.list_jobs.return_value = [FakeJob('ConfigBIOS')]
        self.module.params = {
            'bios_config': {
                'setting1': 'newer value'
            },
        }
        config = drac.get_bios_config(self.module, self.bmc)
        self.bmc.list_bios_settings.assert_called_once_with()
        self.bmc.list_jobs.assert_called_once_with(only_unfinished=True)
        self.assertEqual(config.state, config.states.PRE_COMMITTED)
        applying = config.get_settings_to_apply()
        self.assertDictEqual(applying, {'setting1': 'newer value'})
        config.handle_reboot()
        applying = config.get_settings_to_apply()
        self.assertDictEqual(applying, {'setting1': 'newer value'})


class FakePDisk(object):
    def __init__(self, id, controller, size_mb, raid_status='ready'):
        self.id = id
        self.controller = controller
        self.size_mb = size_mb
        self.raid_status = raid_status


class FakeController(object):
    def __init__(self, id):
        self.id = id


class FakeVDisk(object):
    def __init__(self, name, controller, physical_disks, raid_level,
                 span_length, span_depth, size_mb, pending_operations=None):
        self.name = name
        self.controller = controller
        if physical_disks is not None:
            self.physical_disks = physical_disks
        self.raid_level = str(raid_level)
        self.span_depth = span_depth
        self.span_length = span_length
        self.size_mb = size_mb
        self.pending_operations = pending_operations
        # IDs are not user facing but must be unique.
        self.id = "%s-id" % name

    def __add__(self, other):
        """Override the addition operator to make this look like a tuple."""
        if isinstance(other, tuple):
            return (self.id, self.name, self.controller, self.raid_level,
                    self.size_mb, self.span_depth, self.span_length,
                    self.pending_operations) + other
        return super(FakeVDisk, self).__add__(other)


class TestDRACRAID(BaseTestCase):
    """Test case for Ansible drac module RAID configuration."""

    def test_has_committed_raid_job_no_jobs(self):
        jobs = []
        has_job = drac.has_committed_raid_job(jobs, 'Controller')
        self.assertFalse(has_job)

    def test_has_committed_raid_job_non_raid_jobs(self):
        jobs = [FakeJob('ConfigBIOS')]
        has_job = drac.has_committed_raid_job(jobs, 'Controller1')
        self.assertFalse(has_job)

    def test_has_committed_raid_job_with_raid_job(self):
        jobs = [FakeJob('Config:RAID:Controller1')]
        has_job = drac.has_committed_raid_job(jobs, 'Controller1')
        self.assertTrue(has_job)

    def test_has_committed_raid_job_with_different_controller_job(self):
        jobs = [FakeJob('Config:RAID:Controller2')]
        has_job = drac.has_committed_raid_job(jobs, 'Controller1')
        self.assertFalse(has_job)

    @mock.patch.object(drac, 'drac_exc')
    def test_get_raid_configs_list_pdisks_failure(self, mock_exc):
        mock_exc.BaseClientException = DummyDRACException
        self.bmc.list_physical_disks.side_effect = DummyDRACException
        self.assertRaises(FailJSON, drac.get_raid_configs,
                          self.module, self.bmc)

    @mock.patch.object(drac, 'drac_exc')
    def test_get_raid_configs_list_raid_controllers_failure(self, mock_exc):
        mock_exc.BaseClientException = DummyDRACException
        self.bmc.list_raid_controllers.side_effect = DummyDRACException
        self.assertRaises(FailJSON, drac.get_raid_configs,
                          self.module, self.bmc)

    @mock.patch.object(drac, 'drac_exc')
    def test_get_raid_configs_list_vdisks_failure(self, mock_exc):
        mock_exc.BaseClientException = DummyDRACException
        self.bmc.list_virtual_disks.side_effect = DummyDRACException
        self.assertRaises(FailJSON, drac.get_raid_configs,
                          self.module, self.bmc)

    @mock.patch.object(drac, 'drac_exc')
    def test_get_raid_configs_list_jobs_failure(self, mock_exc):
        mock_exc.BaseClientException = DummyDRACException
        self.bmc.list_jobs.side_effect = DummyDRACException
        self.assertRaises(FailJSON, drac.get_raid_configs,
                          self.module, self.bmc)

    def test_get_raid_configs_no_config(self):
        self.bmc.list_physical_disks.return_value = [
            FakePDisk('pdisk1', 'controller1', 42),
        ]
        self.bmc.list_raid_controllers.return_value = [
            FakeController('controller1'),
        ]
        self.bmc.list_virtual_disks.return_value = [
            FakeVDisk('vdisk1', 'controller1', ['pdisk1'], 1, 2, 1, 42),
        ]
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'raid_config': []
        }
        configs = drac.get_raid_configs(self.module, self.bmc)
        self.bmc.list_physical_disks.assert_not_called()
        self.bmc.list_raid_controllers.assert_not_called()
        self.bmc.list_virtual_disks.assert_not_called()
        self.assertListEqual(configs, [])

    def test_get_raid_configs_no_changes(self):
        self.bmc.list_physical_disks.return_value = [
            FakePDisk('pdisk1', 'controller1', 42),
        ]
        self.bmc.list_raid_controllers.return_value = [
            FakeController('controller1'),
        ]
        self.bmc.list_virtual_disks.return_value = [
            FakeVDisk('vdisk1', 'controller1', ['pdisk1'], 1, 2, 1, 42),
        ]
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'raid_config': [
                {
                    'name': 'vdisk1',
                    'raid_level': 1,
                    'span_length': 2,
                    'span_depth': 1,
                    'pdisks': [
                        'pdisk1',
                    ],
                },
            ],
        }
        configs = drac.get_raid_configs(self.module, self.bmc)
        self.bmc.list_physical_disks.assert_called_once_with()
        self.bmc.list_raid_controllers.assert_called_once_with()
        self.bmc.list_virtual_disks.assert_called_once_with()
        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(config.state, config.states.COMPLETE)

    def test_get_raid_configs_change_one(self):
        self.bmc.list_physical_disks.return_value = [
            FakePDisk('pdisk1', 'controller1', 42),
            FakePDisk('pdisk2', 'controller1', 42),
        ]
        self.bmc.list_raid_controllers.return_value = [
            FakeController('controller1')
        ]
        self.bmc.list_virtual_disks.return_value = [
            FakeVDisk('vdisk1', 'controller1', ['pdisk1'], 1, 2, 1, 42)
        ]
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'raid_config': [
                {
                    'name': 'vdisk1',
                    'raid_level': '1+0',
                    'span_length': 2,
                    'span_depth': 2,
                    'pdisks': [
                        'pdisk1',
                        'pdisk2',
                    ],
                },
            ],
        }
        configs = drac.get_raid_configs(self.module, self.bmc)
        self.bmc.list_physical_disks.assert_called_once_with()
        self.bmc.list_raid_controllers.assert_called_once_with()
        self.bmc.list_virtual_disks.assert_called_once_with()
        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(config.state, config.states.UNCOMMITTED)
        converting = config.get_pdisks_to_convert()
        self.assertListEqual(converting, [])
        deleting = config.get_vdisks_to_delete()
        self.assertListEqual(deleting, ['vdisk1-id'])
        creating = config.get_vdisks_to_create()
        self.assertListEqual(creating,
                             [{'disk_name': 'vdisk1', 'raid_level': '1+0',
                               'span_length': 2, 'span_depth': 2,
                               'size_mb': 84,
                               'physical_disks': ['pdisk1', 'pdisk2']}])

    def test_get_raid_configs_change_one_uncommitted_pending_create(self):
        self.bmc.list_physical_disks.return_value = [
            FakePDisk('pdisk1', 'controller1', 42),
        ]
        self.bmc.list_raid_controllers.return_value = [
            FakeController('controller1')
        ]
        self.bmc.list_virtual_disks.return_value = [
            FakeVDisk('vdisk1', 'controller1', ['pdisk1'], 1, 2, 1, 42,
                      'pending_create')
        ]
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'raid_config': [
                {
                    'name': 'vdisk1',
                    'raid_level': 1,
                    'span_length': 2,
                    'span_depth': 1,
                    'pdisks': [
                        'pdisk1',
                    ],
                },
            ],
        }
        configs = drac.get_raid_configs(self.module, self.bmc)
        self.bmc.list_physical_disks.assert_called_once_with()
        self.bmc.list_raid_controllers.assert_called_once_with()
        self.bmc.list_virtual_disks.assert_called_once_with()
        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(config.state, config.states.APPLIED)

    def test_get_raid_configs_change_one_uncommitted_pending_delete(self):
        self.bmc.list_physical_disks.return_value = [
            FakePDisk('pdisk1', 'controller1', 42),
        ]
        self.bmc.list_raid_controllers.return_value = [
            FakeController('controller1')
        ]
        self.bmc.list_virtual_disks.return_value = [
            FakeVDisk('vdisk1', 'controller1', ['pdisk1'], 1, 2, 1, 42,
                      'pending_delete')
        ]
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'raid_config': [
                {
                    'name': 'vdisk1',
                    'raid_level': 1,
                    'span_length': 2,
                    'span_depth': 1,
                    'pdisks': [
                        'pdisk1',
                    ],
                },
            ],
        }
        configs = drac.get_raid_configs(self.module, self.bmc)
        self.bmc.list_physical_disks.assert_called_once_with()
        self.bmc.list_raid_controllers.assert_called_once_with()
        self.bmc.list_virtual_disks.assert_called_once_with()
        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(config.state, config.states.CONFLICTING)
        config.handle_abandon()
        converting = config.get_pdisks_to_convert()
        self.assertListEqual(converting, [])
        deleting = config.get_vdisks_to_delete()
        self.assertListEqual(deleting, [])
        creating = config.get_vdisks_to_create()
        self.assertListEqual(creating, [])

    def test_get_raid_configs_change_one_committed_pending_create(self):
        self.bmc.list_physical_disks.return_value = [
            FakePDisk('pdisk1', 'controller1', 42),
        ]
        self.bmc.list_raid_controllers.return_value = [
            FakeController('controller1')
        ]
        self.bmc.list_virtual_disks.return_value = [
            FakeVDisk('vdisk1', 'controller1', ['pdisk1'], 1, 2, 1, 42,
                      'pending_create')
        ]
        self.bmc.list_jobs.return_value = [FakeJob('Config:RAID:controller1')]
        self.module.params = {
            'raid_config': [
                {
                    'name': 'vdisk1',
                    'raid_level': 1,
                    'span_length': 2,
                    'span_depth': 1,
                    'pdisks': [
                        'pdisk1',
                    ],
                },
            ],
        }
        configs = drac.get_raid_configs(self.module, self.bmc)
        self.bmc.list_physical_disks.assert_called_once_with()
        self.bmc.list_raid_controllers.assert_called_once_with()
        self.bmc.list_virtual_disks.assert_called_once_with()
        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(config.state, config.states.COMMITTED)

    def test_get_raid_configs_change_one_committed_pending_delete(self):
        self.bmc.list_physical_disks.return_value = [
            FakePDisk('pdisk1', 'controller1', 42),
        ]
        self.bmc.list_raid_controllers.return_value = [
            FakeController('controller1')
        ]
        self.bmc.list_virtual_disks.return_value = [
            FakeVDisk('vdisk1', 'controller1', ['pdisk1'], 1, 2, 1, 42,
                      'pending_delete')
        ]
        self.bmc.list_jobs.return_value = [FakeJob('Config:RAID:controller1')]
        self.module.params = {
            'raid_config': [
                {
                    'name': 'vdisk1',
                    'raid_level': 1,
                    'span_length': 2,
                    'span_depth': 1,
                    'pdisks': [
                        'pdisk1',
                    ],
                },
            ],
        }
        configs = drac.get_raid_configs(self.module, self.bmc)
        self.bmc.list_physical_disks.assert_called_once_with()
        self.bmc.list_raid_controllers.assert_called_once_with()
        self.bmc.list_virtual_disks.assert_called_once_with()
        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(config.state, config.states.PRE_COMMITTED)

    def test_get_raid_configs_change_one_uncommitted_conflicting_create(self):
        self.bmc.list_physical_disks.return_value = [
            FakePDisk('pdisk1', 'controller1', 42),
            FakePDisk('pdisk2', 'controller1', 42),
        ]
        self.bmc.list_raid_controllers.return_value = [
            FakeController('controller1')
        ]
        self.bmc.list_virtual_disks.return_value = [
            FakeVDisk('vdisk1', 'controller1', ['pdisk1'], 1, 2, 1, 42,
                      'pending_create')
        ]
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'raid_config': [
                {
                    'name': 'vdisk1',
                    'raid_level': 1,
                    'span_length': 2,
                    'span_depth': 1,
                    'pdisks': [
                        'pdisk2',
                    ],
                },
            ],
        }
        configs = drac.get_raid_configs(self.module, self.bmc)
        self.bmc.list_physical_disks.assert_called_once_with()
        self.bmc.list_raid_controllers.assert_called_once_with()
        self.bmc.list_virtual_disks.assert_called_once_with()
        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(config.state, config.states.CONFLICTING)
        config.handle_abandon()
        converting = config.get_pdisks_to_convert()
        self.assertListEqual(converting, [])
        deleting = config.get_vdisks_to_delete()
        self.assertListEqual(deleting, [])
        creating = config.get_vdisks_to_create()
        self.assertListEqual(creating,
                             [{'disk_name': 'vdisk1', 'raid_level': 1,
                               'span_length': 2, 'span_depth': 1,
                               'size_mb': 42, 'physical_disks': ['pdisk2']}])

    def test_get_raid_configs_change_one_uncommitted_conflicting_delete(self):
        self.bmc.list_physical_disks.return_value = [
            FakePDisk('pdisk1', 'controller1', 42),
            FakePDisk('pdisk2', 'controller1', 42),
        ]
        self.bmc.list_raid_controllers.return_value = [
            FakeController('controller1')
        ]
        self.bmc.list_virtual_disks.return_value = [
            FakeVDisk('vdisk1', 'controller1', ['pdisk1'], 1, 2, 1, 42,
                      'pending_delete')
        ]
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'raid_config': [
                {
                    'name': 'vdisk1',
                    'raid_level': 1,
                    'span_length': 2,
                    'span_depth': 1,
                    'pdisks': [
                        'pdisk2',
                    ],
                },
            ],
        }
        configs = drac.get_raid_configs(self.module, self.bmc)
        self.bmc.list_physical_disks.assert_called_once_with()
        self.bmc.list_raid_controllers.assert_called_once_with()
        self.bmc.list_virtual_disks.assert_called_once_with()
        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(config.state, config.states.CONFLICTING)
        config.handle_abandon()
        converting = config.get_pdisks_to_convert()
        self.assertListEqual(converting, [])
        deleting = config.get_vdisks_to_delete()
        self.assertListEqual(deleting, ['vdisk1-id'])
        creating = config.get_vdisks_to_create()
        self.assertListEqual(creating,
                             [{'disk_name': 'vdisk1', 'raid_level': 1,
                               'span_length': 2, 'span_depth': 1,
                               'size_mb': 42, 'physical_disks': ['pdisk2']}])

    def test_get_raid_configs_change_one_committed_conflicting_create(self):
        self.bmc.list_physical_disks.return_value = [
            FakePDisk('pdisk1', 'controller1', 42),
            FakePDisk('pdisk2', 'controller1', 42),
        ]
        self.bmc.list_raid_controllers.return_value = [
            FakeController('controller1')
        ]
        self.bmc.list_virtual_disks.return_value = [
            FakeVDisk('vdisk1', 'controller1', ['pdisk1'], 1, 2, 1, 42,
                      'pending_create')
        ]
        self.bmc.list_jobs.return_value = [FakeJob('Config:RAID:controller1')]
        self.module.params = {
            'raid_config': [
                {
                    'name': 'vdisk1',
                    'raid_level': 1,
                    'span_length': 2,
                    'span_depth': 1,
                    'pdisks': [
                        'pdisk2',
                    ],
                },
            ],
        }
        configs = drac.get_raid_configs(self.module, self.bmc)
        self.bmc.list_physical_disks.assert_called_once_with()
        self.bmc.list_raid_controllers.assert_called_once_with()
        self.bmc.list_virtual_disks.assert_called_once_with()
        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(config.state, config.states.PRE_COMMITTED)
        config.handle_reboot()
        converting = config.get_pdisks_to_convert()
        self.assertListEqual(converting, [])
        deleting = config.get_vdisks_to_delete()
        self.assertListEqual(deleting, ['vdisk1-id'])
        creating = config.get_vdisks_to_create()
        self.assertListEqual(creating,
                             [{'disk_name': 'vdisk1', 'raid_level': 1,
                               'span_length': 2, 'span_depth': 1,
                               'size_mb': 42, 'physical_disks': ['pdisk2']}])

    def test_get_raid_configs_change_one_committed_conflicting_delete(self):
        self.bmc.list_physical_disks.return_value = [
            FakePDisk('pdisk1', 'controller1', 42),
            FakePDisk('pdisk2', 'controller1', 42),
        ]
        self.bmc.list_raid_controllers.return_value = [
            FakeController('controller1')
        ]
        self.bmc.list_virtual_disks.return_value = [
            FakeVDisk('vdisk1', 'controller1', ['pdisk1'], 1, 2, 1, 42,
                      'pending_delete')
        ]
        self.bmc.list_jobs.return_value = [FakeJob('Config:RAID:controller1')]
        self.module.params = {
            'raid_config': [
                {
                    'name': 'vdisk1',
                    'raid_level': 1,
                    'span_length': 2,
                    'span_depth': 1,
                    'pdisks': [
                        'pdisk2',
                    ],
                },
            ],
        }
        configs = drac.get_raid_configs(self.module, self.bmc)
        self.bmc.list_physical_disks.assert_called_once_with()
        self.bmc.list_raid_controllers.assert_called_once_with()
        self.bmc.list_virtual_disks.assert_called_once_with()
        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(config.state, config.states.PRE_COMMITTED)
        config.handle_reboot()
        converting = config.get_pdisks_to_convert()
        self.assertListEqual(converting, [])
        deleting = config.get_vdisks_to_delete()
        self.assertListEqual(deleting, [])
        creating = config.get_vdisks_to_create()
        self.assertListEqual(creating,
                             [{'disk_name': 'vdisk1', 'raid_level': 1,
                               'span_length': 2, 'span_depth': 1,
                               'size_mb': 42, 'physical_disks': ['pdisk2']}])

    def test_get_raid_configs_one_controller_multiple_vdisks(self):
        self.bmc.list_physical_disks.return_value = [
            FakePDisk('pdisk1', 'controller1', 42),
            FakePDisk('pdisk2', 'controller1', 42),
        ]
        self.bmc.list_raid_controllers.return_value = [
            FakeController('controller1')
        ]
        self.bmc.list_virtual_disks.return_value = []
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'raid_config': [
                {
                    'name': 'vdisk1',
                    'raid_level': 1,
                    'span_length': 2,
                    'span_depth': 1,
                    'pdisks': [
                        'pdisk1',
                    ],
                },
                {
                    'name': 'vdisk2',
                    'raid_level': 1,
                    'span_length': 2,
                    'span_depth': 1,
                    'pdisks': [
                        'pdisk2',
                    ],
                },
            ],
        }
        configs = drac.get_raid_configs(self.module, self.bmc)
        self.bmc.list_physical_disks.assert_called_once_with()
        self.bmc.list_raid_controllers.assert_called_once_with()
        self.bmc.list_virtual_disks.assert_called_once_with()
        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(config.state, config.states.UNCOMMITTED)
        converting = config.get_pdisks_to_convert()
        self.assertListEqual(converting, [])
        deleting = config.get_vdisks_to_delete()
        self.assertListEqual(deleting, [])
        creating = config.get_vdisks_to_create()
        self.assertListEqual(creating,
                             [{'disk_name': 'vdisk1', 'raid_level': 1,
                               'span_length': 2, 'span_depth': 1,
                               'size_mb': 42, 'physical_disks': ['pdisk1']},
                              {'disk_name': 'vdisk2', 'raid_level': 1,
                               'span_length': 2, 'span_depth': 1,
                               'size_mb': 42, 'physical_disks': ['pdisk2']}])

    def test_get_raid_configs_multiple_controllers(self):
        self.bmc.list_physical_disks.return_value = [
            FakePDisk('pdisk1', 'controller1', 42),
            FakePDisk('pdisk2', 'controller2', 42),
        ]
        self.bmc.list_raid_controllers.return_value = [
            FakeController('controller1'),
            FakeController('controller2'),
        ]
        self.bmc.list_virtual_disks.return_value = []
        self.bmc.list_jobs.return_value = []
        self.module.params = {
            'raid_config': [
                {
                    'name': 'vdisk1',
                    'raid_level': 1,
                    'span_length': 2,
                    'span_depth': 1,
                    'pdisks': [
                        'pdisk1',
                    ],
                },
                {
                    'name': 'vdisk2',
                    'raid_level': 1,
                    'span_length': 2,
                    'span_depth': 1,
                    'pdisks': [
                        'pdisk2',
                    ],
                },
            ],
        }
        configs = drac.get_raid_configs(self.module, self.bmc)
        self.bmc.list_physical_disks.assert_called_once_with()
        self.bmc.list_raid_controllers.assert_called_once_with()
        self.bmc.list_virtual_disks.assert_called_once_with()
        self.assertEqual(len(configs), 2)
        config1 = [config for config in configs
                   if config.controller == 'controller1'][0]
        self.assertEqual(config1.state, config.states.UNCOMMITTED)
        self.assertEqual(config1.controller, 'controller1')
        converting = config1.get_pdisks_to_convert()
        self.assertListEqual(converting, [])
        deleting = config1.get_vdisks_to_delete()
        self.assertListEqual(deleting, [])
        creating = config1.get_vdisks_to_create()
        self.assertListEqual(creating,
                             [{'disk_name': 'vdisk1', 'raid_level': 1,
                               'span_length': 2, 'span_depth': 1,
                               'size_mb': 42, 'physical_disks': ['pdisk1']}])
        config2 = [config for config in configs
                   if config.controller == 'controller2'][0]
        self.assertEqual(config2.state, config.states.UNCOMMITTED)
        self.assertEqual(config2.controller, 'controller2')
        converting = config2.get_pdisks_to_convert()
        self.assertListEqual(converting, [])
        deleting = config2.get_vdisks_to_delete()
        self.assertListEqual(deleting, [])
        creating = config2.get_vdisks_to_create()
        self.assertListEqual(creating,
                             [{'disk_name': 'vdisk2', 'raid_level': 1,
                               'span_length': 2, 'span_depth': 1,
                               'size_mb': 42, 'physical_disks': ['pdisk2']}])

    @mock.patch.object(drac, 'drac_raid')
    @mock.patch.object(drac, 'drac_uris')
    @mock.patch.object(drac, 'drac_utils')
    def test_list_virtual_disks_with_physical_disk_workaround(self, mock_utils,
                                                              mock_uris,
                                                              mock_raid):
        def fake_find_xml(doc, attr, uri, find_all):
            class FakeElem(object):
                def __init__(self, text):
                    self.text = text

            if attr == 'DCIM_VirtualDiskView':
                return ['vdisk1', 'vdisk2']
            if attr == 'PhysicalDiskIDs':
                if doc == 'vdisk1':
                    return [FakeElem('pdisk1'), FakeElem('pdisk2')]
                if doc == 'vdisk2':
                    return [FakeElem('pdisk3'), FakeElem('pdisk4')]

        def fake_resource_attr(elem, uri, attr):
            return "%s-id" % elem

        self.bmc.list_virtual_disks.return_value = [
            FakeVDisk('vdisk1', 'controller1', None, 1, 2, 1, 42, None),
            FakeVDisk('vdisk2', 'controller2', None, 1, 2, 1, 42, None),
        ]
        mock_raid.VirtualDiskTuple._fields = ('id', 'name', 'controller',
            'raid_level', 'size_mb', 'span_depth', 'span_length',
            'pending_operations')
        mock_utils.find_xml.side_effect = fake_find_xml
        mock_utils.get_wsman_resource_attr.side_effect = fake_resource_attr
        vdisks = drac.list_virtual_disks(self.bmc)
        self.bmc.list_virtual_disks.assert_called_once_with()
        self.assertEqual(len(vdisks), 2)
        self.assertEqual(dict(vdisks[0]._asdict()),
            {'id': 'vdisk1-id', 'name': 'vdisk1', 'controller': 'controller1',
             'raid_level': '1', 'size_mb': 42, 'span_depth': 1,
             'span_length': 2, 'pending_operations': None,
             'physical_disks': ['pdisk1', 'pdisk2']})
        self.assertEqual(dict(vdisks[1]._asdict()),
            {'id': 'vdisk2-id', 'name': 'vdisk2', 'controller': 'controller2',
             'raid_level': '1', 'size_mb': 42, 'span_depth': 1,
             'span_length': 2, 'pending_operations': None,
             'physical_disks': ['pdisk3', 'pdisk4']})

    def test_compute_size_mb(self):
        goal_vdisk0 = {
            'name': 'vdisk0',
            'raid_level': 0,
            'span_length': 1,
            'span_depth': 2,
            'pdisks': [
                'pdisk1', 'pdisk2',
            ],
        }
        self.assertEqual(
            42 * 2, FakeRAIDConfig._compute_size_mb(goal_vdisk0, 42))

        goal_vdisk1 = {
            'name': 'vdisk1',
            'raid_level': 1,
            'span_length': 2,
            'span_depth': 1,
            'pdisks': [
                'pdisk1', 'pdisk2',
            ],
        }
        self.assertEqual(
            42, FakeRAIDConfig._compute_size_mb(goal_vdisk1, 42))

        goal_vdisk5 = {
            'name': 'vdisk5',
            'raid_level': 5,
            'span_length': 3,
            'span_depth': 1,
            'pdisks': [
                'pdisk1', 'pdisk2', 'pdisk3',
            ],
        }
        self.assertEqual(
            42 * 2, FakeRAIDConfig._compute_size_mb(goal_vdisk5, 42))

        goal_vdisk6 = {
            'name': 'vdisk6',
            'raid_level': 6,
            'span_length': 4,
            'span_depth': 1,
            'pdisks': [
                'pdisk1', 'pdisk2', 'pdisk3', 'pdisk4',
            ],
        }
        self.assertEqual(
            42 * 2, FakeRAIDConfig._compute_size_mb(goal_vdisk6, 42))

        goal_vdisk10 = {
            'name': 'vdisk10',
            'raid_level': '1+0',
            'span_length': 2,
            'span_depth': 3,
            'pdisks': [
                'pdisk1', 'pdisk2', 'pdisk3', 'pdisk4', 'pdisk5', 'pdisk6',
            ],
        }
        self.assertEqual(
            42 * 3, FakeRAIDConfig._compute_size_mb(goal_vdisk10, 42))

        goal_vdisk50 = {
            'name': 'vdisk50',
            'raid_level': '5+0',
            'span_length': 3,
            'span_depth': 3,
            'pdisks': [
                'pdisk1', 'pdisk2', 'pdisk3', 'pdisk4', 'pdisk5', 'pdisk6',
                'pdisk7', 'pdisk8', 'pdisk9',
            ],
        }
        self.assertEqual(
            42 * 2 * 3, FakeRAIDConfig._compute_size_mb(goal_vdisk50, 42))

        goal_vdisk60 = {
            'name': 'vdisk60',
            'raid_level': '6+0',
            'span_length': 4,
            'span_depth': 2,
            'pdisks': [
                'pdisk1', 'pdisk2', 'pdisk3', 'pdisk4', 'pdisk5', 'pdisk6',
                'pdisk7', 'pdisk8',
            ],
        }
        self.assertEqual(
            42 * 2 * 2, FakeRAIDConfig._compute_size_mb(goal_vdisk60, 42))


class FakeBIOSConfig(drac.BIOSConfig):
    def __init__(self, state, changing_settings):
        self.state = state
        self.changing_settings = changing_settings


class FakeRAIDConfig(drac.RAIDConfig):
    def __init__(self, controller, state, converting, deleting, creating):
        self.controller = controller
        self.state = state
        self.converting = converting
        self.deleting = deleting
        self.creating = creating


class TestValidateArgs(BaseTestCase):
    """Test case for Ansible module argument validation."""

    def setUp(self):
        super(TestValidateArgs, self).setUp()
        self.module.params = {
            'bios_config': {
                'NumLock': 'On'
            },
            'raid_config': [
                {
                    'name': 'vdisk1',
                    'raid_level': 1,
                    'span_length': 2,
                    'span_depth': 1,
                    'pdisks': [
                        'pdisk1',
                    ],
                },
                {
                    'name': 'vdisk2',
                    'raid_level': 1,
                    'span_length': 2,
                    'span_depth': 1,
                    'pdisks': [
                        'pdisk2',
                    ],
                },
            ],
        }

    def test_ok(self):
        drac.validate_args(self.module)

    def test_non_string_bios(self):
        self.module.params['bios_config']['NumLock'] = 1234
        self.assertRaises(FailJSON, drac.validate_args, self.module)

    def test_raid_missing_name(self):
        del(self.module.params['raid_config'][0]['name'])
        self.assertRaises(FailJSON, drac.validate_args, self.module)

    def test_raid_missing_raid_level(self):
        del(self.module.params['raid_config'][0]['raid_level'])
        self.assertRaises(FailJSON, drac.validate_args, self.module)

    def test_raid_missing_span_length(self):
        del(self.module.params['raid_config'][0]['span_length'])
        self.assertRaises(FailJSON, drac.validate_args, self.module)

    def test_raid_missing_span_depth(self):
        del(self.module.params['raid_config'][0]['span_depth'])
        self.assertRaises(FailJSON, drac.validate_args, self.module)

    def test_raid_missing_span_pdisks(self):
        del(self.module.params['raid_config'][0]['pdisks'])
        self.assertRaises(FailJSON, drac.validate_args, self.module)

    def test_raid_invalid_name(self):
        self.module.params['raid_config'][0]['name'] = object()
        self.assertRaises(FailJSON, drac.validate_args, self.module)

    def test_raid_invalid_raid_level(self):
        self.module.params['raid_config'][0]['raid_level'] = object()
        self.assertRaises(FailJSON, drac.validate_args, self.module)

    def test_raid_invalid_span_length(self):
        self.module.params['raid_config'][0]['span_length'] = object()
        self.assertRaises(FailJSON, drac.validate_args, self.module)

    def test_raid_invalid_span_depth(self):
        self.module.params['raid_config'][0]['span_depth'] = object()
        self.assertRaises(FailJSON, drac.validate_args, self.module)

    def test_raid_invalid_pdisks(self):
        self.module.params['raid_config'][0]['pdisks'] = object()
        self.assertRaises(FailJSON, drac.validate_args, self.module)

    def test_raid_invalid_pdisk(self):
        self.module.params['raid_config'][0]['pdisks'][0] = object()
        self.assertRaises(FailJSON, drac.validate_args, self.module)


class TestConfigure(BaseTestCase):
    """Test case for the main drac.configure function."""

    @mock.patch.object(drac, 'build_client')
    @mock.patch.object(drac, 'get_bios_config')
    @mock.patch.object(drac, 'get_raid_configs')
    @mock.patch.object(drac, 'wait_complete')
    def test_configure_bios(self, mock_wait, mock_raid, mock_bios, mock_build):
        mock_build.return_value = self.bmc
        mock_bios.return_value = FakeBIOSConfig(
            FakeBIOSConfig.states.UNCOMMITTED, {'NumLock': 'On'})
        mock_raid.return_value = []
        self.module.params = {
            'address': '',
            'username': '',
            'reboot': True,
            'timeout': 10,
            'interval': 1,
        }
        self.module.check_mode = False
        self.bmc.list_jobs.side_effect = [[FakeJob('ConfigBIOS')], []]
        self.bmc.get_power_state.return_value = 'POWER ON'
        drac.configure(self.module)
        self.bmc.set_bios_settings.assert_called_once_with({'NumLock': 'On'})
        self.bmc.commit_pending_bios_changes.assert_called_once_with(False)
        self.bmc.set_power_state.assert_called_once_with('REBOOT')
        mock_wait.assert_called_once_with(self.module, self.bmc)
        self.bmc.convert_physical_disks.assert_not_called()
        self.bmc.delete_virtual_disk.assert_not_called()
        self.bmc.create_virtual_disk.assert_not_called()

    @mock.patch.object(drac, 'build_client')
    @mock.patch.object(drac, 'get_bios_config')
    @mock.patch.object(drac, 'get_raid_configs')
    @mock.patch.object(drac, 'wait_complete')
    def test_configure_raid(self, mock_wait, mock_raid, mock_bios, mock_build):
        mock_build.return_value = self.bmc
        mock_bios.return_value = FakeBIOSConfig(
            FakeBIOSConfig.states.COMPLETE, {})
        mock_raid.return_value = [
            FakeRAIDConfig(
                'controller1', FakeRAIDConfig.states.UNCOMMITTED,
                ['pdisk1'], ['vdisk1'],
                [{'disk_name': 'vdisk2', 'raid_level': 1, 'span_length': 2,
                  'span_depth': 1, 'size_mb': 42,
                  'physical_disks': ['pdisk1']}]),
        ]
        self.module.params = {
            'address': '',
            'username': '',
            'reboot': True,
            'timeout': 10,
            'interval': 1,
        }
        self.module.check_mode = False
        self.bmc.list_jobs.side_effect = [[FakeJob('ConfigBIOS')], []]
        self.bmc.get_power_state.return_value = 'POWER ON'
        drac.configure(self.module)
        self.bmc.convert_physical_disks.assert_called_once_with(
            'controller1', ['pdisk1'])
        self.bmc.delete_virtual_disk.assert_called_once_with('vdisk1')
        self.bmc.create_virtual_disk.assert_called_once_with(
            'controller1', disk_name='vdisk2', raid_level=1, span_length=2,
            span_depth=1, size_mb=42, physical_disks=['pdisk1'])
        self.bmc.set_power_state.assert_called_with('REBOOT')
        self.assertEqual(3, self.bmc.set_power_state.call_count)
        mock_wait.assert_called_with(self.module, self.bmc)
        self.assertEqual(3, mock_wait.call_count)

    @mock.patch.object(drac, 'build_client')
    @mock.patch.object(drac, 'get_bios_config')
    @mock.patch.object(drac, 'get_raid_configs')
    @mock.patch.object(drac, 'wait_complete')
    def test_configure_bios_and_raid(self, mock_wait, mock_raid, mock_bios,
                                     mock_build):
        mock_build.return_value = self.bmc
        mock_bios.return_value = FakeBIOSConfig(
            FakeBIOSConfig.states.UNCOMMITTED, {'NumLock': 'On'})
        mock_raid.return_value = [
            FakeRAIDConfig(
                'controller1', FakeRAIDConfig.states.UNCOMMITTED,
                ['pdisk1'], ['vdisk1'],
                [{'disk_name': 'vdisk2', 'raid_level': 1, 'span_length': 2,
                  'span_depth': 1, 'size_mb': 42,
                  'physical_disks': ['pdisk1']}]),
        ]
        self.module.params = {
            'address': '',
            'username': '',
            'reboot': True,
            'timeout': 10,
            'interval': 1,
        }
        self.module.check_mode = False
        self.bmc.list_jobs.side_effect = [[FakeJob('ConfigBIOS')], []]
        self.bmc.get_power_state.return_value = 'POWER ON'
        drac.configure(self.module)
        self.bmc.set_bios_settings.assert_called_once_with({'NumLock': 'On'})
        self.bmc.commit_pending_bios_changes.assert_called_once_with(False)
        self.bmc.convert_physical_disks.assert_called_once_with(
            'controller1', ['pdisk1'])
        self.bmc.delete_virtual_disk.assert_called_once_with('vdisk1')
        self.bmc.create_virtual_disk.assert_called_once_with(
            'controller1', disk_name='vdisk2', raid_level=1, span_length=2,
            span_depth=1, size_mb=42, physical_disks=['pdisk1'])
        self.bmc.set_power_state.assert_called_with('REBOOT')
        self.assertEqual(4, self.bmc.set_power_state.call_count)
        mock_wait.assert_called_with(self.module, self.bmc)
        self.assertEqual(4, mock_wait.call_count)


if __name__ == "__main__":
    unittest.main()
