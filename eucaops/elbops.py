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
# Author: vic.iglesias@eucalyptus.com
import re
import copy
from boto.ec2.regioninfo import RegionInfo
import boto
from concurrent.futures import ThreadPoolExecutor
import urllib2
from eutester import Eutester
from boto.ec2.elb.listener import Listener

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
            self.debug("Attempting to create cloud watch connection to " + elb_region.endpoint + str(port) + path)
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

    def create_listner(self, load_balancer_port=80, protocol="HTTP", instance_port=80, load_balancer=None):
        self.debug("Creating ELB Listner for protocol " + protocol + " and port " + str(load_balancer_port) + "->" + str(instance_port))
        listner = Listener(load_balancer=load_balancer,
                           protocol=protocol,
                           load_balancer_port=load_balancer_port,
                           instance_port=instance_port)
        return listner

    def generate_http_requests(self, url, count=100):
        response_futures = []
        with ThreadPoolExecutor(max_workers=count / 2 ) as executor:
            response_futures.append(executor.submit(urllib2.urlopen, url))

        responses = []
        for response in response_futures:
            http_response = response.result()
            http_error_code = http_response.getcode()
            if http_error_code == 200:
                responses.append(http_response)
            else:
                raise Exception("Error code " + http_error_code +" found when sending " +
                                str(count/2) + " concurrent requests to " + url)
        return responses

    def create_load_balancer(self, zones, name="test", load_balancer_port=80):
        self.debug("Creating load balancer: " + name + " on port " + str(load_balancer_port))
        listener = self.create_listner(load_balancer_port=load_balancer_port)
        self.elb.create_load_balancer(name, zones=zones, listeners=[listener])

        ### Validate the creation of the load balancer
        load_balancer = self.elb.get_all_load_balancers(load_balancer_names=[name])
        if len(load_balancer) == 1:
            return load_balancer[0]
        else:
            raise Exception("Unable to retrieve load balancer after creation")


