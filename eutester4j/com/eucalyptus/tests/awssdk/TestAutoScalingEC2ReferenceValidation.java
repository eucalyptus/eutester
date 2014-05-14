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

import com.amazonaws.AmazonServiceException;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

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
        testInfo(this.getClass().getSimpleName());
		getCloudInfo();

		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			// Generate a key to use
			final String keyName = NAME_PREFIX + "EC2ReferenceTest";
			print("Generating an SSH key for test use: " + keyName);
            createKeyPair(keyName);
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting SSH key: " + keyName);
					deleteKeyPair(keyName);
				}
			});

			// Generate a security group to use
			final String securityGroupName = NAME_PREFIX + "EC2ReferenceTest";
			print("Creating a security group for test use: "
					+ securityGroupName);
            createSecurityGroup(securityGroupName, securityGroupName);
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting security group: " + securityGroupName);
					deleteSecurityGroup(securityGroupName);
				}
			});

			// Register cleanup for launch config
			final String launchConfig = NAME_PREFIX + "EC2ReferenceTest";
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting launch configuration: " + launchConfig);
					deleteLaunchConfig(launchConfig);
				}
			});

			// Create scaling group with invalid image id
			print("Creating launch configuration with invalid image id: " + launchConfig);
			try {
                createLaunchConfig(launchConfig,"emi-00000000",INSTANCE_TYPE,null,null,null,null,null,null,null,null);
                assertThat(false, "Creation should fail");
			} catch (AmazonServiceException e) {
				print("Expected error returned: " + e);
			}

			// Create scaling group with invalid kernel id
			print("Creating launch configuration with invalid kernel id: " + launchConfig);
			try {
                createLaunchConfig(launchConfig,IMAGE_ID,INSTANCE_TYPE,null,null,"eki-00000000",null,null,null,null,null);
				assertThat(false, "Creation should fail");
			} catch (AmazonServiceException e) {
				print("Expected error returned: " + e);
			}

			// Create scaling group with invalid ramdisk id
			print("Creating launch configuration with invalid ramdisk id: " + launchConfig);
			try {
                createLaunchConfig(launchConfig,IMAGE_ID,INSTANCE_TYPE,null,null,null,"eri-00000000",null,null,null,null);
				assertThat(false, "Creation should fail");
			} catch (AmazonServiceException e) {
				print("Expected error returned: " + e);
			}

			// Create scaling group with invalid key name
			print("Creating launch configuration with invalid key name: " + launchConfig);
			try {
                createLaunchConfig(launchConfig,IMAGE_ID,INSTANCE_TYPE,"invalid key name",null,null,null,null,null,null,null);
				assertThat(false, "Creation should fail");
			} catch (AmazonServiceException e) {
				print("Expected error returned: " + e);
			}

			// Create scaling group with invalid security group
			print("Creating launch configuration with invalid security group: " + launchConfig);
			try {
                createLaunchConfig(launchConfig,IMAGE_ID,INSTANCE_TYPE,null,"invalid group name",null,null,null,null,null,null);
				assertThat(false, "Creation should fail");
			} catch (AmazonServiceException e) {
				print("Expected error returned: " + e);
			}

			// Create launch configuration
			print("Creating launch configuration: " + launchConfig);
            if (isHVM()){
                print("Using hvm image, not specifying kernel and ramdisk for Launch Config");
                createLaunchConfig(launchConfig,IMAGE_ID,INSTANCE_TYPE,keyName,securityGroupName,null,null,null, null,
                        null,null);
            }
            else {
                print("Using para-virt image specifying kernel and ramdisk for Launch Config");
                createLaunchConfig(launchConfig, IMAGE_ID, INSTANCE_TYPE, keyName, securityGroupName, KERNEL_ID, RAMDISK_ID,
                        null, null, null, null);
            }
			// Register cleanup for auto scaling group
            final String groupName = NAME_PREFIX + "EC2ReferenceTest";
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting group: " + groupName);
					deleteAutoScalingGroup(groupName,true);
				}
			});

			// Create scaling group with invalid availability zone
			print("Creating auto scaling group with invalid availability zone: " + groupName);
			try {
                Integer minSize = 0;
                Integer maxSize = 2;
                createAutoScalingGroup(groupName,launchConfig,minSize,maxSize,null,"invalid availability zone",null,
                        null,null,null,null,null);
				assertThat(false, "Creation should fail");
			} catch (AmazonServiceException e) {
				print("Expected error returned: " + e);
			}

			// Create scaling group
			print("Creating auto scaling group: " + groupName);
            Integer minSize = 0;
            Integer maxSize = 2;
            createAutoScalingGroup(groupName,launchConfig,minSize,maxSize,null,AVAILABILITY_ZONE,null,null,null,null,
                    null,null);
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
