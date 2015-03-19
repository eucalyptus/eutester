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
# Author: Vic Iglesias vic.iglesias@eucalyptus.com
#
from eutester import Eutester
import boto
from boto.ec2.regioninfo import RegionInfo

class CFNops(Eutester):

    def __init__(self,
                 endpoint=None,
                 path=None,
                 port=None,
                 region=None,
                 credpath=None,
                 aws_access_key_id=None,
                 aws_secret_access_key=None,
                 is_secure=True,
                 boto_debug=0):
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.user_id = None
        self.account_id = None
        self.connection = None
        super(CFNops, self).__init__(credpath=credpath)

        self.setup_cfn_connection(endpoint=endpoint,
                                  path=path,
                                  port=port,
                                  region=region,
                                  aws_access_key_id=self.aws_access_key_id,
                                  aws_secret_access_key=self.aws_secret_access_key,
                                  is_secure=True,
                                  boto_debug=0)

    def setup_cfn_connection(self,
                             endpoint=None,
                             path="/",
                             port=443,
                             region=None,
                             aws_access_key_id=None,
                             aws_secret_access_key=None,
                             is_secure=True,
                             boto_debug=0):
        cfn_region = RegionInfo()
        if region:
            self.debug("Check region: " + str(region))
            try:
                if not endpoint:
                    cfn_region.endpoint = "cloudformation.{0}.amazonaws.com".format(region)
                else:
                    cfn_region.endpoint = endpoint
            except KeyError:
                raise Exception( 'Unknown region: %s' % region)
        else:
            cfn_region.name = 'eucalyptus'
            if endpoint:
                cfn_region.endpoint = endpoint
            else:
                cfn_region.endpoint = self.get_cfn_ip()

        try:
            cfn_connection_args = { 'aws_access_key_id' : aws_access_key_id,
                                    'aws_secret_access_key': aws_secret_access_key,
                                    'is_secure': is_secure,
                                    'debug':boto_debug,
                                    'port' : port,
                                    'path' : path,
                                    'region' : cfn_region}
            self.debug("Attempting to create cloudformation connection to " + self.get_cfn_ip() + ':' + str(port) + path)
            self.connection = boto.connect_cloudformation(**cfn_connection_args)
        except Exception, e:
            self.critical("Was unable to create cloudformation connection because of exception: " + str(e))

    def create_stack(self, stack_name, template_body, template_url=None, parameters=None):
        self.info("Creating stack: {0}".format(stack_name))
        self.connection.create_stack(stack_name, template_body, template_url=template_url, parameters=parameters)

    def delete_stack(self, stack_name):
        self.info("Deleting stack: {0}".format(stack_name))
        self.connection.delete_stack(stack_name)