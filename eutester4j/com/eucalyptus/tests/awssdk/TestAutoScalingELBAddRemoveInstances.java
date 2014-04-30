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
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;


/**
 * This application tests add/remove of auto scaling instances to ELB.
 * <p/>
 * This is verification for the story:
 * <p/>
 * https://eucalyptus.atlassian.net/browse/EUCA-5007
 */
public class TestAutoScalingELBAddRemoveInstances {

    @Test
    public void AutoScalingELBAddRemoveInstancesTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // Generate a load balancer to use
            final String loadBalancerName = NAME_PREFIX + "ELBAddRemTest";
            print("Creating a load balancer for test use: " + loadBalancerName);
            createLoadBalancer(loadBalancerName);
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting load balancer: " + loadBalancerName);
                    deleteLoadBlancer(loadBalancerName);
                }
            });

            // Register cleanup for launch config
            final String configName = NAME_PREFIX + "ELBAddRemoveTest";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting launch configuration: " + configName);
                    deleteLaunchConfig(configName);
                }
            });

            // Create launch configuration
            print("Creating launch configuration: " + configName);
            as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
                    .withLaunchConfigurationName(configName)
                    .withImageId(IMAGE_ID)
                    .withInstanceType(INSTANCE_TYPE));

            // Register cleanup for auto scaling group
            final String groupName = NAME_PREFIX + "ELBAddRemoveTest";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting group: " + groupName);
                    deleteAutoScalingGroup(groupName,true);
                }
            });

            // Create scaling group
            print("Creating auto scaling group: " + groupName);
            as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
                    .withAutoScalingGroupName(groupName)
                    .withLaunchConfigurationName(configName)
                    .withMinSize(0)
                    .withMaxSize(1)
                    .withDesiredCapacity(1)
                    .withAvailabilityZones(AVAILABILITY_ZONE)
                    .withLoadBalancerNames(loadBalancerName)
            );

            // Wait for instance to launch
            print("Waiting for instance to launch");
            String instanceId = waitForInstance(as, "InService", TimeUnit.MINUTES.toMillis(10), groupName, false);
            print("Instance launched: " + instanceId);

            // Verify added to load balancer
            print("Waiting for instance to be added to ELB");
            waitForElbInstances(loadBalancerName, TimeUnit.MINUTES.toMillis(10), Arrays.asList(instanceId));
            print("Instance added to ELB");

            // Terminate instance manually
            print("Manually terminating instance");
            as.terminateInstanceInAutoScalingGroup(new TerminateInstanceInAutoScalingGroupRequest()
                    .withInstanceId(instanceId)
                    .withShouldDecrementDesiredCapacity(true));

            // Wait for instance to terminate
            print("Waiting for termination of instance: " + instanceId);
            waitForInstance(as, "Terminated", TimeUnit.MINUTES.toMillis(10), groupName, true);
            print("Instance terminated: " + instanceId);

            // Verify removed from load balancer
            print("Waiting for instance to be removed from load balancer");
            waitForElbInstances(loadBalancerName, TimeUnit.MINUTES.toMillis(10), Collections.<String>emptyList());

            // Set desired capacity back to one
            print("Setting desired capacity to 1 for group: " + groupName);
            as.setDesiredCapacity(new SetDesiredCapacityRequest()
                    .withAutoScalingGroupName(groupName)
                    .withDesiredCapacity(1));

            // Wait for instance to launch
            print("Waiting for instance to launch");
            instanceId = waitForInstance(as, "InService", TimeUnit.MINUTES.toMillis(10), groupName, false);
            print("Instance launched: " + instanceId);

            // Verify added to load balancer
            print("Waiting for instance to be added to ELB");
            waitForElbInstances(loadBalancerName, TimeUnit.MINUTES.toMillis(10), Arrays.asList(instanceId));
            print("Instance added to ELB");

            // Manually set instance to unhealthy
            print("Manually setting instance to unhealthy");
            as.setInstanceHealth(new SetInstanceHealthRequest()
                    .withInstanceId(instanceId)
                    .withShouldRespectGracePeriod(false)
                    .withHealthStatus("Unhealthy"));

            // Verify removed from load balancer
            print("Waiting for instance to be removed from load balancer");
            waitForElbInstances(loadBalancerName, TimeUnit.MINUTES.toMillis(10), Collections.<String>emptyList());

            // Wait for instance to launch
            print("Waiting for replacement instance to launch");
            instanceId = waitForInstance(as, "InService", TimeUnit.MINUTES.toMillis(10), groupName, false);
            print("Instance launched: " + instanceId);

            // Verify added to load balancer
            print("Waiting for instance to be added to ELB");
            waitForElbInstances(loadBalancerName, TimeUnit.MINUTES.toMillis(10), Arrays.asList(instanceId));
            print("Instance added to ELB");

            // Set desired capacity to zero
            print("Setting desired capacity to 0 for group: " + groupName);
            as.setDesiredCapacity(new SetDesiredCapacityRequest()
                    .withAutoScalingGroupName(groupName)
                    .withDesiredCapacity(0));

            // Verify removed from load balancer
            print("Waiting for instance to be removed from load balancer");
            waitForElbInstances(loadBalancerName, TimeUnit.MINUTES.toMillis(10), Collections.<String>emptyList());

            // Wait for instance to terminate
            print("Waiting for instance to terminate");
            waitForInstances("Terminated", TimeUnit.MINUTES.toMillis(10), groupName, true);

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

    private String waitForInstance(final AmazonAutoScaling as,
                                   final String state,
                                   final long timeout,
                                   final String groupName,
                                   final boolean allowEmpty) throws Exception {
        final long startTime = System.currentTimeMillis();
        boolean completed = false;
        String instanceState = null;
        String instanceId = null;
        while (!completed && (System.currentTimeMillis() - startTime) < timeout) {
            final Instance instance = getInstance(as, groupName);
            instanceState = instance == null ? null : instance.getLifecycleState();
            instanceId = instance == null ? null : instance.getInstanceId();
            completed = instanceState == null && allowEmpty || state.equals(instanceState);
            Thread.sleep(2500);
        }
        assertThat(completed, "Instance not found with state " + state + " within the expected timeout");
        print("Instance found in " + (System.currentTimeMillis() - startTime) + "ms for state: " + state + (instanceState == null ? " (instance terminated before state detected)" : ""));
        return instanceId;
    }

    private Instance getInstance(final AmazonAutoScaling as,
                                 final String groupName) {
        final DescribeAutoScalingGroupsResult groupResult = as.describeAutoScalingGroups(new DescribeAutoScalingGroupsRequest().withAutoScalingGroupNames(groupName));
        Instance instance = null;
        for (final AutoScalingGroup group : groupResult.getAutoScalingGroups()) {
            assertThat(groupName.equals(group.getAutoScalingGroupName()), "Unexpected group: " + group.getAutoScalingGroupName());
            assertThat(group.getInstances().size() < 2, "Unexpected instance count: " + group.getInstances().size());
            instance = group.getInstances().isEmpty() ? null : group.getInstances().get(0);
        }
        return instance;
    }

}
