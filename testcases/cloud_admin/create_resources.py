#!/usr/bin/python
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
'''
Create resources (keypairs,groups, volumes,snapshots, buckets) for each user in the cloud. 
'''
from eucaops import Eucaops
import argparse
import re
import time
import os
import string
from eutester import xmlrunner
from eutester.eutestcase import EutesterTestCase
from eutester.eutestcase import EutesterTestResult
from boto.exception import S3ResponseError
from boto.exception import S3CreateError
import boto
import unittest

class ResourceGeneration(EutesterTestCase):
    
    def __init__(self, credpath):
        self.tester = Eucaops(credpath=credpath)


    def CreateResources(self):
        users = self.tester.get_all_users() 
        testers = []
        for user in users:
            keys = self.tester.create_access_key(user_name=user['user_name'], delegate_account=user['account_name'])
            testers.append(Eucaops(aws_access_key_id=keys['access_key_id'], aws_secret_access_key=keys['secret_access_key'], ec2_ip=self.tester.ec2.host, s3_ip=self.tester.s3.host))
            
        for tester in testers:
            import random
            zone = random.choice(tester.get_zones())
            volume = self.tester.create_volume(size=1, azone=zone)
            snapshot = self.tester.create_snapshot(volume_id=volume.id)
            volume_from_snap = self.tester.create_volume(snapshot=snapshot, azone=zone)
            bucket = self.tester.create_bucket(self.tester.id_generator(12, string.ascii_lowercase  + string.digits))
            key = self.tester.upload_object(bucket_name= bucket.name, key_name= self.tester.id_generator(12, string.ascii_lowercase  + string.digits), contents= self.tester.id_generator(200))
            keypair = self.tester.add_keypair(self.tester.id_generator())
            group = self.tester.add_group(self.tester.id_generator())
    
    def run_suite(self):  
        self.testlist = [] 
        testlist = self.testlist
        testlist.append(self.create_testcase_from_method(self.CreateResources))
        self.run_test_case_list(testlist)  
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="create_resources.py",
                                     description="Create resources (keypairs,groups, volumes,snapshots, buckets) for each user in the cloud. ")
    parser.add_argument('--credpath', 
                        help="Path to credentials of an admin user", default=None)
    args = parser.parse_args()
    resource_suite = ResourceGeneration(credpath=args.credpath)
    kbtime=time.time()
    try:
        resource_suite.run_suite()
    except KeyboardInterrupt:
        resource_suite.debug("Caught keyboard interrupt...")
        if ((time.time()-kbtime) < 2):
            resource_suite.clean_created_resources()
            resource_suite.debug("Caught 2 keyboard interupts within 2 seconds, exiting test")
            resource_suite.clean_created_resources()
            raise
        else:          
            resource_suite.print_test_list_results()
            kbtime=time.time()
            pass
    exit(0)    