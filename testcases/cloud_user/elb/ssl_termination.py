# Software License Agreement (BSD License)
#
# Copyright (c) 2009-2014, Eucalyptus Systems, Inc.
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

import os
import time
from eucaops import Eucaops
from eucaops import ELBops
from boto.ec2.elb import LoadBalancer
from eutester.eutestcase import EutesterTestCase
import random

class SSLTermination(EutesterTestCase):
    def __init__(self, extra_args= None):
        self.cert_name = "elb-ssl-test-"+str(int(time.time()))
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

        ### Add and authorize a group for the instance
        self.group = self.tester.add_group(group_name="group-" + str(int(time.time())))
        self.tester.authorize_group_by_name(group_name=self.group.name )
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )
        ### Generate a keypair for the instance
        self.keypair = self.tester.add_keypair( "keypair-" + str(time.time()))
        self.keypath = '%s/%s.pem' % (os.curdir, self.keypair.name)

        ### Get an image
        self.image = self.args.emi
        if not self.image:
            self.image = self.tester.get_emi()

        ### Populate available zones
        zones = self.tester.ec2.get_all_zones()
        self.zone = random.choice(zones).name

        self.load_balancer_port = 80

        (self.web_servers, self.filename) = self.tester.create_web_servers(keypair=self.keypair,
                                                                          group=self.group,
                                                                          zone=self.zone,
                                                                          port=self.load_balancer_port,
                                                                          filename='instance-name',
                                                                          image=self.image,
                                                                          count=1)

        self.load_balancer = self.tester.create_load_balancer(zones=[self.zone],
                                                              name="test-" + str(int(time.time())),
                                                              load_balancer_port=self.load_balancer_port)
        assert isinstance(self.load_balancer, LoadBalancer)
        self.tester.register_lb_instances(self.load_balancer.name,
                                          self.web_servers.instances)

    def ssl_termination(self):
        """
        This will test ELB with HTTPS listener.

        @raise Exception:
        """
        self.debug("ELB SSl test")

        """get ELB ip info and setup url"""
        dns = self.tester.service_manager.get_enabled_dns()
        lb_ip = dns.resolve(self.load_balancer.dns_name)
        lb_url = "https://{0}/instance-name".format(lb_ip)

        """upload server certificate"""
        self.tester.add_server_cert(cert_name=self.cert_name)

        """create a new listener on HTTPS port 443 and remove listener on port 80"""
        cert_arn = self.tester.get_server_cert(self.cert_name).arn
        listener = (443, 80, "HTTPS", cert_arn)
        self.tester.add_lb_listener(lb_name=self.load_balancer.name, listener=listener)
        self.tester.remove_lb_listener(lb_name=self.load_balancer.name, port=self.load_balancer_port)

        """perform https requests to LB"""
        self.tester.sleep(5)
        self.tester.generate_http_requests(url=lb_url, count=10)

    def clean_method(self):
        self.tester.delete_server_cert(self.cert_name)
        self.tester.cleanup_artifacts()

if __name__ == "__main__":
    testcase = SSLTermination()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or ["ssl_termination"]

    ### Convert test suite methods to Eutester UnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append(testcase.create_testunit_by_name(test))

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list, clean_on_exit=True)
    exit(result)
