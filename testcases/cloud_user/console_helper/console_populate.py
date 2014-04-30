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

    def populate_resources_for_console_test(self):
        '''
        This method creates resources in the cloud.

        '''
        zone=self.tester.ec2.get_all_zones()[0].name
        volume=self.tester.ec2.create_volume(1,zone)
        self.tester.wait_for_volume(volume)
        snapshot=self.tester.create_snapshot_from_volume(volume)
        self.tester.create_volume(zone=zone,snapshot=snapshot)
        keypair=self.tester.ec2.create_key_pair("test-key").name
        s_group=self.tester.ec2.create_security_group("mygroup", "Security group for console test.").name
        image=self.tester.get_images()[0]
        image_id=self.tester.get_images()[0].id
        instance=self.tester.run_image(image=image, keypair="test-key", group="mygroup",auto_connect=False, zone=zone)
        instance_id=self.tester.get_instances('running')[0].id
        ip=self.tester.allocate_address().public_ip
        self.tester.allocate_address()
        self.tester.ec2.associate_address(instance_id,ip)
        self.tester.create_launch_config("LC1",image_id ,keypair ,[s_group], instance_type="m1.small")
        self.tester.create_as_group("ASG1","LC1",self.tester.get_zones(),min_size=1,max_size=8,desired_capacity=2)
        instance=self.tester.get_instances('running')[0]
        self.tester.attach_volume(instance,volume,"vdb")

if __name__ == "__main__":
    testcase = ConsoleCleanUp()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or ["populate_resources_for_console_test"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=False)
    exit(result)