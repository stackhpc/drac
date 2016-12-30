DRAC
====

This role supports configuration of BIOS settings and RAID on Dell machines
with an iDRAC card.

[![Build Status](https://travis-ci.org/stackhpc/drac.svg?branch=master)](https://travis-ci.org/stackhpc/drac)
[![Ansible Galaxy](https://img.shields.io/badge/role-stackhpc.drac-blue.svg)](https://galaxy.ansible.com/stackhpc/drac/)

This role will apply changes required to reach the configuration specified by
the user, using the Web Services Management (WSMAN) protocol.
If there are any existing pending changes, whether committed or uncommitted,
these will be taken into account and applied in addition to the specified
changes.
Where any pending changes conflict with specified changes, those specified
as arguments to this module take priority.

If the `drac_reboot` argument is specified as `true`, the system will be
rebooted to apply the changes.
There may be some cases where the changes could not be applied without
rebooting the system at least once. In these cases, the role will fail if
the user has specified the reboot argument as false.
Since the system may be rebooted (up to 3 times in total) to apply the
configuration, this role may take a long time to execute.

Requirements
------------

The role provides a module, `drac`, that is dependent upon the
`python-dracclient` module. This must be installed in order for this module
to function correctly.

Role Variables
--------------

The following variables may be set for this role:

`drac_address`
: The address to use when communicating with the DRAC.

`drac_username`
: The username to use when communicating with the DRAC.

`drac_password`
: The password to use when communicating with the DRAC.

`drac_bios_config`
: Dict mapping BIOS configuration names to their desired values.

`drac_raid_config`
: List of virtual disk configurations. Each item should be a dict containing
  the following items: `name`, `raid\_level`, `span\_length`, `span\_depth`,
  `pdisks`. The `pdisks` item should be a list of physical disk IDs.

`drac_reboot`
: Whether to reboot the node (if required) once the configuration has been
  applied.

`drac_timeout`
: Time in seconds to wait for pending operations to complete. 0 means to wait
  forever.

`drac_interval`
: Time in seconds between polling for operations to complete.

Dependencies
------------

None

Example Playbook
----------------

This role may be used as follows:

    - hosts: dell-servers
      roles:
        - role: stackhpc.drac
          drac_address: 1.2.3.4
          drac_username: foo
          drac_password: bar
          drac_bios_config:
            NumLock: 'On' 
            SysProfile: 'PerfOptimized'
          drac_raid_config:
            - name: Virtual disk 1
              raid_level: 1
              span_length: 2
              span_depth: 1
              pdisks:
                - 'Disk.Bay.1:Enclosure.Internal.0-1:RAID.Integrated.1-1'
                - 'Disk.Bay.2:Enclosure.Internal.0-1:RAID.Integrated.1-1'

License
-------

BSD

Author Information
------------------

- Authors: Mark Goddard & Stig Telfer
- Company: StackHPC Ltd
- Website: https://stackhpc.com
