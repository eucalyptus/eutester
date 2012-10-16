#!/usr/bin/env python
#
#
# Description:  This script encompasses test cases/modules concerning instance specific behavior and
#               features for Eucalyptus.  The test cases/modules that are executed can be 
#               found in the script under the "tests" list.


import time
from eucaops import Eucaops
from eutester.euinstance import EuInstance
from eutester.eutestcase import EutesterTestCase
import os
import random


class ReportingBasics(EutesterTestCase):
    def __init__(self, config_file=None, password=None):
        self.setuptestcase()
        # Setup basic eutester object
        self.tester = Eucaops( config_file=config_file, password=password)
        self.tester.poll_count = 120

        ### Add and authorize a group for the instance
        self.group = self.tester.add_group(group_name="group-" + str(time.time()))
        self.tester.authorize_group_by_name(group_name=self.group.name )
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )
        ### Generate a keypair for the instance
        self.keypair = self.tester.add_keypair( "keypair-" + str(time.time()))
        self.keypath = '%s/%s.pem' % (os.curdir, self.keypair.name)
        self.image = self.tester.get_emi(root_device_type="instance-store")
        self.reservation = None
        self.volume = None
        self.bucket = None
        self.private_addressing = False
        zones = self.tester.ec2.get_all_zones()
        self.zone = random.choice(zones).name

        self.cur_time = str(int(time.time()))

        clcs = self.tester.get_component_machines("clc")
        if len(clcs) is 0:
            raise Exception("No CLC found")
        else:
            self.clc = clcs[0]
        poll_interval = 1
        write_interval = 1
        size_time_size_unit = "MB"
        size_time_time_unit = "MINS"
        size_unit = "MB"
        time_unit = "MINS"
        self.modify_property(property="reporting.default_poll_interval_mins",value=poll_interval)
        self.modify_property(property="reporting.default_write_interval_mins",value=write_interval)
        self.modify_property(property="reporting.default_size_time_size_unit",value=size_time_size_unit)
        self.modify_property(property="reporting.default_size_time_time_unit",value=size_time_time_unit)
        self.modify_property(property="reporting.default_size_unit",value=size_unit)
        self.modify_property(property="reporting.default_time_unit",value=time_unit)

    def clean_method(self):
        if self.reservation:
            self.assertTrue(self.tester.terminate_instances(self.reservation), "Unable to terminate instance(s)")
        if self.volume:
            self.tester.delete_volume(self.volume)
        if self.bucket:
            self.tester.clear_bucket(self.bucket)
        self.tester.delete_group(self.group)
        self.tester.delete_keypair(self.keypair)
        os.remove(self.keypath)

    def instance(self):
        self.reservation = self.tester.run_instance(self.image, keypair=self.keypair.name, group=self.group.name, zone=self.zone)
        self.tester.sleep(120)
        file_size_in_mb = 500
        for instance in self.reservation.instances:
            assert isinstance(instance, EuInstance)
            self.volume = self.tester.create_volume(azone=self.zone, size=4)
            device_path = instance.attach_volume(self.volume)
            instance.sys("mkfs.ext3 -F " + device_path)
            instance.sys("mount " + device_path + " /mnt")
            ### Write to root fs
            instance.sys("dd if=/dev/zero of=/tmp/test.img count=" + str(file_size_in_mb) + " bs=1M")
            ### Write to volume
            instance.sys("dd if=/dev/zero of=/mnt/test.img count=" + str(file_size_in_mb) + " bs=1M")

        self.tester.sleep(120)
        report_output = self.generate_report("instance","csv")

    def s3(self):
        self.bucket = self.tester.create_bucket(bucket_name="reporting-bucket-" + self.cur_time)
        key_size = 10
        self.tester.debug("Creating random " + str(key_size) + "MB of data")
        rand_string = self.tester.id_generator(size=1024*1024*10)
        self.tester.upload_object(self.bucket.name, "reporting-key" ,contents=rand_string)
        self.tester.sleep(120)
        report_output = self.generate_report("s3", "csv")


    def generate_report(self, type, format):
        return self.clc.sys("source " + self.tester.credpath + "/eucarc && eureport-generate-report -t " + str(type) +" -f " + str(format))

    def modify_property(self, property, value):
        """
        Modify a eucalyptus property through the command line euca-modify-property tool
        property        Property to modify
        value           Value to set it too
        """
        command = "source " + self.tester.credpath + "/eucarc && " + self.tester.eucapath + "/usr/sbin/euca-modify-property -p " + str(property) + "=" + str(value)
        if self.clc.found(command, property):
            self.debug("Properly modified property " + property)
        else:
            raise Exception("Setting property " + property + " failed")


if __name__ == "__main__":
    testcase = EutesterTestCase()

    #### Adds argparse to testcase and adds some defaults args
    testcase.setup_parser()

    ### Get all cli arguments and any config arguments and merge them
    testcase.get_args()

    ### Instantiate an object of your test suite class using args found from above
    instance_basics_tests = testcase.do_with_args(ReportingBasics)

    ### Either use the list of tests passed from config/command line to determine what subset of tests to run
    list = testcase.args.tests or [ "s3"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( instance_basics_tests.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    testcase.run_test_case_list(unit_list)
    instance_basics_tests.clean_method()

