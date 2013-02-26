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

import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import com.amazonaws.AmazonServiceException;
import com.amazonaws.services.autoscaling.AmazonAutoScaling;
import com.amazonaws.services.autoscaling.model.CreateAutoScalingGroupRequest;
import com.amazonaws.services.autoscaling.model.CreateLaunchConfigurationRequest;
import com.amazonaws.services.autoscaling.model.DeleteAutoScalingGroupRequest;
import com.amazonaws.services.autoscaling.model.DeleteLaunchConfigurationRequest;
import com.amazonaws.services.ec2.AmazonEC2;
import com.amazonaws.services.elasticloadbalancing.AmazonElasticLoadBalancing;
import com.amazonaws.services.elasticloadbalancing.model.CreateLoadBalancerRequest;
import com.amazonaws.services.elasticloadbalancing.model.DeleteLoadBalancerRequest;
import com.amazonaws.services.elasticloadbalancing.model.Listener;

/**
 * This application tests reference validation for auto scaling groups with ELB.
 * 
 * This is verification for the story:
 * 
 * https://eucalyptus.atlassian.net/browse/EUCA-5027
 */
public class TestAutoScalingELBReferenceValidation {

	@Test
	public void AutoScalingELBReferenceValidationTest() throws Exception {
		getCloudInfo();
		final AmazonAutoScaling as = getAutoScalingClient(ACCESS_KEY,
				SECRET_KEY, AS_ENDPOINT);
		final AmazonEC2 ec2 = getEc2Client(ACCESS_KEY, SECRET_KEY, EC2_ENDPOINT);
		final AmazonElasticLoadBalancing elb = getElbClient(ACCESS_KEY,
				SECRET_KEY, ELB_ENDPOINT);
		final String imageId = findImage(ec2);
		final String availabilityZone = findAvalablityZone(ec2);
		final String namePrefix = eucaUUID() + "-";
		print("Using resource prefix for test: " + namePrefix);

		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			// Generate a load balancer to use
			final String loadBalancerName = namePrefix + "ELBReferenceTest";
			print("Creating a load balancer for test use: " + loadBalancerName);
			elb.createLoadBalancer(new CreateLoadBalancerRequest()
					.withLoadBalancerName(loadBalancerName)
					.withAvailabilityZones(availabilityZone)
					.withListeners(
							new Listener().withInstancePort(8888)
									.withLoadBalancerPort(8888)
									.withProtocol("HTTP")));
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting load balancer: " + loadBalancerName);
					elb.deleteLoadBalancer(new DeleteLoadBalancerRequest()
							.withLoadBalancerName(loadBalancerName));
				}
			});

			// Register cleanup for launch config
			final String configName = namePrefix + "ELBReferenceTest";
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting launch configuration: " + configName);
					as.deleteLaunchConfiguration(new DeleteLaunchConfigurationRequest()
							.withLaunchConfigurationName(configName));
				}
			});

			// Create launch configuration
			print("Creating launch configuration: " + configName);
			as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
					.withLaunchConfigurationName(configName)
					.withImageId(imageId).withInstanceType(INSTANCE_TYPE));

			// Register cleanup for auto scaling group
			final String groupName = namePrefix + "ELBReferenceTest";
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting group: " + groupName);
					as.deleteAutoScalingGroup(new DeleteAutoScalingGroupRequest()
							.withAutoScalingGroupName(groupName)
							.withForceDelete(true));
				}
			});

			// Create scaling group with invalid availability zone
			print("Creating auto scaling group with invalid load balancer: "
					+ groupName);
			try {
				as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
						.withAutoScalingGroupName(groupName)
						.withLaunchConfigurationName(configName).withMinSize(0)
						.withMaxSize(2).withAvailabilityZones(availabilityZone)
						.withLoadBalancerNames("invalid load balancer name"));
				assertThat(false, "Creation should fail");
			} catch (AmazonServiceException e) {
				print("Expected error returned: " + e);
			}

			// Create scaling group
			print("Creating auto scaling group: " + groupName);
			as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
					.withAutoScalingGroupName(groupName)
					.withLaunchConfigurationName(configName).withMinSize(0)
					.withMaxSize(1).withAvailabilityZones(availabilityZone)
					.withLoadBalancerNames(loadBalancerName));

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
