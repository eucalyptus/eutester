#!/usr/bin/python

import time
from eucaops import Eucaops
from eucaops import EC2ops
from eutester.eutestcase import EutesterTestCase
import os
import random

class PopulateUpgrade(EutesterTestCase):
    def __init__(self, extra_args= None):
        self.setuptestcase()
        self.setup_parser()
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()
        # Setup basic eutester object
        self.tester = Eucaops( credpath=self.args.credpath, config_file=self.args.config,password=self.args.password)
        self.tester.poll_count = 120

        self.security_groups = []

        ### Generate a keypair for the instance
        self.keypair = self.tester.add_keypair( "keypair-" + str(time.time()))
        self.keypath = '%s/%s.pem' % (os.curdir, self.keypair.name)
        self.image = self.args.emi
        if not self.image:
            self.image = self.tester.get_emi(root_device_type="instance-store")
        self.address = None
        self.volume = None
        self.snapshot = None
        self.private_addressing = False
        zones = self.tester.ec2.get_all_zones()
        self.zone = random.choice(zones).name
        self.reservation = None

    def clean_method(self):
        pass

    def Instances(self, type="instance-store"):
        """
        This case was developed to run through a series of basic instance tests.
             The tests are as follows:
                   - execute run_instances command
                   - make sure that public DNS name and private IP aren't the same
                       (This is for Managed/Managed-NOVLAN networking modes)
                   - test to see if instance is ping-able
                   - test to make sure that instance is accessible via ssh
                       (ssh into instance and run basic ls command)
             If any of these tests fail, the test case will error out, logging the results.
        """
        test_image = self.tester.get_emi(root_device_type=type)

        ### Add and authorize a group for the instance
        self.group = self.tester.add_group(group_name="group-" + str(time.time()))
        self.tester.authorize_group_by_name(group_name=self.group.name )
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )

        self.security_groups.append(self.group)

        # Test: INSTANCESTORE VOLATTACH:no ADDR:user
        instance_1 = self.tester.run_instance(test_image, keypair=self.keypair.name, group=self.group.name).instances[0]
        instance_1_address = self.tester.allocate_address()
        self.tester.associate_address(instance=instance_1, address=instance_1_address)

        # Test: INSTANCESTORE VOLATTACH:no ADDR:system
        instance_2 = self.tester.run_instance(test_image, keypair=self.keypair.name, group=self.group.name).instances[0]

        # Test: INSTANCESTORE VOLATTACH:no ADDR:system
        instance_3 = self.tester.run_instance(test_image, group=self.group.name, private_addressing=True, is_reachable=False).instances[0]

        # Test: INSTANCESTORE VOLATTACH:yes ADDR:user
        instance_4 = self.tester.run_instance(test_image, keypair=self.keypair.name, group=self.group.name).instances[0]
        instance_4_address = self.tester.allocate_address()
        self.tester.associate_address(instance=instance_4, address=instance_4_address)
        volume = self.tester.create_volume(zone=self.zone)
        instance_4.attach_volume(volume=volume)

        # Test: INSTANCESTORE VOLATTACH:yes ADDR:system
        instance_5 = self.tester.run_instance(test_image, keypair=self.keypair.name, group=self.group.name).instances[0]
        volume = self.tester.create_volume(zone=self.zone)
        instance_5.attach_volume(volume=volume)

        self.group = self.tester.add_group(group_name="group-" + str(time.time()))
        self.tester.authorize_group_by_name(group_name=self.group.name )
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )
        self.security_groups.append(self.group)
        # Test: INSTANCESTORE VOLATTACH:yes ADDR:system
        instance_6 = self.tester.run_instance(test_image, group=self.group.name, private_addressing=True, is_reachable=False).instances[0]

    def PopulateAll(self):
        self.Instances("instance-store")
        self.Instances("ebs")

if __name__ == "__main__":
    testcase = PopulateUpgrade()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or [ "PopulateAll"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)