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

import com.amazonaws.services.autoscaling.model.*;
import com.amazonaws.services.ec2.model.TerminateInstancesRequest;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

/**
 * This application tests manually setting instance health for auto scaling.
 * 
 * This is verification for the story:
 * 
 * https://eucalyptus.atlassian.net/browse/EUCA-4905
 */
public class TestAutoScalingSetInstanceHealth {
	@SuppressWarnings("unchecked")
	@Test
	public void AutoScalingSetInstanceHealthTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // Create launch configuration
            final String configName = NAME_PREFIX + "SetInstanceHealthTest";
            print( "Creating launch configuration: " + configName );
            as.createLaunchConfiguration( new CreateLaunchConfigurationRequest()
                    .withLaunchConfigurationName( configName )
                    .withImageId( IMAGE_ID )
                    .withInstanceType( INSTANCE_TYPE ) );
            cleanupTasks.add( new Runnable() {
                @Override
                public void run() {
                    print( "Deleting launch configuration: " + configName );
                    deleteLaunchConfig(configName);
                }
            } );

            // Create scaling group
            final String groupName = NAME_PREFIX + "SetInstanceHealthTest";
            print( "Creating auto scaling group: " + groupName );
            as.createAutoScalingGroup( new CreateAutoScalingGroupRequest()
                    .withAutoScalingGroupName( groupName )
                    .withLaunchConfigurationName( configName )
                    .withDesiredCapacity( 1 )
                    .withMinSize( 0 )
                    .withMaxSize( 1 )
                    .withHealthCheckType( "EC2" )
                    .withHealthCheckGracePeriod( 600 ) // 10 minutes
                    .withAvailabilityZones( AVAILABILITY_ZONE )
                    .withTerminationPolicies( "OldestInstance" ) );
            cleanupTasks.add( new Runnable() {
                @Override
                public void run() {
                    print( "Deleting group: " + groupName );
                    deleteAutoScalingGroup(groupName,true);
                }
            } );
            cleanupTasks.add( new Runnable() {
                @Override
                public void run() {
                    final List<String> instanceIds = (List<String>) getInstancesForGroup(groupName, null,true );
                    print( "Terminating instances: " + instanceIds );
                    ec2.terminateInstances( new TerminateInstancesRequest().withInstanceIds( instanceIds ) );
                }
            } );

            // Wait for instances to launch
            print( "Waiting for instance to launch" );
            final long timeout = TimeUnit.MINUTES.toMillis( 2 );
            String instanceId = (String) waitForInstances(timeout,1,groupName,true).get(0);

            // Verify initial health status
            verifyInstanceHealthStatus(instanceId, "Healthy" );

            // Set respecting health check grace period, should be ignored
            as.setInstanceHealth( new SetInstanceHealthRequest().withInstanceId( instanceId ).withHealthStatus( "Unhealthy" ).withShouldRespectGracePeriod( true ) );

            // Verify health status is the same
            verifyInstanceHealthStatus(instanceId, "Healthy" );

            // Set health status
            as.setInstanceHealth( new SetInstanceHealthRequest().withInstanceId( instanceId ).withHealthStatus( "Unhealthy" ).withShouldRespectGracePeriod( false ) );

            // Verify health status changed
            verifyInstanceHealthStatus(instanceId, "Unhealthy" );

            print( "Test complete" );
        } finally {
            // Attempt to clean up anything we created
            Collections.reverse( cleanupTasks );
            for ( final Runnable cleanupTask : cleanupTasks ) {
                try {
                    cleanupTask.run();
                } catch ( Exception e ) {
                    e.printStackTrace();
                }
            }
        }
	}
}
