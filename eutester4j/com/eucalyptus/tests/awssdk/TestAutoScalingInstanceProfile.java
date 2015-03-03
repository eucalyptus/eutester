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

import com.amazonaws.services.autoscaling.model.CreateAutoScalingGroupRequest;
import com.amazonaws.services.autoscaling.model.CreateLaunchConfigurationRequest;
import com.amazonaws.services.ec2.model.DescribeInstancesRequest;
import com.amazonaws.services.ec2.model.DescribeInstancesResult;
import com.amazonaws.services.ec2.model.IamInstanceProfile;
import com.amazonaws.services.ec2.model.TerminateInstancesRequest;
import com.amazonaws.services.identitymanagement.model.*;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;


/**
 * This application tests using IAM instance profiles with launch configurations.
 * <p/>
 * This is verification for the story:
 * <p/>
 * https://eucalyptus.atlassian.net/browse/EUCA-5351
 */
public class TestAutoScalingInstanceProfile {
    @Test
    public void AutoScalingInstanceProfileTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // Create role
            final String roleName = NAME_PREFIX + "RoleTest";
            print("Creating role: " + roleName);
            youAre.createRole(new CreateRoleRequest()
                    .withRoleName(roleName)
                    .withPath("/path")
                    .withAssumeRolePolicyDocument(
                            "{\n" +
                                    "    \"Statement\": [ {\n" +
                                    "      \"Effect\": \"Allow\",\n" +
                                    "      \"Principal\": {\n" +
                                    "         \"Service\": [ \"ec2.amazonaws.com\" ]\n" +
                                    "      },\n" +
                                    "      \"Action\": [ \"sts:AssumeRole\" ]\n" +  // Mixed case action
                                    "    } ]\n" +
                                    "}"));
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting role: " + roleName);
                    youAre.deleteRole(new DeleteRoleRequest()
                            .withRoleName(roleName));
                }
            });

            // Create IAM instance profile
            final String instanceProfileName = NAME_PREFIX + "IamInstanceProfileTest";
            print("Creating instance profile: " + instanceProfileName);
            final CreateInstanceProfileResult instanceProfileResult =
                    youAre.createInstanceProfile(new CreateInstanceProfileRequest()
                            .withInstanceProfileName(instanceProfileName));
                    youAre.addRoleToInstanceProfile(new AddRoleToInstanceProfileRequest().withRoleName(roleName).withInstanceProfileName(instanceProfileName));
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting instance profile: " + instanceProfileName);
                    youAre.deleteInstanceProfile(new DeleteInstanceProfileRequest().withInstanceProfileName(instanceProfileName));
                }
            });
            final String instanceProfileArn = instanceProfileResult.getInstanceProfile().getArn();
            print("Instance profile has ARN: " + instanceProfileArn);

            // Create launch configuration
            final String configName = NAME_PREFIX + "IamInstanceProfileTest";
            print("Creating launch configuration: " + configName);
            as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
                    .withLaunchConfigurationName(configName)
                    .withImageId(IMAGE_ID)
                    .withInstanceType(INSTANCE_TYPE)
                    .withIamInstanceProfile(instanceProfileName));
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting launch configuration: " + configName);
                    deleteLaunchConfig(configName);
                }
            });

            // Create scaling group
            final String groupName = NAME_PREFIX + "IamInstanceProfileTest";
            print("Creating auto scaling group: " + groupName);
            as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
                    .withAutoScalingGroupName(groupName)
                    .withLaunchConfigurationName(configName)
                    .withDesiredCapacity(1)
                    .withMinSize(0)
                    .withMaxSize(1)
                    .withAvailabilityZones(AVAILABILITY_ZONE));
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting group: " + groupName);
                    deleteAutoScalingGroup(groupName, true);
                }
            });
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    final List<String> instanceIds = (List<String>) getInstancesForGroup(groupName, null, true);
                    print("Terminating instances: " + instanceIds);
                    ec2.terminateInstances(new TerminateInstancesRequest().withInstanceIds(instanceIds));
                }
            });

            // Wait for instances to launch
            print("Waiting for instances to launch");
            String instanceId = null;
            {
                final long startTime = System.currentTimeMillis();
                final long launchTimeout = TimeUnit.MINUTES.toMillis(15);
                boolean launched = false;
                while (!launched && (System.currentTimeMillis() - startTime) < launchTimeout) {
                    Thread.sleep(5000);
                    final List<String> instanceIds = (List<String>) getInstancesForGroup(groupName, "running", true);
                    launched = instanceIds.size() == 1;
                    instanceId = launched ? instanceIds.get(0) : null;
                }
                assertThat(launched, "Instances were not launched within the expected timeout");
                print("Instances launched in " + (System.currentTimeMillis() - startTime) + "ms");
            }

            // Verify instance uses profile
            print("Verifying launched instance uses profile");
            {
                final DescribeInstancesResult describeInstancesResult =
                        ec2.describeInstances(new DescribeInstancesRequest().withInstanceIds(instanceId));
                assertThat(describeInstancesResult.getReservations() != null && describeInstancesResult.getReservations().size() == 1, "Expected one reservation");
                assertThat(describeInstancesResult.getReservations().get(0).getInstances() != null && describeInstancesResult.getReservations().get(0).getInstances().size() == 1, "Expected one instance");
                final IamInstanceProfile profile = describeInstancesResult.getReservations().get(0).getInstances().get(0).getIamInstanceProfile();
                assertThat(profile != null, "Expected instance profile");
                assertThat(profile.getArn() != null, "Expected instance profile ARN");
                assertThat(profile.getArn().equals(instanceProfileArn), "Unexpected instance profile ARN: " + profile.getArn());
            }

            // Delete and try again with ARN in launch configuration
            print("Deleting group: " + groupName);
            deleteAutoScalingGroup(groupName, true);
            print("Deleting launch config: " + configName);
            deleteLaunchConfig(configName);
            // Create launch configuration
            print("Creating launch configuration using ARN: " + configName);
            as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
                    .withLaunchConfigurationName(configName)
                    .withImageId(IMAGE_ID)
                    .withInstanceType(INSTANCE_TYPE)
                    .withIamInstanceProfile(instanceProfileArn));

            // Create scaling group
            print("Creating auto scaling group: " + groupName);
            as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
                    .withAutoScalingGroupName(groupName)
                    .withLaunchConfigurationName(configName)
                    .withDesiredCapacity(1)
                    .withMinSize(0)
                    .withMaxSize(1)
                    .withAvailabilityZones(AVAILABILITY_ZONE));

            // Wait for instances to launch
            print("Waiting for instances to launch");
            instanceId = null;
            {
                final long startTime = System.currentTimeMillis();
                final long launchTimeout = TimeUnit.MINUTES.toMillis(15);
                boolean launched = false;
                while (!launched && (System.currentTimeMillis() - startTime) < launchTimeout) {
                    Thread.sleep(5000);
                    final List<String> instanceIds = (List<String>) getInstancesForGroup(groupName, "running", true);
                    launched = instanceIds.size() == 1;
                    instanceId = launched ? instanceIds.get(0) : null;
                }
                assertThat(launched, "Instances were not launched within the expected timeout");
                print("Instances launched in " + (System.currentTimeMillis() - startTime) + "ms");
            }

            // Verify instance uses profile
            print("Verifying launched instance uses profile");
            {
                final DescribeInstancesResult describeInstancesResult =
                        ec2.describeInstances(new DescribeInstancesRequest().withInstanceIds(instanceId));
                assertThat(describeInstancesResult.getReservations() != null && describeInstancesResult.getReservations().size() == 1, "Expected one reservation");
                assertThat(describeInstancesResult.getReservations().get(0).getInstances() != null && describeInstancesResult.getReservations().get(0).getInstances().size() == 1, "Expected one instance");
                final IamInstanceProfile profile = describeInstancesResult.getReservations().get(0).getInstances().get(0).getIamInstanceProfile();
                assertThat(profile != null, "Expected instance profile");
                assertThat(profile.getArn() != null, "Expected instance profile ARN");
                assertThat(profile.getArn().equals(instanceProfileArn), "Unexpected instance profile ARN: " + profile.getArn());
            }

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
