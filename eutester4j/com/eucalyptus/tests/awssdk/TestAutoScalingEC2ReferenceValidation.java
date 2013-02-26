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
import com.amazonaws.services.ec2.model.CreateKeyPairRequest;
import com.amazonaws.services.ec2.model.CreateSecurityGroupRequest;
import com.amazonaws.services.ec2.model.DeleteKeyPairRequest;
import com.amazonaws.services.ec2.model.DeleteSecurityGroupRequest;
import com.amazonaws.services.ec2.model.DescribeAvailabilityZonesResult;
import com.amazonaws.services.ec2.model.DescribeImagesRequest;
import com.amazonaws.services.ec2.model.DescribeImagesResult;
import com.amazonaws.services.ec2.model.Filter;

/**
 * This application tests reference validation for launch configurations and
 * auto scaling groups.
 * 
 * This is verification for the story:
 * 
 * https://eucalyptus.atlassian.net/browse/EUCA-5024
 */
public class TestAutoScalingEC2ReferenceValidation {

	@Test
	public void AutoScalingEC2ReferenceValidationTest() throws Exception {
		getCloudInfo();
		final AmazonAutoScaling as = getAutoScalingClient(ACCESS_KEY,
				SECRET_KEY, AS_ENDPOINT);
		final AmazonEC2 ec2 = getEc2Client(ACCESS_KEY, SECRET_KEY, EC2_ENDPOINT);
		final String imageId = findImage(ec2);
		final String availabilityZone = findAvalablityZone(ec2);
		final String namePrefix = eucaUUID() + "-";
		print("Using resource prefix for test: " + namePrefix);

		// Find an appropriate image to launch
		final DescribeImagesResult imagesResult = ec2
				.describeImages(new DescribeImagesRequest()
						.withFilters(
								new Filter().withName("image-type").withValues(
										"machine"),
								new Filter().withName("root-device-type")
										.withValues("instance-store"),
								new Filter().withName("kernel-id").withValues(
										"eki-*"),
								new Filter().withName("ramdisk-id").withValues(
										"eri-*")));

		assertThat(imagesResult.getImages().size() > 0,
				"Image not found (image with explicit kernel and ramdisk required)");

		final String kernelId = imagesResult.getImages().get(0).getKernelId();
		final String ramdiskId = imagesResult.getImages().get(0).getRamdiskId();
		print("Using image: " + imageId);
		print("Using kernel: " + kernelId);
		print("Using ramdisk: " + ramdiskId);

		// Find an AZ to use
		final DescribeAvailabilityZonesResult azResult = ec2
				.describeAvailabilityZones();

		assertThat(azResult.getAvailabilityZones().size() > 0,
				"Availability zone not found");

		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			// Generate a key to use
			final String keyName = namePrefix + "EC2ReferenceTest";
			print("Generating an SSH key for test use: " + keyName);
			ec2.createKeyPair(new CreateKeyPairRequest().withKeyName(keyName));
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting SSH key: " + keyName);
					ec2.deleteKeyPair(new DeleteKeyPairRequest()
							.withKeyName(keyName));
				}
			});

			// Generate a security group to use
			final String securityGroupName = namePrefix + "EC2ReferenceTest";
			print("Creating a security group for test use: "
					+ securityGroupName);
			ec2.createSecurityGroup(new CreateSecurityGroupRequest()
					.withGroupName(securityGroupName).withDescription(
							securityGroupName));
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting security group: " + securityGroupName);
					ec2.deleteSecurityGroup(new DeleteSecurityGroupRequest()
							.withGroupName(securityGroupName));
				}
			});

			// Register cleanup for launch config
			final String configName = namePrefix + "EC2ReferenceTest";
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting launch configuration: " + configName);
					as.deleteLaunchConfiguration(new DeleteLaunchConfigurationRequest()
							.withLaunchConfigurationName(configName));
				}
			});

			// Create scaling group with invalid image id
			print("Creating launch configuration with invalid image id: "
					+ configName);
			try {
				as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
						.withLaunchConfigurationName(configName)
						.withImageId("emi-00000000")
						.withInstanceType(INSTANCE_TYPE));
				assertThat(false, "Creation should fail");
			} catch (AmazonServiceException e) {
				print("Expected error returned: " + e);
			}

			// Create scaling group with invalid kernel id
			print("Creating launch configuration with invalid kernel id: "
					+ configName);
			try {
				as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
						.withLaunchConfigurationName(configName)
						.withImageId(imageId).withKernelId("eki-00000000")
						.withInstanceType(INSTANCE_TYPE));
				assertThat(false, "Creation should fail");
			} catch (AmazonServiceException e) {
				print("Expected error returned: " + e);
			}

			// Create scaling group with invalid ramdisk id
			print("Creating launch configuration with invalid ramdisk id: "
					+ configName);
			try {
				as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
						.withLaunchConfigurationName(configName)
						.withImageId(imageId).withRamdiskId("eri-00000000")
						.withInstanceType(INSTANCE_TYPE));
				assertThat(false, "Creation should fail");
			} catch (AmazonServiceException e) {
				print("Expected error returned: " + e);
			}

			// Create scaling group with invalid key name
			print("Creating launch configuration with invalid key name: "
					+ configName);
			try {
				as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
						.withLaunchConfigurationName(configName)
						.withImageId(imageId).withKeyName("invalid key name")
						.withInstanceType(INSTANCE_TYPE));
				assertThat(false, "Creation should fail");
			} catch (AmazonServiceException e) {
				print("Expected error returned: " + e);
			}

			// Create scaling group with invalid security group
			print("Creating launch configuration with invalid security group: "
					+ configName);
			try {
				as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
						.withLaunchConfigurationName(configName)
						.withImageId(imageId)
						.withSecurityGroups("invalid group name")
						.withInstanceType(INSTANCE_TYPE));
				assertThat(false, "Creation should fail");
			} catch (AmazonServiceException e) {
				print("Expected error returned: " + e);
			}

			// Create launch configuration
			print("Creating launch configuration: " + configName);
			as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
					.withLaunchConfigurationName(configName)
					.withImageId(imageId).withKernelId(kernelId)
					.withRamdiskId(ramdiskId).withKeyName(keyName)
					.withSecurityGroups(securityGroupName)
					.withInstanceType(INSTANCE_TYPE));

			// Register cleanup for auto scaling group
			final String groupName = namePrefix + "EC2ReferenceTest";
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
			print("Creating auto scaling group with invalid availability zone: "
					+ groupName);
			try {
				as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
						.withAutoScalingGroupName(groupName)
						.withLaunchConfigurationName(configName).withMinSize(0)
						.withMaxSize(2)
						.withAvailabilityZones("invalid availability zone"));
				assertThat(false, "Creation should fail");
			} catch (AmazonServiceException e) {
				print("Expected error returned: " + e);
			}

			// Create scaling group
			print("Creating auto scaling group: " + groupName);
			as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
					.withAutoScalingGroupName(groupName)
					.withLaunchConfigurationName(configName).withMinSize(0)
					.withMaxSize(2).withAvailabilityZones(availabilityZone));

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
