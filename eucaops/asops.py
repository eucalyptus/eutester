# Software License Agreement (BSD License)
#
# Copyright (c) 2009-2014, Eucalyptus Systems, Inc.
# All rights reserved.
#
# Redistribution and use of this software in source and binary forms, with or
# without modification, are permitted provided that the following conditions
# are met:
#
#   Redistributions of source code must retain the above
#   copyright notice, this list of conditions and the
#   following disclaimer.
#
#   Redistributions in binary form must reproduce the above
#   copyright notice, this list of conditions and the
#   following disclaimer in the documentation and/or other
#   materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Author: tony@eucalyptus.com
import re
import copy

import boto
from boto.ec2.autoscale import ScalingPolicy, Instance
from boto.ec2.autoscale import Tag
from boto.ec2.autoscale import LaunchConfiguration
from boto.ec2.autoscale import AutoScalingGroup
from boto.ec2.regioninfo import RegionInfo
from boto.exception import BotoServerError

from eutester import Eutester


ASRegionData = {
    'us-east-1': 'autoscaling.us-east-1.amazonaws.com',
    'us-west-1': 'autoscaling.us-west-1.amazonaws.com',
    'us-west-2': 'autoscaling.us-west-2.amazonaws.com',
    'eu-west-1': 'autoscaling.eu-west-1.amazonaws.com',
    'ap-northeast-1': 'autoscaling.ap-northeast-1.amazonaws.com',
    'ap-southeast-1': 'autoscaling.ap-southeast-1.amazonaws.com',
    'ap-southeast-2': 'autoscaling.ap-southeast-2.amazonaws.com',
    'sa-east-1': 'autoscaling.sa-east-1.amazonaws.com'}


class ASops(Eutester):
    def __init__(self, host=None, credpath=None, endpoint=None, aws_access_key_id=None, aws_secret_access_key=None,
                 username="root", region=None, is_secure=False, path='/', port=80, boto_debug=0):
        """
        :param host:
        :param credpath:
        :param endpoint:
        :param aws_access_key_id:
        :param aws_secret_access_key:
        :param username:
        :param region:
        :param is_secure:
        :param path:
        :param port:
        :param boto_debug:
        """
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.account_id = None
        self.user_id = None
        super(ASops, self).__init__(credpath=credpath)

        self.setup_as_connection(host=host,
                                 region=region,
                                 endpoint=endpoint,
                                 aws_access_key_id=self.aws_access_key_id,
                                 aws_secret_access_key=self.aws_secret_access_key,
                                 is_secure=is_secure,
                                 path=path,
                                 port=port,
                                 boto_debug=boto_debug)
        self.poll_count = 48
        self.username = username
        self.test_resources = {}
        self.setup_as_resource_trackers()

    @Eutester.printinfo
    def setup_as_connection(self, endpoint=None, aws_access_key_id=None, aws_secret_access_key=None, is_secure=True,
                            host=None, region=None, path="/", port=443, boto_debug=0):
        """
        :param endpoint:
        :param aws_access_key_id:
        :param aws_secret_access_key:
        :param is_secure:
        :param host:
        :param region:
        :param path:
        :param port:
        :param boto_debug:
        :raise:
        """
        as_region = RegionInfo()
        if region:
            self.debug("Check region: " + str(region))
            try:
                if not endpoint:
                    as_region.endpoint = ASRegionData[region]
                else:
                    as_region.endpoint = endpoint
            except KeyError:
                raise Exception('Unknown region: %s' % region)
        else:
            as_region.name = 'eucalyptus'
            if not host:
                if endpoint:
                    as_region.endpoint = endpoint
                else:
                    as_region.endpoint = self.get_as_ip()
        connection_args = {'aws_access_key_id': aws_access_key_id,
                           'aws_secret_access_key': aws_secret_access_key,
                           'is_secure': is_secure,
                           'debug': boto_debug,
                           'port': port,
                           'path': path,
                           'region': as_region}

        if re.search('2.6', boto.__version__):
            connection_args['validate_certs'] = False
        try:
            as_connection_args = copy.copy(connection_args)
            as_connection_args['path'] = path
            as_connection_args['region'] = as_region
            self.debug("Attempting to create auto scale connection to " + as_region.endpoint + ':' + str(port) + path)
            self.autoscale = boto.ec2.autoscale.AutoScaleConnection(**as_connection_args)
        except Exception, e:
            self.critical("Was unable to create auto scale connection because of exception: " + str(e))

        #Source ip on local test machine used to reach instances
        self.as_source_ip = None

    def setup_as_resource_trackers(self):
        """
        Setup keys in the test_resources hash in order to track artifacts created
        """
        self.test_resources["keypairs"] = []
        self.test_resources["security-groups"] = []
        self.test_resources["images"] = []
        self.test_resources["launch-configurations"] = []
        self.test_resources["auto-scaling-groups"] = []

    def create_launch_config(self, name, image_id, key_name=None, security_groups=None, user_data=None,
                             instance_type=None, kernel_id=None, ramdisk_id=None, block_device_mappings=None,
                             instance_monitoring=False, instance_profile_name=None):
        """
        Creates a new launch configuration with specified attributes.

        :param name: Name of the launch configuration to create. (Required)
        :param image_id: Unique ID of the Amazon Machine Image (AMI) assigned during registration. (Required)
        :param key_name: The name of the EC2 key pair.
        :param security_groups: Names of the security groups with which to associate the EC2 instances.
        """
        lc = LaunchConfiguration(name=name,
                                 image_id=image_id,
                                 key_name=key_name,
                                 security_groups=security_groups,
                                 user_data=user_data,
                                 instance_type=instance_type,
                                 kernel_id=kernel_id,
                                 ramdisk_id=ramdisk_id,
                                 block_device_mappings=block_device_mappings,
                                 instance_monitoring=instance_monitoring,
                                 instance_profile_name=instance_profile_name)
        self.debug("Creating launch config: " + name)
        self.autoscale.create_launch_configuration(lc)
        if len(self.describe_launch_config([name])) != 1:
            raise Exception('Launch Config not created')
        launch_config = self.describe_launch_config([name])[0]
        self.test_resources["launch-configurations"].append(launch_config)
        self.debug('SUCCESS: Created Launch Config: ' +
                   self.describe_launch_config([name])[0].name)

    def describe_launch_config(self, names=None):
        """
        return a list of launch configs

        :param names: list of names to query (optional) otherwise return all launch configs
        :return:
        """
        return self.autoscale.get_all_launch_configurations(names=names)

    def delete_launch_config(self, launch_config_name):
        self.debug("Deleting launch config: " + launch_config_name)
        self.autoscale.delete_launch_configuration(launch_config_name)
        if len(self.describe_launch_config([launch_config_name])) != 0:
            raise Exception('Launch Config not deleted')
        self.debug('SUCCESS: Deleted Launch Config: ' + launch_config_name)

    def create_as_group(self, group_name, launch_config, availability_zones, min_size, max_size, load_balancers=None,
                        desired_capacity=None, termination_policies=None, default_cooldown=None, health_check_type=None,
                        health_check_period=None, tags=None):
        """
        Create auto scaling group.

        :param group_name: Name of autoscaling group (required).
        :param load_balancers: List of load balancers.
        :param availability_zones: List of availability zones (required).
        :param launch_config: Name of launch configuration (required).
        :param min_size:  Minimum size of group (required).
        :param max_size: Maximum size of group (required).
        """
        self.debug("Creating Auto Scaling group: " + group_name)
        as_group = AutoScalingGroup(connection=self.autoscale,
                                    group_name=group_name,
                                    load_balancers=load_balancers,
                                    availability_zones=availability_zones,
                                    launch_config=launch_config,
                                    min_size=min_size,
                                    max_size=max_size,
                                    desired_capacity=desired_capacity,
                                    default_cooldown=default_cooldown,
                                    health_check_type=health_check_type,
                                    health_check_period=health_check_period,
                                    tags=tags,
                                    termination_policies=termination_policies)
        self.autoscale.create_auto_scaling_group(as_group)

        as_group = self.describe_as_group(group_name)
        self.test_resources["auto-scaling-groups"].append(as_group)
        self.debug("SUCCESS: Created Auto Scaling Group: " + as_group.name)
        return as_group

    def describe_as_group(self, name=None):
        """
        Returns a full description of each Auto Scaling group in the given
        list. This includes all Amazon EC2 instances that are members of the
        group. If a list of names is not provided, the service returns the full
        details of all Auto Scaling groups.
        :param name:
        :return:
        """
        groups = self.autoscale.get_all_groups(names=[name])
        if len(groups) > 1:
            raise Exception("More than one group with name: " + name)
        if len(groups) == 0:
            raise Exception("No group found with name: " + name)
        return groups[0]

    def delete_as_group(self, name=None, force=None):
        self.debug("Deleting Auto Scaling Group: " + name)
        self.debug("Forcing: " + str(force))
        self.autoscale.delete_auto_scaling_group(name=name, force_delete=force)
        try:
            self.describe_as_group([name])
            raise Exception('Auto Scaling Group not deleted')
        except:
            self.debug('SUCCESS: Deleted Auto Scaling Group: ' + name)
        return

    def create_as_policy(self, name, adjustment_type, scaling_adjustment, as_name, cooldown=None):
        """
        Create an auto scaling policy

        :param name:
        :param adjustment_type: (ChangeInCapacity, ExactCapacity, PercentChangeInCapacity)
        :param scaling_adjustment:
        :param as_name:
        :param cooldown: (if something gets scaled, the wait in seconds before trying again.)
        """
        scaling_policy = ScalingPolicy(name=name,
                                       adjustment_type=adjustment_type,
                                       as_name=as_name,
                                       scaling_adjustment=scaling_adjustment,
                                       cooldown=cooldown)
        self.debug("Creating Auto Scaling Policy: " + name)
        self.autoscale.create_scaling_policy(scaling_policy)

    def describe_as_policies(self, as_group=None, policy_names=None):
        """
        If no group name or list of policy names are provided, all
        available policies are returned.

        :param as_group:
        :param policy_names:
        """
        self.autoscale.get_all_policies(as_group=as_group, policy_names=policy_names)

    def execute_as_policy(self, policy_name=None, as_group=None, honor_cooldown=None):
        self.debug("Executing Auto Scaling Policy: " + policy_name)
        self.autoscale.execute_policy(policy_name=policy_name, as_group=as_group, honor_cooldown=honor_cooldown)

    def delete_as_policy(self, policy_name=None, autoscale_group=None):
        self.debug("Deleting Policy: " + policy_name + " from group: " + autoscale_group)
        self.autoscale.delete_policy(policy_name=policy_name, autoscale_group=autoscale_group)

    def delete_autoscaling_groups(self, auto_scaling_groups):
            for asg in auto_scaling_groups:
                self.debug("Found Auto Scaling Group: " + asg.name)
                self.wait_for_result(self.gracefully_delete_auto_scaling_group, True, asg=asg)
                self.test_resources['auto-scaling-groups'].remove(asg)


    def delete_all_autoscaling_groups(self):
        """
        This will attempt to delete all launch configs and all auto scaling groups
        """
        ### clear all ASGs
        for asg in self.describe_as_group():
            self.debug("Found Auto Scaling Group: " + asg.name)
            self.delete_as_group(name=asg.name, force=True)
        if len(self.describe_as_group(asg.name)) != 0:
            self.debug("Some AS groups remain")
            for asg in self.describe_as_group():
                self.debug("Found Auto Scaling Group: " + asg.name)

    def delete_launch_configs(self, launch_configs):
        for lc in launch_configs:
            self.debug("Found Launch Config:" + lc.name)
            self.delete_launch_config(lc.name)
            self.test_resources['launch-configurations'].remove(lc)


    def delete_all_launch_configs(self):
        ### clear all LCs
        """
        Attempt to remove all launch configs
        """
        for lc in self.describe_launch_config():
            self.debug("Found Launch Config:" + lc.name)
            self.delete_launch_config(lc.name)
        if len(self.describe_launch_config()) != 0:
            self.debug("Some Launch Configs Remain")
            for lc in self.describe_launch_config():
                self.debug("Found Launch Config:" + lc.name)

    def get_as_ip(self):
        """Parse the eucarc for the AWS_AUTO_SCALING_URL"""
        as_url = self.parse_eucarc("AWS_AUTO_SCALING_URL")
        return as_url.split("/")[2].split(":")[0]

    def get_as_path(self):
        """Parse the eucarc for the AWS_AUTO_SCALING_URL"""
        as_url = self.parse_eucarc("AWS_AUTO_SCALING_URL")
        as_path = "/".join(as_url.split("/")[3:])
        return as_path

    def get_last_instance_id(self):
        reservations = self.ec2.get_all_instances()
        instances = [i for r in reservations for i in r.instances]
        newest_time = None
        newest_id = None
        for i in instances:
            if not newest_time or i.launch_time > newest_time:
                newest_time = i.launch_time
                newest_id = i.id
        return newest_id

    def create_group_tag(self, key, value, resource_id, propagate_at_launch=None):
        # self.debug("Number of tags: " + str(len(self.tester.autoscale.get_all_tags())))
        # self.debug("Autoscale group info: " + str(self.tester.autoscale.get_all_groups(names=[auto_scaling_group_name])[0].tags))

        tag = Tag(key=key, value=value, propagate_at_launch=propagate_at_launch, resource_id=resource_id)
        self.autoscale.create_or_update_tags([tag])
        if len(self.autoscale.get_all_tags(filters=key)) != 1:
            self.debug("Number of tags: " + str(len(self.autoscale.get_all_tags(filters=key))))
            raise Exception('Tag not created')
        self.debug("created or updated tag: " + str(self.autoscale.get_all_tags(filters=key)[0]))

    def delete_all_group_tags(self):
        all_tags = self.autoscale.get_all_tags()
        self.autoscale.delete_tags(all_tags)
        self.debug("Number of tags: " + str(len(self.autoscale.get_all_tags())))

    def delete_all_policies(self):
        policies = self.autoscale.get_all_policies()
        for policy in policies:
            self.delete_as_policy(policy_name=policy.name, autoscale_group=policy.as_name)
        if len(self.autoscale.get_all_policies()) != 0:
            raise Exception('Not all auto scaling policies deleted')
        self.debug("SUCCESS: Deleted all auto scaling policies")

    def update_as_group(self, group_name, launch_config, min_size, max_size, availability_zones=None,
                        desired_capacity=None, termination_policies=None, default_cooldown=None, health_check_type=None,
                        health_check_period=None):
        """

        :param group_name: REQUIRED
        :param launch_config: REQUIRED
        :param min_size: REQUIRED
        :param max_size: REQUIRED
        :param availability_zones:
        :param desired_capacity:
        :param termination_policies:
        :param default_cooldown:
        :param health_check_type:
        :param health_check_period:
        """
        self.debug("Updating ASG: " + group_name)
        return AutoScalingGroup(connection=self.autoscale,
                         name=group_name,
                         launch_config=launch_config,
                         min_size=min_size,
                         max_size=max_size,
                         availability_zones=availability_zones,
                         desired_capacity=desired_capacity,
                         default_cooldown=default_cooldown,
                         health_check_type=health_check_type,
                         health_check_period=health_check_period,
                         termination_policies=termination_policies).update()

    def wait_for_instances(self, group_name, number=1):
        asg = self.describe_as_group(group_name)
        instances = asg.instances
        if not instances:
            self.debug("No instances in scaling group: " + group_name)
            return False
        if len(asg.instances) != number:
            self.debug("Instances not yet allocated")
            return False
        for instance in instances:
            assert isinstance(instance, Instance)
            instance = self.get_instances(idstring=instance.instance_id)[0]
            if instance.state != "running":
                self.debug("Instance: " + str(instance) + " still in " + instance.state + " state")
                return False
            else:
                self.debug("Instance: " + str(instance) + " now running")
        return True

    def gracefully_delete_auto_scaling_group(self, asg=None):
            assert isinstance(asg, AutoScalingGroup)
            try:
                self.delete_as_group(name=asg.name, force=True)

            except BotoServerError, e:
                if e.status == 400 and e.reason == "ScalingActivityInProgress":
                    return False
            return True

    def create_as_webservers(self, name, keypair, group, zone, user_data=None, count=2, image=None, load_balancer=None):
        lc_name = "lc-"+name
        asg_name = "asg-"+name
        self.create_launch_config(name=lc_name,
                                  image_id=image,
                                  instance_type="t1.micro",
                                  key_name=keypair,
                                  security_groups=[group],
                                  user_data=open(user_data).read(),
                                  instance_monitoring=True)
        self.create_as_group(group_name=asg_name,
                             launch_config=lc_name,
                             availability_zones=[zone],
                             min_size=0,
                             max_size=5,
                             desired_capacity=count,
                             load_balancers=[load_balancer])
        return
