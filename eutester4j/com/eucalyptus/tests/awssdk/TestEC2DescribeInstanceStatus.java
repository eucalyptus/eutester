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

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;
import org.testng.annotations.Test;
import com.amazonaws.services.ec2.AmazonEC2;
import com.amazonaws.services.ec2.model.DescribeInstanceStatusRequest;
import com.amazonaws.services.ec2.model.DescribeInstanceStatusResult;
import com.amazonaws.services.ec2.model.Filter;
import com.amazonaws.services.ec2.model.Instance;
import com.amazonaws.services.ec2.model.InstanceStatus;
import com.amazonaws.services.ec2.model.InstanceStatusSummary;
import com.amazonaws.services.ec2.model.Reservation;
import com.amazonaws.services.ec2.model.RunInstancesRequest;
import com.amazonaws.services.ec2.model.RunInstancesResult;
import com.amazonaws.services.ec2.model.TerminateInstancesRequest;

/**
 * This application tests the EC2 DescribeInstanceStatus operation.
 * 
 * This is verification for the task:
 * 
 * https://eucalyptus.atlassian.net/browse/EUCA-5052
 */
public class TestEC2DescribeInstanceStatus {

	@Test
	public void EC2DescribeInstanceStatusTest() throws Exception {
		final String credpath = "/Users/tony/Desktop/as_test_cloud/eucarc";
		final String ec2Endpoint = parseEucarc(credpath, "EC2_URL") + "/";
		final String secretKey = parseEucarc(credpath, "EC2_SECRET_KEY")
				.replace("'", "");
		final String accessKey = parseEucarc(credpath, "EC2_ACCESS_KEY")
				.replace("'", "");
		final AmazonEC2 ec2 = getEc2Client(accessKey, secretKey, ec2Endpoint);
		final String imageId = findImage(ec2);
		final String namePrefix = eucaUUID() + "-";
		logger.info("Using resource prefix for test: " + namePrefix);

		// End discovery, start test
		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			// Create launch configuration
			logger.info("Running instance");
			final RunInstancesResult runResult = ec2
					.runInstances(new RunInstancesRequest()
							.withImageId(imageId).withMinCount(1)
							.withMaxCount(1));
			final String instanceId = getInstancesIds(
					runResult.getReservation()).get(0);
			logger.info("Launched instance: " + instanceId);
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					logger.info("Terminating instance: " + instanceId);
					ec2.terminateInstances(new TerminateInstancesRequest()
							.withInstanceIds(instanceId));
				}
			});

			// Wait for instance
			final long timeout = TimeUnit.MINUTES.toMillis(1);
			waitForInstance(ec2, timeout, instanceId, "pending");
			final String az = waitForInstance(ec2, timeout, instanceId,
					"running");

			// Verify response format
			final DescribeInstanceStatusResult instanceStatusResult = ec2
					.describeInstanceStatus(new DescribeInstanceStatusRequest()
							.withInstanceIds(instanceId));
			assertThat(instanceStatusResult.getInstanceStatuses().size() == 1,
					"Instance not found");
			final InstanceStatus status = instanceStatusResult
					.getInstanceStatuses().get(0);
			assertThat(status != null, "Null instance status");
			assertThat(status.getAvailabilityZone() != null,
					"Missing availability zone");
			assertThat(instanceId.equals(status.getInstanceId()),
					"Unexpected instance id : " + status.getInstanceId());
			assertThat(status.getInstanceState() != null,
					"Missing instance state");
			assertThat(status.getInstanceState().getCode() == 16,
					"Unexpected instance state code : "
							+ status.getInstanceState().getCode());
			assertThat("running".equals(status.getInstanceState().getName()),
					"Unexpected instance state name : "
							+ status.getInstanceState().getName());
			assertStatusSummary(status.getInstanceStatus(), "instance");
			assertStatusSummary(status.getSystemStatus(), "system");

			// Test selection with filters
			String[][] filterTestValues = {
					{ "availability-zone", az, "invalid-zone-name" },
					{ "instance-state-name", "running", "pending" },
					{ "instance-state-code", "16", "0" },
					{ "system-status.status", "ok", "impaired" },
					{ "system-status.reachability", "passed", "failed" },
					{ "instance-status.status", "ok", "impaired" },
					{ "instance-status.reachability", "passed", "failed" }, };
			for (final String[] values : filterTestValues) {
				final String filterName = values[0];
				final String filterGoodValue = values[1];
				final String filterBadValue = values[2];

				logger.info("Testing filter - " + filterName);
				assertThat(
						describeInstanceStatus(ec2, instanceId, filterName,
								filterGoodValue, 1), "Expected result for "
								+ filterName + "=" + filterGoodValue);
				assertThat(
						describeInstanceStatus(ec2, instanceId, filterName,
								filterBadValue, 0), "Expected no results for "
								+ filterName + "=" + filterBadValue);
			}

			logger.info("Test complete");
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

	private void assertStatusSummary(final InstanceStatusSummary status,
			final String description) {
		assertThat(status != null, "Missing " + description + " status");
		assertThat(
				Arrays.asList("ok", "impaired", "initializing",
						"insufficient-data", "not-applicable").contains(
						status.getStatus()),
				"Invalid status value: " + status.getStatus());
		assertThat(status.getDetails() != null, "Missing status details");
		assertThat(status.getDetails().size() == 1,
				"Unexpected details count: " + status.getDetails().size());
		assertThat("reachability".equals(status.getDetails().get(0).getName()),
				"Unexpected details type: "
						+ status.getDetails().get(0).getName());
		assertThat(
				Arrays.asList("passed", "failed", "initializing",
						"insufficient-data").contains(
						status.getDetails().get(0).getStatus()),
				"Invalid details value: "
						+ status.getDetails().get(0).getStatus());
	}

	private boolean describeInstanceStatus(final AmazonEC2 ec2,
			final String instanceId, final String filterName,
			final String filterValue, final int expectedCount) {
		final DescribeInstanceStatusResult instanceStatusResult = ec2
				.describeInstanceStatus(new DescribeInstanceStatusRequest()
						.withInstanceIds(instanceId).withFilters(
								new Filter().withName(filterName).withValues(
										filterValue)));
		return instanceStatusResult.getInstanceStatuses().size() == expectedCount;
	}

	private String waitForInstance(final AmazonEC2 ec2, final long timeout,
			final String expectedId, final String state) throws Exception {
		logger.info("Waiting for instance state " + state);
		String az = null;
		final long startTime = System.currentTimeMillis();
		boolean completed = false;
		while (!completed && (System.currentTimeMillis() - startTime) < timeout) {
			final DescribeInstanceStatusResult instanceStatusResult = ec2
					.describeInstanceStatus(new DescribeInstanceStatusRequest()
							.withInstanceIds(expectedId)
							.withIncludeAllInstances(true)
							.withFilters(
									new Filter()
											.withName("instance-state-name")
											.withValues(state)));
			completed = instanceStatusResult.getInstanceStatuses().size() == 1;
			if (completed) {
				az = instanceStatusResult.getInstanceStatuses().get(0)
						.getAvailabilityZone();
				assertThat(
						expectedId.equals(instanceStatusResult
								.getInstanceStatuses().get(0).getInstanceId()),
						"Incorrect instance id");
				assertThat(
						state.equals(instanceStatusResult.getInstanceStatuses()
								.get(0).getInstanceState().getName()),
						"Incorrect instance state");
			}
			sleep(5);
		}
		assertThat(completed,
				"Instance not reported within the expected timeout");
		logger.info("Instance reported " + state + " in "
				+ (System.currentTimeMillis() - startTime) + "ms");
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
