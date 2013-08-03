#!/usr/bin/env python
#
#
# Description:  This test case checks the fix in EUCA-4329, to make sure that the meta-data
#               elements hostname and local-hostname match based upon the state of 
#               bootstrap.webservices.use_instance_dns

import time
from eucaops import EC2ops, Eucaops
from eutester.euinstance import EuInstance
from eutester.eutestcase import EutesterTestCase
from eutester.machine import Machine
import os
import re
import random


class Euca4329(EutesterTestCase):
    def __init__(self):
        extra_args = ['--instance_dns']
        self.setuptestcase()
        self.setup_parser()
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()
        # Setup basic eutester object
        self.tester = Eucaops(config_file=self.args.config, password=self.args.password, credpath=self.args.credpath)
        self.instance_timeout = 480

        ### Add and authorize a group for the instance
        self.group = self.tester.add_group(group_name="group-" + str(time.time()))
        self.tester.authorize_group_by_name(group_name=self.group.name )
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )
        ### Generate a keypair for the instance
        self.keypair = self.tester.add_keypair( "keypair-" + str(time.time()))
        self.keypath = '%s/%s.pem' % (os.curdir, self.keypair.name)
        self.image = self.args.emi
        if not self.image:
            self.image = self.tester.get_emi(root_device_type="instance-store")
        self.address = None
        self.volume = None
        self.private_addressing = False
        if not self.args.zone:
            zones = self.tester.ec2.get_all_zones()
            self.zone = random.choice(zones).name
        else:
            self.zone = self.args.zone
        self.reservation = None
        self.run_instance_params = {'image': self.image, 'user_data': self.args.user_data, 'username': self.args.instance_user,
                                'keypair': self.keypair.name, 'group': self.group.name,'zone': self.zone,
                                'timeout': self.instance_timeout}

    def set_reservation(self, reservation):
        self.reservation = reservation

    def clean_method(self):
        self.tester.cleanup_artifacts()

    def MetaDataHostnameCheck(self):
        """
        This case was developed to test the metadata service for the following
        meta-data attributes:
           - local-hostname
           - hostname
        After confirming that they are available, per AWS behavior, they are compared
        to each other to make sure they match in value.
        In addition, this test will change the cloud property bootstrap.webservices.use_instance_dns
        to make sure the behavior is consistent whether bootstrap.webservices.use_instance_dns is
        set to true or false.
        If any of these tests fail, the test case will error out; logging the results.
        """
        # Set bootstrap.webservices.use_instance_dns to specific value; if not use cloud's current seting
        if hasattr(self.args, 'instance_dns'):
            clc = self.tester.get_component_machines("clc")[0]
            clc.sys("source " + self.tester.credpath + "/eucarc && " + self.tester.eucapath + "/usr/sbin/euca-modify-property -p bootstrap.webservices.use_instance_dns" +"=" + self.args.instance_dns, code=0)

        if not self.reservation:
            reservation = self.tester.run_instance(**self.run_instance_params)
        else:
            reservation = self.reservation
        for instance in reservation.instances:
            self.assertTrue(re.match(instance.get_metadata("local-hostname")[0], instance.private_dns_name), 'Incorrect private host name in metadata')
            self.assertTrue(re.match(instance.get_metadata("hostname")[0], instance.private_dns_name), 'Incorrect host name in metadata')
            self.assertTrue(re.match(instance.get_metadata("local-hostname")[0], instance.get_metadata("hostname")[0]), 'local-hostname and hostname do not match')
        self.set_reservation(reservation)
        return reservation

if __name__ == "__main__":
    testcase = Euca4329()
    list = testcase.args.tests or [ "MetaDataHostnameCheck"]
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)

