#!/usr/bin/python

from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase

class SampleTest(EutesterTestCase):
    def __init__(self):
        self.setuptestcase()
        self.setup_parser()
        self.get_args()
        # Setup basic eutester object
        self.tester = Eucaops( config_file=self.args.config,password=self.args.password)

    def clean_method(self):
        pass

    def MyTest(self):
        """
        This is where the test description goes
        """
        for machine in self.tester.get_component_machines("clc"):
            machine.sys("ifconfig")

if __name__ == "__main__":
    testcase = SampleTest()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or ["MyTest"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)