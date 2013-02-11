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
from eutester import Eutester


EC2RegionData = {
    'us-east-1': 'monitoring.us-east-1.amazonaws.com',
    'us-west-1': 'monitoring.us-west-1.amazonaws.com',
    'eu-west-1': 'monitoring.eu-west-1.amazonaws.com',
    'ap-northeast-1': 'monitoring.ap-northeast-1.amazonaws.com',
    'ap-southeast-1': 'monitoring.ap-southeast-1.amazonaws.com'}


class CWops(Eutester):
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
        super(CWops, self).__init__(credpath=credpath)

        self.setup_cw_connection(host=host,
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
        self.setup_cw_resource_trackers()

    @Eutester.printinfo
    def setup_cw_connection(self, endpoint=None, aws_access_key_id=None, aws_secret_access_key=None, is_secure=True,
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
        ec2_region = RegionInfo()
        if region:
            self.debug("Check region: " + str(region))
            try:
                if not endpoint:
                    ec2_region.endpoint = EC2RegionData[region]
                else:
                    ec2_region.endpoint = endpoint
            except KeyError:
                raise Exception('Unknown region: %s' % region)
        else:
            ec2_region.name = 'eucalyptus'
            if not host:
                if endpoint:
                    ec2_region.endpoint = endpoint
                else:
                    ec2_region.endpoint = self.get_cw_ip()
        connection_args = {'aws_access_key_id': aws_access_key_id,
                           'aws_secret_access_key': aws_secret_access_key,
                           'is_secure': is_secure,
                           'debug': boto_debug,
                           'port': port,
                           'path': path,
                           'region': ec2_region}

        if re.search('2.6', boto.__version__):
            connection_args['validate_certs'] = False

        try:
            ec2_connection_args = copy.copy(connection_args)
            ec2_connection_args['path'] = path
            ec2_connection_args['region'] = ec2_region
            self.debug("Attempting to create cloud watch connection to " + ec2_region.endpoint + str(port) + path)
            self.cw = boto.connect_cloudwatch(**ec2_connection_args)
        except Exception, e:
            self.critical("Was unable to create ec2 connection because of exception: " + str(e))

        #Source ip on local test machine used to reach instances
        self.ec2_source_ip = None

    def setup_cw_resource_trackers(self):
        """
        Setup keys in the test_resources hash in order to track artifacts created
        """
        self.test_resources["alarms"] = []
        self.test_resources["metric"] = []
        self.test_resources["datapoint"] = []

    def get_cw_ip(self):
        """Parse the eucarc for the EC2_URL"""
        ec2_url = self.parse_eucarc("AWS_CLOUDWATCH_URL")
        return ec2_url.split("/")[2].split(":")[0]