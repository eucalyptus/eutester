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
import com.amazonaws.services.autoscaling.model.CreateAutoScalingGroupRequest;
import com.amazonaws.services.autoscaling.model.CreateLaunchConfigurationRequest;
import com.amazonaws.services.autoscaling.model.DeleteAutoScalingGroupRequest;
import com.amazonaws.services.autoscaling.model.DeleteLaunchConfigurationRequest;
import com.amazonaws.services.autoscaling.model.ExecutePolicyRequest;
import com.amazonaws.services.autoscaling.model.PutScalingPolicyRequest;
import com.amazonaws.services.autoscaling.model.SetDesiredCapacityRequest;
import com.amazonaws.services.ec2.AmazonEC2;
import com.amazonaws.services.ec2.model.TerminateInstancesRequest;

/**
 * This application tests cooldown for changing group desired capacity
 * 
 * This is verification for the story:
 * 
 * https://eucalyptus.atlassian.net/browse/EUCA-4989
 */
public class TestAutoScalingCooldown {
	@SuppressWarnings("unchecked")
	@Test
	public void AutoScalingCooldownTest() throws Exception {
		getCloudInfo();
		final AmazonAutoScaling as = getAutoScalingClient(ACCESS_KEY, SECRET_KEY, AS_ENDPOINT);
		final AmazonEC2 ec2 = getEc2Client(ACCESS_KEY, SECRET_KEY, EC2_ENDPOINT);
		final String imageId = findImage(ec2);
		final String availabilityZone = findAvalablityZone(ec2);
		final String namePrefix = eucaUUID() + "-";
		print("Using resource prefix for test: " + namePrefix);

		// End discovery, start test		
		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			// Create launch configuration
			final String configName = namePrefix + "DescribeGroupsInstances";
			print("Creating launch configuration: " + configName);
			as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
					.withLaunchConfigurationName(configName)
					.withImageId(imageId).withInstanceType(INSTANCE_TYPE));
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting launch configuration: " + configName);
					as.deleteLaunchConfiguration(new DeleteLaunchConfigurationRequest()
							.withLaunchConfigurationName(configName));
				}
			});

			// Create scaling group
			final String groupName = namePrefix + "DescribeGroupsInstances";
			print("Creating auto scaling group: " + groupName);
			as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
					.withAutoScalingGroupName(groupName)
					.withLaunchConfigurationName(configName).withMinSize(0)
					.withMaxSize(2).withDefaultCooldown(10)
					.withAvailabilityZones(availabilityZone));
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting group: " + groupName);
					as.deleteAutoScalingGroup(new DeleteAutoScalingGroupRequest()
							.withAutoScalingGroupName(groupName)
							.withForceDelete(true));
				}
			});
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					final List<String> instanceIds = (List<String>) getInstancesForGroup(ec2, groupName, null, true);
					print("Terminating instances: " + instanceIds);
					ec2.terminateInstances(new TerminateInstancesRequest()
							.withInstanceIds(instanceIds));
				}
			});

			//
			print("Waiting for initial cooldown to expire");
			Thread.sleep(10000);

			// Set desired capacity
			print("Setting desired capacity to 1");
			as.setDesiredCapacity(new SetDesiredCapacityRequest()
					.withAutoScalingGroupName(groupName)
					.withHonorCooldown(true).withDesiredCapacity(1));

			try {
				print("Setting desired capacity to 0 (will fail)");
				as.setDesiredCapacity(new SetDesiredCapacityRequest()
						.withAutoScalingGroupName(groupName)
						.withHonorCooldown(true).withDesiredCapacity(0));
				assertThat(false,
						"Set desired capacity should fail due to cooldown");
			} catch (Exception e) {
				// expected failure
			}

			print("Setting desired capacity to 0");
			as.setDesiredCapacity(new SetDesiredCapacityRequest()
					.withAutoScalingGroupName(groupName)
					.withHonorCooldown(false).withDesiredCapacity(0));

			Thread.sleep(10000);
			print("Setting desired capacity to 1 after cooldown expiry");
			as.setDesiredCapacity(new SetDesiredCapacityRequest()
					.withAutoScalingGroupName(groupName)
					.withHonorCooldown(true).withDesiredCapacity(1));
			as.setDesiredCapacity(new SetDesiredCapacityRequest()
					.withAutoScalingGroupName(groupName)
					.withHonorCooldown(false).withDesiredCapacity(0));

			// Create / execute policy
			print("Creating scaling policy");
			final String policyName = namePrefix + "DescribeGroupsInstances";
			as.putScalingPolicy(new PutScalingPolicyRequest()
					.withAutoScalingGroupName(groupName)
					.withPolicyName(policyName)
					.withAdjustmentType("ChangeInCapacity").withCooldown(5)
					.withScalingAdjustment(1));

			print("Executing policy");
			as.executePolicy(new ExecutePolicyRequest()
					.withAutoScalingGroupName(groupName)
					.withPolicyName(policyName).withHonorCooldown(false));
			try {
				print("Executing policy (will fail)");
				as.executePolicy(new ExecutePolicyRequest()
						.withAutoScalingGroupName(groupName)
						.withPolicyName(policyName).withHonorCooldown(true));
				assertThat(false,
						"Set desired capacity should fail due to cooldown");
			} catch (Exception e) {
				// expected failure
			}

			Thread.sleep(5000);
			print("Executing policy after cooldown expiry");
			as.executePolicy(new ExecutePolicyRequest()
					.withAutoScalingGroupName(groupName)
					.withPolicyName(policyName).withHonorCooldown(true));

			print("Waiting for scaling to complete");
			waitForInstances(ec2, TimeUnit.MINUTES.toMillis(2), 2, groupName,true);

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
}
