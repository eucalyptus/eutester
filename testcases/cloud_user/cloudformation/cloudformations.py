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
# Author: Vic Iglesias vic.iglesias@eucalyptus.com
#

from troposphere import Base64, FindInMap, GetAtt
from troposphere import Parameter, Ref, Template
import troposphere.ec2 as ec2
import time
from eucaops import Eucaops, CFNops
from eutester.eutestcase import EutesterTestCase
import os

class CloudFormations(EutesterTestCase):
    def __init__(self, extra_args= None):
        self.setuptestcase()
        self.setup_parser()
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()
        # Setup basic eutester object
        if self.args.region:
            self.tester = CFNops( credpath=self.args.credpath, region=self.args.region)
        else:
            self.tester = Eucaops( credpath=self.args.credpath, config_file=self.args.config,password=self.args.password)
        self.group = self.tester.add_group(group_name="group-" + str(time.time()))
        self.tester.authorize_group_by_name(group_name=self.group.name)
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp")
        ### Generate a keypair for the instance
        self.keypair = self.tester.add_keypair("keypair-" + str(time.time()))
        self.keypath = '%s/%s.pem' % (os.curdir, self.keypair.name)

    def InstanceVolumeTemplate(self):
        self.stack_name = "volumeTest{0}".format(int(time.time()))
        template = Template()
        keyname_param = template.add_parameter(Parameter("KeyName", Description="Name of an existing EC2 KeyPair "
                                                                                "to enable SSH access to the instance",
                                                         Type="String",))
        template.add_mapping('RegionMap', {"": {"AMI": self.tester.get_emi().id}})
        for i in xrange(2):
            ec2_instance = template.add_resource(ec2.Instance("Instance{0}".format(i),
                                                              ImageId=FindInMap("RegionMap", Ref("AWS::Region"), "AMI"),
                                                              InstanceType="t1.micro", KeyName=Ref(keyname_param),
                                                              SecurityGroups=[self.group.name], UserData=Base64("80")))
            vol = template.add_resource(ec2.Volume("Volume{0}".format(i), Size="8",
                                                   AvailabilityZone=GetAtt("Instance{0}".format(i), "AvailabilityZone")))
            mount = template.add_resource(ec2.VolumeAttachment("MountPt{0}".format(i), InstanceId=Ref("Instance{0}".format(i)),
                                                               VolumeId=Ref("Volume{0}".format(i)), Device="/dev/vdc"))
        stack = self.tester.create_stack(self.stack_name, template.to_json(), parameters=[("KeyName",self.keypair.name)])
        def stack_completed():
            return self.tester.cloudformation.describe_stacks(self.stack_name).status == "CREATE_COMPLETE"
        self.tester.wait_for_result(stack_completed, True, timeout=600)
        self.tester.delete_stack(self.stack_name)

    def clean_method(self):
        self.tester.cleanup_artifacts()

if __name__ == "__main__":
    testcase = CloudFormations()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or [ "InstanceVolumeTemplate"]
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )
    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)

