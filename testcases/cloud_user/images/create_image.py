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
# Author: Vic Iglesias vic.iglesias@eucalyptus.com
#
#!/usr/bin/python
import os
import re
import time
import random
from eucaops import EC2ops, Eucaops
from eutester.euinstance import EuInstance
from eutester.eutestcase import EutesterTestCase
from eutester.machine import Machine

class ImageCreator(EutesterTestCase):
    def __init__(self):
        extra_args = ['--size', '--repo-url', '--packages', '--user-data']
        self.setuptestcase()
        self.setup_parser()
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()
        # Setup basic eutester object
        if self.args.region:
            self.tester = EC2ops( credpath=self.args.credpath, region=self.args.region)
        else:
            self.tester = Eucaops(config_file=self.args.config, password=self.args.password, credpath=self.args.credpath)
        self.tester.poll_count = 120

        ### Add and authorize a group for the instance
        self.group = self.tester.add_group(group_name="group-" + str(time.time()))
        self.tester.authorize_group_by_name(group_name=self.group.name )
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )
        ### Generate a keypair for the instance
        self.keypair = self.tester.add_keypair( "keypair-" + str(time.time()))
        self.keypath = '%s/%s.pem' % (os.curdir, self.keypair.name)
        if not self.args.emi:
            raise Exception("Must pass base image id to use as parameter --emi")
        self.image =  self.tester.get_emi(self.args.emi)
        self.address = None
        self.volume = None
        self.private_addressing = False
        zones = self.tester.ec2.get_all_zones()
        self.zone = random.choice(zones).name
        self.reservation = None

    def clean_method(self):
        if self.reservation:
            self.tester.terminate_instances(self.reservation)
            self.reservation = None
        if self.volume:
            self.tester.delete_volume(self.volume)

    def CreateImage(self, zone= None):
        '''Register a BFEBS snapshot'''
        if zone is None:
            zone = self.zone
        user_data = open(self.args.user_data, mode="r").read()
        self.reservation = self.tester.run_instance(image=self.args.emi,keypair=self.keypair.name, group=self.group.name,
                                                    zone=zone, user_data=user_data)
        for instance in self.reservation.instances:
            if instance.root_device_type == "ebs":
                self.CreateEBS(instance)
            else:
                self.CreateInstanceStore(instance)
        self.tester.terminate_instances(self.reservation)
        self.reservation = None

    def get_machine(self, instance):
        assert isinstance(instance, EuInstance)
        distro = instance.sys('head -1 /etc/issue')[0]
        if re.search("CentOS", distro):
            return Machine(instance.ip_address, keypath=self.keypath, distro="CENTOS", distro_ver="6")
        elif re.search("Ubuntu", distro):
            return Machine(instance.ip_address, keypath=self.keypath, distro="UBUNTU", distro_ver="PRECISE")
        raise Exception("Unable to find supported distro on image")

    def CreateEBS(self, instance):
        machine = self.get_machine(instance)
        if hasattr(self.args, 'repo'):
            machine.package_manager.add_repo(self.args.repo_url)
        if hasattr(self.args, 'packages'):
            machine.package_manager.install(self.args.packages)
        volume = self.tester.get_volumes(attached_instance=instance.id)[0]
        snapshot = self.tester.create_snapshot(volume.id)
        self.tester.register_snapshot(snapshot)

    def CreateInstanceStore(self, instance):
        machine = self.get_machine(instance)
        if hasattr(self.args, 'repo'):
            machine.package_manager.add_repo(self.args.repo_url)
        if hasattr(self.args, 'packages'):
            machine.package_manager.install(self.args.packages)
        mount_point = "/mnt"
        instance.sys("mfks.ext3 -F /dev/" + instance.rootfs_device + "2" )
        instance.sys("mount " + "/dev/" + instance.rootfs_device + "2 " + mount_point )

        image_file_name = "server.img"
        remote_image_file = mount_point + "/" + image_file_name
        instance.sys("dd bs=1M if=/dev/" + instance.rootfs_device + "1 of=" + remote_image_file, timeout=600)
        machine.sftp.get(remote_image_file, image_file_name)

    def find_filesystem(self, machine, block_device):
        for device in machine.sys('ls -1 ' + block_device + "*"):
            if machine.found('file -s ' + device, "filesystem"):
                return device
        raise Exception("Unable to find a filesystem on block device:" + block_device)

if __name__ == "__main__":
    testcase = ImageCreator()
    ### Either use the list of tests passed from config/command line to determine what subset of tests to run
    list = [ "CreateImage"]
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )
        ### Run the EutesterUnitTest objects

    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)
