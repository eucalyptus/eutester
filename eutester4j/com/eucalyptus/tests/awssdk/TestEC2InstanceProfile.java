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

import com.amazonaws.services.ec2.AmazonEC2;
import com.amazonaws.services.ec2.model.*;
import com.amazonaws.services.identitymanagement.model.*;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

/**
 * This application test the EC2 RunInstances operation with instance profiles.
 * <p/>
 * This is verification for the task:
 * <p/>
 * https://eucalyptus.atlassian.net/browse/EUCA-5407
 */
public class TestEC2InstanceProfile {

    @Test
    public void EC2InstanceProfileTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();

        // End discovery, start test
        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            final String namePrefix = UUID.randomUUID().toString() + "-";
            print("Using prefix for test: " + namePrefix);

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

            // Create instance profile
            final String profileName = namePrefix + "EC2ProfileTest";
            print("Creating instance profile: " + profileName);
            final CreateInstanceProfileResult instanceProfileResult = youAre.createInstanceProfile(new CreateInstanceProfileRequest()
                    .withInstanceProfileName(profileName)
                    .withPath("/path"));
            youAre.addRoleToInstanceProfile(new AddRoleToInstanceProfileRequest().withRoleName(roleName).withInstanceProfileName(profileName));

            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting instance profile: " + profileName);
                    youAre.deleteInstanceProfile(new DeleteInstanceProfileRequest()
                            .withInstanceProfileName(profileName));
                }
            });
            final String profileArn = instanceProfileResult.getInstanceProfile().getArn();
            print("Created instance profile with ARN: " + profileArn);

            // Run instance with ARN
            {
                print("Running instance with instance profile ARN");
                final RunInstancesResult runResult =
                        ec2.runInstances(new RunInstancesRequest()
                                .withImageId(IMAGE_ID)
                                .withMinCount(1)
                                .withMaxCount(1)
                                .withIamInstanceProfile(new IamInstanceProfileSpecification()
                                        .withArn(profileArn)));
                final String instanceId = getInstancesIds(runResult.getReservation()).get(0);
                print("Launched instance: " + instanceId);
                cleanupTasks.add(new Runnable() {
                    @Override
                    public void run() {
                        print("Terminating instance: " + instanceId);
                        ec2.terminateInstances(new TerminateInstancesRequest().withInstanceIds(instanceId));
                    }
                });

                // Wait for instance
                waitForInstance(ec2, instanceId, "running");

                // Verify instance profile used for instance
                print("Verifying run instances response references instance profile");
                assertThat(runResult.getReservation().getInstances().get(0).getIamInstanceProfile() != null, "Expected instance profile");
                assertThat(profileArn.equals(runResult.getReservation().getInstances().get(0).getIamInstanceProfile().getArn()), "Unexpected instance profile ARN: " + runResult.getReservation().getInstances().get(0).getIamInstanceProfile().getArn());
                assertThat(runResult.getReservation().getInstances().get(0).getIamInstanceProfile().getId() != null, "Expected instance profile ID");

                //
                print("Terminating instance: " + instanceId);
                ec2.terminateInstances(new TerminateInstancesRequest().withInstanceIds(instanceId));
            }

            // Run instance with name
            {
                print("Running instance with instance profile name");
                final RunInstancesResult runResult =
                        ec2.runInstances(new RunInstancesRequest()
                                .withImageId(IMAGE_ID)
                                .withMinCount(1)
                                .withMaxCount(1)
                                .withIamInstanceProfile(new IamInstanceProfileSpecification()
                                        .withName(profileName)));
                final String instanceId = getInstancesIds(runResult.getReservation()).get(0);
                print("Launched instance: " + instanceId);
                cleanupTasks.add(new Runnable() {
                    @Override
                    public void run() {
                        print("Terminating instance: " + instanceId);
                        ec2.terminateInstances(new TerminateInstancesRequest().withInstanceIds(instanceId));
                    }
                });

                // Wait for instance
                waitForInstance(ec2, instanceId, "running");

                // Verify instance profile used for instance
                print("Verifying run instances response references instance profile");
                assertThat(runResult.getReservation().getInstances().get(0).getIamInstanceProfile() != null, "Expected instance profile");
                assertThat(profileArn.equals(runResult.getReservation().getInstances().get(0).getIamInstanceProfile().getArn()), "Unexpected instance profile ARN: " + runResult.getReservation().getInstances().get(0).getIamInstanceProfile().getArn());
                assertThat(runResult.getReservation().getInstances().get(0).getIamInstanceProfile().getId() != null, "Expected instance profile ID");

                //
                print("Terminating instance: " + instanceId);
                ec2.terminateInstances(new TerminateInstancesRequest().withInstanceIds(instanceId));
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

    private String waitForInstance(final AmazonEC2 ec2,
                                   final String expectedId,
                                   final String state) throws Exception {
        print("Waiting for instance state " + state);
        String az = null;
        final long startTime = System.currentTimeMillis();
        boolean completed = false;
        while (!completed && (System.currentTimeMillis() - startTime) < TimeUnit.MINUTES.toMillis(15)) {
            final DescribeInstanceStatusResult instanceStatusResult =
                    ec2.describeInstanceStatus(new DescribeInstanceStatusRequest()
                            .withInstanceIds(expectedId)
                            .withIncludeAllInstances(true)
                            .withFilters(new Filter()
                                    .withName("instance-state-name")
                                    .withValues(state)));
            completed = instanceStatusResult.getInstanceStatuses().size() == 1;
            if (completed) {
                az = instanceStatusResult.getInstanceStatuses().get(0).getAvailabilityZone();
                assertThat(expectedId.equals(instanceStatusResult.getInstanceStatuses().get(0).getInstanceId()), "Incorrect instance id");
                assertThat(state.equals(instanceStatusResult.getInstanceStatuses().get(0).getInstanceState().getName()), "Incorrect instance state");
            }
            Thread.sleep(5000);
        }
        assertThat(completed, "Instance not reported within the expected timeout");
        print("Instance reported " + state + " in " + (System.currentTimeMillis() - startTime) + "ms");
        return az;
    }

    private List<String> getInstancesIds(final Reservation... reservations) {
        final List<String> instances = new ArrayList<String>();
        for (final Reservation reservation : reservations) {
            for (final Instance instance : reservation.getInstances()) {
                instances.add(instance.getInstanceId());
            }
        }
        return instances;
    }
}
