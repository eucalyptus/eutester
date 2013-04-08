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
import com.amazonaws.services.ec2.model.DescribeAvailabilityZonesResult;
import org.testng.annotations.Test;

import java.util.*;
import java.util.concurrent.TimeUnit;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

/**
 * This application tests rebalancing when availability zones are updated.
 * <p/>
 * This is verification for the story:
 * <p/>
 * https://eucalyptus.atlassian.net/browse/EUCA-4995
 */
public class TestAutoScalingAvailabilityZoneRebalancing {
    @Test
    public void AutoScalingAvailabilityZoneRebalancingTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();

        // Find an AZ to use
        final DescribeAvailabilityZonesResult azResult = ec2.describeAvailabilityZones();

        // If only 1 AZ then do not run test but pass w/ a message
        if (azResult.getAvailabilityZones().size() < 2) {
            print("Test Skipped: Multiple Availability Zones Required");
            return;
        }

        final String availabilityZone1 = azResult.getAvailabilityZones().get(0).getZoneName();
        final String availabilityZone2 = azResult.getAvailabilityZones().get(1).getZoneName();
        print("Using availability zones: " + Arrays.asList(availabilityZone1, availabilityZone2));

        // End discovery, start test
        final String namePrefix = UUID.randomUUID().toString() + "-";
        print("Using resource prefix for test: " + namePrefix);

        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // Create launch configuration
            final String launchConfig = namePrefix + "ZoneRebalancing";
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
            final String groupName = namePrefix + "ZoneRebalancing";
            print("Creating auto scaling group: " + groupName + ", with availability zone: " + availabilityZone1);
            as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
                    .withAutoScalingGroupName(groupName)
                    .withLaunchConfigurationName(launchConfig)
                    .withDesiredCapacity(1)
                    .withMinSize(0)
                    .withMaxSize(2)
                    .withAvailabilityZones(availabilityZone1)
                    .withTerminationPolicies("OldestInstance"));
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting group: " + groupName);
                    as.deleteAutoScalingGroup(new DeleteAutoScalingGroupRequest().withAutoScalingGroupName(groupName).withForceDelete(true));

                }
            });

            // Wait for instances to launch
            print("Waiting for 1 instance to launch");
            final long timeout = TimeUnit.MINUTES.toMillis(2);
            waitForInstances(as, "InService", availabilityZone1, timeout, 1, groupName, false);

            // Change availability zones
            print("Changing availability zone to : " + availabilityZone2);
            as.updateAutoScalingGroup(new UpdateAutoScalingGroupRequest()
                    .withAutoScalingGroupName(groupName)
                    .withAvailabilityZones(availabilityZone2));

            // Wait for instance to launch
            print("Waiting for 1 instance to launch in zone: " + availabilityZone2);
            waitForInstances(as, "InService", availabilityZone2, timeout, 1, groupName, false);

            // Wait for instance to terminate
            print("Waiting for 1 instance to terminate in zone: " + availabilityZone1);
            waitForInstances(as, "Terminated", availabilityZone1, timeout, 1, groupName, true);

            // Update group configuration for multiple instance test
            print("Setting desired capacity to 2 and enabling 2 zones for group: " + groupName);
            as.updateAutoScalingGroup(new UpdateAutoScalingGroupRequest()
                    .withAutoScalingGroupName(groupName)
                    .withDesiredCapacity(2)
                    .withAvailabilityZones(availabilityZone1, availabilityZone2));

            // Wait for instance to launch
            print("Waiting for 1 instance to launch in zone: " + availabilityZone1);
            waitForInstances(as, "InService", availabilityZone1, timeout, 1, groupName, false);

            // Verify instance in zone 2
            print("Verifying 1 instance in zone: " + availabilityZone2);
            waitForInstances(as, "InService", availabilityZone2, timeout, 1, groupName, false);

            // Remove zone to trigger rebalancing
            print("Changing availability zone to : " + availabilityZone1);
            as.updateAutoScalingGroup(new UpdateAutoScalingGroupRequest()
                    .withAutoScalingGroupName(groupName)
                    .withAvailabilityZones(availabilityZone1));

            // Wait for instance to launch
            print("Waiting for 1 instance to launch in zone: " + availabilityZone1);
            waitForInstances(as, "InService", availabilityZone1, timeout, 2, groupName, false);

            // Wait for instance to terminate
            print("Waiting for 1 instance to terminate in zone: " + availabilityZone2);
            waitForInstances(as, "Terminated", availabilityZone2, timeout, 1, groupName, true);

            // Add zone to trigger rebalancing
            print("Configuring group for 2 availability zones: " + groupName);
            as.updateAutoScalingGroup(new UpdateAutoScalingGroupRequest()
                    .withAutoScalingGroupName(groupName)
                    .withAvailabilityZones(availabilityZone1, availabilityZone2));

            // Wait for instance to launch
            print("Waiting for 1 instance to launch in zone: " + availabilityZone2);
            waitForInstances(as, "InService", availabilityZone2, timeout, 1, groupName, false);

            // Wait for instance to terminate
            print("Waiting for 1 instance to terminate in zone: " + availabilityZone1);
            waitForInstances(as, "InService", availabilityZone1, timeout, 1, groupName, false);

            // Set desired capacity to zero for shutdown
            print("Setting desired capacity to zero for group: " + groupName);
            as.setDesiredCapacity(new SetDesiredCapacityRequest()
                    .withAutoScalingGroupName(groupName)
                    .withDesiredCapacity(0));

            // Wait for instance to terminate
            print("Waiting for 2 instances to terminate");
            waitForInstances(as, "Terminated", null, timeout, 2, groupName, true);

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

    private List<Instance> waitForInstances(final AmazonAutoScaling as,
                                            final String state,
                                            final String zone,
                                            final long timeout,
                                            final int instanceCount,
                                            final String groupName,
                                            final boolean allowEmpty) throws Exception {
        List<Instance> instances = Collections.emptyList();
        final long startTime = System.currentTimeMillis();
        boolean completed = false;
        while (!completed && (System.currentTimeMillis() - startTime) < timeout) {
            instances = getInstancesInState(as, groupName, state, zone);
            completed = instances.isEmpty() && allowEmpty && getInstancesInState(as, groupName, null, zone).isEmpty() || instanceCount == instances.size();
            Thread.sleep(2500);
        }
        assertThat(completed, "Instance not found with state " + state + " within the expected timeout");
        print("Instance found in " + (System.currentTimeMillis() - startTime) + "ms for state: " + state + (instances.isEmpty() ? " (instance(s) terminated before state detected)" : ""));
        return instances;
    }

    private List<Instance> getInstancesInState(final AmazonAutoScaling as,
                                               final String groupName,
                                               final String state,
                                               final String zone) {
        final List<Instance> instances = new ArrayList<Instance>();
        final DescribeAutoScalingGroupsResult groupResult = as.describeAutoScalingGroups(new DescribeAutoScalingGroupsRequest().withAutoScalingGroupNames(groupName));
        for (final AutoScalingGroup group : groupResult.getAutoScalingGroups()) {
            assertThat(groupName.equals(group.getAutoScalingGroupName()), "Unexpected group: " + group.getAutoScalingGroupName());
            for (final Instance instance : group.getInstances()) {
                if ((state == null || state.equals(instance.getLifecycleState())) &&
                        (zone == null || zone.equals(instance.getAvailabilityZone()))) {
                    instances.add(instance);
                }
            }
        }
        return instances;
    }

}
