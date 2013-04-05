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

import com.amazonaws.AmazonServiceException;
import com.amazonaws.services.autoscaling.model.CreateAutoScalingGroupRequest;
import com.amazonaws.services.autoscaling.model.CreateLaunchConfigurationRequest;
import com.amazonaws.services.autoscaling.model.DeleteAutoScalingGroupRequest;
import com.amazonaws.services.autoscaling.model.DeleteLaunchConfigurationRequest;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

/**
 * This application tests unsupported options for auto scaling.
 * <p/>
 * This is verification for the story:
 * <p/>
 * https://eucalyptus.atlassian.net/browse/EUCA-5200
 */
public class TestAutoScalingUnsupportedOptions {

    @Test
    public void AutoScalingUnsupportedOptionsTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();

        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // Add clean up for configuration
            final String configName = NAME_PREFIX + "OptionsTest";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting launch configuration: " + configName);
                    as.deleteLaunchConfiguration(new DeleteLaunchConfigurationRequest().withLaunchConfigurationName(configName));
                }
            });

            // Create invalid launch configuration
            print("Creating launch configuration with invalid spot price: " + configName);
            try {
                as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
                        .withLaunchConfigurationName(configName)
                        .withImageId(IMAGE_ID)
                        .withInstanceType(INSTANCE_TYPE)
                        .withSpotPrice("foo")
                );
                assertThat(false, "Expected error");
            } catch (AmazonServiceException e) {
                print("Got expected exception: " + e);
            }

            // Create launch configuration
            print("Creating launch configuration with spot price: " + configName);
            as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
                    .withLaunchConfigurationName(configName)
                    .withImageId(IMAGE_ID)
                    .withInstanceType(INSTANCE_TYPE)
                    .withSpotPrice("0.045")
            );

            // Add clean up for group
            final String groupName = NAME_PREFIX + "OptionsTest";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting group: " + groupName);
                    as.deleteAutoScalingGroup(new DeleteAutoScalingGroupRequest().withAutoScalingGroupName(groupName).withForceDelete(true));
                }
            });

            // Create scaling group
            print("Creating auto scaling group with VPC zone identifier: " + groupName);
            try {
                as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
                        .withAutoScalingGroupName(groupName)
                        .withLaunchConfigurationName(configName)
                        .withMinSize(0)
                        .withMaxSize(0)
                        .withAvailabilityZones(AVAILABILITY_ZONE)
                        .withVPCZoneIdentifier("test"));
                assertThat(false, "Expected error");
            } catch (AmazonServiceException e) {
                print("Got expected exception: " + e);
            }

            // Create scaling group
            print("Creating auto scaling group with placement group: " + groupName);
            try {
                as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
                        .withAutoScalingGroupName(groupName)
                        .withLaunchConfigurationName(configName)
                        .withMinSize(0)
                        .withMaxSize(0)
                        .withAvailabilityZones(AVAILABILITY_ZONE)
                        .withPlacementGroup("test"));
                assertThat(false, "Expected error");
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
