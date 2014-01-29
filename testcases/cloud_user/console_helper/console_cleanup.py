#!/usr/bin/python

import time
from eucaops import Eucaops
from eucaops import EC2ops
from eutester.eutestcase import EutesterTestCase
import os
import random

class ConsoleCleanUp(EutesterTestCase):
    def __init__(self, extra_args= None, **kwargs):
        self.setuptestcase()
        self.setup_parser()
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()
        for kwarg in kwargs:
            self.args[kwarg] = kwarg[kwarg]
        # Setup basic eutester object
        if self.args.region:
            self.tester = EC2ops( credpath=self.args.credpath, region=self.args.region)
        else:
            self.tester = Eucaops( credpath=self.args.credpath, config_file=self.args.config,password=self.args.password)
        self.tester.poll_count = 120



    def scan_and_clean_all_existing_resources(self):
        tester=self.tester

        tester.test_resources['volumes']=tester.ec2.get_all_volumes()
        tester.test_resources['keys']=tester.ec2.get_all_key_pairs()
        tester.test_resources['snapshots']=tester.ec2.get_all_snapshots()
        tester.test_resources['security-groups']=tester.ec2.get_all_security_groups()
        tester.test_resources['reservations']=tester.ec2.get_all_instances()
        tester.test_resources['addresses']=tester.ec2.get_all_addresses()
        tester.test_resources['auto-scaling-groups']=tester.autoscale.get_all_groups()
        tester.test_resources['launch-configurations']=tester.autoscale.get_all_launch_configurations()
        tester.cleanup_artifacts()






if __name__ == "__main__":
    testcase = ConsoleCleanUp()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or ["scan_and_clean_all_existing_resources"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=False)
    exit(result)