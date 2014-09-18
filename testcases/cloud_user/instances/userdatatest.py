#!/usr/bin/env python
#
#
# Description:  This script encompasses test cases/modules concerning instance specific behavior
#               regarding userdata.  The test cases/modules that are executed can be 
#               found in the script under the "tests" list.

import time
from concurrent.futures import ThreadPoolExecutor
import threading
from eucaops import Eucaops
from eutester.euinstance import EuInstance
from eutester.eutestcase import EutesterTestCase
from eucaops import EC2ops
import os
import re
import random
import StringIO
import difflib


class InstanceBasics(EutesterTestCase):
    def __init__( self, name="InstanceBasics", credpath=None, region=None, config_file=None, password=None, emi=None, zone=None,
                  user_data=None, user_data_file=None, instance_user=None, **kwargs):
        """
        EC2 API tests focused on instance store instances

        :param credpath: Path to directory containing eucarc file
        :param region: EC2 Region to run testcase in
        :param config_file: Configuration file path
        :param password: SSH password for bare metal machines if config is passed and keys arent synced
        :param emi: Image id to use for test
        :param zone: Availability Zone to run test in
        :param user_data: User Data to pass to instance
        :param user_data_file: User Data file to pass to instance
        :param instance_user: User to login to instance as
        :param kwargs: Additional arguments
        """
        super(InstanceBasics, self).__init__(name=name)
        if region:
            self.tester = EC2ops(credpath=credpath, region=region)
        else:
            self.tester = Eucaops(config_file=config_file, password=password, credpath=credpath)
        self.instance_timeout = 480

        ### Add and authorize a group for the instance
        self.group = self.tester.add_group(group_name="group-" + str(time.time()))
        self.tester.authorize_group_by_name(group_name=self.group.name)
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )
        ### Generate a keypair for the instance
        self.keypair = self.tester.add_keypair( "keypair-" + str(time.time()))
        self.keypath = '%s/%s.pem' % (os.curdir, self.keypair.name)
        if emi:
            self.image = emi
        else:
            self.image = self.tester.get_emi(root_device_type="instance-store",not_location="loadbalancer")
        if user_data_file:
            self.user_data_file = user_data_file
            self.user_data = None
        elif user_data:
            self.user_data = user_data  
            self.user_data_file = None

        self.address = None
        self.volume = None
        self.private_addressing = False
        if not zone:
            zones = self.tester.ec2.get_all_zones()
            self.zone = random.choice(zones).name
        else:
            self.zone = zone
        self.reservation = None
        self.reservation_lock = threading.Lock()
        self.run_instance_params = {'image': self.image, 'user_data': self.user_data, 'user_data_file': self.user_data_file,
                                'username': instance_user, 'keypair': self.keypair.name, 'group': self.group.name,'zone': self.zone,
                                'timeout': self.instance_timeout}
        self.managed_network = True

        ### If I have access to the underlying infrastructure I can look
        ### at the network mode and only run certain tests where it makes sense
        if hasattr(self.tester,"service_manager"):
            cc = self.tester.get_component_machines("cc")[0]
            network_mode = cc.sys("cat " + self.tester.eucapath + "/etc/eucalyptus/eucalyptus.conf | grep MODE")[0]
            if re.search("(SYSTEM|STATIC)", network_mode):
                self.managed_network = False

    def set_reservation(self, reservation):
        self.reservation_lock.acquire()
        self.reservation = reservation
        self.reservation_lock.release()

    def clean_method(self):
        self.tester.cleanup_artifacts()

    def UserData(self):
        """
        This case was developed to test the user-data service of an instance for consistency.
        This case does a comparison of the user data passed in by the user-data argument to
        the data supplied by the user-data service within the instance. Supported
        user data formats can be found here: https://cloudinit.readthedocs.org/en/latest/topics/format.html
        If this test fails, the test case will error out; logging the results.
        """
        if not self.reservation:
            reservation = self.tester.run_instance(**self.run_instance_params)
        else:
            reservation = self.reservation
        for instance in reservation.instances:
            """
            Test to see if user data value is a file; if its a file, convert to string then compare,
            if not, do a string compare
            """
            if self.user_data_file:
                with open(self.user_data_file) as user_data_file:
                    user_data = user_data_file.read()
                instance_user_data = StringIO.StringIO(instance.get_userdata())
                self.assertTrue(difflib.SequenceMatcher(None, instance_user_data.getvalue(), user_data), 'Incorrect User Data File')
            elif self.user_data:
                self.assertEqual(instance.get_userdata()[0], self.user_data, 'Incorrect User Data String')


if __name__ == "__main__":
    testcase= EutesterTestCase(name='userdatatest')
    testcase.setup_parser(description="Test the Eucalyptus EC2 instance store userdata functionality.")
    testcase.get_args()
    instancetestsuite= testcase.do_with_args(InstanceBasics)

    ### Either use the list of tests passed from config/command line to determine what subset of tests to run
    list = testcase.args.tests or [ "UserData"]
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = []
    for test in list:
        test = getattr(instancetestsuite,test)
        unit_list.append(testcase.create_testunit_from_method(test))
    testcase.clean_method = instancetestsuite.clean_method
    result = testcase.run_test_case_list(unit_list)
    exit(result)

