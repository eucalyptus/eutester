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
from eutester.euinstance import EuInstance
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
        testers.append(self.tester)
        for user in users:
            user_name = user['user_name']
            user_account = user['account_name']
            self.tester.debug("Creating access key for " + user_name + " in account " +  user_account)
            keys = self.tester.create_access_key(user_name=user_name, delegate_account=user_account)
            access_key = keys['access_key_id']
            secret_key = keys['secret_access_key']
            self.tester.debug("Creating Eucaops object with access key " + access_key + " and secret key " +  secret_key)
            new_tester = Eucaops(aws_access_key_id=access_key, aws_secret_access_key=secret_key, ec2_ip=self.tester.ec2.host, s3_ip=self.tester.s3.host,username=user_name, account=user_account)
            if not re.search("eucalyptus", user_account ):
                testers.append(new_tester)

        self.tester.debug("Created a total of " + str(len(testers)) + " testers" )

        for resource_tester in testers:
            import random
            zone = random.choice(resource_tester.get_zones())
            keypair = resource_tester.add_keypair(resource_tester.id_generator())
            group = resource_tester.add_group(resource_tester.id_generator())
            resource_tester.authorize_group_by_name(group_name=group.name )
            resource_tester.authorize_group_by_name(group_name=group.name, port=-1, protocol="icmp" )
            reservation = resource_tester.run_instance(keypair=keypair.name,group=group.name,zone=zone)
            instance = reservation.instances[0]
            address = resource_tester.allocate_address()
            resource_tester.associate_address(instance=instance, address=address)
            resource_tester.disassociate_address_from_instance(instance)
            resource_tester.release_address(address)
            volume = resource_tester.create_volume(size=1, azone=zone)
            if isinstance(instance, EuInstance):
                instance.attach_volume(volume)
            snapshot = resource_tester.create_snapshot(volume_id=volume.id)
            volume_from_snap = resource_tester.create_volume(snapshot=snapshot, azone=zone)
            bucket = resource_tester.create_bucket(resource_tester.id_generator(12, string.ascii_lowercase  + string.digits))
            key = resource_tester.upload_object(bucket_name= bucket.name, key_name= resource_tester.id_generator(12, string.ascii_lowercase  + string.digits), contents= resource_tester.id_generator(200))
            resource_tester.terminate_instances(reservation)

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