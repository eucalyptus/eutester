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


from eutester import Eutester
import time
import re
import os
import copy
from datetime import datetime
from boto.ec2.image import Image
from boto.ec2.keypair import KeyPair
from boto.ec2.blockdevicemapping import BlockDeviceMapping, BlockDeviceType
from boto.ec2.volume import Volume
from boto.exception import EC2ResponseError
from eutester.euinstance import EuInstance
from eutester.euvolume import EuVolume
from eutester.eusnapshot import EuSnapshot
from boto.ec2.autoscale import AutoScaleConnection
from boto.ec2.autoscale import LaunchConfiguration
from boto.ec2.autoscale import AutoScalingGroup
import boto.ec2.autoscale
from boto.ec2.regioninfo import RegionInfo
import boto

ASRegionData = {
    'us-east-1' : 'autoscaling.us-east-1.amazonaws.com',
    'us-west-1' : 'autoscaling.us-west-1.amazonaws.com',
    'us-west-2' : 'autoscaling.us-west-2.amazonaws.com',
    'eu-west-1' : 'autoscaling.eu-west-1.amazonaws.com',
    'ap-northeast-1' : 'autoscaling.ap-northeast-1.amazonaws.com',
    'ap-southeast-1' : 'autoscaling.ap-southeast-1.amazonaws.com',
    'ap-southeast-2' : 'autoscaling.ap-southeast-2.amazonaws.com',
    'sa-east-1' : 'autoscaling.sa-east-1.amazonaws.com'}

class ASops(Eutester):
    def __init__(self, host=None, credpath=None, endpoint=None, aws_access_key_id=None, aws_secret_access_key = None, username="root",region=None,
                 is_secure=False, path='/', port=80, boto_debug=0, APIVersion = '2011-01-01'):
        super(ASops, self).__init__(credpath=credpath, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
        self.setup_as_connection(host= host, region=region, endpoint=endpoint, aws_access_key_id=self.aws_access_key_id ,
            aws_secret_access_key=self.aws_secret_access_key, is_secure=is_secure, path=path, port=port,
            boto_debug=boto_debug, APIVersion=APIVersion)
        self.poll_count = 48
        self.username = username
        self.test_resources = {}
        self.key_dir = "./"

    def setup_as_connection(self, endpoint=None, aws_access_key_id=None, aws_secret_access_key=None, is_secure=True,host=None ,
                             region=None, path = "/", port = 443,  APIVersion ='2011-01-01', boto_debug=0):
        as_region = RegionInfo()
        if region:
            self.debug("Check region: " + str(region))
            try:
                if not endpoint:
                    as_region.endpoint = ASRegionData[region]
                else:
                    as_region.endpoint = endpoint
            except KeyError:
                raise Exception( 'Unknown region: %s' % region)
        else:
            as_region.name = 'eucalyptus'
            if not host:
                if endpoint:
                    as_region.endpoint = endpoint
                else:
                    as_region.endpoint = self.get_as_ip()
        connection_args = { 'aws_access_key_id' : aws_access_key_id,
                            'aws_secret_access_key': aws_secret_access_key,
                            'is_secure': is_secure,
                            'debug':boto_debug,
                            'port' : port,
                            'path' : path,
                            'host' : host}

        if re.search('2.6', boto.__version__):
            connection_args['validate_certs'] = False

        try:
            as_connection_args = copy.copy(connection_args)
            as_connection_args['path'] = path
            as_connection_args['api_version'] = APIVersion
            as_connection_args['region'] = as_region
            self.debug("Attempting to create AS connection to " + as_region.endpoint + str(port) + path)
            self.AS = boto.connect_autoscale(aws_access_key_id, aws_secret_access_key)
        except Exception, e:
            self.critical("Was unable to create AS connection because of exception: " + str(e))

    def create_launch_config(self, name, image_id, key_name, security_groups):
        self.debug("name : " + name);
        self.debug("image_id : " + image_id);
        lc = LaunchConfiguration(name, image_id, key_name, security_groups)
        self.AS.create_launch_configuration(lc)

