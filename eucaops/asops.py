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

EC2RegionData = {
    'us-east-1' : 'ec2.us-east-1.amazonaws.com',
    'us-west-1' : 'ec2.us-west-1.amazonaws.com',
    'eu-west-1' : 'ec2.eu-west-1.amazonaws.com',
    'ap-northeast-1' : 'ec2.ap-northeast-1.amazonaws.com',
    'ap-southeast-1' : 'ec2.ap-southeast-1.amazonaws.com'}

class ASops(Eutester):
    def __init__(self, credpath=None, aws_access_key_id=None, aws_secret_access_key = None, username="root",region=None, ec2_ip=None, s3_ip=None, boto_debug=0):
        Eutester.__init__(self, credpath=credpath, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key,region=region,  s3_ip=s3_ip, ec2_ip=ec2_ip, boto_debug=boto_debug)
        self.poll_count = 48
        self.username = username
        self.test_resources = {}
        self.setup_ec2_resource_trackers()
        self.key_dir = "./"

    def setup_as_connection(self, endpoint=None, aws_access_key_id=None, aws_secret_access_key=None, is_secure=True,host=None ,
                             region=None, path = "/", port = 443,  APIVersion ='2012-07-20', boto_debug=0):
        ec2_region = RegionInfo()
        if region:
            self.debug("Check region: " + str(region))
            try:
                if not endpoint:
                    ec2_region.endpoint = EC2RegionData[region]
                else:
                    ec2_region.endpoint = endpoint
            except KeyError:
                raise Exception( 'Unknown region: %s' % region)
        else:
            ec2_region.name = 'eucalyptus'
            if not host:
                if endpoint:
                    ec2_region.endpoint = endpoint
                else:
                    ec2_region.endpoint = self.get_ec2_ip()
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
            ec2_connection_args = copy.copy(connection_args)
            ec2_connection_args['path'] = path
            ec2_connection_args['api_version'] = APIVersion
            ec2_connection_args['region'] = ec2_region
            self.debug("Attempting to create ec2 connection to " + ec2_region.endpoint + str(port) + path)
            self.ec2 = boto.connect_ec2(**ec2_connection_args)
        except Exception, e:
            self.critical("Was unable to create ec2 connection because of exception: " + str(e))



