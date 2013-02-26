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
import com.amazonaws.services.autoscaling.model.ResourceInUseException;
import com.amazonaws.services.autoscaling.model.TerminateInstanceInAutoScalingGroupRequest;
import com.amazonaws.services.ec2.AmazonEC2;
import com.amazonaws.services.ec2.model.TerminateInstancesRequest;

/**
 * This application tests manually terminating instances with auto scaling.
 * 
 * This is verification for the story:
 * 
 * https://eucalyptus.atlassian.net/browse/EUCA-4899
 */
public class TestAutoScalingTerminateInstances {
	
	@SuppressWarnings("unchecked")
	@Test
	public void AutoScalingTerminateInstancesTest() throws Exception {
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
			final String configName = namePrefix + "TerminateTest";
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
			final String groupName = namePrefix + "TerminateTest";
			print("Creating auto scaling group: " + groupName);
			as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
					.withAutoScalingGroupName(groupName)
					.withLaunchConfigurationName(configName)
					.withDesiredCapacity(2).withMinSize(0).withMaxSize(2)
					.withHealthCheckType("EC2")
					.withAvailabilityZones(availabilityZone)
					.withTerminationPolicies("OldestInstance"));
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

			// Wait for instances to launch
			print("Waiting for instances to launch");
			final long timeout = TimeUnit.MINUTES.toMillis(2);
			List<String> instanceIds = (List<String>) waitForInstances(ec2, timeout, 2, groupName, true);

			// Terminate instance with capacity decrement
			final String instanceToTerminate = instanceIds.get(1);
			as.terminateInstanceInAutoScalingGroup(new TerminateInstanceInAutoScalingGroupRequest()
					.withInstanceId(instanceToTerminate)
					.withShouldDecrementDesiredCapacity(true));
			print("Waiting for instance to terminate");
			List<String> remainingInstances = (List<String>) waitForInstances(ec2, timeout, 1, groupName, true);
			assertThat(!remainingInstances.contains(instanceToTerminate),
					"Expected instance terminated");
			assertThat(remainingInstances.contains(instanceIds.get(0)),
					"Expected instance to remain: " + instanceIds.get(0));

			// Terminate instance without capacity decrement, ensure replaced
			as.terminateInstanceInAutoScalingGroup(new TerminateInstanceInAutoScalingGroupRequest()
					.withInstanceId(remainingInstances.get(0))
					.withShouldDecrementDesiredCapacity(false));
			print("Waiting for instance to be replaced");
			Thread.sleep(10000); // We sleep to ensure the first instance has a
									// chance to start terminating ...
			List<String> remainingInstances2 = (List<String>) waitForInstances(ec2, timeout, 1, groupName, true);
			assertThat(
					!remainingInstances2.contains(remainingInstances.get(0)),
					"Instance replaced");

			// Delete group without force, should fail due to existing instance
			print("Deleting group without force, error expected");
			try {
				as.deleteAutoScalingGroup(new DeleteAutoScalingGroupRequest()
						.withAutoScalingGroupName(groupName).withForceDelete(
								false));
				assertThat(false, "Expected resource in use error");
			} catch (final ResourceInUseException e) {
				// expected
			}

			// Delete group with force to remove remaining instances
			print("Deleting group with force, instances should be terminated.");
			as.deleteAutoScalingGroup(new DeleteAutoScalingGroupRequest()
					.withAutoScalingGroupName(groupName).withForceDelete(true));
			waitForInstances(ec2, timeout, 0, groupName, true);

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
