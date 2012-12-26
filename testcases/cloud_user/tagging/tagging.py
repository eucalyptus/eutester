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
        tags = { u'name': 'instance-tag-test', u'location' : 'over there'}
        for instance in self.reservation.instances:
            self.tester.create_tags([instance.id], tags)
            instance.update()
            if instance.tags != tags:
                raise Exception('Tags were not set properly for the instance resource')
            instance_id = instance.id

        ### Test Filtering
        instances = self.tester.ec2.get_all_instances(filters=tags)
        if len(instances) is not 1:
            raise Exception('Filter for instances returned too many results')
        instance = instances[0]
        if instance.id is not instance_id:
            raise Exception('Wrong instance id returned after filtering')

        ### Test Deletion
        self.tester.delete_tags([instance_id], tags)
        instance.update()
        instances = self.tester.ec2.get_all_instances(filters=tags)
        if len(instances) is not 0:
            raise Exception('Filter returned instances when there shouldnt be any')
        if instance.tags != {}:
            raise Exception('Tags still returned after deletion')
        self.test_restrictions(instance)
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

        ### Test Deletion
        self.tester.delete_tags([self.volume.id], tags)
        self.volume.update()
        instances = self.tester.ec2.get_all_instances(filters=tags)
        if len(instances) is not 0:
            raise Exception('Filter returned volumes when there shouldnt be any')
        if self.volume.tags != {}:
            raise Exception('Tags still returned after deleting them from volume')
        self.test_restrictions(self.volume)

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

        ### Test Deletion
        self.tester.delete_tags([self.snapshot.id], tags)
        self.snapshot.update()
        instances = self.tester.ec2.get_all_instances(filters=tags)
        if len(instances) is not 0:
            raise Exception('Filter returned volumes when there shouldnt be any')
        if self.snapshot.tags != {}:
            raise Exception('Tags still returned after deleting them from volume')
        self.test_restrictions(self.snapshot)
        self.tester.delete_snapshot(self.snapshot)
        self.snapshot = None


    def test_restrictions(self, resource):
        max_tags = { u'name': 'snapshot-tag-test', u'location' : 'over there',  u'tag3' : 'test3', u'tag4' : 'test4',
                     u'tag5' : 'test5', u'tag6' : 'test6', u'tag7' : 'test7', u'tag8' : 'test8',
                     u'tag9' : 'test9', u'tag10' : 'test10'}
        self.test_tag_creation(max_tags, resource=resource, fail_message="Failure when trying to add max allowable tags (10)", operation_allowed=True)
        self.test_tag_deletion(max_tags, fail_message="Failure when trying to delete max allowable tags (10)", operation_allowed=True)

        too_many_tags = { u'name': 'snapshot-tag-test', u'location' : 'over there',  u'tag3' : 'test3', u'tag4' : 'test4',
                          u'tag5' : 'test5', u'tag6' : 'test6', u'tag7' : 'test7', u'tag8' : 'test8',
                          u'tag9' : 'test9', u'tag10' : 'test10', u'tag11' : 'test11'}
        self.test_tag_creation(too_many_tags, fail_message="Allowed too many tags to be created", operation_allowed=False)

        maximum_key_length = { u'000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
                               u'00000000000000000000000000000000000000000000': 'my value'}
        self.test_tag_creation(maximum_key_length, fail_message="Unable to use a key with 128 characters", operation_allowed=True)
        self.test_tag_deletion(maximum_key_length, fail_message="Unable to delete a key with 128 characters", operation_allowed=True)

        key_too_large = { u'000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
                          u'00000000000000000000000000000000000000000000000': 'my value'}
        self.test_tag_creation(key_too_large, fail_message="Allowed key with more than 128 chars", operation_allowed=False)

        maximum_value_length = { u'my_key': '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
                                            '00000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
                                            '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000'}
        self.test_tag_creation(maximum_key_length, fail_message="Unable to use a value with 128 characters", operation_allowed=True)
        self.test_tag_deletion(maximum_key_length, fail_message="Unable to delete a value with 128 characters", operation_allowed=True)

        value_too_large = { u'my_key': '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
                                       '00000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
                                       '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000'}
        self.test_tag_creation(value_too_large, fail_message="Allowed value with more than 128 chars", operation_allowed=False)

        aws_key_prefix = { u'aws:something': 'asdfadsf'}
        self.test_tag_creation(aws_key_prefix, fail_message="Allowed key with 'aws:' prefix'", operation_allowed=False)

        aws_key_prefix = { u'my_key': 'aws:somethingelse'}
        self.test_tag_creation(aws_key_prefix, fail_message="Allowed key with 'aws:' prefix'", operation_allowed=False)

        lower_case = {u'case': 'value'}
        upper_case = {u'CASE': 'value'}
        self.test_tag_creation(lower_case, fail_message="Unable to add key with all lower case", operation_allowed=True)
        self.test_tag_creation(upper_case, fail_message="Case sensitivity not enforced, unable to create tag with different capitalization", operation_allowed=True)
        self.test_tag_deletion(lower_case, fail_message="Unable to delete a tag, when testing case sensitivity", operation_allowed=True)
        self.test_tag_deletion(upper_case, fail_message="Unable to delete a tag, when testing case sensitivity", operation_allowed=True)

    def test_tag_creation(self, tags, resource, fail_message, expected_outcome=True):
        actual_outcome = None
        try:
            self.tester.create_tags([resource.id], tags)
            actual_outcome =  True
        except:
            actual_outcome =  False
        finally:
            if actual_outcome is not expected_outcome:
                raise Exception(fail_message)

    def test_tag_deletion(self, tags, resource, fail_message, expected_outcome=True):
        actual_outcome = None
        try:
            self.tester.delete_tags([resource.id], tags)
            actual_outcome =  True
        except:
            actual_outcome =  False
        finally:
            if actual_outcome is not expected_outcome:
                raise Exception(fail_message)


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