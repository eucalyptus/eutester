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
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

/**
 *
 */
public class TestAutoScalingInstanceLifecycle {

    @Test
    public void AutoScalingInstanceLifecycleTest() throws Exception {
        getCloudInfo();
        final AmazonAutoScaling as = getAutoScalingClient(ACCESS_KEY, SECRET_KEY, AS_ENDPOINT);
        final AmazonEC2 ec2 = getEc2Client(ACCESS_KEY, SECRET_KEY, EC2_ENDPOINT);
        final String imageId = findImage(ec2);
        final String availabilityZone = findAvalablityZone(ec2);
        final String namePrefix = eucaUUID() + "-";
        print("Using resource prefix for test: " + namePrefix);
        // End discovery, start test

        final List<Runnable> cleanupTasks = new ArrayList<>();
        try {
            // Register cleanup for launch config
            final String configName = namePrefix + "InstanceLifecycleTest";
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
            final String groupName = namePrefix + "InstanceLifecycleTest";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting group: " + groupName);
                    deleteAutoScalingGroup(as, groupName);
                }
            });

            // Create scaling group
            print("Creating auto scaling group: " + groupName);
            createAutoScalingGroup(as, groupName, configName, 0, 1, 1, availabilityZone);

            // Wait for instance to start
            print("Waiting for Pending instance: " + groupName);
            waitForInstances(as, "Pending", TimeUnit.MINUTES.toMillis(1), groupName, false);

            print("Waiting for InService instance: " + groupName);
            waitForInstances(as, "InService", TimeUnit.MINUTES.toMillis(5), groupName, false);

            // Terminate instance
            print("Terminating instance");
            as.setDesiredCapacity(new SetDesiredCapacityRequest()
                    .withAutoScalingGroupName(groupName)
                    .withDesiredCapacity(0)
            );

            // Wait for instance to terminate
            print("Waiting for Terminating instance: " + groupName);
            waitForInstances(as, "Terminating", TimeUnit.MINUTES.toMillis(1), groupName, true);

            print("Test complete");
        } finally {
            // Attempt to clean up anything we created
            Collections.reverse(cleanupTasks);
            for (final Runnable cleanupTask : cleanupTasks) {
                while (true) try {
                    cleanupTask.run();
                    break;
                } catch (ScalingActivityInProgressException e) {
                    print("Cleanup failed due to ScalingActivityInProgress, will retry in 5 seconds.");
                    Thread.sleep(5000);
                } catch (Exception e) {
                    e.printStackTrace();
                    break;
                }
            }
        }
    }
}
