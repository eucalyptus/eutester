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

import com.amazonaws.services.autoscaling.model.*;
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
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();

		// End discovery, start test		
		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			// Create launch configuration
            final String launchConfig = NAME_PREFIX + "DescribeGroupsInstances";
			print("Creating launch configuration: " + launchConfig);
            createLaunchConfig(launchConfig,IMAGE_ID,INSTANCE_TYPE,null,null,null,null,null,null,null,null);
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting launch configuration: " + launchConfig);
                    deleteLaunchConfig(launchConfig);
				}
			});

			// Create scaling group
            final String groupName = NAME_PREFIX + "DescribeGroupsInstances";
			print("Creating auto scaling group: " + groupName);
            Integer minSize = 0;
            Integer maxSize = 2;
            Integer cooldown = 10;
            createAutoScalingGroup(groupName,launchConfig,minSize,maxSize,null, AVAILABILITY_ZONE, cooldown, null, null, null, null,null);
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting group: " + groupName);
                    deleteAutoScalingGroup(groupName,true);
				}
			});
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					final List<String> instanceIds = (List<String>) getInstancesForGroup(groupName, null, true);
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

			Thread.sleep(15000);
			print("Setting desired capacity to 1 after cooldown expiry");
			as.setDesiredCapacity(new SetDesiredCapacityRequest()
					.withAutoScalingGroupName(groupName)
					.withHonorCooldown(true).withDesiredCapacity(1));
			as.setDesiredCapacity(new SetDesiredCapacityRequest()
					.withAutoScalingGroupName(groupName)
					.withHonorCooldown(false).withDesiredCapacity(0));

			// Create / execute policy
			print("Creating scaling policy");
			final String policyName = NAME_PREFIX + "DescribeGroupsInstances";
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

			Thread.sleep(7000);
			print("Executing policy after cooldown expiry");
			as.executePolicy(new ExecutePolicyRequest()
					.withAutoScalingGroupName(groupName)
					.withPolicyName(policyName).withHonorCooldown(true));

			print("Waiting for scaling to complete");
			waitForInstances(TimeUnit.MINUTES.toMillis(15), 2, groupName,true);

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
