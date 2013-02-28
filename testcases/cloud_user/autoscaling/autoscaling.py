#!/usr/bin/python

# Software License Agreement (BSD License)
#
# Copyright (c) 2009-2013, Eucalyptus Systems, Inc.
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
import os
from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase


class AutoScalingBasics(EutesterTestCase):
    def __init__(self, extra_args= None):
        self.setuptestcase()
        self.setup_parser()
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
        ### test create  and describe launch config
        self.launch_config_name = 'Test-Launch-Config-' + str(time.time())
        self.tester.create_launch_config(name=self.launch_config_name,
                                         image_id=self.image.id,
                                         key_name=self.keypair.name,
                                         security_groups=[self.group.name])
        if len(self.tester.describe_launch_config([self.launch_config_name])) != 1:
            raise Exception('Launch Config not created')
        self.debug('**** Created Launch Config: ' +
                   self.tester.describe_launch_config([self.launch_config_name])[0].name)

        ### test create and describe auto scale group
        self.initial_size = len(self.tester.describe_as_group())
        self.auto_scaling_group_name = 'ASG-' + str(time.time())
        self.tester.create_as_group(group_name=self.auto_scaling_group_name,
                                    launch_config=self.launch_config_name,
                                    availability_zones=self.tester.get_zones(),
                                    min_size=0,
                                    max_size=5,
                                    connection=self.tester.AS)
        if len(self.tester.describe_as_group([self.auto_scaling_group_name])) != 1:
            raise Exception('Auto Scaling Group not created')
        self.debug("**** Created Auto Scaling Group: " +
                   self.tester.describe_as_group([self.auto_scaling_group_name])[0].name)

        ### Test Create and describe Auto Scaling Policy
        self.up_policy_name = "Up-Policy-" + str(time.time())
        self.up_size = 4
        self.tester.create_as_policy(name=self.up_policy_name,
                                     adjustment_type="ChangeInCapacity",
                                     as_name=self.auto_scaling_group_name,
                                     scaling_adjustment=4,
                                     cooldown=120)

        self.down_policy_name = "Down-Policy-" + str(time.time())
        self.down_size = -50
        self.tester.create_as_policy(name=self.down_policy_name,
                                     adjustment_type="PercentChangeInCapacity",
                                     as_name=self.auto_scaling_group_name,
                                     scaling_adjustment=self.down_size,
                                     cooldown=120)

        self.exact_policy_name = "Exact-Policy-" + str(time.time())
        self.exact_size = 0
        self.tester.create_as_policy(name=self.exact_policy_name,
                                     adjustment_type="ExactCapacity",
                                     as_name=self.auto_scaling_group_name,
                                     scaling_adjustment=self.exact_size,
                                     cooldown=120)

        ### Test all policies added to group
        if len(self.tester.AS.get_all_policies()) != 3:
            raise Exception('Auto Scaling policies not created')
        self.debug("**** Created Auto Scaling Policies: " + self.up_policy_name + " " + self.down_policy_name + " " +
                   self.exact_policy_name)

        ### Test Execute ChangeInCapacity Auto Scaling Policy
        self.tester.execute_as_policy(policy_name=self.up_policy_name, as_group=self.auto_scaling_group_name)
        if self.tester.describe_as_group([self.auto_scaling_group_name])[0].desired_capacity != self.up_size:
            raise Exception("Auto Scale Up not executed")
        self.debug("Executed  ChangeInCapacity policy, increased desired capacity to: " +
                   str(self.tester.describe_as_group([self.auto_scaling_group_name])[0].desired_capacity))

        ### Test Execute PercentChangeInCapacity Auto Scaling Policy
        self.tester.execute_as_policy(policy_name=self.down_policy_name, as_group=self.auto_scaling_group_name)
        if self.tester.describe_as_group([self.auto_scaling_group_name])[0].desired_capacity != 0.5 * self.up_size:
            raise Exception("Auto Scale down percentage not executed")
        self.debug("Executed PercentChangeInCapacity policy, decreased desired capacity to: " +
                   str(self.tester.describe_as_group([self.auto_scaling_group_name])[0].desired_capacity))

        ### Test Execute ExactCapacity Auto Scaling Policy
        self.tester.execute_as_policy(policy_name=self.exact_policy_name, as_group=self.auto_scaling_group_name)
        if self.tester.describe_as_group([self.auto_scaling_group_name])[0].desired_capacity != self.exact_size:
            raise Exception("Auto Scale down percentage not executed")
        self.debug("Executed ExactCapacity policy, exact capacity is: " +
                   str(self.tester.describe_as_group([self.auto_scaling_group_name])[0].desired_capacity))

        ### Test Delete all Auto Scaling Policies
        for policy in self.tester.AS.get_all_policies():
            self.tester.delete_as_policy(policy_name=policy.name, autoscale_group=policy.as_name)
        if len(self.tester.AS.get_all_policies()) != 0:
            raise Exception('Auto Scaling policy not deleted')
        self.debug("**** Deleted Auto Scaling Policy: " + self.up_policy_name + " " + self.down_policy_name + " " +
                   self.exact_policy_name)

        ### Test Delete Auto Scaling Group
        self.tester.delete_as_group(names=self.auto_scaling_group_name)
        if len(self.tester.describe_as_group([self.auto_scaling_group_name])) != 0:
            raise Exception('Auto Scaling Group not deleted')
        self.debug('**** Deleted Auto Scaling Group: ' + self.auto_scaling_group_name)

        ### pause for Auto scaling group to be deleted
        # TODO write wait/poll op for auto scaling groups
        # time.sleep(5)

        ### Test delete launch config
        self.tester.delete_launch_config(self.launch_config_name)
        if len(self.tester.describe_launch_config([self.launch_config_name])) != 0:
            raise Exception('Launch Config not deleted')
        self.debug('**** Deleted Launch Config: ' + self.launch_config_name)

    def AutoScalingInstanceBasics(self):
        """
        This case will test DescribeAutoScalingInstances, SetInstanceHealth and TerminateInstanceInAutoScalingGroup
        """
        pass

    def too_many_launch_configs_test(self):
        """
        AWS enforces a 100 LC per account limit this tests what happens if we create more
        """
        for i in range(101):
            self.launch_config_name = 'Test-Launch-Config-' + str(i + 1)
            self.tester.create_launch_config(name=self.launch_config_name,
                                             image_id=self.image.id)
        if len(self.tester.describe_launch_config()) > 100:
            raise Exception("More then 100 launch configs exist in 1 account")
        for lc in self.tester.describe_launch_config():
            self.tester.delete_launch_config(lc.name)

    def too_many_policies_test(self):
        launch_config_name = 'LC-' + str(time.time())
        self.tester.create_launch_config(name=launch_config_name,
                                         image_id=self.image.id,
                                         key_name=self.keypair.name,
                                         security_groups=[self.group.name])
        asg = 'ASG-' + str(time.time())
        self.tester.create_as_group(group_name=asg,
                                    launch_config=launch_config_name,
                                    availability_zones=self.tester.get_zones(),
                                    min_size=0,
                                    max_size=5,
                                    connection=self.tester.AS)
        for i in range(26):
            policy_name = "Policy-" + str(i + 1)
            self.tester.create_as_policy(name=policy_name,
                                         adjustment_type="ExactCapacity",
                                         as_name=asg,
                                         scaling_adjustment=0,
                                         cooldown=120)
        if len(self.tester.AS.get_all_policies()) > 25:
            raise Exception("More than 25 policies exist for 1 auto scaling group")
        self.tester.delete_as_group(names=asg)

    def too_many_as_groups(self):
        """
        AWS imposes a 20 ASG/acct limit
        """
        pass

    def clear_all(self):
        self.tester.delete_all_autoscaling_groups()
        self.tester.delete_all_launch_configs()

if __name__ == "__main__":
    testcase = AutoScalingBasics()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list "AutoScalingGroupBasics", "LaunchConfigBasics", "AutoScalingInstanceBasics"
    # list = testcase.args.tests or ["AutoScalingBasics"] ["clean_groups_and_configs"] too_many_launch_configs_test
    # too_many_policies_test
    list = testcase.args.tests or ["AutoScalingBasics"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list, clean_on_exit=True)
    exit(result)