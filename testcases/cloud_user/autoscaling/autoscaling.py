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

    def AutoScalingGroupBasics(self):
        """
        This case will be for basic Auto Scaling Group CRUD, SetDesiredCapacity and
        """
        pass

    def AutoScalingInstanceBasics(self):
        """
        This case will test DescribeAutoScalingInstances, SetInstanceHealth and TerminateInstanceInAutoScalingGroup
        """
        pass

    def LaunchConfigBasics(self):
        self.name = 'Test-Launch-Config-' + str(time.time())

        self.tester.create_launch_config(name=self.name, image_id=self.image.id, key_name=self.keypair.name,
                                         security_groups=self.group.name)
        list_size_after_create = len(self.tester.describe_launch_config([self.name]))
        if list_size_after_create != 1:
            raise Exception('Launch Config not created')

        lcname = self.tester.describe_launch_config([self.name])
        lc = lcname[0]
        self.debug('***** Created Launch Config: ' + lc.name)

        self.tester.delete_launch_config(self.name)
        list_size_after_delete = len(self.tester.describe_launch_config([self.name]))
        if list_size_after_delete != 0:
            raise Exception('Launch Config not deleted')
        self.debug('***** Deleted Launch Config: ' + self.name)

if __name__ == "__main__":
    testcase = AutoScalingBasics()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list "AutoScalingGroupBasics", "LaunchConfigBasics", "AutoScalingInstanceBasics"
    list = testcase.args.tests or ["LaunchConfigBasics"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list, clean_on_exit=True)
    exit(result)