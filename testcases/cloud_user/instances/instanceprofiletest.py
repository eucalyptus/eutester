#!/usr/bin/env python
#
#
# Description:  This script encompasses test cases/modules concerning instance specific behavior and
#               features regarding the metadata service with regards to IAM roles and instance profiles in Eucalyptus.
#               The test cases/modules that are executed can be found in the script under the "tests" list.

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
import json

class InstanceBasics(EutesterTestCase):
    def __init__( self, name="InstanceBasics", credpath=None, region=None, config_file=None, password=None, emi=None, zone=None,
                  user_data=None, instance_user=None, instance_profile_name=None, instance_profile_arn=None, **kwargs):
        """
        EC2 API tests focused on instance store instances

        :param credpath: Path to directory containing eucarc file
        :param region: EC2 Region to run testcase in
        :param config_file: Configuration file path
        :param password: SSH password for bare metal machines if config is passed and keys arent synced
        :param emi: Image id to use for test
        :param zone: Availability Zone to run test in
        :param user_data: User Data to pass to instance
        :param instance_profile_name: Instance Profile name to pass to instance
        :param instance_profile_arn: Instance Profile ARN to pass to instance
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
        self.address = None
        self.volume = None
        self.private_addressing = False
        if instance_profile_name:
            self.instance_profile_name = instance_profile_name
            self.instance_profile_arn = None
        elif instance_profile_arn:
            self.instance_profile_arn = instance_profile_arn
            self.instance_profile_name = None
        if not zone:
            zones = self.tester.ec2.get_all_zones()
            self.zone = random.choice(zones).name
        else:
            self.zone = zone
        self.reservation = None
        self.reservation_lock = threading.Lock()
        self.run_instance_params = {'image': self.image, 'user_data': user_data, 'username': instance_user,
                                'keypair': self.keypair.name, 'group': self.group.name,'zone': self.zone,
                                'instance_profile_name': self.instance_profile_name,
                                'instance_profile_arn': self.instance_profile_arn, 'timeout': self.instance_timeout}
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

    def InstanceProfileChecks(self):
        """
        This case was developed to test the metadata service regarding instance profile of an instance for consistency.
        The following meta-data attributes are tested:
           - iam/security-credentials/<role-name>
           - iam/info/instance-profile-arn
           - iam/info/instance-profile-id
           - iam/info/last-updated-date
        If any of these tests fail, the test case will error out; logging the results.
        """
        if not self.reservation:
            reservation = self.tester.run_instance(**self.run_instance_params)
        else:
            reservation = self.reservation
        for instance in reservation.instances:
            # Check to see if instance profile ARN/Name matches metadata instance-profile-arn
            if self.instance_profile_name:
                self.assertTrue(re.search(self.instance_profile_name, 
                                                                instance.get_metadata("iam/info/instance-profile-arn")[0]), 'Incorrect Instance Profile Name')
            else:
                self.assertTrue(re.match(instance.get_metadata("iam/info/instance-profile-arn")[0], 
                                                                self.instance_profile_arn), 'Incorrect Instance Profile ARN')
            # Check to see if instance profile ARN is at least 20 characters and at a maximum 2048 characters 
            # based on AWS IAM InstanceProfile data type definition
            self.assertTrue(len(instance.get_metadata("iam/info/instance-profile-arn")[0]) >= 20, 'Instance Profile ARN is less than 20 characters')
            self.assertTrue(len(instance.get_metadata("iam/info/instance-profile-arn")[0]) <= 2048, 'Instance Profile ARN is greater than 2048 characters')
            # Check to see if instance profile ID is at least 16 characters and at a maximum 32 characters 
            # based on AWS IAM InstanceProfile data type definition
            self.assertTrue(len(instance.get_metadata("iam/info/instance-profile-id")[0]) >= 16, 'Instance Profile ID is less than 16 characters')
            self.assertTrue(len(instance.get_metadata("iam/info/instance-profile-id")[0]) <= 32, 'Instance Profile ID is greater than 32 characters')
            # Check date format of instance profile LastUpdated
            self.assertTrue(re.match('(\d{4})[/.-](\d{2})[/.-](\d{2})T(\d{2})[/.:](\d{2})[/.:](\d{2})Z',instance.get_metadata("iam/info/last-updated-date")[0]),
                            'Incorrect date format for Instance Profile LastUpdated')
            # Check to see if iam/security-credentials/<role-name> is available, then check contents
            self.assertTrue(instance.get_metadata("iam/security-credentials/")[0], 'IAM Role Not Available in Metadata')
            try:
                role_name = instance.get_metadata("iam/security-credentials/")[0]
                temp_creds = json.loads(''.join(instance.get_metadata("iam/security-credentials/%s"%role_name)))
            except Exception, e:
                self.tester.debug("Unable to access IAM Role temporary credentials:\n"+ str(e))
                raise e
            # Check date format of temporary credentials LastUpdated variable
            self.assertTrue(re.match('(\d{4})[/.-](\d{2})[/.-](\d{2})T(\d{2})[/.:](\d{2})[/.:](\d{2})Z',temp_creds['LastUpdated'].encode('ascii')),
                            'Incorrect date format for temporary credentials LastUpdated variable')
            # Check to see if AccessKeyId is at least 16 characters and at a maximum 32 characters 
            # based on AWS STS Credentials data type definition
            self.assertTrue(len(temp_creds['AccessKeyId'].encode('ascii')) >= 16, 'AccessKeyId is less than 16 characters')
            self.assertTrue(len(temp_creds['AccessKeyId'].encode('ascii')) <= 32, 'AccessKeyId is greater than 32 characters')
            self.assertTrue(temp_creds['SecretAccessKey'].encode('ascii'), "SecretAccessKey does not exist in " + role_name + " temporary credentials") 
            self.assertTrue(temp_creds['Token'].encode('ascii'), "Token does not exist in " + role_name + " temporary credentials") 
            # Check date format of temporary credentials Expiration variable
            self.assertTrue(re.match('(\d{4})[/.-](\d{2})[/.-](\d{2})T(\d{2})[/.:](\d{2})[/.:](\d{2})Z',temp_creds['Expiration'].encode('ascii')),
                            'Incorrect date format for temporary credentials Expiration variable')
        self.set_reservation(reservation)
        return reservation

if __name__ == "__main__":
    testcase= EutesterTestCase(name='instanceprofiletest')
    testcase.setup_parser(description="Test the Eucalyptus EC2 instance profile metadata functionality.")
    testcase.get_args()
    instancetestsuite= testcase.do_with_args(InstanceBasics)

    ### Either use the list of tests passed from config/command line to determine what subset of tests to run
    list = testcase.args.tests or [ "InstanceProfileChecks"]
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = []
    for test in list:
        test = getattr(instancetestsuite,test)
        unit_list.append(testcase.create_testunit_from_method(test))
    testcase.clean_method = instancetestsuite.clean_method
    result = testcase.run_test_case_list(unit_list)
    exit(result)

