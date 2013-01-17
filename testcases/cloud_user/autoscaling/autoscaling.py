#!/usr/bin/python
# Software License Agreement (BSD License)
#
# Copyright (c) 2009-2011, Eucalyptus Systems, Inc.
# All rights reserved.
#
# Redistribution and use of this software in source and binary forms, with or
# without modification, are permitted provided that the following conditions
# are met:
#
#   Redistributions of source code must retain the above
#   copyright notice, this list of conditions and the
#   following disclaimer.
#
#   Redistributions in binary form must reproduce the above
#   copyright notice, this list of conditions and the
#   following disclaimer in the documentation and/or other
#   materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Author: tony@eucalyptus.com

import time
from eucaops import EC2ops
from eucaops import ASops
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
            self.AS_tester = ASops( credpath=self.args.credpath, region=self.args.region)
            self.EC2_tester = EC2ops( credpath=self.args.credpath, region=self.args.region)

        ### Add and authorize a group for the instance
        self.group = self.EC2_tester.add_group(group_name="group-" + str(time.time()))
        self.EC2_tester.authorize_group_by_name(group_name=self.group.name )
        self.EC2_tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )
        ### Generate a keypair for the instance
        self.keypair = self.EC2_tester.add_keypair( "keypair-" + str(time.time()))
        self.keypath = '%s/%s.pem' % (os.curdir, self.keypair.name)
        self.image = self.args.emi
        if not self.image:
            self.image = self.EC2_tester.get_emi(root_device_type="instance-store")
        self.address = None

    def clean_method(self):
        ### DELETE group
        self.EC2_tester.delete_group(self.group)

        ### Delete keypair in cloud and from filesystem
        self.EC2_tester.delete_keypair(self.keypair)
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
        self.name='test_launch_config'

        self.AS_tester.create_launch_config(name=self.name, image_id=self.image, key_name=self.keypair.name, security_groups=[self.group.name])
        list_size_after_create = len(self.AS_tester.describe_launch_config([self.name]))
        if list_size_after_create != 1:
            raise Exception('Launch Config not created')
        self.debug('***** Launch Config Created')

        self.AS_tester.delete_launch_config(self.name)
        list_size_after_delete = len(self.AS_tester.describe_launch_config([self.name]))
        if list_size_after_delete != 0:
            raise Exception('Launch Config not deleted')
        self.debug('***** Launch Config Deleted')

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
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)