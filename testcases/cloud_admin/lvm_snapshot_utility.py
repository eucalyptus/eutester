#!/usr/bin/python
# Software License Agreement (BSD License)
#
# Copyright (c) 2009-2011, Eucalyptus Systems, Inc.
# All rights reserved.
#
# Redistribution and use of this software in source and binary forms, with or
# without modification, are permitted provided that the following conditions
# are met:
#
#   Redistributions of source code must retain the above
#   copyright notice, this list of conditions and the
#   following disclaimer.
#
#   Redistributions in binary form must reproduce the above
#   copyright notice, this list of conditions and the
#   following disclaimer in the documentation and/or other
#   materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Author: tony@eucalyptus.com
from platform import machine

from eucaops import Eucaops
import re
import string
from eutester.euinstance import EuInstance
from eutester.eutestcase import EutesterTestCase
from eutester.sshconnection import CommandTimeoutException


class LVMSnapshotUtility(EutesterTestCase):
    
    def __init__(self,extra_args = None):
        self.setuptestcase()
        self.setup_parser()
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.parser.add_argument("--name", default="post_config")
        self.get_args()
        # Setup basic eutester object
        self.tester = Eucaops( config_file=self.args.config, password=self.args.password, download_creds=False)

    def clean_method(self):
        pass

    def CreateLVMSnapshot(self):
        '''
        Create LVM Snapshot
        '''
        machines = self.tester.get_component_machines()
        for machine in machines:
            if machine.distro.name is "vmware":
                continue
            machine.sys("lvcreate -l 100%origin -s -n " + self.args.name + " `blkid -L rootfs`", code=0)

    def RestoreLVMSnapshot(self):
        '''
        Restore LVM Snapshot
        '''

        machines = self.tester.get_component_machines()
        check_file = "/root/merge-executed"
        for machine in machines:
            if machine.distro.name is "vmware":
                continue
            logical_volume = "/dev/vg01/" + self.args.name
            machine.sys("e2label " + logical_volume + " rootfs")
            machine.sys("touch " + check_file)
            machine.sys("lvconvert --merge " + logical_volume, code=0)
            try:
                machine.sys("reboot -f", timeout=2)
            except CommandTimeoutException:
                pass

        self.tester.sleep(30)

        for machine in machines:
            self.tester.ping(machine.hostname, poll_count=120)

        for machine in machines:
            def ssh_refresh():
                try:
                    machine.refresh_ssh()
                    return True
                except:
                    return False
            self.tester.wait_for_result(ssh_refresh, True, timeout=120)
            machine.sys('ls ' + check_file, code=2)
            def lv_gone():
                try:
                    machine.sys("lvdisplay " + logical_volume, code=5)
                    return True
                except:
                    return False
            self.tester.wait_for_result(lv_gone, True, timeout=240)
            machine.sys("lvcreate -l 100%origin -s -n " + logical_volume + " `blkid -L rootfs`", code=0)

    def get_safe_uptime(self, machine):
            uptime = None
            try:
                uptime = machine.get_uptime()
            except: pass
            return uptime


if __name__ == "__main__":
    testcase = LVMSnapshotUtility()
    ### Either use the list of tests passed from config/command line to determine what subset of tests to run
    list = testcase.args.tests or ["CreateLVMSnapshot"]
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )
        ### Run the EutesterUnitTest objects

    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)