#!/usr/bin/env python
#
#
# Description:  This script encompasses test cases/modules concerning instance specific behavior and
#               features for Eucalyptus.  The test cases/modules that are executed can be 
#               found in the script under the "tests" list.
import re

import time
from eucaops import Eucaops
from eutester.euinstance import EuInstance
from eutester.eutestcase import EutesterTestCase
import os
import random
from collections import namedtuple

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
        self.clean_method = self.cleanup
        self.cur_time = str(int(time.time()))
        date_fields = time.localtime()
        self.date = str(date_fields.tm_year) + "-" + str(date_fields.tm_mon) + "-31"
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

    def cleanup(self):
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
        file_size_in_mb = 500
        for instance in self.reservation.instances:
            assert isinstance(instance, EuInstance)
            self.volume = self.tester.create_volume(zone=self.zone, size=4)
            device_path = instance.attach_volume(self.volume)
            instance.sys("mkfs.ext3 -F " + device_path)
            instance.sys("mount " + device_path + " /mnt")
            ### Write to root fs
            instance.sys("dd if=/dev/zero of=/tmp/test.img count=" + str(file_size_in_mb) + " bs=1M")
            ### Write to volume
            instance.sys("dd if=/dev/zero of=/mnt/test.img count=" + str(file_size_in_mb) + " bs=1M")

        self.tester.sleep(180)
        for instance in self.reservation.instances:
            report_output = self.generate_report("instance","csv", self.date)
            instance_lines = self.tester.grep(instance.id, report_output)
            for line in instance_lines:
                instance_data = self.parse_instance_line(line)
                #if not re.search( instance.id +",m1.small,1,9,0.2,0,0,0,0,93,200,0.2,0.0,0,1", line):
                if not re.match(instance_data.type, "m1.small"):
                    raise Exception("Failed to find proper output for " + str(instance) + " type. Received: " + instance_data.type )
                if not int(instance_data.number)  == 1:
                    raise Exception("Failed to find proper output for " + str(instance) + " number. Received: " + instance_data.number )
                if not int(instance_data.unit_time)  > 2 :
                    raise Exception("Failed to find proper output for " + str(instance) + " unit_time. Received: " + instance_data.unit_time )
                if not int(instance_data.disk_write)  > 1000:
                    raise Exception("Failed to find proper output for " + str(instance) + " disk_write. Received: " + instance_data.disk_write )
                if not int(instance_data.disk_time_write)  > 200:
                    raise Exception("Failed to find proper output for " + str(instance) + " disk_time_write. Received: " + instance_data.disk_time_write )


    def parse_instance_line(self, line):
        InstanceData = namedtuple('InstanceData', 'id type number unit_time cpu net_total_in net_total_out '
                                                'net_extern_in net_extern_out disk_read disk_write disk_iops_read '
                                                'disk_iops_write disk_time_read disk_time_write')
        values = line.split(",")
        return InstanceData(values[0],values[1],values[2],values[3],values[4],values[5],values[6],values[7],
                            values[8],values[9],values[10],values[11],values[12],values[13],values[14])

    def s3(self):
        self.bucket = self.tester.create_bucket(bucket_name="reporting-bucket-" + self.cur_time)
        key_size = 10
        self.tester.debug("Creating random " + str(key_size) + "MB of data")
        rand_string = self.tester.id_generator(size=1024*1024*10)
        self.tester.upload_object(self.bucket.name, "reporting-key" ,contents=rand_string)
        self.tester.sleep(120)
        report_output = self.generate_report("s3", "csv",self.date)
        bucket_lines = self.tester.grep(self.bucket.name, report_output)
        for line in bucket_lines:
            bucket_data = self.parse_bucket_line(line)
            if not int(bucket_data.size) == 10:
                raise Exception('Failed to find proper size for %s' % str(self.bucket))
            if not int(bucket_data.keys) == 1:
                raise Exception('Failed to find proper number of keys for %s' % str(self.bucket))
            if not int(bucket_data.unit_time) > 16:
                raise Exception('Failed to find proper amount of usage for %s' % str(self.bucket))

    def parse_bucket_line(self, line):
        BucketData = namedtuple('BucketData', 'name keys size unit_time')
        values = line.split(",")
        return BucketData(values[0],values[1],values[2],values[3] )

    def generate_report(self, type, format, end_date):
        return self.clc.sys("source " + self.tester.credpath + "/eucarc && eureport-generate-report -t " +
                    str(type) +" -f " + str(format) + " -e " + str(end_date) )

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
    list = testcase.args.tests or ["instance"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( instance_basics_tests.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    testcase.run_test_case_list(unit_list)


