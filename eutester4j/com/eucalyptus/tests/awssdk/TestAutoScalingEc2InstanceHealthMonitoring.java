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

import com.amazonaws.services.ec2.model.TerminateInstancesRequest;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

/**
 * This application tests EC2 monitoring of instance health for auto scaling.
 * 
 * This is verification for the story:
 * 
 * https://eucalyptus.atlassian.net/browse/EUCA-4902
 */

public class TestAutoScalingEc2InstanceHealthMonitoring {
	@SuppressWarnings("unchecked")
	@Test
	public void AutoScalingEc2InstanceHealthMonitoringTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();

		// End discovery, start test
		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			// Create launch configuration
            final String launchConfig = NAME_PREFIX
					+ "Ec2InstanceHealthMonitoringTest";
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
            final String groupName = NAME_PREFIX	+ "Ec2InstanceHealthMonitoringTest";
            Integer minSize = 1;
            Integer maxSize = 1;
            Integer desiredCapacity = 1;
            Integer cooldown = 90;
            String healthCheckType = "EC2";
            String terminationPolicy = "OldestInstance";
			print("Creating auto scaling group: " + groupName);
            createAutoScalingGroup(groupName,launchConfig,minSize,maxSize,desiredCapacity,AVAILABILITY_ZONE,cooldown,
                    null,healthCheckType,null,null,terminationPolicy);
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

			// Wait for instances to launch
			print("Waiting for instance to launch");
			final long timeout = TimeUnit.MINUTES.toMillis(10);
			final String instanceId = (String) waitForInstances(timeout, 1, groupName, true).get(0);

			// Verify initial health status
			print("Verifying initial instance status");
			verifyInstanceHealthStatus(instanceId, "Healthy");

			// Terminate via EC2
			print("Terminating instance via EC2 : " + instanceId);
			ec2.terminateInstances(new TerminateInstancesRequest()
					.withInstanceIds(instanceId));

			// Verify initial health status
			print("Waiting for auto scaling instance health to change : "
					+ instanceId);
			waitForHealthStatus(instanceId, "Unhealthy");

			// Delay to allow for health status to be acted on
			print("Waiting for unhealthy instance replacement : " + instanceId);
			Thread.sleep(TimeUnit.SECONDS.toMillis(30));

			// Wait for replacement instance
			print("Waiting for replacement instance to launch");
			final String replacementInstanceId = (String) waitForInstances(timeout, 1, groupName, true).get(0);
			assertThat(!replacementInstanceId.equals(instanceId),
					"Instance not replaced");

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
