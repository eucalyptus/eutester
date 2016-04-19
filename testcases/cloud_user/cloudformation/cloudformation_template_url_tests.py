# Software License Agreement (BSD License)
#
# Copyright (c) 2009-2016, Eucalyptus Systems, Inc.
# All rights reserved.
#
# Redistribution and use of this software in source and binary forms, with or
# without modification, are permitted provided that the following conditions
# are met:
#
# Redistributions of source code must retain the above
# copyright notice, this list of conditions and the
# following disclaimer.
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
# Author: Tony Beckham tony@eucalyptus.com
#

import time
from eucaops import Eucaops, CFNops
from eutester.eutestcase import EutesterTestCase
import os


class CloudFormationTemplateURLTests(EutesterTestCase):
    def __init__(self, extra_args=None):
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument('--template_urls', dest='template_urls',
                                 help='comma separated list of template_urls',
                                 default=None)
        self.parser.add_argument('--timeout', dest='timeout',
                                 help='number of seconds to wait for stacks to complete',
                                 default=300)
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()
        self.show_args()
        self.template_urls = self.args.template_urls.split(',')
        self.timeout = int(self.args.timeout)
        # Setup basic eutester object
        if self.args.region:
            self.tester = CFNops(credpath=self.args.credpath, region=self.args.region)
        else:
            self.tester = Eucaops(credpath=self.args.credpath, config_file=self.args.config,
                                  password=self.args.password)
        # Generate a keypair for the instance
        self.keypair = self.tester.add_keypair("keypair-" + str(time.time()))
        self.keypath = '%s/%s.pem' % (os.curdir, self.keypair.name)
        self.stacks = []

    def Stack_Template_URL_Test(self):
        for url in self.template_urls:
            # get template name from URL, remove file extension and any "-"
            template = os.path.splitext(url.rsplit('/', 1)[1])[0].replace("-", "")
            self.stack_name = template + str(os.urandom(8).encode('hex'))
            self.stacks.append(self.stack_name)
            self.template_parameters = [('KeyName', self.keypair.name), ('ImageId', self.tester.get_emi().id)]
            self.tester.create_stack(stack_name=self.stack_name,
                                     template_body=None,
                                     template_url=url,
                                     parameters=self.template_parameters)

            def stack_completed():
                stack_status = False
                if len(self.tester.cloudformation.describe_stack_events(self.stack_name)) > 0:
                    stack_info = self.tester.cloudformation.describe_stack_events(self.stack_name)
                    for inf in stack_info:
                        if (inf.logical_resource_id == self.stack_name) and (inf.resource_status == "CREATE_COMPLETE"):
                            self.debug("Stack Logical Resource: " + inf.logical_resource_id)
                            self.debug("Stack Resource Status: " + inf.resource_status)
                            stack_status = True
                return stack_status
            self.tester.wait_for_result(stack_completed, True, timeout=self.timeout)

    def clean_method(self):
        self.tester.cleanup_artifacts()
        for stack in self.stacks:
            self.tester.delete_stack(stack)


if __name__ == "__main__":
    testcase = CloudFormationTemplateURLTests()
    # Use the list of tests passed from config/command line to determine what subset of tests to run
    # or use a predefined list
    list = testcase.args.tests or ["Stack_Template_URL_Test"]
    # Convert test suite methods to EutesterUnitTest objects
    unit_list = []
    for test in list:
        unit_list.append(testcase.create_testunit_by_name(test))
    # Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list, clean_on_exit=True)
    exit(result)
