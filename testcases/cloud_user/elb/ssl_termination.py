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
        self.setuptestcase()
        self.setup_parser()
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()

        # Setup basic eutester object
        if self.args.region:
            self.tester = ELBops(credpath=self.args.credpath, region=self.args.region)
        else:
            self.tester = Eucaops(credpath=self.args.credpath, config_file=self.args.config,password=self.args.password)

        # test resource hash
        self.test_hash = str(int(time.time()))

        # test resources dir
        self.resource_dir = "./testcases/cloud_user/elb/test_data"

        # User data file
        self.user_data = self.resource_dir+"/webserver_user_data.sh"

        # Add and authorize a group for the instances
        self.group = self.tester.add_group(group_name="group-" + self.test_hash)
        self.tester.authorize_group_by_name(group_name=self.group.name)
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp")
        self.tester.authorize_group_by_name(group_name=self.group.name, port=80, protocol="tcp")
        self.tester.authorize_group_by_name(group_name=self.group.name, port=443, protocol="tcp")

        # Generate a keypair for the instances
        self.keypair = self.tester.add_keypair("keypair-" + self.test_hash)
        self.keypath = '%s/%s.pem' % (os.curdir, self.keypair.name)

        # Get an image
        self.image = self.args.emi
        if not self.image:
            self.image = self.tester.get_emi()

        # Populate available zones
        zones = self.tester.ec2.get_all_zones()
        self.zone = random.choice(zones).name

        # create base load balancer
        self.load_balancer_port = 80
        self.load_balancer = self.tester.create_load_balancer(zones=[self.zone],
                                                              name="elb-" + self.test_hash,
                                                              load_balancer_port=self.load_balancer_port)
        assert isinstance(self.load_balancer, LoadBalancer)

        # create autoscaling group of webservers that register to the load balancer
        self.count = 1
        (self.web_servers) = self.tester.create_as_webservers(name=self.test_hash,
                                                              keypair=self.keypair.name,
                                                              group=self.group.name,
                                                              zone=self.zone,
                                                              image=self.image.id,
                                                              count=self.count,
                                                              user_data=self.user_data,
                                                              load_balancer=self.load_balancer.name)

        # web servers scaling group
        self.asg = self.tester.describe_as_group(name="asg-"+self.test_hash)

        # wait until scaling instances are InService with the load balancer before continuing - 5 min timeout
        assert self.tester.wait_for_result(self.tester.wait_for_lb_instances, True, timeout=300,
                                           lb=self.load_balancer.name, number=self.count)

    def ssl_termination(self):
        """
        This will test ELB with HTTPS listener.

        @raise Exception:
        """
        self.debug("ELB SSl test")

        # get ELB ip info and setup url (also verifies DNS lookup)
        dns = self.tester.service_manager.get_enabled_dns()
        lb_ip = dns.resolve(self.load_balancer.dns_name)
        lb_url = "https://{0}/instance-name".format(lb_ip)

        # upload server certificate
        frontend_cert_name = "elb-ssl-test-"+str(int(time.time()))
        self.tester.add_server_cert(cert_name=frontend_cert_name)

        # remove listener on port 80 and create a new listener on HTTPS port 443
        self.tester.remove_lb_listener(lb_name=self.load_balancer.name, port=self.load_balancer_port)
        self.update_listener(lb_port=443,
                             lb_protocol="HTTPS",
                             instance_port=80,
                             instance_protocol="HTTP",
                             cert=frontend_cert_name)

        # perform https requests to LB
        self.tester.sleep(10)
        self.tester.generate_http_requests(url=lb_url, count=10)

    def update_listener(self, lb_port, lb_protocol, instance_port, instance_protocol, cert):
        self.debug("Configuring ELB listener")
        # get the arn of the certificate
        cert_arn = self.tester.get_server_cert(cert).arn

        # remove any existing listener on the port and create a new listener with backend authentication
        self.debug("Attempting to remove any listener already existing for port " + str(lb_port))
        self.tester.remove_lb_listener(lb_name=self.load_balancer.name, port=lb_port)
        listener = (lb_port, instance_port, lb_protocol, instance_protocol, cert_arn)
        self.tester.add_lb_listener(lb_name=self.load_balancer.name, listener=listener)
        self.debug("Listener: " + str(self.tester.describe_lb_listeners(self.load_balancer.name)))
        return

    def clean_method(self):
        try:
            self.tester.delete_all_server_certs()
        except:
            self.debug("Delete certificates went awry")
        finally:
            self.tester.cleanup_artifacts()
            if self.tester.test_resources["security-groups"]:
                for group in self.tester.test_resources["security-groups"]:
                    self.tester.wait_for_result(self.tester.gracefully_delete_group, True, timeout=60, group=group)

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
