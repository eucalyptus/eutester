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
import re
import string
from eutester.euinstance import EuInstance
from eutester.eutestcase import EutesterTestCase

class ResourceGeneration(EutesterTestCase):
    
    def __init__(self):
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument("--no-cleanup", action='store_true')
        self.get_args()
        # Setup basic eutester object
        self.tester = Eucaops( credpath=self.args.credpath, config_file=self.args.config, password=self.args.password)
        self.testers = []

    def clean_method(self):
        if not self.args.no_cleanup:
            for tester in self.testers:
                try:
                    tester.show_euare_whoami()
                except: pass
                tester.cleanup_artifacts()

    def CreateResources(self):
        users = self.tester.get_all_users()
        self.testers.append(self.tester)
        try:
            self.tester.show_all_users()
        except: pass
        for user in users:
            user_name = user['user_name']
            user_account = user['account_name']
            if not re.search("eucalyptus", user_account ):
                self.tester.debug("Creating access key for " + user_name + " in account " + user_account)
                keys = self.tester.create_access_key(user_name=user_name, delegate_account=user_account)
                access_key = keys['access_key_id']
                secret_key = keys['secret_access_key']
                self.tester.debug("Creating Eucaops object with access key " + access_key +
                                  " and secret key " + secret_key)
                new_tester = Eucaops(aws_access_key_id=access_key, aws_secret_access_key=secret_key,
                                     ec2_ip=self.tester.ec2.host, ec2_path=self.tester.ec2.path,
                                     iam_ip=self.tester.euare.host, iam_path=self.tester.euare.path,
                                     s3_ip=self.tester.s3.host, s3_path=self.tester.s3.path,
                                     sts_ip=self.tester.tokens.host, sts_path=self.tester.tokens.path,
                                     cw_ip=self.tester.cw.host, cw_path=self.tester.cw.path,
                                     as_ip=self.tester.autoscale.host, as_path=self.tester.autoscale.path,
                                     elb_ip=self.tester.elb.host, elb_path=self.tester.elb.path,
                                     username=user_name, account=user_account)
                self.testers.append(new_tester)

        self.tester.debug("Created a total of " + str(len(self.testers)) + " testers" )
        try:
            self.tester.show_all_users()
        except: pass
        for resource_tester in self.testers:
            import random
            assert isinstance(resource_tester, Eucaops)
            try:
                resource_tester.show_euare_whoami()
            except:pass
            zone = random.choice(resource_tester.get_zones())
            keypair = resource_tester.add_keypair(resource_tester.id_generator())
            group = resource_tester.add_group(resource_tester.id_generator())
            resource_tester.authorize_group_by_name(group_name=group.name)
            resource_tester.authorize_group_by_name(group_name=group.name, port=-1, protocol="icmp" )
            reservation = resource_tester.run_instance(keypair=keypair.name,group=group.name,zone=zone)
            instance = reservation.instances[0]
            assert isinstance(instance, EuInstance)
            if not instance.ip_address == instance.private_ip_address:
                self.tester.show_addresses(None, True)
                address = resource_tester.allocate_address()
                resource_tester.associate_address(instance=instance, address=address)
                resource_tester.disassociate_address_from_instance(instance)
                if not self.args.no_cleanup:
                    resource_tester.release_address(address)
            self.tester.sleep(20)
            instance.update()
            instance.reset_ssh_connection()
            volume = resource_tester.create_volume(size=1, zone=zone)
            instance.attach_volume(volume)
            snapshot = resource_tester.create_snapshot(volume_id=volume.id)
            volume_from_snap = resource_tester.create_volume(snapshot=snapshot, zone=zone)
            bucket = resource_tester.create_bucket(resource_tester.id_generator(12, string.ascii_lowercase  + string.digits))
            key = resource_tester.upload_object(bucket_name=bucket.name, key_name=resource_tester.id_generator(12, string.ascii_lowercase  + string.digits), contents= resource_tester.id_generator(200))
            if not self.args.no_cleanup:
                resource_tester.terminate_instances(reservation)

if __name__ == "__main__":
    testcase = ResourceGeneration()
    ### Either use the list of tests passed from config/command line to determine what subset of tests to run
    list = testcase.args.tests or [ "CreateResources"]
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )
        ### Run the EutesterUnitTest objects

    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)
