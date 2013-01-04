#!/usr/bin/python

import time
from eucaops import Eucaops
from eucaops import EC2ops
from eucaops import ASops
from eutester.eutestcase import EutesterTestCase
import os
import random

class AutoScalingBasics(EutesterTestCase):
    def __init__(self, extra_args= None):
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument("--region", default=None)
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()
        # Setup basic eutester object
        if self.args.region:
            self.tester = EC2ops( credpath=self.args.credpath, region=self.args.region)
        else:
            self.tester = Eucaops( credpath=self.args.credpath)
        self.tester.poll_count = 120

        ### Add and authorize a group for the instance
        self.group = self.tester.add_group(group_name="group-" + str(time.time()))
        self.tester.authorize_group_by_name(group_name=self.group.name )
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )
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
        ### Terminate the reservation if it is still up
        if self.reservation:
            self.assertTrue(self.tester.terminate_instances(self.reservation), "Unable to terminate instance(s)")

        if self.volume:
            self.tester.delete_volume(self.volume,timeout=600)

        if self.snapshot:
            self.tester.delete_snapshot(self.snapshot)

        ### DELETE group
        self.tester.delete_group(self.group)

        ### Delete keypair in cloud and from filesystem
        self.tester.delete_keypair(self.keypair)
        os.remove(self.keypath)

    def CreateAutoScalingGroup(self):
        """
            This case was developed to exercise creating an Auto Scaling group
        """

    def DeleteAutoScalingGroup(self):
        """
            This case was developed to exercise deleting an Auto Scaling group
        """

    def DescribeAutoScalingGroups(self):
        """
            This case was developed to exercise describing an Auto Scaling group
        """

    def DescribeAutoScalingInstances(self):
        """
            This case was developed to exercise describing Auto Scaling instances
        """

    def SetDesiredCapacity(self):
        """
            This case was developed to exercise setting Auto Scaling group capacity
        """

    def SetInstanceHealth(self):
        """
            This case was developed to exercise setting the health of an instance belonging to an Auto Scaling group
        """

    def TerminateInstanceInAutoScalingGroup(self):
        """
            This case was developed to exercise terminating an instance belonging to an Auto Scaling group
        """

    def UpdateAutoScalingGroup(self):
        """
            This case was developed to exercise updating a specified Auto Scaling group
        """

    def CreateLaunchConfiguration(self):
        """
            This case was developed to exercise creating a new launch configuration
        """
        create_launch_config(test-lc, self.image)

    def DeleteLaunchConfiguration(self):
        """
            This case was developed to exercise deleting a launch configuration
        """

    def DescribeLaunchConfigurations(self):
        """
            This case was developed to exercise describing launch configurations
        """

if __name__ == "__main__":
    testcase = AutoScalingBasics()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list "CreateAutoScalingGroup", "DeleteAutoScalingGroup", "DescribeAutoScalingGroups",
    # "DescribeAutoScalingInstances", "SetDesiredCapacity", "SetInstanceHealth", "TerminateInstanceInAutoScalingGroup",
    # "UpdateAutoScalingGroup", "CreateLaunchConfiguration", "DeleteLaunchConfiguration", "DescribeLaunchConfigurations"
    list = testcase.args.tests or ["CreateLaunchConfiguration"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)