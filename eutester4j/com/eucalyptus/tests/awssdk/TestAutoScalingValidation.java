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
import com.amazonaws.services.autoscaling.model.*;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

/**
 * This application tests parameter validation for auto scaling.
 * <p/>
 * This is verification for the story:
 * <p/>
 * https://eucalyptus.atlassian.net/browse/EUCA-5016
 */
public class TestAutoScalingValidation {

    @Test
    public void AutoScalingValidationTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();

        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // Register cleanup for launch configs
            final String configName = NAME_PREFIX + "ValidationTest";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting launch configuration: " + configName);
                    deleteLaunchConfig(configName);
                }
            });

            // Create launch configuration with invalid name
            print("Creating launch configuration with invalid name: " + configName + ":");
            try {
                as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
                        .withLaunchConfigurationName(configName + ":")
                        .withImageId(IMAGE_ID)
                        .withInstanceType(INSTANCE_TYPE));
                assertThat(false, "Expected error when creating launch configuration with invalid name");
            } catch (AmazonServiceException e) {
                print("Got expected exception: " + e);
            }

            // Create launch configuration with missing required parameter
            print("Creating launch configuration with missing parameter: " + configName);
            try {
                as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
                        .withLaunchConfigurationName(configName + ":")
                        .withInstanceType(INSTANCE_TYPE));
                assertThat(false, "Expected error when creating launch configuration with missing parameter");
            } catch (AmazonServiceException e) {
                print("Got expected exception: " + e);
            }

            // Create launch configuration
            print("Creating launch configuration: " + configName);
            as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
                    .withLaunchConfigurationName(configName)
                    .withImageId(IMAGE_ID)
                    .withInstanceType(INSTANCE_TYPE));

            // Register cleanup for auto scaling groups
            final String groupName = NAME_PREFIX + "ValidationTest";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting group: " + groupName);
                    deleteAutoScalingGroup(groupName,true);
                }
            });

            // Create scaling group with invalid size
            print("Creating auto scaling group with invalid size: " + groupName);
            try {
                as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
                        .withAutoScalingGroupName(groupName)
                        .withLaunchConfigurationName(configName)
                        .withMinSize(-1)
                        .withMaxSize(1)
                        .withAvailabilityZones(AVAILABILITY_ZONE)
                );
                assertThat(false, "Expected error when creating launch group with invalid size");
            } catch (AmazonServiceException e) {
                print("Got expected exception: " + e);
            }

            // Create scaling group with invalid capacity
            print("Creating auto scaling group with invalid capacity: " + groupName);
            try {
                as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
                        .withAutoScalingGroupName(groupName)
                        .withLaunchConfigurationName(configName)
                        .withMinSize(1)
                        .withMaxSize(1)
                        .withDesiredCapacity(2)
                        .withAvailabilityZones(AVAILABILITY_ZONE)
                );
                assertThat(false, "Expected error when creating launch group with invalid capacity");
            } catch (AmazonServiceException e) {
                print("Got expected exception: " + e);
            }

            // Create scaling group with invalid tag
            print("Creating auto scaling group with invalid tag: " + groupName);
            char[] nameSuffixChars = new char[128];
            Arrays.fill(nameSuffixChars, '1');
            String nameSuffix = new String(nameSuffixChars);
            try {
                as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
                        .withAutoScalingGroupName(groupName)
                        .withLaunchConfigurationName(configName)
                        .withMinSize(0)
                        .withMaxSize(0)
                        .withAvailabilityZones(AVAILABILITY_ZONE)
                        .withTags(
                                new Tag().withKey("tag1" + nameSuffix).withValue("propagate").withPropagateAtLaunch(Boolean.TRUE)
                        )
                );
                assertThat(false, "Expected error when creating launch group with invalid tag");
            } catch (AmazonServiceException e) {
                print("Got expected exception: " + e);
            }

            // Create scaling group
            print("Creating auto scaling group: " + groupName);
            as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
                    .withAutoScalingGroupName(groupName)
                    .withLaunchConfigurationName(configName)
                    .withMinSize(0)
                    .withMaxSize(0)
                    .withAvailabilityZones(AVAILABILITY_ZONE));

            // Create tag on invalid group
            print("Creating tag on invalid group: " + groupName + ".invalid");
            try {
                as.createOrUpdateTags(new CreateOrUpdateTagsRequest().withTags(
                        new Tag().withResourceType("auto-scaling-group").withResourceId(groupName + ".invalid").withKey("tag1").withValue("propagate").withPropagateAtLaunch(Boolean.TRUE)
                ));
                assertThat(false, "Expected error when creating tag on invalid group");
            } catch (AmazonServiceException e) {
                print("Got expected exception: " + e);
            }

            // Register cleanup for launch configs
            final String policyName = NAME_PREFIX + "ValidationTest";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting scaling policy: " + policyName);
                    as.deletePolicy(new DeletePolicyRequest().withAutoScalingGroupName(groupName).withPolicyName(policyName));
                }
            });

            // Create invalid scaling policy
            try {
                as.putScalingPolicy(new PutScalingPolicyRequest()
                        .withAutoScalingGroupName(groupName)
                        .withPolicyName(policyName)
                        .withScalingAdjustment(1)
                        .withAdjustmentType("ExactCapacity")
                        .withMinAdjustmentStep(1)
                );
                assertThat(false, "Expected error when creating invalid scaling policy");
            } catch (AmazonServiceException e) {
                print("Got expected exception: " + e);
            }

            // Create invalid scaling policy
            try {
                as.putScalingPolicy(new PutScalingPolicyRequest()
                        .withAutoScalingGroupName(groupName)
                        .withPolicyName(policyName)
                        .withScalingAdjustment(-1)
                        .withAdjustmentType("ExactCapacity")
                );
                assertThat(false, "Expected error when creating invalid scaling policy");
            } catch (AmazonServiceException e) {
                print("Got expected exception: " + e);
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
