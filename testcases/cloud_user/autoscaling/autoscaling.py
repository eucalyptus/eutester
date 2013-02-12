#!/usr/bin/python

import time
from eucaops import Eucaops
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

    def AutoScalingBasics(self):
        self.launch_config_name = 'Test-Launch-Config-' + str(time.time())

        ### test create  and describe launch config
        self.tester.create_launch_config(name=self.launch_config_name, image_id=self.image.id, key_name=self.keypair.name,
                                         security_groups=[self.group.name])
        if len(self.tester.describe_launch_config([self.launch_config_name])) != 1:
            raise Exception('Launch Config not created')
        self.debug('***** Created Launch Config: ' + self.tester.describe_launch_config([self.launch_config_name])[0].name)

        ### test create and descibe auto scale group
        self.debug("Number of AS groups before create: " + len(self.tester.describe_as_group()))
        self.auto_scaling_group_name = 'Auto-Scaling-Group-' + str(time.time())
        self.tester.create_as_group(group_name=self.auto_scaling_group_name,
                                    launch_config=self.launch_config_name,
                                    availability_zones=self.tester.get_zones(),
                                    min_size=0,
                                    max_size=5,
                                    connection=self.tester.AS)
        self.debug("Created Auto Scaling Group: " + self.tester.describe_as_group(self.auto_scaling_group_name)[0].name)
        self.debug("Number of AS groups after create: " + len(self.tester.describe_as_group()))
        if len(self.tester.describe_as_group(self.auto_scaling_group_name)) != 1:
            raise Exception('Auto Scaling Group not created')

        ### Test Delete Auto Scaling Group
        self.tester.delete_as_group(self.auto_scaling_group_name, True)
        if len(self.tester.describe_as_group(self.auto_scaling_group_name)) != 0:
            raise Exception('Auto Scaling Group not deleted')
        self.debug('***** Deleted Auto Scaling Group: ' + self.auto_scaling_group_name)


        ### Test delete launch config
        self.tester.delete_launch_config(self.launch_config_name)
        if len(self.tester.describe_launch_config([self.launch_config_name])) != 0:
            raise Exception('Launch Config not deleted')
        self.debug('***** Deleted Launch Config: ' + self.launch_config_name)

    def AutoScalingInstanceBasics(self):
        """
        This case will test DescribeAutoScalingInstances, SetInstanceHealth and TerminateInstanceInAutoScalingGroup
        """
        pass

    def AutoScalingGroupBasics(self):
        """
        This case will be for basic Auto Scaling Group CRUD, SetDesiredCapacity and
        """
        pass

if __name__ == "__main__":
    testcase = AutoScalingBasics()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list "AutoScalingGroupBasics", "LaunchConfigBasics", "AutoScalingInstanceBasics"
    list = testcase.args.tests or ["AutoScalingBasics"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list, clean_on_exit=True)
    exit(result)