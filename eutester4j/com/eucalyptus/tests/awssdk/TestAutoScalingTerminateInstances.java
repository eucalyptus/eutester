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
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
		
		// End discovery, start test
		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			// Create launch configuration
            final String launchConfig = NAME_PREFIX + "TerminateTest";
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
            final String asGroupName = NAME_PREFIX + "TerminateTest";
            Integer minSize = 0;
            Integer maxSize = 2;
            Integer desiredCapacity =2;
            String healthCheckType = "EC2";
            String terminationPolicy = "OldestInstance";
			print("Creating auto scaling group: " + asGroupName);
            createAutoScalingGroup(asGroupName,launchConfig,minSize,maxSize,desiredCapacity,AVAILABILITY_ZONE, null,
                    null, healthCheckType, null, null, terminationPolicy);
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting group: " + asGroupName);
					deleteAutoScalingGroup(asGroupName,true);
				}
			});
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					final List<String> instanceIds = (List<String>) getInstancesForGroup(asGroupName, null, true);
					print("Terminating instances: " + instanceIds);
					ec2.terminateInstances(new TerminateInstancesRequest()
							.withInstanceIds(instanceIds));
				}
			});

			// Wait for instances to launch
			print("Waiting for instances to launch");
			final long timeout = TimeUnit.MINUTES.toMillis(2);
			List<String> instanceIds = (List<String>) waitForInstances(timeout, 2, asGroupName, true);

			// Terminate instance with capacity decrement
			final String instanceToTerminate = instanceIds.get(1);
//            final String instanceToTerminate = String.valueOf(getLastlaunchedInstance().get(0));
            print("Terminating: " + instanceToTerminate);
            as.terminateInstanceInAutoScalingGroup(new TerminateInstanceInAutoScalingGroupRequest()
                    .withInstanceId(instanceToTerminate)
                    .withShouldDecrementDesiredCapacity(true));
			print("Waiting for instance to terminate");
			List<String> remainingInstances = (List<String>) waitForInstances(timeout, 1, asGroupName, true);
			assertThat(!remainingInstances.contains(instanceToTerminate),
					"Expected instance terminated");
			assertThat(remainingInstances.contains(instanceIds.get(0)),
					"Expected instance to remain: " + instanceIds.get(0));

			// Terminate instance without capacity decrement, ensure replaced
            print("Terminating without capacity decrement");

			as.terminateInstanceInAutoScalingGroup(new TerminateInstanceInAutoScalingGroupRequest()
					.withInstanceId(remainingInstances.get(0))
					.withShouldDecrementDesiredCapacity(false));
            print("Now terminating instance: " + remainingInstances.get(0));
			print("Waiting for instance to be replaced");
			Thread.sleep(10000); // We sleep to ensure the first instance has a
									// chance to start terminating ...
			List<String> remainingInstances2 = (List<String>) waitForInstances(timeout, 1, asGroupName, true);
			assertThat(
					!remainingInstances2.contains(remainingInstances.get(0)),
					"Instance replaced");

			// Delete group without force, should fail due to existing instance
			print("Deleting group without force, error expected");
			try {
				as.deleteAutoScalingGroup(new DeleteAutoScalingGroupRequest()
						.withAutoScalingGroupName(asGroupName).withForceDelete(false));
				assertThat(false, "Expected resource in use error");
			} catch (final ResourceInUseException e) {
				// expected
			}

			// Delete group with force to remove remaining instances
			print("Deleting group with force, instances should be terminated.");
			as.deleteAutoScalingGroup(new DeleteAutoScalingGroupRequest()
					.withAutoScalingGroupName(asGroupName).withForceDelete(true));
			waitForInstances(timeout, 0, asGroupName, true);

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
