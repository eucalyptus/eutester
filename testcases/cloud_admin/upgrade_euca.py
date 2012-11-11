#!/usr/bin/env python
#
#
# Description:  This script upgrades a Eucalyptus cloud
from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase

class Upgrade(EutesterTestCase):
    def __init__(self, extra_args= None):
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument("--euca-url")
        self.parser.add_argument("--enterprise-url")
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()
        # Setup basic eutester object
        self.tester = Eucaops( config_file=self.args.config_file, password=self.args.password, download_creds=False)

    def add_euca_repo(self):
        for machine in self.tester.config["machines"]:
            machine.add_repo(self.args.euca_url,"euca-upgrade")

    def add_enterprise_repo(self):
        for machine in self.tester.config["machines"]:
            machine.add_repo(self.args.enterprise_url, "ent-upgrade")

    def upgrade_packages(self):
        for machine in self.tester.config["machines"]:
            machine.upgrade()

    def start_components(self):
        for machine in self.tester.config["machines"]:
            if "clc" in machine.components or "ws" in machine.components or "sc" in machine.components:
                machine.sys("service eucalyptus-cloud start")
            if "nc" in machine.components:
                machine.sys("service eucalyptus-nc start")
            if "cc" in machine.components:
                machine.sys("service eucalyptus-cc start")

    def UpgradeAll(self):
        #self.add_euca_repo()
        if self.args.enterprise_url:
            self.add_enterprise_repo()
        self.upgrade_packages()
        self.start_components()


if __name__ == "__main__":
    testcase = Upgrade()
    ### Either use the list of tests passed from config/command line to determine what subset of tests to run
    list = testcase.args.tests or [ "UpgradeAll"]
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )
        ### Run the EutesterUnitTest objects

    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)