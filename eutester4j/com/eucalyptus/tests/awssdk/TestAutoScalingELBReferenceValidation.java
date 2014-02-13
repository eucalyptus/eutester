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
 * This application tests reference validation for auto scaling groups with ELB.
 * 
 * This is verification for the story:
 * 
 * https://eucalyptus.atlassian.net/browse/EUCA-5027
 */
public class TestAutoScalingELBReferenceValidation {

	@Test
	public void AutoScalingELBReferenceValidationTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();

        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
            // Generate a load balancer to use
            final String loadBalancer = NAME_PREFIX + "ELBReference";
            print("Creating a load balancer for test use: " + loadBalancer);
            createLoadBalancer(loadBalancer);
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting load balancer: " + loadBalancer);
                    deleteLoadBlancer(loadBalancer);
                }
            });

			// Register cleanup for launch config
            final String launchConfig = NAME_PREFIX + "ELBReferenceTest";
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting launch configuration: " + launchConfig);
					deleteLaunchConfig(launchConfig);
				}
			});

			// Create launch configuration
			print("Creating launch configuration: " + launchConfig);
            createLaunchConfig(launchConfig,IMAGE_ID,INSTANCE_TYPE,null,null,null,null,null,null,null,null);

			// Register cleanup for auto scaling group
            final String groupName = NAME_PREFIX + "ELBReferenceTest";
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting group: " + groupName);
					deleteAutoScalingGroup(groupName,true);
				}
			});

			// Create scaling group with invalid load balancer
			print("Creating auto scaling group with invalid load balancer: " + groupName);
			try {
                Integer minSize = 0;
                Integer maxSize = 2;
                createAutoScalingGroup(groupName,launchConfig, minSize, maxSize,null,AVAILABILITY_ZONE,null,null,null,
                        "invalid load balancer name", null,null);
				assertThat(false, "Creation should fail");
			} catch (AmazonServiceException e) {
				print("Expected error returned: " + e);
			}

			// Create scaling group
			print("Creating auto scaling group: " + groupName);
            Integer minSize = 0;
            Integer maxSize = 1;
            createAutoScalingGroup(groupName, launchConfig,minSize,maxSize,null,AVAILABILITY_ZONE,null,null,null,
                    loadBalancer,null,null);
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
