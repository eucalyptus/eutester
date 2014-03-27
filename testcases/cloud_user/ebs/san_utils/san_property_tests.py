#!/usr/bin/python
# -*- coding: utf-8 -*-
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
__author__ = 'clarkmatthew'

'''
Data deduplication removes duplicate blocks, storing only unique blocks in the flex volume,
and it creates a small amount of additional metadata in the process.
 Data compression is a software-based solution that provides transparent data compression.
 Deduplication is a process that can be scheduled to run when it is most convenient,
 while data compression has the ability to run either as an inline process as data is written to disk or as a scheduled process.
 When the two are enabled on the same volume, the data is first compressed and then deduplicated.
'''

from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase
from san_client import San_Client
from eutester.euvolume import EuVolume
import time
import types
import re




class San_Properties_Test(EutesterTestCase):

    def __init__(self, san_ip, san_user, san_password, santype=None, tester=None, **kwargs):
        #### Pre-conditions
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument("--santype",
                                 dest="santype",
                                 help="String representing san type. Default='netapp'",
                                 default='netapp')


        self.tester = tester
        self.get_args()
        # Allow __init__ to get args from __init__'s kwargs or through command line parser...
        for kw in kwargs:
            print 'Setting kwarg:'+str(kw)+" to "+str(kwargs[kw])
            self.set_arg(kw ,kwargs[kw])
        self.show_args()
        #if self.args.config:
        #    setattr(self.args, 'config_file',self.args.config)
        # Setup basic eutester object
        if not self.tester:
            try:
                self.tester = self.do_with_args(Eucaops)
            except Exception, e:
                raise Exception('Couldnt create Eucaops tester object, make sure credpath, ' \
                                'or config_file and password was provided, err:' + str(e))
            #replace default eutester debugger with eutestcase's for more verbosity...
            self.tester.debug = lambda msg: self.debug(msg, traceback=2, linebyline=False)
        self.tester.update_property_manager()
        self.san_ip = san_ip
        self.san_user = san_user
        self.san_password = san_password
        self.san = None
        self.zone = self.args.zone
        self.santype = santype or self.args.santype
        self.instance = None
        if self.args.zone:
            self.zone = str(self.args.zone)
        else:
            self.zone = 'PARTI00'
            self.groupname = 'san_property_tests'

        self.group = self.tester.add_group(self.groupname)
        self.tester.authorize_group(self.group)
        self.tester.authorize_group(self.group, protocol='icmp',port='-1')
        ### Generate a keypair for the instance
        if self.instance_password:
            self.keypair = None
        else:
            try:
                keys = self.tester.get_all_current_local_keys()
                if keys:
                    self.keypair = keys[0]
                else:
                    self.keypair = self.tester.add_keypair('sanpropertytestskey'+str(time.time()))
            except Exception, ke:
                raise Exception("Failed to find/create a keypair, error:" + str(ke))
        self.get_san_client()



    def get_san_client(self):
        self.san = san_client.get_san_client_by_type(host=self.host,
                                                             username=self.username,
                                                             password=self.password,
                                                             santype=self.santype)
        return self.san


    def update_volume_san_info(self, volume):
        if hasattr(volume, 'san_info'):
            volume.san_info.update()
        else:
            volume.san_info = self.san.get_volume_info_by_id(volume.id)


    def test_property_storage_deduppolicy(self):
        policy_property = self.tester.property_manager.get_property('deduppolicy', 'storage', self.zone)
        self.debug('Description: ' + str(policy_property.description))
        self.debug('Property before:' + str(policy_property.value))
        policy_before = policy_property.value
        enabled_property = self.tester.property_manager.get_property('', 'storage', self.zone)
        enabled_before = enabled_property.value
        enabled_property.set('true')

        property.print_self(print_method=self.debug)
        property.set('euca-policy')
        volume = self.tester.create



    def test_property_storage_dedupschedule(self):
        pass

    def test_property_storage_enablecompression(self):
        pass

    def test_property_storage_enablededup(self):
        pass

    def test_property_storage_enableinlinecompression(self):
        pass

