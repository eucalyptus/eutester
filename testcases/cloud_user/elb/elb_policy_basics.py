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
# Author: Tony Beckham tony@eucalyptus.com
#

import time
from eucaops import Eucaops
from eucaops import ELBops
from boto.ec2.elb import LoadBalancer
from boto.exception import BotoServerError
from eutester.eutestcase import EutesterTestCase
import os
import random

class LoadBalancerPolicy(EutesterTestCase):
    def __init__(self, extra_args= None):
        self.setuptestcase()
        self.setup_parser()
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()

        # Setup basic eutester object
        if self.args.region:
            self.tester = ELBops( credpath=self.args.credpath, region=self.args.region)
        else:
            self.tester = Eucaops( credpath=self.args.credpath, config_file=self.args.config,password=self.args.password)
        self.tester.poll_count = 120

        ### Populate available zones
        zones = self.tester.ec2.get_all_zones()
        self.zone = random.choice(zones).name
        self.load_balancer_port = 80
        self.lb_name="test-" + str(time.time())
        self.load_balancer = self.tester.create_load_balancer(zones=[self.zone],
                                                              name=self.lb_name,
                                                              load_balancer_port=self.load_balancer_port)
        assert isinstance(self.load_balancer, LoadBalancer)

    def Policy_CRUD(self):
        """
        This will test creating and deleting AppCookieStickiness and LBCookieStickiness policies.

        Since policies are not part of get_all_loadbalancers method I have chosen to test that policy has been added
        by trying to add the same policy again which should fail if the load balancer already has that policy.

        Now we will know whether add policy works and we can check delete. In this case we delete the policy and try to
        add the same policy again. This time it should succeed because it has been deleted.

        @raise Exception:
        """
        self.debug("policy test")

        ### create policies
        appcookiestickinesspolicy = "Test-AppCookieStickinessPolicy"
        lbcookiestickinesspolicy = "Test-LBCookieStickinessPolicy"
        self.tester.create_app_cookie_stickiness_policy(name="test_cookie", lb_name=self.lb_name, policy_name=appcookiestickinesspolicy)
        self.tester.create_lb_cookie_stickiness_policy(cookie_expiration_period=300, lb_name=self.lb_name, policy_name=lbcookiestickinesspolicy)

        ### try to add duplicate policies
        try:
            self.tester.create_app_cookie_stickiness_policy(name="test_cookie", lb_name=self.lb_name, policy_name=appcookiestickinesspolicy)
        except BotoServerError:
            self.debug("Successfully caught exception trying to add duplicate app cookie policy")
        else:
            raise Exception("app cookie policy not added to lb")

        try:
            self.tester.create_lb_cookie_stickiness_policy(cookie_expiration_period=300, lb_name=self.lb_name, policy_name=lbcookiestickinesspolicy)
        except BotoServerError:
            self.debug("Successfully caught exception trying to add duplicate lb cookie policy")
        else:
            raise Exception("lb cookie policy not added to lb")

        ### now we delete the policies and add them again. There are grace periods added between calls
        self.tester.sleep(2)
        self.tester.delete_lb_policy(lb_name=self.lb_name, policy_name=appcookiestickinesspolicy)
        self.tester.sleep(2)
        self.tester.delete_lb_policy(lb_name=self.lb_name, policy_name=lbcookiestickinesspolicy)
        self.tester.sleep(2)
        self.tester.create_app_cookie_stickiness_policy(name="test_cookie", lb_name=self.lb_name, policy_name=appcookiestickinesspolicy)
        self.tester.sleep(2)
        self.tester.create_lb_cookie_stickiness_policy(cookie_expiration_period=300, lb_name=self.lb_name, policy_name=lbcookiestickinesspolicy)
        self.tester.sleep(2)


    def clean_method(self):
        self.tester.cleanup_artifacts()

if __name__ == "__main__":
    testcase = LoadBalancerPolicy()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or ["Policy_CRUD"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)
