#!/usr/bin/python
# Software License Agreement (BSD License)
#
# Copyright (c) 2009-2015, Eucalyptus Systems, Inc.
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
# Author: Shaon imran.hossain@hpe.com


import os
import time
from eucaops import Eucaops
from eutester.euinstance import EuInstance
from eutester.eutestcase import EutesterTestCase
import random
from eutester.euvolume import EuVolume
from testcases.cloud_user.instances.bfebstest import BFEBSBasics


class MigrationTest(EutesterTestCase):
    def __init__(self, extra_args= None):
        self.setuptestcase()
        self.setup_parser()
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.parser.add_argument('--imgurl',
                        help="BFEBS Image to splat down", default=None)
        self.get_args()
        self.tester = Eucaops(config_file=self.args.config, password=self.args.password)

        self.clusters = self.tester.service_manager.get_all_cluster_controllers()
        for cluster in self.clusters:
            self.nodes = self.tester.service_manager.get_all_node_controllers(part_name=cluster.partition)
            if len(self.nodes) < 2:
                self.tester.debug("Not enough NCs in partition '" + cluster.partition + "' to test instance migration.")
                exit(0)
        # TODO
        if len(self.clusters) > 1:
            self.tester.debug("TBD: handle multiple clusters during instance migration tests")
            exit(0)

        self.group = self.tester.add_group(group_name="group-" + str(time.time()))
        self.tester.authorize_group_by_name(group_name=self.group.name )
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )

        self.keypair = self.tester.add_keypair( "keypair-" + str(time.time()))
        self.keypath = '%s/%s.pem' % (os.curdir, self.keypair.name)

        self.image = self.args.emi
        if not self.image:
            self.image = self.tester.get_emi(root_device_type="instance-store")
        self.numberOfResources = 3
        zones = self.tester.ec2.get_all_zones()
        self.zone = random.choice(zones).name

        try:
            self.tester.get_emi(root_device_type="ebs")
        except:
            bfebs = self.do_with_args(BFEBSBasics)
            bfebs.RegisterImage()

    def clean_method(self):
        self.tester.cleanup_artifacts()

    def MigrationBasic(self, volume=None):
        enabled_clc = self.tester.service_manager.get_enabled_clc().machine
        self.reservation = self.tester.run_instance(self.image, username=self.args.instance_user, keypair=self.keypair.name, group=self.group.name, zone=self.zone)
        instance = self.reservation.instances[0]
        assert isinstance(instance, EuInstance)
        volume_device = None
        if volume is not None:
            volume_device = instance.attach_euvolume(volume)

        self.tester.service_manager.populate_nodes()
        source_nc = self.tester.service_manager.get_all_node_controllers(instance_id=instance.id)[0]
        enabled_clc.sys( "source " + self.tester.credpath + "/eucarc &&" +
                         " euserv-migrate-instances -i " + instance.id, code=0)

        def wait_for_new_nc():
            self.tester.service_manager.populate_nodes()
            destination_nc = self.tester.service_manager.get_all_node_controllers(instance_id=instance.id)[0]
            return source_nc.hostname == destination_nc.hostname

        self.tester.wait_for_result(wait_for_new_nc, False, timeout=600, poll_wait=60)
        self.assertTrue(self.tester.ping(instance.public_dns_name), 'Could not ping instance')

        if volume_device:
            instance.sys("ls " + volume_device, code=0)

        destination_nc = self.tester.service_manager.get_all_node_controllers(instance_id=instance.id)[0]
        if destination_nc.machine.distro.name is not "vmware":
            destination_nc.machine.sys("virsh list | grep " + instance.id, code=0)
        else:
            destination_nc.machine.sys("esxcli vm process list | grep " + instance.id, code=0)

        self.tester.terminate_instances(reservation=self.reservation)
        if volume is not None:
            self.tester.delete_volume(volume)

    def MigrationInstanceStoreWithVol(self):
        volume = self.tester.create_volume(zone=self.zone)
        assert isinstance(volume, EuVolume)
        self.MigrationBasic(volume)

    def MigrationBasicEBSBacked(self, volume=None):
        self.image = self.tester.get_emi(root_device_type="ebs")
        self.MigrationBasic(volume)

    def MigrationBasicEBSBackedWithVol(self):
        volume = self.tester.create_volume(zone=self.zone)
        assert isinstance(volume, EuVolume)
        self.MigrationBasicEBSBacked(volume)

    def MigrateToDest(self):
        enabled_clc = self.tester.service_manager.get_enabled_clc().machine
        self.reservation = self.tester.run_instance(self.image, username=self.args.instance_user, keypair=self.keypair.name, group=self.group.name, zone=self.zone)
        instance = self.reservation.instances[0]
        self.tester.service_manager.populate_nodes()
        self.source_nc = self.tester.service_manager.get_all_node_controllers(instance_id=instance.id)[0]

        all_nc = self.tester.service_manager.get_all_node_controllers()
        self.destination_nc = None

        for nc in all_nc:
            if nc.machine.hostname != self.source_nc.machine.hostname:
                self.destination_nc = nc
                enabled_clc.sys("source " + self.tester.credpath + "/eucarc && " +
                                    " euserv-migrate-instances -i " +
                                    instance.id + " --include-dest " + self.destination_nc.machine.hostname, code=0)

                def wait_for_new_nc():
                    self.tester.service_manager.populate_nodes()
                    self.instance_node = self.tester.service_manager.get_all_node_controllers(instance_id=instance.id)[0]
                    return self.instance_node.hostname == self.destination_nc.hostname

                self.tester.wait_for_result(wait_for_new_nc, True, timeout=600, poll_wait=60)
                self.assertTrue( self.tester.ping(instance.public_dns_name), 'Could not ping instance')

        # migrate the instance to it's original source node
        self.destination_nc = self.source_nc
        enabled_clc.sys("source " + self.tester.credpath + "/eucarc && " +
                            " euserv-migrate-instances -i " +
                            instance.id + " --include-dest " + self.destination_nc.machine.hostname, code=0)

        self.tester.wait_for_result(wait_for_new_nc, True, timeout=600, poll_wait=60)
        self.assertTrue(self.tester.ping(instance.public_dns_name), 'Could not ping instance')

        self.tester.terminate_instances(reservation=self.reservation)

    def MigrationToDestEBSBacked(self):
        self.image = self.tester.get_emi(root_device_type="ebs")
        self.MigrateToDest()

    def EvacuateNC(self, volume_list = []):
        instance_list = []
        enabled_clc = self.tester.service_manager.get_enabled_clc().machine
        self.nodes = self.tester.service_manager.populate_nodes()
        # pop out one NC to fill in
        self.source_nc = self.nodes.pop()

        def set_state(node, state):
            # retrying, see EUCA-6389
            while node.state != state:
                self.tester.debug(node.hostname + ": SET STATE TO " + state)
                enabled_clc.sys("euca-modify-service -s " + state + " " + node.hostname, code=0)
                self.tester.sleep(10)
                tmpnodes = self.tester.service_manager.populate_nodes()
                for tmpnode in tmpnodes:
                    if tmpnode.hostname == node.hostname:
                        node = tmpnode

        # stop all the NCs
        for node in self.nodes:
            set_state(node, "STOPPED")

        self.image = self.tester.get_emi(root_device_type="instance-store")
        self.reservation = self.tester.run_instance(self.image, min=3, max=3, username=self.args.instance_user, keypair=self.keypair.name, group=self.group.name, zone=self.zone)

        for i in xrange(3):
            instance = self.reservation.instances[i]
            instance_list.append(instance)
            assert isinstance(instance, EuInstance)
            volume_device = None
            if volume_list:
                volume_device = instance.attach_euvolume(volume_list[i])

        self.nodes = self.tester.service_manager.populate_nodes()
        # start all the NCs
        for node in self.nodes:
            if node.hostname is not self.source_nc.hostname:
                set_state(node, "ENABLED")

        self.nodes = self.tester.service_manager.populate_nodes()
        # evacuate source NC
        enabled_clc.sys("source " + self.tester.credpath + "/eucarc && " +
                            " euserv-migrate-instances -s " +
                        self.source_nc.machine.hostname, code=0)

        def wait_for_evacuation():
            self.tester.service_manager.populate_nodes()
            if self.source_nc.machine.distro.name is "vmware":
                emptyNC = self.source_nc.sys("esxcli vm process list | grep 'Display Name' | awk '{print $3}'")
            else:
                emptyNC = self.source_nc.get_virsh_list()
            return len(emptyNC) == 0

        self.tester.wait_for_result(wait_for_evacuation, True, timeout=600, poll_wait=60)

        for inst in instance_list:
            self.assertTrue(self.tester.ping(inst.public_dns_name), 'Could not ping instance')

        self.tester.terminate_instances(reservation=self.reservation)
        if volume_list:
            self.tester.delete_volumes(volume_list)

    def EvacuateNCWithVol(self):
        volume_list = []
        for i in xrange(self.numberOfResources):
            volume = self.tester.create_volume(zone=self.zone)
            assert isinstance(volume, EuVolume)
            volume_list.append(volume)
        self.EvacuateNC(volume_list)

    def EvacuateNCAllEBS(self):
        self.image = self.tester.get_emi(root_device_type="ebs")
        self.EvacuateNC()

if __name__ == "__main__":
    testcase = MigrationTest()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or ["MigrationBasic", "MigrationInstanceStoreWithVol", "MigrationBasicEBSBacked", "MigrationBasicEBSBackedWithVol", "MigrateToDest", "MigrationToDestEBSBacked", "EvacuateNC", "EvacuateNCWithVol", "EvacuateNCAllEBS"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append(testcase.create_testunit_by_name(test))

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)
