#!/usr/bin/env python
#
#
# Description:  This script encompasses test cases/modules concerning instance specific behavior and
#               features for Eucalyptus.  The test cases/modules that are executed can be
#               found in the script under the "tests" list.


import time
from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase

class MyTestCase(EutesterTestCase):
    def __init__(self, config_file=None, password=None):
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument("--command", default="free")
        self.parser.add_argument("--component", default=None)
        self.get_args()
        # Setup basic eutester object
        self.tester = Eucaops( config_file=self.args.config_file, password=self.args.password,download_creds=False)

    def clean_method(self):
        pass

    def MyTestUnit(self):
        """
        A test description must go here......
        This test will simply run an instance and check that it is reachable via ssh
        """
        target_machines = []
        if not self.args.component:
            target_machines = self.tester.config['machines']
        else:
            target_machines = self.tester.get_component_machines(self.args.component)

        for machine in target_machines:
            if machine.distro.name is "vmware":
                continue
            machine.sys(self.args.command)

if __name__ == "__main__":
    testcase = MyTestCase()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list  "VolumeTagging", "InstanceTagging", "SnapshotTagging", "ImageTagging"
    list = testcase.args.tests or ["MyTestUnit"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)
