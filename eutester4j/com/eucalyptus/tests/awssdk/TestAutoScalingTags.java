/*************************************************************************
 * Copyright 2009-2013 Eucalyptus Systems, Inc.
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see http://www.gnu.org/licenses/.
 *
 * Please contact Eucalyptus Systems, Inc., 6755 Hollister Ave., Goleta
 * CA 93117, USA or visit http://www.eucalyptus.com/licenses/ if you need
 * additional information or have any questions.
 ************************************************************************/
package com.eucalyptus.tests.awssdk;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;
import com.amazonaws.services.autoscaling.AmazonAutoScaling;
import com.amazonaws.services.autoscaling.model.AutoScalingGroup;
import com.amazonaws.services.autoscaling.model.CreateAutoScalingGroupRequest;
import com.amazonaws.services.autoscaling.model.CreateOrUpdateTagsRequest;
import com.amazonaws.services.autoscaling.model.DeleteTagsRequest;
import com.amazonaws.services.autoscaling.model.DescribeAutoScalingGroupsRequest;
import com.amazonaws.services.autoscaling.model.DescribeAutoScalingGroupsResult;
import com.amazonaws.services.autoscaling.model.DescribeTagsResult;
import com.amazonaws.services.autoscaling.model.SetDesiredCapacityRequest;
import com.amazonaws.services.autoscaling.model.Tag;
import com.amazonaws.services.autoscaling.model.TagDescription;
import com.amazonaws.services.ec2.AmazonEC2;
import com.amazonaws.services.ec2.model.DescribeTagsRequest;
import com.amazonaws.services.ec2.model.Filter;

/**
 * This application tests tags for auto scaling.
 * 
 * This is verification for the story:
 * 
 * https://eucalyptus.atlassian.net/browse/EUCA-4758
 */
public class TestAutoScalingTags {

	@Test
	public void AutoScalingTagsTest() throws Exception {
		getCloudInfo();
		final AmazonAutoScaling as = getAutoScalingClient(ACCESS_KEY,
				SECRET_KEY, AS_ENDPOINT);
		final AmazonEC2 ec2 = getEc2Client(ACCESS_KEY, SECRET_KEY, EC2_ENDPOINT);
		final String imageId = findImage(ec2);
		final String availabilityZone = findAvalablityZone(ec2);
		final String namePrefix = eucaUUID() + "-";
		print("Using resource prefix for test: " + namePrefix);

		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			// Register cleanup for launch config
			final String configName = namePrefix + "TagTest";
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting launch configuration: " + configName);
					deleteLaunchConfig(as, configName);
				}
			});

			// Create launch configuration
			print("Creating launch configuration: " + configName);
			createLaunchConfig(as, configName, imageId, INSTANCE_TYPE, null, null);

			// Register cleanup for auto scaling group
			final String groupName = namePrefix + "TagTest";
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting group: " + groupName);
					deleteAutoScalingGroup(as, groupName);
				}
			});

			// Create scaling group
			print("Creating auto scaling group with tags: " + groupName);
			as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
					.withAutoScalingGroupName(groupName)
					.withLaunchConfigurationName(configName)
					.withMinSize(0)
					.withMaxSize(1)
					.withAvailabilityZones(availabilityZone)
					.withTags(
							new Tag().withKey("tag1").withValue("propagate")
									.withPropagateAtLaunch(Boolean.TRUE),
							new Tag().withKey("tag2")
									.withValue("don't propagate")
									.withPropagateAtLaunch(Boolean.FALSE)));

			// Verify tags
			{
				print("Verifying tags when describing group");
				final DescribeAutoScalingGroupsResult describeGroupsResult = as
						.describeAutoScalingGroups(new DescribeAutoScalingGroupsRequest()
								.withAutoScalingGroupNames(groupName));
				assertThat(describeGroupsResult.getAutoScalingGroups() != null,
						"Expected groups in result");
				assertThat(
						describeGroupsResult.getAutoScalingGroups().size() == 1,
						"Expected one group in result");
				final AutoScalingGroup group = describeGroupsResult
						.getAutoScalingGroups().get(0);
				assertThat(group != null, "Expected group");
				assertThat(
						groupName.equals(group.getAutoScalingGroupName()),
						"Unexpected group name: "
								+ group.getAutoScalingGroupName());
				assertThat(group.getTags() != null, "Expected tags");
				print("Found tags: " + group.getTags());
				assertThat(group.getTags().size() == 2,
						"Expected two tags but found " + group.getTags().size());
				assertTag(group.getTags().get(0), "tag1", "propagate", true);
				assertTag(group.getTags().get(1), "tag2", "don't propagate",
						false);

				print("Verifying tags when describing tags");
				final DescribeTagsResult describeTagsResult = as.describeTags();
				assertThat(describeTagsResult.getTags() != null,
						"Expected tags");
				print("Found tags: " + describeTagsResult.getTags());
				assertThat(describeTagsResult.getTags().size() == 2,
						"Expected two tags but found "
								+ describeTagsResult.getTags().size());
				int tag1Index = "tag1".equals(describeTagsResult.getTags()
						.get(0).getKey()) ? 0 : 1;
				assertTag(describeTagsResult.getTags().get(tag1Index), "tag1",
						"propagate", true);
				assertTag(describeTagsResult.getTags().get(++tag1Index % 2),
						"tag2", "don't propagate", false);
			}

			// Delete tags
			as.deleteTags(new DeleteTagsRequest().withTags(
					new Tag().withResourceType("auto-scaling-group")
							.withResourceId(groupName).withKey("tag1")
							.withValue("propagate")
							.withPropagateAtLaunch(Boolean.TRUE), new Tag()
							.withResourceType("auto-scaling-group")
							.withResourceId(groupName).withKey("tag2")
							.withValue("don't propagate")
							.withPropagateAtLaunch(Boolean.FALSE)));

			// Verify deleted
			{
				print("Verifying no tags when describing group");
				final DescribeAutoScalingGroupsResult describeGroupsResult = as
						.describeAutoScalingGroups(new DescribeAutoScalingGroupsRequest()
								.withAutoScalingGroupNames(groupName));
				assertThat(describeGroupsResult.getAutoScalingGroups() != null,
						"Expected groups in result");
				assertThat(
						describeGroupsResult.getAutoScalingGroups().size() == 1,
						"Expected one group in result");
				final AutoScalingGroup group = describeGroupsResult
						.getAutoScalingGroups().get(0);
				assertThat(group != null, "Expected group");
				assertThat(
						groupName.equals(group.getAutoScalingGroupName()),
						"Unexpected group name: "
								+ group.getAutoScalingGroupName());
				assertThat(
						group.getTags() == null || group.getTags().isEmpty(),
						"Expected no tags");

				print("Verifying no tags when describing tags");
				final DescribeTagsResult describeTagsResult = as.describeTags();
				assertThat(describeTagsResult.getTags() == null
						|| describeTagsResult.getTags().isEmpty(),
						"Expected no tags");
			}

			// Create via API
			as.createOrUpdateTags(new CreateOrUpdateTagsRequest().withTags(
					new Tag().withResourceType("auto-scaling-group")
							.withResourceId(groupName).withKey("tag1")
							.withValue("propagate")
							.withPropagateAtLaunch(Boolean.TRUE), new Tag()
							.withResourceType("auto-scaling-group")
							.withResourceId(groupName).withKey("tag2")
							.withValue("don't propagate")
							.withPropagateAtLaunch(Boolean.FALSE)));

			// Verify tags
			{
				print("Verifying tags when describing group");
				final DescribeAutoScalingGroupsResult describeGroupsResult = as
						.describeAutoScalingGroups(new DescribeAutoScalingGroupsRequest()
								.withAutoScalingGroupNames(groupName));
				assertThat(describeGroupsResult.getAutoScalingGroups() != null,
						"Expected groups in result");
				assertThat(
						describeGroupsResult.getAutoScalingGroups().size() == 1,
						"Expected one group in result");
				final AutoScalingGroup group = describeGroupsResult
						.getAutoScalingGroups().get(0);
				assertThat(group != null, "Expected group");
				assertThat(
						groupName.equals(group.getAutoScalingGroupName()),
						"Unexpected group name: "
								+ group.getAutoScalingGroupName());
				assertThat(group.getTags() != null, "Expected tags");
				print("Found tags: " + group.getTags());
				assertThat(group.getTags().size() == 2,
						"Expected two tags but found " + group.getTags().size());
				assertTag(group.getTags().get(0), "tag1", "propagate", true);
				assertTag(group.getTags().get(1), "tag2", "don't propagate",
						false);

				print("Verifying tags when describing tags");
				final DescribeTagsResult describeTagsResult = as.describeTags();
				assertThat(describeTagsResult.getTags() != null,
						"Expected tags");
				print("Found tags: " + describeTagsResult.getTags());
				assertThat(describeTagsResult.getTags().size() == 2,
						"Expected two tags but found " + group.getTags().size());
				assertTag(describeTagsResult.getTags().get(0), "tag1",
						"propagate", true);
				assertTag(describeTagsResult.getTags().get(1), "tag2",
						"don't propagate", false);
			}

			// Launch instance
			print("Launching instance to test tag propagation");
			as.setDesiredCapacity(new SetDesiredCapacityRequest()
					.withAutoScalingGroupName(groupName)
					.withHonorCooldown(false).withDesiredCapacity(1));
			final String instanceId = (String) waitForInstances(ec2, TimeUnit.MINUTES.toMillis(2), 1, groupName, true).get(0);

			// Verify tag on instance
			final com.amazonaws.services.ec2.model.DescribeTagsResult describeTagsResult = ec2
					.describeTags(new DescribeTagsRequest().withFilters(
							new Filter().withName("resource-id").withValues(
									instanceId),
							new Filter().withName("resource-type").withValues(
									"instance"),
							new Filter().withName("key").withValues("tag1"),
							new Filter().withName("value").withValues(
									"propagate")));
			assertThat(describeTagsResult.getTags() != null, "Expected tags");
			assertThat(describeTagsResult.getTags().size() == 1,
					"Expected one tag");

			print("Test complete");
		} finally {
			// Attempt to clean up anything we created
			Collections.reverse(cleanupTasks);
			for (final Runnable cleanupTask : cleanupTasks) {
				try {
					cleanupTask.run();
				} catch (Exception e) {
					e.printStackTrace();
				}
			}
		}
	}

	private void assertTag(final TagDescription tagDescription,
			final String key, final String value, final boolean propagate) {
		assertThat(tagDescription != null, "Null tag");
		assertThat(key.equals(tagDescription.getKey()), "Unexpected tag key: "
				+ tagDescription.getKey());
		assertThat(value.equals(tagDescription.getValue()),
				"Unexpected tag value: " + tagDescription.getValue());
		assertThat(
				propagate == tagDescription.getPropagateAtLaunch(),
				"Unexpected tag propagation: "
						+ tagDescription.getPropagateAtLaunch());
	}

}
