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
 * This application tests reference validation for VM types.
 * <p/>
 * This is verification for the story:
 * <p/>
 * https://eucalyptus.atlassian.net/browse/EUCA-5134
 */
public class TestAutoScalingVMTypeReferenceValidation {

    @Test
    public void AutoScalingVMTypeReferenceValidationTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();

        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // Register cleanup for launch config
            final String launchConfig = NAME_PREFIX + "VMTypeReferenceTest";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting launch configuration: " + launchConfig);
                    deleteLaunchConfig(launchConfig);
                }
            });

            // Create launch configuration with invalid vm type
            print("Creating launch configuration with invalid vm type: " + launchConfig);
            try {
                String instanceType =  NAME_PREFIX+"-invalid";
                createLaunchConfig(launchConfig,IMAGE_ID,instanceType,null,null,null,null,null,null,null,null);
                assertThat(false, "Creation should fail");
                INSTANCE_TYPE = "m1.small";
            } catch (AmazonServiceException ase) {
                print("Expected error returned: " + ase);
            }

            // Create launch configuration
            print("Creating launch configuration: " + launchConfig);
            createLaunchConfig(launchConfig,IMAGE_ID,INSTANCE_TYPE,null,null,null,null,null,null,null,null);
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
