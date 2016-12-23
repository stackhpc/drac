DRAC BIOS
=========

This role supports configuration of BIOS settings on Dell machines with an
iDRAC card.

[![Build Status](https://travis-ci.org/stackhpc/drac.svg?branch=master)](https://travis-ci.org/stackhpc/drac)
[![Ansible Galaxy](https://img.shields.io/badge/role-stackhpc.drac-blue.svg)](https://galaxy.ansible.com/stackhpc/drac/)

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
: Dict mapping ?

`drac_reboot`
: Whether to reboot the node once BIOS settings have been applied.

`drac_timeout`
: Time in seconds to wait for pending operations to complete. 0 means to wait forever.

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
            ?

License
-------

BSD

Author Information
------------------

- Authors: Mark Goddard & Stig Telfer
- Company: StackHPC Ltd
- Website: https://stackhpc.com
