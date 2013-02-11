#!/usr/bin/python

import time
from eucaops import Eucaops
from eucaops import ASops
from eucaops.ec2ops import EC2ops
from eutester.eutestcase import EutesterTestCase
import os

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
        if self.args.emi:
            # self.AS_tester = ASops(credpath=self.args.credpath, region=self.args.region)
            # self.EC2_tester = EC2ops(credpath=self.args.credpath, region=self.args.region)
            self.tester = Eucaops(credpath=self.args.credpath, region=self.args.region)
        else:
            self.tester = Eucaops(credpath=self.args.credpath)

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

    def clean_method(self):
        ### DELETE group
        self.tester.delete_group(self.group)

        ### Delete keypair in cloud and from filesystem
        self.tester.delete_keypair(self.keypair)
        os.remove(self.keypath)

    def CreateAutoScalingGroup(self):
        """
            This case was developed to exercise creating an Auto Scaling group
        """
        pass

    def DeleteAutoScalingGroup(self):
        """
            This case was developed to exercise deleting an Auto Scaling group
        """
        pass

    def DescribeAutoScalingGroups(self):
        """
            This case was developed to exercise describing an Auto Scaling group
        """
        pass

    def DescribeAutoScalingInstances(self):
        """
            This case was developed to exercise describing Auto Scaling instances
        """
        pass

    def SetDesiredCapacity(self):
        """
            This case was developed to exercise setting Auto Scaling group capacity
        """
        pass

    def SetInstanceHealth(self):
        """
            This case was developed to exercise setting the health of an instance belonging to an Auto Scaling group
        """
        pass

    def TerminateInstanceInAutoScalingGroup(self):
        """
            This case was developed to exercise terminating an instance belonging to an Auto Scaling group
        """
        pass

    def UpdateAutoScalingGroup(self):
        """
            This case was developed to exercise updating a specified Auto Scaling group
        """
        pass

    def CreateLaunchConfiguration(self):
        """
            This case was developed to exercise creating a new launch configuration
            image_id="ami-0af30663" a us-east image
        """
        # self.tester.create_launch_config(name="test_lc", image_id=str(self.image), key_name=str(self.keypair),
        #                                  security_groups=self.group.name)

        self.tester.create_launch_config(name="test_lc", image_id="ami-0af30663")

    def DeleteLaunchConfiguration(self):
        """
            This case was developed to exercise deleting a launch configuration
        """
        self.tester.delete_launch_config(launch_config_name="test_lc")

    def DescribeLaunchConfigurations(self):
        """
            This case was developed to exercise describing launch configurations
        """
        pass

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
    result = testcase.run_test_case_list(unit_list, clean_on_exit=True)
    exit(result)