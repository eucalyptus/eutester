#!/usr/bin/python

import os
import time
import random
from eutester.euca.euca_ops import Eucaops
from eutester.utils.eutestcase import EutesterTestCase


class InstanceBasics(EutesterTestCase):
    def __init__(self, extra_args=None):
        self.setuptestcase()
        self.setup_parser()
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()
        self.tester = Eucaops(config_file=self.args.config, password=self.args.password)
        self.tester.poll_count = 120

        ### Add and authorize a group for the instance
        self.group = self.tester.ec2.add_group(group_name="group-" + str(time.time()))
        self.tester.ec2.authorize_group_by_name(group_name=self.group.name )
        self.tester.ec2.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )
        ### Generate a keypair for the instance
        self.keypair = self.tester.ec2.add_keypair( "keypair-" + str(time.time()))
        self.keypath = '%s/%s.pem' % (os.curdir, self.keypair.name)
        self.image = self.args.emi
        if not self.image:
            self.image = self.tester.ec2.get_emi(root_device_type="instance-store")
        self.address = None
        self.volume = None
        self.snapshot = None
        self.private_addressing = False
        zones = self.tester.ec2.connection.get_all_zones()
        self.zone = random.choice(zones).name
        self.reservation = None

    def clean_method(self):
        self.tester.cleanup_artifacts()

    def my_test(self):
        reservation = self.tester.ec2.run_image(self.image,
                                                keypair=self.keypair.name,
                                                group=self.group.name, return_reservation=True)
        for instance in reservation.instances:
            self.assertTrue(self.tester.ec2.wait_for_reservation(reservation), 'Instance did not go to running')
            self.assertTrue(self.tester.ping(instance.ip_address), 'Could not ping instance')
            if self.image.virtualization_type == "paravirtual":
                paravirtual_ephemeral = "/dev/" + instance.rootfs_device + "2"
                self.assertFalse(instance.found("ls -1 " + paravirtual_ephemeral,  "No such file or directory"),
                                 "Did not find ephemeral storage at " + paravirtual_ephemeral)
            elif self.image.virtualization_type == "hvm":
                hvm_ephemeral = "/dev/" + instance.block_device_prefix + "b"
                self.assertFalse(instance.found("ls -1 " + hvm_ephemeral,  "No such file or directory"),
                                 "Did not find ephemeral storage at " + hvm_ephemeral)
            self.debug("Pinging instance public IP from inside instance")
            instance.sys('ping -c 1 ' + instance.ip_address, code=0)
            self.debug("Pinging instance private IP from inside instance")
            instance.sys('ping -c 1 ' + instance.private_ip_address, code=0)
        return reservation

if __name__ == "__main__":
    testcase = InstanceBasics()
    list = testcase.args.tests or ["my_test"]
    unit_list = []
    for test in list:
        unit_list.append(testcase.create_testunit_by_name(test))
    result = testcase.run_test_case_list(unit_list, clean_on_exit=True)
    exit(result)