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
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

/**
 * This application tests RunInstances with a client token.
 * <p/>
 * This is verification for the task:
 * <p/>
 * https://eucalyptus.atlassian.net/browse/EUCA-5346
 */
public class TestEC2RunInstancesClientToken {

    @Test
    public void EC2RunInstancesClientTokenTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        // End discovery, start test
        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // Run instance with client token
            final String clientToken = UUID.randomUUID().toString() + "-ClientToken";
            print("Running instance with client token: " + clientToken);
            final RunInstancesResult runResult =
                    ec2.runInstances(new RunInstancesRequest()
                            .withImageId(IMAGE_ID)
                            .withClientToken(clientToken)
                            .withMinCount(1)
                            .withMaxCount(1));
            final String instanceId = getInstancesIds(runResult.getReservation()).get(0);
            print("Launched instance: " + instanceId);
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Terminating instance: " + instanceId);
                    ec2.terminateInstances(new TerminateInstancesRequest().withInstanceIds(instanceId));
                }
            });

            // Rerunning instance with client token
            final RunInstancesResult runResult2 =
                    ec2.runInstances(new RunInstancesRequest()
                            .withImageId(IMAGE_ID)
                            .withClientToken(clientToken)
                            .withMinCount(1)
                            .withMaxCount(1));
            final String instanceId2 = getInstancesIds(runResult2.getReservation()).get(0);
            print("Launched instance: " + instanceId2);
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Terminating instance: " + instanceId2);
                    ec2.terminateInstances(new TerminateInstancesRequest().withInstanceIds(instanceId2));
                }
            });

            assertThat(instanceId2.equals(instanceId), "Instance identifiers did not match");

            // Test client token filter
            print("Describing instances using client token filter");
            {
                final DescribeInstancesResult describeInstancesResult =
                        ec2.describeInstances(new DescribeInstancesRequest().withFilters(
                                new Filter().withName("client-token").withValues(clientToken)));
                final List<String> describedInstances = getInstancesIds(describeInstancesResult.getReservations());
                assertThat(describedInstances.size() == 1, "Expected one instance");
                assertThat(instanceId.equals(describedInstances.get(0)), "Unexpected instance id: " + describedInstances.get(0));
            }

            // Terminate instance
            print("Terminating instance: " + instanceId);
            sleep(10); // small buffer
            ec2.terminateInstances(new TerminateInstancesRequest().withInstanceIds(instanceId));
            waitForInstanceToTerminate(ec2, TimeUnit.MINUTES.toMillis(10), instanceId);

            // Rerun instance with client token
            final RunInstancesResult runResult3 =
                    ec2.runInstances(new RunInstancesRequest()
                            .withImageId(IMAGE_ID)
                            .withClientToken(clientToken)
                            .withMinCount(1)
                            .withMaxCount(1));
            final String instanceId3 = getInstancesIds(runResult3.getReservation()).get(0);
            print("Launched instance: " + instanceId3);
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Terminating instance: " + instanceId3);
                    ec2.terminateInstances(new TerminateInstancesRequest().withInstanceIds(instanceId3));
                }
            });

            assertThat(instanceId3.equals(instanceId), "Instance identifiers did not match (after termination)");

            // Test client token filter after termination
            print("Describing instances using client token filter (after termination)");
            {
                final DescribeInstancesResult describeInstancesResult =
                        ec2.describeInstances(new DescribeInstancesRequest().withFilters(
                                new Filter().withName("client-token").withValues(clientToken)));
                final List<String> describedInstances = getInstancesIds(describeInstancesResult.getReservations());
                assertThat(describedInstances.size() == 1, "Expected one instance");
                assertThat(instanceId.equals(describedInstances.get(0)), "Unexpected instance id: " + describedInstances.get(0));
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

    private List<String> getInstancesIds(final Reservation reservation) {
        return getInstancesIds(Collections.singletonList(reservation));
    }

    private List<String> getInstancesIds(final List<Reservation> reservations) {
        final List<String> instances = new ArrayList<String>();
        for (final Reservation reservation : reservations) {
            for (final Instance instance : reservation.getInstances()) {
                instances.add(instance.getInstanceId());
            }
        }
        return instances;
    }

    private void waitForInstanceToTerminate(final AmazonEC2 ec2,
                                            final long timeout,
                                            final String instanceId) throws Exception {
        final long startTime = System.currentTimeMillis();
        boolean completed = false;
        outer:
        while ((System.currentTimeMillis() - startTime) < timeout) {
            Thread.sleep(5000);

            final DescribeInstancesResult instancesResult = ec2.describeInstances(new DescribeInstancesRequest().withInstanceIds(
                    instanceId
            ));
            for (final Reservation reservation : instancesResult.getReservations()) {
                for (final Instance instance : reservation.getInstances()) {
                    if ("terminated".equals(instance.getState().getName())) {
                        completed = true;
                        break outer;
                    }
                }
            }
        }
        assertThat(completed, "Instance did not terminate within the expected timeout");
        print("Instance terminated in " + (System.currentTimeMillis() - startTime) + "ms");
    }
}
