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

import java.util.*;
import java.util.concurrent.TimeUnit;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;


/**
 *
 */
public class TestAutoScalingSuspendAndResumeProcesses {

    @Test
    public void AutoScalingSuspendAndResumeProcessesTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();

        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // Create launch configuration
            final String configName = NAME_PREFIX + "SuspendResumeTest";
            print("Creating launch configuration: " + configName);
            as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
                    .withLaunchConfigurationName(configName)
                    .withImageId(IMAGE_ID)
                    .withInstanceType(INSTANCE_TYPE));
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting launch configuration: " + configName);
                    deleteLaunchConfig(configName);
                }
            });

            // Create scaling group
            final String groupName = NAME_PREFIX + "SuspendResumeTest";
            print("Creating auto scaling group: " + groupName);
            as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
                    .withAutoScalingGroupName(groupName)
                    .withLaunchConfigurationName(configName)
                    .withDesiredCapacity(0)
                    .withMinSize(0)
                    .withMaxSize(1)
                    .withHealthCheckType("EC2")
                    .withAvailabilityZones(AVAILABILITY_ZONE)
                    .withTerminationPolicies("OldestInstance"));
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting group: " + groupName);
                    deleteAutoScalingGroup(groupName,true);
                }
            });

            // Check process types
            print("Verifying process types.");
            final Set<String> expectedProcessTypes = new HashSet<String>();
            expectedProcessTypes.add("Launch");
            expectedProcessTypes.add("Terminate");
            expectedProcessTypes.add("HealthCheck");
            expectedProcessTypes.add("ReplaceUnhealthy");
            expectedProcessTypes.add("AZRebalance");
            expectedProcessTypes.add("AlarmNotification");
            expectedProcessTypes.add("ScheduledActions");
            expectedProcessTypes.add("AddToLoadBalancer");
            final DescribeScalingProcessTypesResult scalingProcessTypesResult = as.describeScalingProcessTypes();
            assertThat(scalingProcessTypesResult.getProcesses() != null, "Expected processes");
            assertThat(scalingProcessTypesResult.getProcesses().size() == 8, "Expected 8 processes, but got " + scalingProcessTypesResult.getProcesses().size());
            final Set<String> foundProcessTypes = new HashSet<String>();
            for (final ProcessType processType : scalingProcessTypesResult.getProcesses()) {
                foundProcessTypes.add(processType.getProcessName());
            }
            assertThat(expectedProcessTypes.equals(foundProcessTypes), "Process types incorrect: " + foundProcessTypes);

            // Disable all processes
            print("Suspending all processes");
            as.suspendProcesses(new SuspendProcessesRequest().withAutoScalingGroupName(groupName));

            // Verify all disabled
            print("Verifying all processes suspended");
            assertProcessesSuspended(as, groupName, expectedProcessTypes);

            // Enable all processes
            print("Resuming all processes");
            as.resumeProcesses(new ResumeProcessesRequest().withAutoScalingGroupName(groupName));

            // Verify all enabled
            print("Verifying all processes resumed");
            assertProcessesSuspended(as, groupName, Collections.<String>emptySet());

            // Disable launch process
            print("Suspending launch process");
            as.suspendProcesses(new SuspendProcessesRequest()
                    .withAutoScalingGroupName(groupName)
                    .withScalingProcesses("Launch"));

            // Verifying launch disabled
            print("Verify launch process suspended");
            assertProcessesSuspended(as, groupName, Collections.singleton("Launch"));

            // Update group desired capacity and wait for instances to launch
            print("Setting desired capacity to 1 for group: " + groupName);
            as.setDesiredCapacity(new SetDesiredCapacityRequest()
                    .withAutoScalingGroupName(groupName)
                    .withDesiredCapacity(1));

            // Verify no instances launch
            print("Waiting to verify no instances launch");
            Thread.sleep(TimeUnit.SECONDS.toMillis(30));
            assertThat(getInstancesForGroup(groupName, null,true).isEmpty(), "Instance launched when launch suspended");

            // Resume launch process
            print("Resuming launch process");
            as.resumeProcesses(new ResumeProcessesRequest()
                    .withAutoScalingGroupName(groupName)
                    .withScalingProcesses("Launch"));

            // Verify launch enabled
            print("Verifying launch process resumed");
            assertProcessesSuspended(as, groupName, Collections.<String>emptySet());

            // Wait for instances to launch
            print("Waiting for instance to launch");
            final long startTime = System.currentTimeMillis();
            final long launchTimeout = TimeUnit.MINUTES.toMillis(5);
            boolean launched = false;
            while (!launched && (System.currentTimeMillis() - startTime) < launchTimeout) {
                Thread.sleep(5000);
                final List<String> instanceIds = (List<String>) getInstancesForGroup(groupName, "running",true);
                launched = instanceIds.size() == 1;
            }
            assertThat(launched, "Instance was not launched within the expected timeout");
            print("Instance launched in " + (System.currentTimeMillis() - startTime) + "ms");

            // Update group desired capacity and wait for instances to terminate
            print("Setting desired capacity to 0 for group: " + groupName);
            as.setDesiredCapacity(new SetDesiredCapacityRequest()
                    .withAutoScalingGroupName(groupName)
                    .withDesiredCapacity(0));

            // Wait for instances to terminate
            print("Waiting for instance to terminate");
            final long terminateStartTime = System.currentTimeMillis();
            final long terminateTimeout = TimeUnit.MINUTES.toMillis(5);
            boolean terminated = false;
            while (!terminated && (System.currentTimeMillis() - terminateStartTime) < terminateTimeout) {
                Thread.sleep(5000);
                final List<String> instanceIds = (List<String>) getInstancesForGroup(groupName, null, true);
                terminated = instanceIds.size() == 0;
            }
            assertThat(terminated, "Instance was not terminated within the expected timeout");
            print("Instance terminated in " + (System.currentTimeMillis() - terminateStartTime) + "ms");

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

    private void assertProcessesSuspended(final AmazonAutoScaling as,
                                          final String groupName,
                                          final Set<String> processNames) {
        final DescribeAutoScalingGroupsResult groupsResult =
                as.describeAutoScalingGroups(new DescribeAutoScalingGroupsRequest().withAutoScalingGroupNames(groupName));

        assertThat(groupsResult.getAutoScalingGroups() != null, "Expected groups");
        assertThat(groupsResult.getAutoScalingGroups().size() == 1, "Expected 1 group");
        final AutoScalingGroup group = groupsResult.getAutoScalingGroups().get(0);
        assertThat(groupName.equals(group.getAutoScalingGroupName()), "Unexpected group: " + group.getAutoScalingGroupName());
        if (processNames.isEmpty()) {
            assertThat(group.getSuspendedProcesses() == null || group.getSuspendedProcesses().isEmpty(), "Expected no processes: " + group.getSuspendedProcesses());
        } else {
            final Set<String> groupProcessNames = new HashSet<String>();
            for (final SuspendedProcess suspendedProcess : group.getSuspendedProcesses()) {
                groupProcessNames.add(suspendedProcess.getProcessName());
            }
            assertThat(processNames.equals(groupProcessNames), "Expected processes " + processNames + ", but got: " + groupProcessNames);
        }
    }
}
