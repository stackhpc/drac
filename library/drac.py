#!/usr/bin/python

import collections
import syslog
import time

from ansible.module_utils.basic import *

# Store a list of import errors to report to the user.
IMPORT_ERRORS = []
try:
    import dracclient.client as drac
    import dracclient.exceptions as drac_exc
    from dracclient.resources import raid as drac_raid
    from dracclient.resources import uris as drac_uris
    from dracclient import utils as drac_utils
except Exception as e:
    IMPORT_ERRORS.append(e)
    drac, drac_exc, drac_raid, drac_uris, drac_utils = (
        None, None, None, None, None)


DOCUMENTATION = """
---
module: drac
short_description: Ansible module for configuring BIOS and RAID via DRAC
description:
  - Ansible module for configuring BIOS settings and RAID controllers on Dell
    machines with an iDRAC card.
  - The module will apply changes required to reach the configuration
    specified by the user, using the Web Services Management (WSMAN) protocol.
  - If there are any existing pending changes, whether committed or
    uncommitted, these will be taken into account and applied in addition to
    the specified changes.
  - Where any pending changes conflict with specified changes, those specified
    as arguments to this module take priority.
  - If the reboot argument is specified as true, the system will be rebooted
    to apply the changes.
  - There may be some cases where the changes could not be applied without
    rebooting the system at least once. In these cases, the module will fail if
    the user has specified the reboot argument as false.
  - Since the system may be rebooted (up to 3 times in total) to apply the
    configuration, this module may take a long time to execute.
author: Mark Goddard (@markgoddard) & Stig Telfer (@oneswig)
requirements:
  - python-dracclient >= 2.0.0
options:
  address:
    description: Address to use when communicating with the DRAC
    required: True
  username:
    description: Username to use when communicating with the DRAC
    required: True
  password:
    description: Address to use when communicating with the DRAC
    required: True
  bios_config:
    description: Dict mapping BIOS configuration names to their desired values
    required: False
    default: {}
  raid_config:
    description: >
      List of RAID virtual disk configurations. Each item is a dict containing
      the following items: 'name', 'raid_level', 'span_length', 'span_depth',
      'pdisks'. The 'pdisks' item should be a list of IDs of physical disks.
    required: False
    default: []
  reboot:
    description: >
      Whether to reboot the node once BIOS settings have been applied, if
      required
    required: False
    default: False
  timeout:
    description: >
      Time in seconds to wait for pending operations to complete. 0 means to
      wait forever
    required: False
    default: 0
  interval:
    description: >
      Time in seconds between polling for pending operations to complete
    required: False
    default: 5
"""

EXAMPLES = """
# Set the NumLock BIOS setting to 'On'.
- drac:
    address: 1.2.3.4
    username: admin
    password: secretpass
    bios_config:
      NumLock: "On"
    reboot: True
    timeout: 600

# Configure RAID with two virtual disks.
- drac:
    address: 1.2.3.4
    username: admin
    password: secretpass
    raid_config:
      - name: vol1
        raid_level: 1
        span_length: 2
        span_depth: 1
        pdisks:
          - Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1
          - Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1
      - name: vol2
        raid_level: 10
        span_length: 2
        span_depth: 3
        pdisks:
          - Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1
          - Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1
          - Disk.Bay.4:Enclosure.Internal.0-1:RAID.Integrated.1-1
          - Disk.Bay.5:Enclosure.Internal.0-1:RAID.Integrated.1-1
          - Disk.Bay.6:Enclosure.Internal.0-1:RAID.Integrated.1-1
          - Disk.Bay.7:Enclosure.Internal.0-1:RAID.Integrated.1-1
    reboot: True
    timeout: 600
"""

RETURN = """
changed_bios_settings:
  description: >
    Dict mapping names of BIOS settings that were changed to their new values
  returned: success
  type: dict
  sample:
    NumLock: "On"
converted_physical_disks:
  description: >
    List of physical disks that were converted to RAID mode from non-RAID mode.
    Each item is a dict containing the RAID controller ID and physical disk ID.
  returned: success
  type: list
  sample:
    - controller: RAID.Integrated.1-1
      id: Disk.Bay.0:Enclosure.Internal.0-1:RAID.Integrated.1-1
    - controller: RAID.Integrated.1-1
      id: Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1
created_virtual_disks:
  description: >
    List of virtual disks that were created. Each item is a dict containing the
    name, RAID controller ID, RAID level, span length, span depth and
    constituent physical disks of the virtual disk.
  returned: success
  type: list
  sample:
    - name: Virtual Disk 1
      controller: RAID.Integrated.1-1
      raid_level: 1
      span_length: 2
      span_depth: 1
      physical_disks:
        - Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1
        - Disk.Bay.3:Enclosure.Internal.0-1:RAID.Integrated.1-1
deleted_virtual_disks:
  description: >
    List of virtual disks that were deleted. Each item is a dict containing the
    RAID controller ID and virtual disk ID.
  returned: success
  type: list
  sample:
    - controller: RAID.Integrated.1-1
      id: Disk.Virtual.0:RAID.Integrated.1-1
reboot_required:
  description: Whether a reboot is required to apply the settings
  returned: success
  type: bool
"""


class UnknownSetting(Exception):
    """A configuration option was not found."""


class Timeout(Exception):
    """A timeout occurred."""


class VDiskLost(Exception):
    """A previously reported virtual disk is no longer being reported."""


class DRACConfig(object):
    """State machine for DRAC configuration via WSMAN.

    This object should be used as a base class for classes representing a
    particular channel of WSMAN configuration, such as the BIOS settings or
    RAID configuration for a RAID controller.

    The object tracks the current phase of configuration and provides
    information on the actions that are required to reach the goal state.
    """

    class states(object):
        """State name constants."""

        # Unknown starting state.
        UNKNOWN = 'unknown'

        # Existing conflicting changes applied but uncommitted.
        CONFLICTING = 'conflicting'

        # Existing conflicting changes abandoned.
        ABANDONED = 'abandoned'

        # Existing changes committed, further changes required to reach goal.
        PRE_COMMITTED = 'pre-committed'

        # Required changes not applied or committed. No committed or
        # uncommitted changes.
        UNCOMMITTED = 'uncommitted'

        # Required changes applied.
        APPLIED = 'applied'

        # Required changes committed.
        COMMITTED = 'committed'

        # Complete - no further changes required.
        COMPLETE = 'complete'

    class actions(object):
        """Action name constants."""

        # Pending changes have been abandoned.
        ABANDON = 'abandon'

        # Changes have been applied.
        APPLY = 'apply'

        # Applied changes have been committed.
        COMMIT = 'commit'

        # The system has been rebooted, flushing any committed pending changes.
        REBOOT = 'reboot'

    # Required actions for each state. A dict mapping current states to the
    # action required to progress the configuration.
    required_actions = {
        states.UNCOMMITTED: actions.APPLY,
        states.CONFLICTING: actions.ABANDON,
        states.ABANDONED: actions.APPLY,
        states.PRE_COMMITTED: actions.REBOOT,
        states.APPLIED: actions.COMMIT,
        states.COMMITTED: actions.REBOOT,
        states.COMPLETE: None,
    }

    def __init__(self, name, committed_job):
        # A human-friendly name for this configuration.
        self.name = name
        # Whether there are any current committed changes.
        self.committed_job = committed_job
        # Our current state.
        self.state = self.states.UNKNOWN

    def is_change_required(self):
        """Return whether any changes need to be applied.

        This method should be implemented by subclasses.
        """
        raise NotImplemented()

    def _is_action_required(self, action):
        """Return whether a given action is required to progress to the goal.

        :param action: The action to query.
        """
        assert self.state in self.required_actions
        return self.required_actions[self.state] == action

    def is_flush_required(self):
        """Return whether a flush is required to progress to the goal."""
        return (self.is_reboot_required() and
                self.state != self.states.COMMITTED)

    def is_abandon_required(self):
        """Return whether an abandon is required to progress to the goal."""
        return self._is_action_required(self.actions.ABANDON)

    def is_apply_required(self):
        """Return whether an apply is required to progress to the goal."""
        return self._is_action_required(self.actions.APPLY)

    def is_commit_required(self):
        """Return whether a commit is required to progress to the goal."""
        return self._is_action_required(self.actions.COMMIT)

    def is_reboot_required(self):
        """Return whether a reboot is required to progress to the goal."""
        return self._is_action_required(self.actions.REBOOT)

    def is_complete(self, include_reboot):
        """Return whether configuration is complete.

        :param include_reboot: Whether to include reboot in the required
            actions to reach completion.
        """
        if self.state == self.states.COMPLETE:
            return True
        if not include_reboot and self.state == self.states.COMMITTED:
            return True
        return False

    def _validate_transition(self, action, allowed_states):
        """Validate a state transition.

        :param action: The action being taken
        :param allowed_states: A list of valid current states
        :raises AssertionError: If the transition is invalid
        """
        assert self.state in allowed_states, (
            "Coding error: invalid state transition detected for %s handling "
            "action %s, current state %s, allowed states %s" %
            (self.name, action, self.state, ", ".join(allowed_states)))

    def handle_abandon(self):
        """Handle an abandon action."""
        self._validate_transition(self.actions.ABANDON,
                                  {self.states.CONFLICTING})
        if not self.is_change_required():
            self.state = self.states.COMPLETE
        else:
            self.state = self.states.ABANDONED

    def handle_apply(self):
        """Handle an apply action."""
        self._validate_transition(self.actions.APPLY,
                                  {self.states.UNCOMMITTED,
                                   self.states.ABANDONED})
        self.state = self.states.APPLIED

    def handle_commit(self):
        """Handle a commit action."""
        self._validate_transition(self.actions.COMMIT,
                                  {self.states.APPLIED})
        self.state = self.states.COMMITTED

    def handle_reboot(self):
        """Handle a reboot action."""
        # NOTE: reboot is valid in any state.
        if self.state == self.states.COMMITTED:
            self.state = self.states.COMPLETE
        elif self.state == self.states.PRE_COMMITTED:
            self.state = self.states.UNCOMMITTED

    def set_initial_state(self, changing, pending, conflicting):
        """Set the initial state of the configuration state machine.

        :param changing: Whether any changes are required
        :param pending: Whether there are any pending changes that must be
            applied
        :param conflicting: Whether there are any conflicting pending changes
        """
        if self.committed_job:
            if changing or conflicting:
                self.state = self.states.PRE_COMMITTED
            elif pending:
                self.state = self.states.COMMITTED
            else:
                self.state = self.states.COMPLETE
        else:
            if conflicting:
                self.state = self.states.CONFLICTING
            elif changing:
                self.state = self.states.UNCOMMITTED
            elif pending:
                self.state = self.states.APPLIED
            else:
                self.state = self.states.COMPLETE


class BIOSConfig(DRACConfig):
    """Configuration state machine for DRAC BIOS settings."""

    def __init__(self, bios_settings, committed_job):
        super(BIOSConfig, self).__init__('BIOS', committed_job)
        # The current BIOS settings as reported by the DRAC.
        self.bios_settings = bios_settings
        # Dict names of settings we need to change to their new values.
        self.changing_settings = {}

    def is_change_required(self):
        return bool(self.changing_settings)

    def validate(self, goal_settings):
        """Validate the requested BIOS configuration settings.

        :param goal_settings: The requested BIOS configuration settings.
        :raises UnknownSetting if the requested settings are invalid.
        """
        unknown = set(goal_settings) - set(self.bios_settings)
        if unknown:
            raise UnknownSetting("BIOS setting(s) do not exist: %s" %
                                 ", ".join(unknown))

    def process(self, goal_settings):
        """Process the requested BIOS configuration settings.

        :param goal_settings: The requested BIOS configuration settings.
        """
        self._determine_initial_state(goal_settings)
        self._determine_required_changes(goal_settings)

    def _determine_initial_state(self, goal_settings):
        """Determine and set the initial state of the state machine.

        :param goal_settings: The requested BIOS configuration settings.
        """
        changing = False
        pending = False
        conflicting = False
        for key, goal_setting in goal_settings.items():
            bios_setting = self.bios_settings[key]
            # If there is a pending change and it is correct, we do not need to
            # apply this setting.
            if bios_setting.pending_value is not None:
                if bios_setting.pending_value == goal_setting:
                    pending = True
                    continue
                else:
                    conflicting = True

            # We need to apply this setting if the current value is not the
            # desired value or there is a pending change.
            if (bios_setting.current_value != goal_setting or
                    bios_setting.pending_value is not None):
                changing = True

        self.set_initial_state(changing, pending, conflicting)

    def _determine_required_changes(self, goal_settings):
        """Determine the changes required to apply the requested BIOS settings.

        :param goal_settings: The requested BIOS configuration settings.
        """
        abandoning = self.is_abandon_required()
        # If abandoning, initialise the settings with any pending values.
        if abandoning:
            self.changing_settings = {
                key: bios_setting.pending_value
                for key, bios_setting in self.bios_settings.items()
                if bios_setting.pending_value is not None
            }
            self.changing_settings.update(goal_settings)
        else:
            self.changing_settings = {}
            for key, goal_setting in goal_settings.items():
                bios_setting = self.bios_settings[key]
                # If there is a pending change and it is correct, we do not
                # need to apply this setting.
                if bios_setting.pending_value is not None:
                    if bios_setting.pending_value == goal_setting:
                        continue

                # We need to apply this setting if the current value is not the
                # desired value or there is a pending change.
                if (bios_setting.current_value != goal_setting or
                        bios_setting.pending_value is not None):
                    self.changing_settings[key] = goal_setting

    def get_settings_to_apply(self):
        """Return the BIOS settings to apply."""
        return self.changing_settings.copy()


class RAIDConfig(DRACConfig):
    """Configuration state machine for a single RAID controller."""

    def __init__(self, controller, pdisks, vdisks, committed_job):
        super(RAIDConfig, self).__init__('RAID:%s' % controller, committed_job)
        # ID of the RAID controller.
        self.controller = controller
        # Dict mapping reported physical disk IDs to physical disks.
        self.pdisks = pdisks
        # Dict mapping reported virtual disk names to virtual disks.
        self.vdisks = vdisks
        # List of physical disk IDs on this controller to be converted.
        self.converting = []
        # List of IDs of virtual disks to be deleted.
        self.deleting = []
        # List of virtual disks to be created, containing keyword
        # arguments to dracclient.client.DRACClient.create_virtual_disk().
        self.creating = []

    def is_change_required(self):
        return bool(self.converting or self.deleting or self.creating)

    @staticmethod
    def vdisk_diff(goal_vdisk, vdisk, min_size_mb):
        """Return whether two virtual disks differ.

        :param goal_vdisk: The requested virtual disk configuration.
        :param vdisk: The reported virtual disk configuration.
        :param min_size_mb: Size of the smallest disk in MB.
        """
        # Compare RAID level as a string. FIXME: make this more intelligent.
        return (str(goal_vdisk['raid_level']) != vdisk.raid_level or
                goal_vdisk['span_depth'] != vdisk.span_depth or
                goal_vdisk['span_length'] != vdisk.span_length or
                goal_vdisk['pdisks'] != vdisk.physical_disks or
                min_size_mb * goal_vdisk['span_depth'] != vdisk.size_mb)

    def process(self, goal_vdisks):
        """Process the requested RAID configuration.

        :param goal_vdisks: List of requested virtual disks for this controller
        """
        self._determine_initial_state(goal_vdisks)
        self._determine_required_changes(goal_vdisks)

    def _determine_initial_state(self, goal_vdisks):
        """Determine and set the initial state of the state machine.

        :param goal_vdisks: List of requested virtual disks for this controller
        """
        changing = False
        pending = False
        conflicting = False
        for goal_vdisk in goal_vdisks.values():
            if goal_vdisk['name'] in self.vdisks:
                min_size_mb = min([self.pdisks[pdisk_id].size_mb
                                   for pdisk_id in goal_vdisk['pdisks']])
                vdisk = self.vdisks[goal_vdisk['name']]
                diff = self.vdisk_diff(goal_vdisk, vdisk, min_size_mb)
                if diff:
                    changing = True
                    if vdisk.pending_operations is not None:
                        conflicting = True
                else:
                    if vdisk.pending_operations == 'pending_delete':
                        conflicting = True
                    elif vdisk.pending_operations == 'pending_create':
                        pending = True
            else:
                changing = True

        self.set_initial_state(changing, pending, conflicting)

    @staticmethod
    def _compute_size_mb(goal_vdisk, min_size_mb):
        raid_level = str(goal_vdisk['raid_level'])
        if raid_level in ('6', '6+0'):
            parity_disks_per_span = 2
        elif raid_level in ('5', '5+0'):
            parity_disks_per_span = 1
        else:
            parity_disks_per_span = 0
        length = goal_vdisk['span_length'] - parity_disks_per_span
        effective_length = 1 if raid_level in ('1', '1+0') else length
        return min_size_mb * effective_length * goal_vdisk['span_depth']

    def _determine_required_changes(self, goal_vdisks):
        """Determine the changes required to apply the requested RAID config.

        :param goal_vdisks: List of requested virtual disks for this controller
        """
        # Determine which physical disks to convert.
        for goal_vdisk in goal_vdisks.values():
            for pdisk_id in goal_vdisk['pdisks']:
                pdisk = self.pdisks[pdisk_id]
                if pdisk.raid_status == 'non-RAID':
                    self.converting.append(pdisk_id)

        # Determine which of the requested virtual disks need to be deleted
        # and/or (re)created.
        abandoning = self.is_abandon_required()
        for goal_vdisk in goal_vdisks.values():
            min_size_mb = min([self.pdisks[pdisk_id].size_mb
                               for pdisk_id in goal_vdisk['pdisks']])
            create = True
            if goal_vdisk['name'] in self.vdisks:
                vdisk = self.vdisks[goal_vdisk['name']]
                diff = self.vdisk_diff(goal_vdisk, vdisk, min_size_mb)
                if diff:
                    delete = False
                    if abandoning:
                        if vdisk.pending_operations in {None,
                                                        'pending_delete'}:
                            delete = True
                    else:
                        if vdisk.pending_operations in {None,
                                                        'pending_create'}:
                            delete = True
                    if delete:
                        self.deleting.append(vdisk.id)
                else:
                    if abandoning:
                        if vdisk.pending_operations in {None,
                                                        'pending_delete'}:
                            create = False
                    else:
                        if vdisk.pending_operations in {None,
                                                        'pending_create'}:
                            create = False

            if create:
                size_mb = self._compute_size_mb(goal_vdisk, min_size_mb)
                create_vdisk = {
                    'physical_disks': goal_vdisk['pdisks'],
                    'raid_level': goal_vdisk['raid_level'],
                    'size_mb': size_mb,
                    'disk_name': goal_vdisk['name'],
                    'span_length': goal_vdisk['span_length'],
                    'span_depth': goal_vdisk['span_depth'],
                }
                self.creating.append(create_vdisk)

        # If we're abandoning any pending changes on other vdisks, ensure they
        # get reapplied.
        if abandoning:
            for vdisk in self.vdisks.values():
                if vdisk.name in goal_vdisks:
                    continue
                if vdisk.pending_operations == 'pending_create':
                    create_vdisk = {
                        'physical_disks': vdisk.physical_disks,
                        'raid_level': vdisk.raid_level,
                        'size_mb': vdisk.size_mb,
                        'disk_name': vdisk.disk_name,
                        'span_length': vdisk.span_length,
                        'span_depth': vdisk.span_depth,
                    }
                    self.creating.append(create_vdisk)
                elif vdisk.pending_operations == 'pending_delete':
                    self.deleting.append(vdisk.id)

    def is_convert_required(self):
        """Return whether any physical disks need to be converted to RAID."""
        return bool(self.converting)

    def get_pdisks_to_convert(self):
        """Return a list of physical disks to convert to RAID mode."""
        return self.converting[:]

    def get_vdisks_to_delete(self):
        """Return a list of IDs of virtual disks to delete."""
        return self.deleting[:]

    def get_vdisks_to_create(self):
        """Return a list of virtual disks to create.

        :returns: A list of dicts containing keyword arguments for the
            dracclient.client.DRACClient.create_virtual_disk method.
        """
        return self.creating[:]


def debug(module, message):
    """Log a debug message.

    :param module: The AnsibleModule instance
    :param message: The message to log
    """
    log_args = {"PRIORITY": syslog.LOG_DEBUG, "MODULE": "drac",
                "CODE_FILE": "drac.py"}
    module.log(message, log_args)


def build_client(module):
    """Build a DRAC client instance.

    :param module: The AnsibleModule instance
    :returns: dracclient.client.DRACClient instance
    """
    return drac.DRACClient(module.params['address'],
                           module.params['username'],
                           module.params['password'])


def has_committed_bios_job(jobs):
    """Determine whether there are any committed pending ConfigBIOS jobs.

    :param jobs: A list of dracclient.resources.job.Job object
    :returns: Whether there are any pending ConfigBIOS jobs
    """
    return any(job.name.startswith('ConfigBIOS') for job in jobs)


def has_committed_raid_job(jobs, controller):
    """Determine whether there are any committed pending Config:RAID jobs.

    :param jobs: A list of dracclient.resources.job.Job object
    :param controller: ID of the RAID controller
    :returns: Whether there are any pending RAID jobs
    """
    job_name = 'Config:RAID:%s' % controller
    return any(job.name == job_name for job in jobs)


def wait_complete(module, bmc):
    """Poll BMC state until there are no unfinished jobs.

    :param module: The AnsibleModule instance
    :param bmc: A dracclient.client.DRACClient instance
    :raises Timeout: If the job queue did not empty before the timeout
    """
    timeout = module.params['timeout']
    interval = module.params['interval']
    end = time.time() + timeout if timeout > 0 else None
    while True:
        try:
            jobs = bmc.list_jobs(only_unfinished=True)
        except drac_exc.BaseClientException as e:
            module.fail_json(msg="Failed to check unfinished jobs: %s" %
                             repr(e))
        if len(jobs) == 0:
            debug(module, "No pending jobs")
            return

        job_descs = [repr(job) for job in jobs]
        # Check for timeouts.
        if end and time.time() > end:
            raise Timeout("Timed out after %s seconds waiting for BMC to "
                          "complete pending jobs: %s" %
                          (timeout, ", ".join(job_descs)))

        debug(module, "Waiting for pending jobs to complete: %s" %
              ", ".join(job_descs))
        time.sleep(interval)


def get_bios_config(module, bmc):
    """Query current BIOS settings and return a BIOS configuration object.

    :param module: The AnsibleModule instance
    :param bmc: A dracclient.client.DRACClient instance
    :returns: A BIOSConfig object initialised with the initial state of the
        configuration state machine.
    """
    if not module.params['bios_config']:
        debug(module, "No BIOS settings requested")
        # Return an empty config object.
        config = BIOSConfig({}, False)
        config.process({})
        return config

    debug(module, "Checking BIOS settings")
    try:
        bios_settings = bmc.list_bios_settings()
        unfinished_jobs = bmc.list_jobs(only_unfinished=True)
    except drac_exc.BaseClientException as e:
        module.fail_json(msg="Failed to list BIOS settings: %s" % repr(e))

    settings_descs = {key: {"current": value.current_value,
                            "pending": value.pending_value}
                      for key, value in bios_settings.items()}
    debug(module, "Existing BIOS settings: %s" % repr(settings_descs))

    committed_job = has_committed_bios_job(unfinished_jobs)
    config = BIOSConfig(bios_settings, committed_job)
    try:
        config.validate(module.params['bios_config'])
    except UnknownSetting as e:
        module.fail_json(msg=repr(e))
    config.process(module.params['bios_config'])

    debug(module, "Created BIOS config: state=%s" % config.state)

    return config


def add_pdisks_to_vdisks(bmc, vdisks):
    """Add a list of constituent physical disks to each virtual disk object.

    :param bmc: A dracclient.client.DRACClient instance
    :param vdisks: A list of dracclient.resources.raid.VirtualDisk objects.
    :returns: A list of VirtualDisk-like objects with physical disks.
    """
    doc = bmc.client.enumerate(drac_uris.DCIM_VirtualDiskView)
    vdisk_elems = drac_utils.find_xml(doc, 'DCIM_VirtualDiskView',
                                      drac_uris.DCIM_VirtualDiskView,
                                      find_all=True)
    new_fields = drac_raid.VirtualDiskTuple._fields + ('physical_disks',)
    VirtualDisk = collections.namedtuple('VirtualDisk', new_fields)
    new_vdisks = []
    for vdisk in vdisks:
        for vdisk_elem in vdisk_elems:
            vdisk_elem_id = drac_utils.get_wsman_resource_attr(
                vdisk_elem, drac_uris.DCIM_VirtualDiskView, 'FQDD')
            if vdisk_elem_id == vdisk.id:
                break
        else:
            raise VDiskLost("Unable to find a matching virtual disk in "
                            "returned XML. Has the node been rebooted during "
                            "execution of this module?")

        pdisk_elems = drac_utils.find_xml(vdisk_elem, 'PhysicalDiskIDs',
                                          drac_uris.DCIM_VirtualDiskView,
                                          find_all=True)
        pdisks = [pdisk_elem.text.strip() for pdisk_elem in pdisk_elems
                  if pdisk_elem.text]
        new_vdisk = VirtualDisk(*(vdisk + (pdisks,)))
        new_vdisks.append(new_vdisk)
    return new_vdisks


def list_virtual_disks(bmc):
    """List RAID virtual disks.

    Ensure that the VirtualDisk objects returned have lists of their
    component physical disks. If the dracclient module is too old to provide
    this feature, manually query the DRAC to pull the physical disk information
    from the returned XML.

    :param bmc: A dracclient.client.DRACClient instance
    :returns: A list of virtual disk objects.
    """
    vdisks = bmc.list_virtual_disks()
    if not vdisks:
        return vdisks

    # Check whether the virtual disks already have a physical_disks attribute.
    try:
        vdisks[0].physical_disks
    except AttributeError:
        return add_pdisks_to_vdisks(bmc, vdisks)
    else:
        return vdisks


def map_controller_to_vdisks(module, pdisks, vdisks):
    """Map RAID controllers to requested virtual disk configurations.

    :param module: The AnsibleModule instance
    :param pdisks: List of physical disks reported by the DRAC
    :param vdisks: List of virtual disks reported by the DRAC
    :returns: A dict mapping RAID controller IDs to dicts mapping requested
        virtual disk names to the requested configuration.
    """
    # Provide a mapping from reported physical disk ID to controller ID.
    pdisk_to_controller = {pdisk.id: pdisk.controller for pdisk in pdisks}

    # Ensure that all specified physical disks are valid.
    for goal_vdisk in module.params['raid_config']:
        unknown_pdisks = set(goal_vdisk['pdisks']) - set(pdisk_to_controller)
        if unknown_pdisks:
            module.fail_json(msg="Requested RAID configuration for %s "
                             "contains physical disks not reported by DRAC: "
                             "%s" % (goal_vdisk['name'], unknown_pdisks))

    # Ensure that each virtual disk maps to a single RAID controller.
    mapping = {}
    for goal_vdisk in module.params['raid_config']:
        goal_controllers = {pdisk_to_controller[pdisk]
                            for pdisk in goal_vdisk['pdisks']}
        if len(goal_controllers) > 1:
            goal_pdisk_to_controller = {pdisk.id: pdisk.controller
                                        for pdisk in pdisks
                                        if pdisk.id in goal_vdisk['pdisks']}
            module.fail_json(msg="Requested RAID configuration for %s "
                             "contains physical disks on multiple "
                             "controllers: %s" %
                             (goal_vdisk['name'], goal_pdisk_to_controller))
        controller = goal_controllers.pop()
        mapping.setdefault(controller, collections.OrderedDict())
        mapping[controller][goal_vdisk['name']] = goal_vdisk
    return mapping


def get_raid_configs(module, bmc):
    """Query current RAID config and return a list of RAID config objects.

    :param module: The AnsibleModule instance
    :param bmc: A dracclient.client.DRACClient instance
    :returns: A list of RAIDConfig objects for each RAID controller with
        a requested virtual disk configuration.
    """
    if not module.params['raid_config']:
        debug(module, "No RAID configuration requested")
        return []

    debug(module, "Checking RAID configuration")
    try:
        pdisks = bmc.list_physical_disks()
        controllers = bmc.list_raid_controllers()
        vdisks = list_virtual_disks(bmc)
        unfinished_jobs = bmc.list_jobs(only_unfinished=True)
    except (drac_exc.BaseClientException, VDiskLost) as e:
        module.fail_json(msg="Failed to list RAID configuration: %s" % repr(e))

    pdisk_descs = [repr(pdisk) for pdisk in pdisks]
    controller_descs = [repr(controller) for controller in controllers]
    vdisk_descs = [repr(vdisk) for vdisk in vdisks]
    debug(module, "Existing physical disks: %s" % ", ".join(pdisk_descs))
    debug(module, "Existing controllers: %s" % ", ".join(controller_descs))
    debug(module, "Existing virtual disks: %s" % ", ".join(vdisk_descs))

    mapping = map_controller_to_vdisks(module, pdisks, vdisks)
    configs = []
    for controller, goal_vdisks in mapping.items():
        committed_job = has_committed_raid_job(unfinished_jobs, controller)
        controller_pdisks = {pdisk.id: pdisk for pdisk in pdisks
                             if pdisk.controller == controller}
        controller_vdisks = {vdisk.name: vdisk for vdisk in vdisks
                             if vdisk.controller == controller}
        config = RAIDConfig(controller, controller_pdisks, controller_vdisks,
                            committed_job)
        config.process(goal_vdisks)
        configs.append(config)

    for config in configs:
        debug(module, "Created RAID config: controller=%s state=%s" %
              (config.controller, config.state))

    return configs


def flush(module, bmc):
    """Flush any committed pending configuration changes by rebooting.

    Wait for any committed jobs to be flushed by polling the job queue.

    :param module: The AnsibleModule instance
    :param bmc: A dracclient.client.DRACClient instance
    """
    debug(module, "Flushing BIOS and/or RAID settings by rebooting")
    current_state = bmc.get_power_state()
    goal_state = 'POWER_ON' if current_state == 'POWER_OFF' else 'REBOOT'
    # Reboot or power on the node.
    try:
        bmc.set_power_state(goal_state)
    except drac_exc.BaseClientException as e:
        module.fail_json(msg="Failed to set power state to %s to apply "
                         "pending BIOS settings: %s" % (goal_state, repr(e)))

    # Wait for the reboot to flush pending jobs.
    try:
        wait_complete(module, bmc)
    except Timeout as e:
        module.fail_json(msg="Failed waiting for reboot to flush "
                         "pending BIOS settings: %s" % repr(e))

    # Power off the node if it was previously powered off.
    if current_state == 'POWER_OFF':
        try:
            bmc.set_power_state('POWER_OFF')
        except drac_exc.BaseClientException as e:
            module.fail_json(msg="Failed to set power state to off: %s"
                             % repr(e))


def abandon_bios(module, bmc):
    """Abandon uncommitted pending BIOS configuration changes.

    :param module: The AnsibleModule instance
    :param bmc: A dracclient.client.DRACClient instance
    """
    debug(module, "Abandoning pending BIOS configuration changes")
    try:
        bmc.abandon_pending_bios_changes()
    except drac_exc.BaseClientException as e:
        module.fail_json(msg="Failed to abandon pending BIOS jobs: %s" %
                         repr(e))


def apply_bios(module, bmc, settings):
    """Apply BIOS configuration changes.

    :param module: The AnsibleModule instance
    :param bmc: A dracclient.client.DRACClient instance
    :param settings: A dict of BIOS settings to apply.
    """
    debug(module, "Applying BIOS settings; %s" % settings)
    try:
        bmc.set_bios_settings(settings)
    except drac_exc.BaseClientException as e:
        module.fail_json(msg="Failed while applying BIOS settings: %s" %
                         repr(e))


def commit_bios(module, bmc):
    """Commit pending BIOS configuration changes.

    :param module: The AnsibleModule instance
    :param bmc: A dracclient.client.DRACClient instance
    """
    debug(module, "Committing pending BIOS settings")
    try:
        bmc.commit_pending_bios_changes(False)
    except drac_exc.BaseClientException as e:
        module.fail_json(msg="Failed while committing BIOS settings: %s" %
                         repr(e))


def abandon_raid(module, bmc, controller):
    """Abandon uncommitted pending RAID configuration changes.

    :param module: The AnsibleModule instance
    :param bmc: A dracclient.client.DRACClient instance
    :param controller: The RAID controller ID
    """
    debug(module, "Abandoning pending RAID configuration changes for "
          "controller %s" % controller)
    try:
        bmc.abandon_pending_raid_changes(controller)
    except drac_exc.BaseClientException as e:
        module.fail_json(msg="Failed to abandon pending RAID jobs: %s" %
                         repr(e))


def convert_raid(module, bmc, controller, pdisks):
    """Convert physical disks to RAID mode.

    :param module: The AnsibleModule instance
    :param bmc: A dracclient.client.DRACClient instance
    :param controller: The RAID controller ID
    :param pdisks: A list of IDs of physical disks to convert
    """
    debug(module, "Converting physical disks to RAID mode: %s" %
          ", ".join(pdisks))
    try:
        bmc.convert_physical_disks(controller, pdisks)
    except drac_exc.BaseClientException as e:
        module.fail_json(msg="Failed while converting physical disks to RAID "
                         "mode: %s" % repr(e))


def apply_raid(module, bmc, controller, deleting, creating):
    """Apply RAID configuration changes.

    :param module: The AnsibleModule instance
    :param bmc: A dracclient.client.DRACClient instance
    :param controller: The RAID controller ID
    :param deleting: A list of IDs of virtual disks to delete
    :param creating: A list of dicts of keyword arguments to the
        dracclient.client.DRACClient.create_virtual_disks method
    """
    for vdisk in deleting:
        debug(module, "Deleting RAID virtual disk %s" % vdisk)
        try:
            bmc.delete_virtual_disk(vdisk)
        except drac_exc.BaseClientException as e:
            module.fail_json(msg="Failed while deleting RAID virtual disk: "
                             "%s" % repr(e))

    for vdisk in creating:
        debug(module, "Creating RAID virtual disk %s" % vdisk)
        try:
            bmc.create_virtual_disk(controller, **vdisk)
        except drac_exc.BaseClientException as e:
            module.fail_json(msg="Failed while creating RAID virtual disk: "
                             "%s" % repr(e))


def commit_raid(module, bmc, controller):
    """Commit pending RAID configuration changes.

    :param module: The AnsibleModule instance
    :param bmc: A dracclient.client.DRACClient instance
    :param controller: The RAID controller ID
    """
    debug(module, "Committing pending RAID settings for controller %s" %
          controller)
    try:
        bmc.commit_pending_raid_changes(controller, False)
    except drac_exc.BaseClientException as e:
        module.fail_json(msg="Failed while committing RAID settings: %s" %
                         repr(e))


def configure(module):
    """Configure a node's BIOS and RAID via DRAC.

    :param module: The AnsibleModule instance
    :returns: A dict of keyword arguments for module.exit_json()
    """
    debug(module, "Configuring BIOS for %s@%s" %
          (module.params["username"], module.params["address"]))
    bmc = build_client(module)

    # Gather required changes.
    bios_config = get_bios_config(module, bmc)
    raid_configs = get_raid_configs(module, bmc)
    all_configs = [bios_config] + raid_configs

    do_reboot = module.params['reboot']
    # Do we need to make any changes?
    any_incomplete = any(not config.is_complete(do_reboot)
                         for config in all_configs)
    # Do we need to convert any physical disks to RAID mode?
    any_converting = any(config.is_convert_required()
                         for config in raid_configs)
    # Do we need to both flush committed changes and convert physical disks to
    # RAID mode for any RAID controllers?
    any_flushing_and_converting = any(config.is_flush_required() or
                                      config.is_convert_required()
                                      for config in raid_configs)

    # Check whether we require a pre-configuration flush.
    pre_flush_required = False
    if bios_config.is_flush_required() and not any_converting:
        pre_flush_required = True
    elif any_flushing_and_converting:
        pre_flush_required = True

    # Check whether the requested configuration requires a reboot.
    if not do_reboot:
        if pre_flush_required or any_converting:
            module.fail_json(msg="Requested configuration requires the system "
                             "to be rebooted before being applied but the "
                             "module 'reboot' argument was false.")

    # Will the system need to be rebooted after this module has exited?
    reboot_required = not do_reboot and any_incomplete

    # The result to be returned by the module.
    result = {
        "changed": any_incomplete,
        "changed_bios_settings": bios_config.get_settings_to_apply(),
        "converted_physical_disks": [
            {
                "controller": config.controller,
                "id": converted
            }
            for config in raid_configs
            for converted in config.get_pdisks_to_convert()
        ],
        "created_virtual_disks": [
            {
                "controller": config.controller,
                "name": created["disk_name"],
                "raid_level": created["raid_level"],
                "span_length": created["span_length"],
                "span_depth": created["span_depth"],
                "physical_disks": created["physical_disks"]
            }
            for config in raid_configs
            for created in config.get_vdisks_to_create()
        ],
        "deleted_virtual_disks": [
            {
                "controller": config.controller,
                "id": deleted
            }
            for config in raid_configs
            for deleted in config.get_vdisks_to_delete()
        ],
        "reboot_required": reboot_required,
    }

    if module.check_mode:
        return result

    if not result["changed"]:
        debug(module, "No BIOS or RAID configuration changes required")
        return result

    # Abandon pending BIOS changes if required.
    if bios_config.is_abandon_required():
        abandon_bios(module, bmc)
        bios_config.handle_abandon()

    # Abandon pending RAID changes if required.
    for raid_config in raid_configs:
        if raid_config.is_abandon_required():
            abandon_raid(module, bmc, raid_config.controller)
            raid_config.handle_abandon()

    # Reboot #1:
    # Reboot to flush previously committed configuration if required.
    if pre_flush_required:
        assert do_reboot, (
            "Coding error: require flush but can't due to module arguments")
        flush(module, bmc)
        for config in all_configs:
            config.handle_reboot()

    # Convert physical disks to RAID mode if required.
    for raid_config in raid_configs:
        if raid_config.is_convert_required():
            to_convert = raid_config.get_pdisks_to_convert()
            convert_raid(module, bmc, raid_config.controller, to_convert)
            commit_raid(module, bmc, raid_config.controller)
            # NOTE: Don't handle_apply() or handle_commit() here as this
            # doesn't move us to the goal state.

    # Reboot #2:
    # Flush configuration if any physical disks were converted.
    if any_converting:
        assert do_reboot, (
            "Coding error: require flush but can't due to module arguments")
        flush(module, bmc)
        for config in all_configs:
            config.handle_reboot()

    # NOTE: Previously we were configuring BIOS and RAID simultaneously in
    # order to avoid an unnecessary reboot. This was found to cause problems
    # on a particular R630 server, causing the configuration to fail and the
    # Lifecycle controller to enter a reboot loop. The issue was resolved by
    # resetting the iDRAC configuration to factory defaults and clearing the
    # job queue. Rather than go through that process again we'll apply BIOS
    # and RAID configuration separately.

    # If there are any BIOS changes to apply, then apply them.
    if bios_config.is_apply_required():
        apply_bios(module, bmc, bios_config.get_settings_to_apply())
        bios_config.handle_apply()

    # Commit pending BIOS configuration changes.
    if bios_config.is_commit_required():
        commit_bios(module, bmc)
        bios_config.handle_commit()

    # Reboot #3:
    # Reboot to apply BIOS changes.
    if do_reboot and bios_config.is_reboot_required():
        flush(module, bmc)
        for config in all_configs:
            config.handle_reboot()

    # If there are any RAID changes to apply, then apply them.
    for raid_config in raid_configs:
        if raid_config.is_apply_required():
            deleting = raid_config.get_vdisks_to_delete()
            creating = raid_config.get_vdisks_to_create()
            apply_raid(module, bmc, raid_config.controller, deleting, creating)
            raid_config.handle_apply()

    # Commit pending RAID configuration changes.
    for raid_config in raid_configs:
        if raid_config.is_commit_required():
            commit_raid(module, bmc, raid_config.controller)
            raid_config.handle_commit()

    # Reboot #4:
    # Reboot to apply RAID changes.
    if do_reboot and any(config.is_reboot_required()
                         for config in raid_configs):
        flush(module, bmc)
        for config in all_configs:
            config.handle_reboot()

    # Sanity check that all required actions have been taken.
    any_incomplete = any(not config.is_complete(do_reboot)
                         for config in all_configs)
    if any_incomplete:
        module.fail_json(msg="DRAC configuration incomplete at end of module "
                         "execution. States: %s" % {config.name: config.state
                                                    for config in all_configs})
    return result


def validate_vdisk(vdisk):
    """Validate a virtual disk argument.

    :param vdisk: A single virtual disk argument
    """
    if not isinstance(vdisk, dict):
        return False
    required_keys = {'name', 'raid_level', 'span_length', 'span_depth',
                     'pdisks'}
    missing_keys = required_keys - set(vdisk)
    if missing_keys:
        return False
    if not isinstance(vdisk['name'], basestring):
        return False
    if not all(isinstance(vdisk[attr], (basestring, int))
               for attr in {'raid_level', 'span_length', 'span_depth'}):
        return False
    pdisks = vdisk['pdisks']
    if not isinstance(pdisks, list):
        return False
    if not all(isinstance(pdisk, basestring) for pdisk in pdisks):
        return False
    return True


def validate_args(module):
    """Validate module arguments.

    :param module: An ansible.module_utils.basic.AnsibleModule instance
    """
    non_string_settings = {
        name: setting
        for name, setting in module.params['bios_config'].items()
        if not isinstance(setting, basestring)
    }
    if non_string_settings:
        module.fail_json(msg="BIOS settings must be string values. The "
                         "following settings are not strings: %s" %
                         non_string_settings)

    invalid_vdisks = [
        vdisk for vdisk in module.params['raid_config']
        if not validate_vdisk(vdisk)
    ]
    if invalid_vdisks:
        module.fail_json(msg="RAID configuration must be a list of dicts with "
                         "the following items: 'name', 'raid_level', "
                         "'span_length', 'span_depth', 'pdisks'. The 'pdisks' "
                         "item should be a list of IDs of physical disks. The "
                         "following items were invalid: %s" % invalid_vdisks)


def main():
    """Module entry point."""
    module = AnsibleModule(
        argument_spec=dict(
            address=dict(required=True, type='str'),
            username=dict(required=True, type='str'),
            password=dict(required=True, type='str'),
            bios_config=dict(required=False, default={}, type='dict'),
            raid_config=dict(required=False, default=[], type='list'),
            reboot=dict(default=False, type='bool'),
            timeout=dict(default=0, type='int'),
            interval=dict(default=5, type='int'),
        ),
        supports_check_mode=True,
    )

    # Fail if there were any exceptions when importing modules.
    if IMPORT_ERRORS:
        module.fail_json(msg="Import errors: %s" %
                         ", ".join([repr(e) for e in IMPORT_ERRORS]))

    # Further argument validation.
    validate_args(module)

    try:
        result = configure(module)
    except Exception as e:
        debug(module, traceback.format_exc())
        module.fail_json(msg="Failed to configure DRAC: %s" % repr(e))
    else:
        module.exit_json(**result)


if __name__ == '__main__':
    main()
