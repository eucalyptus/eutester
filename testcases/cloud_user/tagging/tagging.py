#!/usr/bin/python

import time
from eucaops import Eucaops
from eucaops import EC2ops
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
        if self.args.region:
            self.tester = EC2ops( credpath=self.args.credpath, region=self.args.region)
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

    def InstanceTagging(self):
        """
        This case was developed to exercise tagging of an instance resource
        """
        if not self.reservation:
            self.reservation = self.tester.run_instance(self.image, keypair=self.keypair.name, group=self.group.name)
        test_instance = None
        tags = { u'name': 'instance-tag-test', u'location' : 'over there'}
        for instance in self.reservation.instances:
            instance.create_tags(tags)
            test_instance = instance

        ### Test Filtering , u'tag:location' : 'over there'
        tag_filter = { u'tag:name': u'instance-tag-test'}
        reservations = self.tester.ec2.get_all_instances(filters=tag_filter)
        if len(reservations) != 1:
            raise Exception('Filter for instances returned too many results')
        reservation = reservations[0]
        if self.reservation.id not in reservation.id:
            raise Exception('Wrong instance id returned after filtering, Expected: ' + self.reservation.id  + ' Received: ' + reservation.id )

        ### Test non-tag Filtering
        ### Filters can be found here, most will be tested manually, but a spot check should be added
        ### http://docs.aws.amazon.com/AWSEC2/latest/CommandLineReference/ApiReference-cmd-DescribeInstances.html
        new_group = self.tester.add_group("filter-test")
        self.tester.authorize_group_by_name(group_name=new_group.name )
        self.tester.authorize_group_by_name(group_name=new_group.name, port=-1, protocol="icmp" )
        filter_test_reservation = self.tester.run_instance(self.image, keypair=self.keypair.name, group=new_group.name)
        keypair_filter = {u'key-name': self.keypair.name}
        group_filter = {u'group-name': new_group.name}

        keypair_match = self.tester.ec2.get_all_instances(filters=keypair_filter)
        group_match = self.tester.ec2.get_all_instances(filters=group_filter)
        self.tester.terminate_instances(filter_test_reservation)
        self.tester.delete_group(new_group)
        self.tester.delete_keypair(self.keypair)

        if len(group_match) != 1:
            raise Exception("Non-tag Filtering of instances by group name: " + str(len(group_match))  + " expected: 1")
        if len(keypair_match) != 2:
            raise Exception("Non-tag Filtering of instances by keypair name: " + str(len(keypair_match))  + " expected: 2")

        ### Test Deletion
        test_instance.delete_tags(tags)
        instances = self.tester.ec2.get_all_instances(filters=tag_filter)
        if len(instances) != 0:
            raise Exception('Filter returned instances when there shouldnt be any')

        if all(item in test_instance.tags.items() for item in tags.items()):
            raise Exception('Tags still returned after deletion')
        #self.test_restrictions(test_instance)
        #self.test_in_series(test_instance)
        self.tester.terminate_instances(self.reservation)
        self.reservation = None

    def VolumeTagging(self):
        """
        This case was developed to exercise tagging of an instance resource
        """
        self.volume = self.tester.create_volume(zone=self.zone)
        tags = { u'name': 'volume-tag-test', u'location' : 'datacenter'}
        self.volume.create_tags(tags)

        ### Test Filtering
        tag_filter = { u'tag:name': u'volume-tag-test'}
        volumes = self.tester.ec2.get_all_volumes(filters=tag_filter)
        if len(volumes) is 0:
            raise Exception('Filter for instances returned no results ' + str(volumes))
        if len(volumes) is not 1:
            raise Exception('Filter for instances returned too many results ' + str(volumes))
        if volumes[0].id != self.volume.id:
            raise Exception('Wrong volume ID returned after filtering ' + str(volumes) )

        ### Test non-tag Filtering
        ### Filters can be found here, most will be tested manually, but a spot check should be added
        ### http://docs.aws.amazon.com/AWSEC2/latest/CommandLineReference/ApiReference-cmd-DescribeImages.html
        vol_size = 3
        filter_test_volume_1 = self.tester.create_volume(zone=self.zone, size=vol_size)
        filter_test_volume_2 = self.tester.create_volume(zone=self.zone, size=vol_size)
        size_filter = {u'size': vol_size }
        id_filter = {u'volume-id': self.volume.id}

        size_match = self.tester.ec2.get_all_volumes(filters=size_filter)
        id_match = self.tester.ec2.get_all_volumes(filters=id_filter)

        self.tester.delete_volume(filter_test_volume_1)
        self.tester.delete_volume(filter_test_volume_2)

        if len(size_match) != 2:
            raise Exception("Non-tag Filtering of volumes by size: " + str(len(size_match))  + " expected: 2")
        if len(id_match) != 1:
            raise Exception("Non-tag Filtering of volumes by id: " + str(len(id_match))  + " expected: 1")

        ### Test Deletion
        self.volume.delete_tags(tags)
        instances = self.tester.ec2.get_all_instances(filters=tag_filter)
        if len(instances) != 0:
            raise Exception('Filter returned volumes when there shouldnt be any')
        if self.volume.tags != {}:
            raise Exception('Tags still returned after deleting them from volume')
        #self.test_restrictions(self.volume)
        #self.test_in_series(self.volume)

    def SnapshotTagging(self):
        """
        This case was developed to exercise tagging of an instance resource
        """
        if not self.volume:
            self.volume = self.tester.create_volume(zone=self.zone)
        self.snapshot = self.tester.create_snapshot_from_volume(self.volume)
        tags = { u'name': 'snapshot-tag-test', u'location' : 'over there'}
        self.snapshot.create_tags(tags)

        ### Test Filtering , u'tag:location' : 'over there'
        tag_filter = { u'tag:name': 'snapshot-tag-test'}
        snapshots = self.tester.ec2.get_all_snapshots(filters=tag_filter)
        if len(snapshots) != 1:
            raise Exception('Filter for instances returned too many results')
        if snapshots[0].id != self.snapshot.id:
            raise Exception('Wrong instance id returned after filtering')

        ### Test non-tag Filtering
        ### Filters can be found here, most will be tested manually, but a spot check should be added
        ### http://docs.aws.amazon.com/AWSEC2/latest/CommandLineReference/ApiReference-cmd-DescribeSnapshots.html
        filter_description = "filtering" + str(int(time.time()))
        filter_test_snapshot = self.tester.create_snapshot_from_volume(self.volume, description=filter_description)

        description_filter = {u'description': filter_description }
        volume_filter = {u'volume-id': self.volume.id}

        description_match = self.tester.ec2.get_all_snapshots(filters=description_filter)
        volume_match = self.tester.ec2.get_all_snapshots(filters=volume_filter)

        self.tester.delete_snapshot(filter_test_snapshot)

        if len(description_match) != 1:
            raise Exception("Non-tag Filtering of snapshots by volume description: " + str(len(description_match))  + " expected: 1")

        if len(volume_match) != 2:
            raise Exception("Non-tag Filtering of snapshots by volume id returned: " + str(len(volume_match))  + " expected: 2")

        ### Test Deletion
        self.snapshot.delete_tags(tags)
        instances = self.tester.ec2.get_all_instances(filters=tag_filter)
        if len(instances) != 0:
            raise Exception('Filter returned snapshots when there shouldnt be any')
        if self.snapshot.tags != {}:
            raise Exception('Tags still returned after deleting them from volume')
        #self.test_restrictions(self.snapshot)
        #self.test_in_series(self.snapshot)
        self.tester.delete_snapshot(self.snapshot)
        self.snapshot = None

    def ImageTagging(self):
        """
        This case was developed to exercise tagging of an instance resource
        """
        tags = { u'name': 'image-tag-test', u'location' : 'over there'}
        self.tester.create_tags([self.image.id], tags)

        ### Test Tag Filtering , u'tag:location' : 'over there'
        tag_filter = { u'tag:name': 'image-tag-test'}
        images = self.tester.ec2.get_all_images(filters=tag_filter)
        if len(images) != 1:
            raise Exception('Filter for instances returned too many results')
        if images[0].id != self.image.id:
            raise Exception('Wrong instance id returned after filtering')

        ### Test non-tag Filtering
        ### Filters can be found here, most will be tested manually, but a spot check should be added
        ### http://docs.aws.amazon.com/AWSEC2/latest/CommandLineReference/ApiReference-cmd-DescribeImages.html
        image_description = "image-filtering"
        filter_image_id = self.tester.register_image(
            image_location=self.image.location,
            description=image_description,
            virtualization_type=self.image.virtualization_type)

        description_filter = {u'description': image_description }
        location_filter = {u'manifest-location': self.image.location}

        description_match = self.tester.ec2.get_all_images(filters=description_filter)
        location_match = self.tester.ec2.get_all_images(filters=location_filter)
        filter_image = self.tester.get_emi(emi=filter_image_id)
        self.tester.deregister_image(filter_image)

        if len(description_match) != 1:
            raise Exception("Non-tag Filtering of volumes by size: " + str(len(description_match))  + " expected: 1")
        if len(location_match) != 2:
            raise Exception("Non-tag Filtering of volumes by zone: " + str(len(location_match))  + " expected: 2")

        ### Test Deletion
        self.tester.delete_tags([self.image.id], tags)
        images = self.tester.ec2.get_all_images(filters=tag_filter)
        if len(images) != 0:
            raise Exception('Filter returned volumes when there shouldnt be any')
        if self.image.tags != {}:
            raise Exception('Tags still returned after deleting them from image: ' + str(self.image.tags) )
        #self.test_restrictions(self.image)
        #self.test_in_series(self.image)

    def SecurityGroupTagging(self):
        """
        This case was developed to exercise tagging of an security group resource
        """
        tags = { u'name': 'security-tag-test', u'location' : 'over there'}
        self.debug("Security group ID: " + self.group.id)
        self.tester.create_tags([self.group.id], tags)

        ### Test Tag Filtering , u'tag:location' : 'over there'
        tag_filter = { u'tag:name': 'security-tag-test'}
        groups = self.tester.ec2.get_all_security_groups(filters=tag_filter)
        if len(groups) != 1:
            raise Exception('Filter for groups returned too many results')
        if groups[0].id != self.group.id:
            raise Exception('Wrong group id returned after filtering')

        ### Test non-tag Filtering
        ### Filters can be found here, most will be tested manually, but a spot check should be added
        ### http://docs.aws.amazon.com/AWSEC2/latest/CommandLineReference/ApiReference-cmd-DescribeSecurityGroups.html
        group_name = "filter-test"
        group_description = "group-filtering"
        filter_group = self.tester.add_group(group_name=group_name, description=group_description)
        filter_group_2 = self.tester.add_group(group_name=group_name + "2", description=group_description)

        description_filter = {u'description': group_description }
        group_id_filter = {u'group-id': filter_group.id}
        description_match = self.tester.ec2.get_all_security_groups(filters=description_filter)
        self.debug("Groups matching description:" + str(description_match))
        group_id_match = self.tester.ec2.get_all_security_groups(filters=group_id_filter)
        self.debug("Groups matching owner-id (" + group_id_filter[u'group-id']  + "):" + str(group_id_match))

        self.tester.delete_group(filter_group)
        self.tester.delete_group(filter_group_2)

        if len(description_match) != 2:
            raise Exception("Non-tag Filtering of security groups by description: " + str(len(description_match))  + " expected: 2")
        if len(group_id_match) != 1:
            raise Exception("Non-tag Filtering of security groups by id: " + str(len(group_id_match))  + " expected: 1")

        ### Test Deletion
        self.tester.delete_tags([self.group.id], tags)
        groups = self.tester.ec2.get_all_security_groups(filters=tag_filter)
        if len(groups) != 0:
            raise Exception('Filter returned volumes when there shouldnt be any')
        if self.image.tags != {}:
            raise Exception('Tags still returned after deleting them from volume')
        #self.test_restrictions(self.group)
        #self.test_in_series(self.group)


    def test_restrictions(self, resource):
        max_tags_number = 10
        max_tags = {}

        for i in xrange(max_tags_number):
            max_tags[u'key' + str(i)] = 'value' + str(i)

        self.test_tag_creation(max_tags, resource=resource, fail_message="Failure when trying to add max allowable tags (" + str(max_tags_number) + ")", expected_outcome=True)
        self.test_tag_deletion(max_tags, resource=resource,fail_message="Failure when trying to delete max allowable tags (" + str(max_tags_number) + ")", expected_outcome=True)

        too_many_tags = {}
        for i in xrange(max_tags_number + 1):
            too_many_tags[u'key' + str(i)] = 'value' + str(i)

        self.test_tag_creation(too_many_tags, resource=resource,fail_message="Allowed too many tags to be created", expected_outcome=False)

        max_key = u'0' * 127

        maximum_key_length = { max_key : 'my value'}
        self.test_tag_creation(maximum_key_length, resource=resource, fail_message="Unable to use a key with " + str(max_key) + " characters", expected_outcome=True)
        self.test_tag_deletion(maximum_key_length, resource=resource, fail_message="Unable to delete a key with " + str(max_key) + " characters", expected_outcome=True)

        key_too_large = { max_key + u'0' : 'my value'}
        self.test_tag_creation(key_too_large, resource=resource, fail_message="Allowed key with more than " + str(max_key) + " chars", expected_outcome=False)

        maximum_value = '0' * 255

        maximum_value_length = { u'my_key': maximum_value}
        self.test_tag_creation(maximum_value_length, resource=resource, fail_message="Unable to use a value with " + str(maximum_value) + " characters", expected_outcome=True)
        self.test_tag_deletion(maximum_value_length, resource=resource, fail_message="Unable to delete a value with " + str(maximum_value) + " characters", expected_outcome=True)

        value_too_large = { u'my_key': maximum_value + '0'}
        self.test_tag_creation(value_too_large, resource=resource, fail_message="Allowed value with more than " + str(maximum_value) + " chars", expected_outcome=False)

        aws_key_prefix = { u'aws:something': 'asdfadsf'}
        self.test_tag_creation(aws_key_prefix, resource=resource, fail_message="Allowed key with 'aws:' prefix'", expected_outcome=False)

        aws_value_prefix = { u'my_key': 'aws:somethingelse'}
        self.test_tag_creation(aws_value_prefix, resource=resource, fail_message="Did not allow creation value with 'aws:' prefix'", expected_outcome=True)
        self.test_tag_creation(aws_value_prefix, resource=resource, fail_message="Did not allow deletion of value with 'aws:' prefix'", expected_outcome=True)

        lower_case = {u'case': 'value'}
        upper_case = {u'CASE': 'value'}
        self.test_tag_creation(lower_case, resource=resource, fail_message="Unable to add key with all lower case", expected_outcome=True)
        self.test_tag_creation(upper_case, resource=resource, fail_message="Case sensitivity not enforced, unable to create tag with different capitalization", expected_outcome=True)
        self.test_tag_deletion(lower_case, resource=resource, fail_message="Unable to delete a tag, when testing case sensitivity", expected_outcome=True)
        self.test_tag_deletion(upper_case, resource=resource, fail_message="Unable to delete a tag, when testing case sensitivity", expected_outcome=True)

    def test_tag_creation(self, tags, resource, fail_message, expected_outcome=True, timeout=600):
        actual_outcome = None
        exception = None
        try:
            resource.create_tags(tags, timeout=timeout)
            actual_outcome =  True
        except Exception, e:
            exception = e
            actual_outcome =  False
        finally:
            if actual_outcome is not expected_outcome:
                raise Exception(fail_message + "\nDue to: " + str(exception) )

    def test_tag_deletion(self, tags, resource, fail_message, expected_outcome=True, timeout=600):
        actual_outcome = None
        exception = None
        try:
            resource.delete_tags(tags, timeout=timeout)
            actual_outcome =  True
        except Exception, e:
            exception = e
            actual_outcome =  False
        finally:
            if actual_outcome is not expected_outcome:
                raise Exception(fail_message + "\nDue to: " + str(exception) )

    def test_in_series(self, resource, count=5):
        for i in xrange(count):
            normal_tag = { u'series_key': '!@$$%^^&&*()*&&^%{}":?><|][~'}
            self.test_tag_creation(normal_tag, resource=resource, fail_message="Failed adding tags in series", expected_outcome=True)
            self.test_tag_deletion(normal_tag, resource=resource, fail_message="Failed deleting tags in series", expected_outcome=True)


if __name__ == "__main__":
    testcase = TaggingBasics()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list  "VolumeTagging", "InstanceTagging", "SnapshotTagging", "ImageTagging"
    list = testcase.args.tests or ["VolumeTagging", "SnapshotTagging","ImageTagging", "InstanceTagging", "SecurityGroupTagging"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)