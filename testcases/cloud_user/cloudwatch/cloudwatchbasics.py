#!/usr/bin/python

import time
from eucaops import Eucaops
from eucaops import CWops
from eutester.eutestcase import EutesterTestCase
import os
import random
import datetime

class CloudWatchBasics(EutesterTestCase):
    def __init__(self, extra_args= None):
        self.setuptestcase()
        self.setup_parser()
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()
        # Setup basic eutester object
        if self.args.region:
            self.tester = CWops( credpath=self.args.credpath, region=self.args.region)
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
        self.image = self.args.emi
        if not self.image:
            self.image = self.tester.get_emi(root_device_type="instance-store")
        self.address = None
        self.volume = None
        self.snapshot = None
        self.private_addressing = False
        zones = self.tester.ec2.get_all_zones()
        self.zone = random.choice(zones).name
        self.reservation = None

    def clean_method(self):
        ### Terminate the reservation if it is still up
        if self.reservation:
            for instance in self.reservation.instances:
                instance.delete_tags(instance.tags)
            self.assertTrue(self.tester.terminate_instances(self.reservation), "Unable to terminate instance(s)")

        if self.volume:
            self.tester.delete_volume(self.volume,timeout=600)

        if self.snapshot:
            self.tester.delete_snapshot(self.snapshot)

        ### DELETE group
        self.tester.delete_group(self.group)

        ### Delete keypair in cloud and from filesystem
        self.tester.delete_keypair(self.keypair)
        os.remove(self.keypath)

    def get_time_window(self, hours_ago=1, end=None):
        if not end:
            end = datetime.datetime.utcnow()
        start = end - datetime.timedelta(hours=hours_ago)
        return (start,end)

    def print_timeseries_for_graphite(timeseries):
            for datapoint in timeseries:
                print "graph.Namespace-1361426618 " + str(int(datapoint['Average'])) + " " + \
                      str((datapoint['Timestamp'] - datetime.datetime(1970,1,1)).total_seconds())

    def GetPut(self):
        seconds_to_put_data = 600000000000000
        starting_metric_data = 1
        time_string =  str(int(time.time()))
        namespace = "Namespace-" + time_string
        metric_name = "Metric-" + time_string
        incrementing = True
        for i in xrange(seconds_to_put_data):
            self.tester.cw.put_metric_data(namespace, [metric_name],[starting_metric_data])
            if starting_metric_data == 600 or starting_metric_data == 0:
                incrementing = not incrementing
            if incrementing:
                starting_metric_data += 1
            else:
                starting_metric_data -= 1
            self.tester.sleep(1)

if __name__ == "__main__":
    testcase = CloudWatchBasics()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list  "VolumeTagging", "InstanceTagging", "SnapshotTagging", "ImageTagging"
    list = testcase.args.tests or ["GetPut"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)