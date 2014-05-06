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
# Author: vic.iglesias@eucalyptus.com
import re
import copy
import time
from boto.ec2.regioninfo import RegionInfo
import boto
from concurrent.futures import ThreadPoolExecutor
import urllib2
import cookielib
from eutester import Eutester
from boto.ec2.elb.listener import Listener
from boto.ec2.elb.healthcheck import HealthCheck
from os.path import join

ELBRegionData = {
    'us-east-1': 'elasticloadbalancing.us-east-1.amazonaws.com',
    'us-west-1': 'elasticloadbalancing.us-west-1.amazonaws.com',
    'us-west-2': 'elasticloadbalancing.us-west-2.amazonaws.com',
    'eu-west-1': 'elasticloadbalancing.eu-west-1.amazonaws.com',
    'ap-northeast-1': 'elasticloadbalancing.ap-northeast-1.amazonaws.com',
    'ap-southeast-1': 'elasticloadbalancing.ap-southeast-1.amazonaws.com'}


class ELBops(Eutester):
    @Eutester.printinfo
    def __init__(self, host=None, credpath=None, endpoint=None, aws_access_key_id=None, aws_secret_access_key=None,
                 username="root", region=None, is_secure=False, path='/', port=80, boto_debug=0):
        """

        :param host:
        :param credpath:
        :param endpoint:
        :param aws_access_key_id:
        :param aws_secret_access_key:
        :param username:
        :param region:
        :param is_secure:
        :param path:
        :param port:
        :param boto_debug:
        """
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.account_id = None
        self.user_id = None
        super(ELBops, self).__init__(credpath=credpath)

        self.setup_elb_connection(host=host,
                                  region=region,
                                  endpoint=endpoint,
                                  aws_access_key_id=self.aws_access_key_id,
                                  aws_secret_access_key=self.aws_secret_access_key,
                                  is_secure=is_secure,
                                  path=path,
                                  port=port,
                                  boto_debug=boto_debug)
        self.poll_count = 48
        self.username = username
        self.test_resources = {}
        self.setup_elb_resource_trackers()

    @Eutester.printinfo
    def setup_elb_connection(self, endpoint=None, aws_access_key_id=None, aws_secret_access_key=None, is_secure=True,
                             host=None,
                             region=None, path="/", port=443, boto_debug=0):
        """

        :param endpoint:
        :param aws_access_key_id:
        :param aws_secret_access_key:
        :param is_secure:
        :param host:
        :param region:
        :param path:
        :param port:
        :param boto_debug:
        :raise:
        """
        elb_region = RegionInfo()
        if region:
            self.debug("Check region: " + str(region))
            try:
                if not endpoint:
                    elb_region.endpoint = ELBRegionData[region]
                else:
                    elb_region.endpoint = endpoint
            except KeyError:
                raise Exception('Unknown region: %s' % region)
        else:
            elb_region.name = 'eucalyptus'
            if not host:
                if endpoint:
                    elb_region.endpoint = endpoint
                else:
                    elb_region.endpoint = self.get_elb_ip()
        connection_args = {'aws_access_key_id': aws_access_key_id,
                           'aws_secret_access_key': aws_secret_access_key,
                           'is_secure': is_secure,
                           'debug': boto_debug,
                           'port': port,
                           'path': path,
                           'region': elb_region}

        if re.search('2.6', boto.__version__):
            connection_args['validate_certs'] = False

        try:
            elb_connection_args = copy.copy(connection_args)
            elb_connection_args['path'] = path
            elb_connection_args['region'] = elb_region
            self.debug(
                "Attempting to create load balancer connection to " + elb_region.endpoint + ':' + str(port) + path)
            self.elb = boto.connect_elb(**elb_connection_args)
        except Exception, e:
            self.critical("Was unable to create elb connection because of exception: " + str(e))

    def setup_elb_resource_trackers(self):
        """
        Setup keys in the test_resources hash in order to track artifacts created
        """
        self.test_resources["load_balancers"] = []

    def get_elb_ip(self):
        """Parse the eucarc for the AWS_ELB_URL"""
        elb_url = self.parse_eucarc("AWS_ELB_URL")
        return elb_url.split("/")[2].split(":")[0]

    def get_elb_path(self):
        """Parse the eucarc for the AWS_ELB_URL"""
        elb_url = self.parse_eucarc("AWS_ELB_URL")
        elb_path = "/".join(elb_url.split("/")[3:])
        return elb_path

    def create_listener(self, load_balancer_port=80, protocol="HTTP", instance_port=80, load_balancer=None):
        self.debug(
            "Creating ELB Listener for protocol " + protocol + " and port " + str(load_balancer_port) + "->" + str(
                instance_port))
        listner = Listener(load_balancer=load_balancer,
                           protocol=protocol,
                           load_balancer_port=load_balancer_port,
                           instance_port=instance_port)
        return listner

    def create_healthcheck(self, target="HTTP:80/instance-name", interval=10, timeout=5, healthy_threshold=2,
                           unhealthy_threshold=10):
        self.debug("Creating healthcheck: " + target + " interval=" + str(interval) + " timeout=" + str(timeout) +
                   " healthy threshold=" + str(healthy_threshold) + " unhealthy threshold=" + str(unhealthy_threshold))
        healthcheck = HealthCheck(target=target,
                                  timeout=timeout,
                                  interval=interval,
                                  healthy_threshold=healthy_threshold,
                                  unhealthy_threshold=unhealthy_threshold)
        return healthcheck

    def generate_http_requests(self, url, count=100, worker_threads=20):
        self.debug("Generating {0} http requests against {1}".format(count, url))
        jar = cookielib.FileCookieJar("cookies")
        handler = urllib2.HTTPCookieProcessor(jar)
        opener = urllib2.build_opener(handler)
        urllib2.install_opener(opener)
        response_futures = []
        with ThreadPoolExecutor(max_workers=worker_threads) as executor:
            for _ in range(count):
                response_futures.append(executor.submit(urllib2.urlopen, url))

        responses = []
        for response in response_futures:
            http_response = response.result()
            try:
                http_error_code = http_response.getcode()
                if http_error_code == 200:
                    result = "{0}".format(http_response.read().rstrip())
                    self.debug("Request response: " + result)
                    responses.append(result)
                else:
                    raise Exception("Error code " + http_error_code + " found when sending " +
                                    str(worker_threads) + " concurrent requests to " + url)
            finally:
                http_response.close()
        return responses

    def register_lb_instances(self, name, instances, timeout=360, poll_count=15):
        inst_ids = [inst.id for inst in instances]
        self.debug("Registering instances {0} with lb {1}".format(inst_ids, name))
        self.elb.register_instances(name, inst_ids)
        poll_sleep = timeout / poll_count
        for _ in range(poll_count):
            self.debug("Checking instance health for {0}".format(inst_ids))
            inst_states = self.elb.describe_instance_health(name, instances=inst_ids)
            states = [state.state for state in inst_states]
            if not states or 'OutOfService' in states:
                time.sleep(poll_sleep)
            elif 'InService' in states:
                self.debug("Instances {0} for lb {1} are InService".format(inst_ids, name))
                return
            else:
                # This should never happen
                pass
        raise Exception("Instances {0} failed to enter InService state before timeout".format(inst_ids))

    def create_load_balancer(self, zones, name="test", load_balancer_port=80, instances=None):
        self.debug("Creating load balancer: " + name + " on port " + str(load_balancer_port))
        listener = self.create_listener(load_balancer_port=load_balancer_port)
        self.elb.create_load_balancer(name, zones=zones, listeners=[listener])

        healthcheck = self.create_healthcheck()
        self.elb.configure_health_check(name, healthcheck)

        if instances:
            self.register_instances(name, instances)

        ### Validate the creation of the load balancer
        lbs = self.elb.get_all_load_balancers(load_balancer_names=[name])
        if not "load_balancers" in self.test_resources:
            self.test_resources["load_balancers"] = []

        if len(lbs) == 1:
            self.test_resources["load_balancers"].append(lbs[0])
            return lbs[0]
        else:
            raise Exception("Unable to retrieve load balancer after creation")

    def delete_load_balancers(self, lbs, timeout=60):
        for lb in lbs:
            self.delete_load_balancer(lb, timeout)

    def delete_load_balancer(self, lb, timeout=60, poll_sleep=10):
        self.debug("Deleting Loadbalancer: {0}".format(lb.name))
        self.elb.delete_load_balancer(lb.name)
        poll_count = timeout / poll_sleep
        for _ in range(poll_count):
            lbs = self.elb.get_all_load_balancers(load_balancer_names=[lb.name])
            if lb in lbs:
                time.sleep(poll_sleep)
        if lb in self.test_resources["load_balancers"]:
            self.test_resources["load_balancers"].remove(lb)

    def create_app_cookie_stickiness_policy(self, name, lb_name, policy_name):
        self.debug("Create app cookie stickiness policy: " + str(policy_name))
        self.elb.create_app_cookie_stickiness_policy(name=name,
                                                     lb_name=lb_name,
                                                     policy_name=policy_name)

    def create_lb_cookie_stickiness_policy(self, cookie_expiration_period, lb_name, policy_name):
        self.debug("Create lb cookie stickiness policy: " + str(policy_name))
        self.elb.create_lb_cookie_stickiness_policy(cookie_expiration_period=cookie_expiration_period,
                                                    lb_name=lb_name,
                                                    policy_name=policy_name)

    def create_lb_policy(self, lb_name, policy_name, policy_type, policy_attributes):
        self.debug("Create lb policy: " + str(policy_name))
        self.elb.create_lb_policy(lb_name=lb_name,
                                  policy_name=policy_name,
                                  policy_type=policy_type,
                                  policy_attributes=policy_attributes)

    def set_lb_policy(self, lb_name, lb_port, policy_name=None):
        self.debug("Set policy " + str(policy_name) + " for " + lb_name)
        self.elb.set_lb_policies_of_listener(lb_name=lb_name,
                                             lb_port=lb_port,
                                             policies=policy_name)

    def delete_lb_policy(self, lb_name, policy_name):
        self.debug("Deleting lb policy " + str(policy_name) + " from " + str(lb_name))
        self.elb.delete_lb_policy(lb_name=lb_name,
                                  policy_name=policy_name)

    def describe_lb_policies(self, lb):
        lbs = self.elb.get_all_load_balancers(load_balancer_names=[lb])
        return lbs[0].policies

    def add_lb_listener(self, lb_name, listener):
        self.debug("adding listener")
        self.elb.create_load_balancer_listeners(name=lb_name, listeners=[listener])

    def remove_lb_listener(self, lb_name, port):
        self.debug("removing listener")
        self.elb.delete_load_balancer_listeners(name=lb_name, ports=[port])

    def add_server_cert(self, cert_name, cert_dir="./test_data", cert_file="ssl_server_certs_basics.crt",
                           key_file="ssl_server_certs_basics.pem"):
        cert_body = open(join(cert_dir, cert_file)).read()
        cert_key = open(join(cert_dir, key_file)).read()
        self.upload_server_cert(cert_name=cert_name, cert_body=cert_body, private_key=cert_key)