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
import com.amazonaws.services.autoscaling.model.SetDesiredCapacityRequest;
import com.amazonaws.services.ec2.AmazonEC2;
import com.amazonaws.services.ec2.model.TerminateInstancesRequest;

//import sun.rmi.runtime.NewThreadAction;

/**
 * This application tests launching and terminating instances with auto scaling.
 * 
 * This is verification for the story:
 * 
 * https://eucalyptus.atlassian.net/browse/EUCA-4893
 */
public class TestAutoScalingLaunchAndTerminate {
	@SuppressWarnings("unchecked")
	@Test
	public void AutoScalingLaunchAndTerminateTest() throws Exception {
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
			final String configName = namePrefix + "LaunchTest";
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
			final String groupName = namePrefix + "LaunchTest";
			logger.info("Creating auto scaling group: " + groupName);
			as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
					.withAutoScalingGroupName(groupName)
					.withLaunchConfigurationName(configName)
					.withDesiredCapacity(0).withMinSize(0).withMaxSize(2)
					.withHealthCheckType("EC2")
					.withAvailabilityZones(availabilityZone)
					.withTerminationPolicies("OldestInstance"));
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

			// Update group desired capacity and wait for instances to launch
			logger.info("Setting desired capacity to 2 for group: " + groupName);
			as.setDesiredCapacity(new SetDesiredCapacityRequest()
					.withAutoScalingGroupName(groupName).withDesiredCapacity(2));

			// Wait for instances to launch
			logger.info("Waiting for instances to launch");
			final long startTime = System.currentTimeMillis();
			final long launchTimeout = TimeUnit.MINUTES.toMillis(2);
			boolean launched = false;
			while (!launched
					&& (System.currentTimeMillis() - startTime) < launchTimeout) {
				Thread.sleep(5000);
				final List<String> instanceIds = (List<String>) getInstancesForGroup(ec2, groupName, "running", true);
				launched = instanceIds.size() == 2;
			}
			assertThat(launched,
					"Instances were not launched within the expected timeout");
			logger.info("Instances launched in "
					+ (System.currentTimeMillis() - startTime) + "ms");

			// Update group desired capacity and wait for instances to terminate
			logger.info("Setting desired capacity to 0 for group: " + groupName);
			as.setDesiredCapacity(new SetDesiredCapacityRequest()
					.withAutoScalingGroupName(groupName).withDesiredCapacity(0));

			// Wait for instances to launch
			logger.info("Waiting for instances to terminate");
			final long terminateStartTime = System.currentTimeMillis();
			final long terminateTimeout = TimeUnit.MINUTES.toMillis(2);
			boolean terminated = false;
			while (!terminated
					&& (System.currentTimeMillis() - terminateStartTime) < terminateTimeout) {
				Thread.sleep(5000);
				final List<String> instanceIds = (List<String>) getInstancesForGroup(ec2, groupName, null, true);
				terminated = instanceIds.size() == 0;
			}
			assertThat(terminated,
					"Instances were not terminated within the expected timeout");
			logger.info("Instances terminated in "
					+ (System.currentTimeMillis() - terminateStartTime) + "ms");
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
