#!/usr/bin/python

import time
from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase
import os
import random

class TaggingBasics(EutesterTestCase):
    def __init__(self, extra_args= None):
        self.setuptestcase()
        self.setup_parser()
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()
        # Setup basic eutester object
        self.tester = Eucaops( credpath=self.args.credpath)
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
            self.assertTrue(self.tester.terminate_instances(self.reservation), "Unable to terminate instance(s)")

        if self.volume:
            self.tester.delete_volume(self.volume)

        if self.snapshot:
            self.tester.delete_snapshot(self.snapshot)

        ### DELETE group
        self.tester.delete_group(self.group)

        ### Delete keypair in cloud and from filesystem
        self.tester.delete_keypair(self.keypair)
        os.remove(self.keypath)

    def InstanceTagging(self):
        """
        This case was developed to exercise tagging of an instance resource
        """
        if not self.reservation:
            self.reservation = self.tester.run_instance(self.image, keypair=self.keypair.name, group=self.group.name)
        instance_id = None
        for instance in self.reservation.instances:
            tags = { u'name': 'instance-tag-test', u'location' : 'over there'}
            self.tester.create_tags([instance.id], tags)
            instance.update()
            if instance.tags != tags:
                raise Exception('Tags were not set properly for the instance resource')
            instance_id = instance.id

        ### Test Filtering
        instances = self.tester.ec2.get_all_instances(filters=tags)
        if len(instances) is not 1:
            raise Exception('Filter for instances returned too many results')
        if instances[0].id is not instance_id:
            raise Exception('Wrong instance id returned after filtering')
        self.tester.terminate_instances(self.reservation)
        self.reservation = None

    def VolumeTagging(self):
        """
        This case was developed to exercise tagging of an instance resource
        """
        self.volume = self.tester.create_volume(azone=self.zone)
        tags = { u'name': 'volume-tag-test', u'location' : 'over there'}
        self.tester.create_tags([self.volume.id], tags)
        self.volume.update()
        if self.volume.tags != tags:
            raise Exception('Tags were not set properly for the volume resource')

        ### Test Filtering
        volumes = self.tester.ec2.get_all_volumes(filters=tags)
        if len(volumes) is not 1:
            raise Exception('Filter for instances returned too many results')
        if volumes[0].id is not self.volume.id:
            raise Exception('Wrong instance id returned after filtering')

    def SnapshotTagging(self):
        """
        This case was developed to exercise tagging of an instance resource
        """
        if not self.volume:
            self.volume = self.tester.create_volume(azone=self.zone)
        self.snapshot = self.tester.create_snapshot_from_volume(self.volume)
        tags = { u'name': 'snapshot-tag-test', u'location' : 'over there'}
        self.tester.create_tags([self.volume.id], tags)
        self.snapshot.update()
        if self.snapshot.tags != tags:
            raise Exception('Tags were not set properly for the snapshot resource')

        ### Test Filtering
        snapshots = self.tester.ec2.get_all_snapshots(filters=tags)
        if len(snapshots) is not 1:
            raise Exception('Filter for instances returned too many results')
        if snapshots[0].id is not self.snapshot.id:
            raise Exception('Wrong instance id returned after filtering')

if __name__ == "__main__":
    testcase = TaggingBasics()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or [ "InstanceTagging", "VolumeTagging", "SnapshotTagging"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)