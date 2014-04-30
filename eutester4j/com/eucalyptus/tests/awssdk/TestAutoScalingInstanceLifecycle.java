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

import com.amazonaws.services.autoscaling.model.ScalingActivityInProgressException;
import com.amazonaws.services.autoscaling.model.SetDesiredCapacityRequest;
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
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();

        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // Register cleanup for launch config
            final String launchConfig = NAME_PREFIX + "InstanceLifecycleTest";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting launch configuration: " + launchConfig);
                    deleteLaunchConfig(launchConfig);
                }
            });

            // Create launch configuration
            print("Creating launch configuration: " + launchConfig);
            createLaunchConfig(launchConfig,IMAGE_ID,INSTANCE_TYPE,null,null,null,null,null,null,null,null);

            // Register cleanup for auto scaling group
            final String groupName = NAME_PREFIX + "InstanceLifecycleTest";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting group: " + groupName);
                    deleteAutoScalingGroup(groupName, true);
                }
            });

            // Create scaling group
            Integer minSize = 0;
            Integer maxSize = 1;
            Integer desiredCapacity = 1;
            Integer cooldown =0;
            print("Creating auto scaling group: " + groupName);
            createAutoScalingGroup(groupName,launchConfig,minSize,maxSize,desiredCapacity,AVAILABILITY_ZONE,cooldown,
                    null,null,null,null,null);

            // Wait for instance to start
            print("Waiting for Pending instance: " + groupName);
            waitForInstances("Pending", TimeUnit.MINUTES.toMillis(10), groupName, false);

            print("Waiting for InService instance: " + groupName);
            waitForInstances("InService", TimeUnit.MINUTES.toMillis(10), groupName, false);

            // Terminate instance
            print("Terminating instance");
            as.setDesiredCapacity(new SetDesiredCapacityRequest()
                    .withAutoScalingGroupName(groupName)
                    .withDesiredCapacity(0)
            );

            // Wait for instance to terminate
            print("Waiting for Terminating instance: " + groupName);
            waitForInstances("Terminating", TimeUnit.MINUTES.toMillis(10), groupName, true);

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
