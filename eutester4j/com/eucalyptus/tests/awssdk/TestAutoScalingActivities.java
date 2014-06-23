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

import org.testng.annotations.Test;

import com.amazonaws.services.autoscaling.AmazonAutoScaling;
import com.amazonaws.services.autoscaling.model.*;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

/**
 * This application tests auto scaling activities.
 * <p/>
 * This is verification for the story:
 * <p/>
 * https://eucalyptus.atlassian.net/browse/EUCA-4998
 */
public class TestAutoScalingActivities {

    @Test
    public void AutoScalingActivitiesTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();

        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // Register cleanup for launch config
            final String configName = NAME_PREFIX + "ActivityTest";
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
            final String groupName = NAME_PREFIX + "ActivityTest";
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
                    .withHealthCheckGracePeriod(300)
                    .withAvailabilityZones(AVAILABILITY_ZONE)
            );

            // Register cleanup for auto scaling policy
            final String policyName = NAME_PREFIX + "ActivityTest";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting policy: " + policyName);
                    deletePolicy(policyName);
                }
            });

            // Create policy
            print("Creating auto scaling policy " + policyName);
            final PutScalingPolicyResult putScalingPolicyResult =
                    as.putScalingPolicy(new PutScalingPolicyRequest()
                            .withAutoScalingGroupName(groupName)
                            .withPolicyName(policyName)
                            .withAdjustmentType("ExactCapacity")
                            .withScalingAdjustment(0));
            final String policyArn = putScalingPolicyResult.getPolicyARN();
            print("Using policy ARN: " + policyArn);

            // Manual scale up
            print("Setting desired capacity to 1 for group: " + groupName);
            as.setDesiredCapacity(new SetDesiredCapacityRequest().withAutoScalingGroupName(groupName).withDesiredCapacity(1).withHonorCooldown(false));
            waitForInstance(as, "InService", groupName, false);

            // Policy scale down
            print("Executing policy " + policyName + " for group: " + groupName);
            as.executePolicy(new ExecutePolicyRequest().withPolicyName(policyArn).withHonorCooldown(false));
            waitForInstance(as, "Terminated", groupName, true);

            // Manual group update
            print("Updating group to change desired capacity to 1 for group: " + groupName);
            as.updateAutoScalingGroup(new UpdateAutoScalingGroupRequest().withAutoScalingGroupName(groupName).withDesiredCapacity(1));
            final String instanceId1 = waitForInstance(as, "InService", groupName, false);

            // Set instance unhealthy
            print("Setting instance " + instanceId1 + " unhealthy for group: " + groupName);
            as.setInstanceHealth(new SetInstanceHealthRequest().withInstanceId(instanceId1).withHealthStatus("Unhealthy").withShouldRespectGracePeriod(false));
            waitForInstance(as, "Pending", groupName, true); // Use Pending to detect termination / start of new instance
            final String instanceId2 = waitForInstance(as, "InService", groupName, false);

            // Manually terminate instance
            print("Manually terminating instance for group: " + groupName);
            as.terminateInstanceInAutoScalingGroup(new TerminateInstanceInAutoScalingGroupRequest().withInstanceId(instanceId2).withShouldDecrementDesiredCapacity(true));
            waitForInstance(as, "Terminated", groupName, true);

            // Get activities for verification
            print("Describing scaling activities for group: " + groupName);
            final DescribeScalingActivitiesResult describeScalingActivitiesResult = as.describeScalingActivities(new DescribeScalingActivitiesRequest().withAutoScalingGroupName(groupName));
            print(describeScalingActivitiesResult.toString().replace("ActivityId: ", "\nActivityId: "));

            assertThat(describeScalingActivitiesResult.getActivities() != null, "Expected activities");
            assertThat(describeScalingActivitiesResult.getActivities().size() == 6, "Expected 6 activities, got: " + describeScalingActivitiesResult.getActivities().size());
            // verify activity details
            for (final Activity activity : describeScalingActivitiesResult.getActivities()) {
                assertThat(activity.getProgress() == 100, "Expected activity to be complete");
                assertThat("Successful".equals(activity.getStatusCode()), "Expected activity to be successful");
                assertThat(activity.getActivityId() != null, "Expected activity to have an identifier");
                assertThat(groupName.equals(activity.getAutoScalingGroupName()), "Expected activity to be for group: " + groupName);
                assertThat(activity.getStartTime() != null, "Expected activity to have a start time");
                assertThat(activity.getEndTime() != null, "Expected activity to have an end time");
                assertThat(activity.getStartTime().before(activity.getEndTime()), "Expected activity start time to be before end time");
                assertThat(activity.getStatusMessage() == null, "Expected no status message for activity");
                assertThat(activity.getDetails() == null, "Expected no details for activity");
            }
            final List<Activity> activities = describeScalingActivitiesResult.getActivities();
            // Verify activity descriptions
            assertThat(activities.get(0).getDescription().startsWith("Terminating EC2 instance: i-"), "Expected terminate activity");
            assertThat(activities.get(1).getDescription().startsWith("Launching a new EC2 instance: i-"), "Expected launch activity");
            assertThat(activities.get(2).getDescription().startsWith("Terminating EC2 instance: "), "Expected terminate activity");
            assertThat(activities.get(3).getDescription().startsWith("Launching a new EC2 instance: i-"), "Expected launch activity");
            assertThat(activities.get(4).getDescription().startsWith("Terminating EC2 instance: "), "Expected terminate activity");
            assertThat(activities.get(5).getDescription().startsWith("Launching a new EC2 instance: i-"), "Expected launch activity");
            // Verify activity causes
            assertThat(activities.get(0).getCause().contains("instance was taken out of service in response to a user request"), "Expected user termination cause");
            assertThat(activities.get(1).getCause().contains("an instance was started in response to a difference between desired and actual capacity, increasing the capacity from 0 to 1"), "Expected launch due to capacity difference cause");
            assertThat(activities.get(2).getCause().contains("an instance was taken out of service in response to a health-check"), "Expected health check failure cause");
            assertThat(activities.get(3).getCause().contains("a user request update of AutoScalingGroup constraints to min: 0, max: 1, desired: 1 changing the desired capacity from 0 to 1"), "Expected group update cause");
            assertThat(activities.get(4).getCause().contains("a user request executed policy"), "Expected policy execution cause");
            assertThat(activities.get(5).getCause().contains("a user request explicitly set group desired capacity changing the desired capacity from 0 to 1"), "Expected set desired capacity cause");

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
                                   final String groupName,
                                   final boolean allowEmpty) throws Exception {
        print("Waiting for instance to enter state: " + state);
        final long startTime = System.currentTimeMillis();
        boolean completed = false;
        Instance instance = null;
        while (!completed && (System.currentTimeMillis() - startTime) < TimeUnit.MINUTES.toMillis(15)) {
            instance = getInstance(as, groupName);
            completed = instance == null && allowEmpty || instance != null && state.equals(instance.getLifecycleState());
            Thread.sleep(2500);
        }
        assertThat(completed, "Instance not found with state " + state + " within the expected timeout");
        print("Instance found in " + (System.currentTimeMillis() - startTime) + "ms for state: " + state + (instance == null ? " (instance terminated before state detected)" : ""));
        return instance != null ? instance.getInstanceId() : null;
    }

    private Instance getInstance(final AmazonAutoScaling as,
                                 final String groupName) {
        final DescribeAutoScalingGroupsResult groupResult = as.describeAutoScalingGroups(new DescribeAutoScalingGroupsRequest().withAutoScalingGroupNames(groupName));
        Instance instance = null;
        for (final AutoScalingGroup group : groupResult.getAutoScalingGroups()) {
            assertThat(groupName.equals(group.getAutoScalingGroupName()), "Unexpected group: " + group.getAutoScalingGroupName());
            assertThat(group.getInstances().size() < 2, "Unexpected instance count: " + group.getInstances().size());
            for (final Instance groupInstance : group.getInstances()) {
                instance = groupInstance;
            }
        }
        return instance;
    }
}
