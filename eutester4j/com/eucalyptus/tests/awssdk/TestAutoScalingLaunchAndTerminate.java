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
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();

		// End discovery, start test
		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			// Create launch configuration
            final String launchConfig = NAME_PREFIX + "LaunchTest";
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
            final String groupName = NAME_PREFIX + "LaunchTest";
			print("Creating auto scaling group: " + groupName);
            Integer minSize = 0;
            Integer maxSize = 2;
            Integer desiredCapacity = 0;
            String healthCheckType = "EC2";
            String terminationPolicy = "OldestInstance";
            createAutoScalingGroup(groupName,launchConfig,minSize,maxSize,desiredCapacity,AVAILABILITY_ZONE,null,null,
                    healthCheckType,null,null,terminationPolicy);
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

			// Update group desired capacity and wait for instances to launch
			print("Setting desired capacity to 2 for group: " + groupName);
			as.setDesiredCapacity(new SetDesiredCapacityRequest()
					.withAutoScalingGroupName(groupName).withDesiredCapacity(2));

			// Wait for instances to launch
			print("Waiting for instances to launch");
			final long startTime = System.currentTimeMillis();
			final long launchTimeout = TimeUnit.MINUTES.toMillis(2);
			boolean launched = false;
			while (!launched
					&& (System.currentTimeMillis() - startTime) < launchTimeout) {
				Thread.sleep(5000);
				final List<String> instanceIds = (List<String>) getInstancesForGroup(groupName, "running", true);
				launched = instanceIds.size() == 2;
			}
			assertThat(launched,
					"Instances were not launched within the expected timeout");
			print("Instances launched in "
					+ (System.currentTimeMillis() - startTime) + "ms");

			// Update group desired capacity and wait for instances to terminate
			print("Setting desired capacity to 0 for group: " + groupName);
			as.setDesiredCapacity(new SetDesiredCapacityRequest()
					.withAutoScalingGroupName(groupName).withDesiredCapacity(0));

			// Wait for instances to launch
			print("Waiting for instances to terminate");
			final long terminateStartTime = System.currentTimeMillis();
			final long terminateTimeout = TimeUnit.MINUTES.toMillis(2);
			boolean terminated = false;
			while (!terminated
					&& (System.currentTimeMillis() - terminateStartTime) < terminateTimeout) {
				Thread.sleep(5000);
				final List<String> instanceIds = (List<String>) getInstancesForGroup(groupName, null, true);
				terminated = instanceIds.size() == 0;
			}
			assertThat(terminated,
					"Instances were not terminated within the expected timeout");
			print("Instances terminated in "
					+ (System.currentTimeMillis() - terminateStartTime) + "ms");
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
