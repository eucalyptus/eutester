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

import com.amazonaws.services.autoscaling.AmazonAutoScaling;
import com.amazonaws.services.autoscaling.model.*;
import com.amazonaws.services.ec2.AmazonEC2;
import com.amazonaws.services.ec2.model.TerminateInstancesRequest;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

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
		logger.info("Using resource prefix for test: " + namePrefix);

		// End discovery, start test		
		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			// Create launch configuration
			final String configName = namePrefix + "DescribeGroupsInstances";
			logger.info("Creating launch configuration: " + configName);
			as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
					.withLaunchConfigurationName(configName)
					.withImageId(imageId).withInstanceType(INSTANCE_TYPE));
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					logger.info("Deleting launch configuration: " + configName);
					as.deleteLaunchConfiguration(new DeleteLaunchConfigurationRequest()
							.withLaunchConfigurationName(configName));
				}
			});

			// Create scaling group
			final String groupName = namePrefix + "DescribeGroupsInstances";
			logger.info("Creating auto scaling group: " + groupName);
			as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
					.withAutoScalingGroupName(groupName)
					.withLaunchConfigurationName(configName).withMinSize(0)
					.withMaxSize(2).withDefaultCooldown(10)
					.withAvailabilityZones(availabilityZone));
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					logger.info("Deleting group: " + groupName);
					as.deleteAutoScalingGroup(new DeleteAutoScalingGroupRequest()
							.withAutoScalingGroupName(groupName)
							.withForceDelete(true));
				}
			});
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					final List<String> instanceIds = (List<String>) getInstancesForGroup(ec2, groupName, null, true);
					logger.info("Terminating instances: " + instanceIds);
					ec2.terminateInstances(new TerminateInstancesRequest()
							.withInstanceIds(instanceIds));
				}
			});

			//
			logger.info("Waiting for initial cooldown to expire");
			Thread.sleep(10000);

			// Set desired capacity
			logger.info("Setting desired capacity to 1");
			as.setDesiredCapacity(new SetDesiredCapacityRequest()
					.withAutoScalingGroupName(groupName)
					.withHonorCooldown(true).withDesiredCapacity(1));

			try {
				logger.info("Setting desired capacity to 0 (will fail)");
				as.setDesiredCapacity(new SetDesiredCapacityRequest()
						.withAutoScalingGroupName(groupName)
						.withHonorCooldown(true).withDesiredCapacity(0));
				assertThat(false,
						"Set desired capacity should fail due to cooldown");
			} catch (Exception e) {
				// expected failure
			}

			logger.info("Setting desired capacity to 0");
			as.setDesiredCapacity(new SetDesiredCapacityRequest()
					.withAutoScalingGroupName(groupName)
					.withHonorCooldown(false).withDesiredCapacity(0));

			Thread.sleep(10000);
			logger.info("Setting desired capacity to 1 after cooldown expiry");
			as.setDesiredCapacity(new SetDesiredCapacityRequest()
					.withAutoScalingGroupName(groupName)
					.withHonorCooldown(true).withDesiredCapacity(1));
			as.setDesiredCapacity(new SetDesiredCapacityRequest()
					.withAutoScalingGroupName(groupName)
					.withHonorCooldown(false).withDesiredCapacity(0));

			// Create / execute policy
			logger.info("Creating scaling policy");
			final String policyName = namePrefix + "DescribeGroupsInstances";
			as.putScalingPolicy(new PutScalingPolicyRequest()
					.withAutoScalingGroupName(groupName)
					.withPolicyName(policyName)
					.withAdjustmentType("ChangeInCapacity").withCooldown(5)
					.withScalingAdjustment(1));

			logger.info("Executing policy");
			as.executePolicy(new ExecutePolicyRequest()
					.withAutoScalingGroupName(groupName)
					.withPolicyName(policyName).withHonorCooldown(false));
			try {
				logger.info("Executing policy (will fail)");
				as.executePolicy(new ExecutePolicyRequest()
						.withAutoScalingGroupName(groupName)
						.withPolicyName(policyName).withHonorCooldown(true));
				assertThat(false,
						"Set desired capacity should fail due to cooldown");
			} catch (Exception e) {
				// expected failure
			}

			Thread.sleep(5000);
			logger.info("Executing policy after cooldown expiry");
			as.executePolicy(new ExecutePolicyRequest()
					.withAutoScalingGroupName(groupName)
					.withPolicyName(policyName).withHonorCooldown(true));

			logger.info("Waiting for scaling to complete");
			waitForInstances(ec2, TimeUnit.MINUTES.toMillis(2), 2, groupName,true);

			logger.info("Test complete");
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
