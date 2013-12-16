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

import com.amazonaws.services.autoscaling.AmazonAutoScaling;
import com.amazonaws.services.autoscaling.AmazonAutoScalingClient;
import com.amazonaws.services.autoscaling.model.*;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

/**
 * This application tests auto scaling administrative extensions.
 *
 * This tests requires administrative privileges to be separately configured.
 *
 * https://github.com/eucalyptus/architecture/wiki/autoscaling-3.3-design#wiki-Administrative_Functionality
 */
public class TestAutoScalingAdministration {

    @Test
    public void AutoscalingAdminitrationTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();



        // End discovery, start test
        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            print( "Using prefix for test: " + NAME_PREFIX );

            // create non-admin user in non-euca account then get credentials and connection for user
            final String user = NAME_PREFIX + "user";
            final String account = NAME_PREFIX + "account";
            createAccount(account);
            createUser(account, user);
            createIAMPolicy(account, user, NAME_PREFIX + "policy", null);
            final AmazonAutoScaling as_user = new AmazonAutoScalingClient(getUserCreds(account, user));
            as_user.setEndpoint(AS_ENDPOINT);
            cleanupTasks.add( new Runnable() {
                @Override
                public void run() {
                    print( "Deleting account: " + account );
                    deleteAccount(account);
                }
            } );

            // Create launch configuration
            final String launchConfigurationName = NAME_PREFIX + "Config1";
            print( "Creating launch configuration: " + launchConfigurationName );
            as_user.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
                    .withImageId(IMAGE_ID)
                    .withInstanceType("m1.small")
                    .withLaunchConfigurationName(launchConfigurationName)
            );
            cleanupTasks.add( new Runnable() {
                @Override
                public void run() {
                    print( "Deleting launch configuration: " + launchConfigurationName );
                    as_user.deleteLaunchConfiguration(new DeleteLaunchConfigurationRequest().withLaunchConfigurationName(launchConfigurationName));
                }
            } );

            // List launch configuration
            print( "Testing admin listing for launch configurations" );
            final List<LaunchConfiguration> configurations = as.describeLaunchConfigurations( new DescribeLaunchConfigurationsRequest()
                    .withLaunchConfigurationNames( "verbose", launchConfigurationName )
            ).getLaunchConfigurations( );
            int size = configurations==null ? 0 : configurations.size();
            assertThat( size==1, "Unexpected launch configuration count: " + size );
            final String configArn = configurations.get( 0 ).getLaunchConfigurationARN();

            // Create group
            final String groupName = NAME_PREFIX + "Group1";
            print( "Creating group: " + groupName );
            as_user.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
                    .withMinSize(0)
                    .withMaxSize(2)
                    .withAvailabilityZones(AVAILABILITY_ZONE)
                    .withLaunchConfigurationName(launchConfigurationName)
                    .withAutoScalingGroupName(groupName)
            );
            cleanupTasks.add( new Runnable() {
                @Override
                public void run() {
                    print( "Deleting group: " + groupName );
                    as_user.deleteAutoScalingGroup(new DeleteAutoScalingGroupRequest().withAutoScalingGroupName(groupName));
                }
            } );

            // List group
            print( "Testing admin listing for groups" );
            final List<AutoScalingGroup> groups = as.describeAutoScalingGroups( new DescribeAutoScalingGroupsRequest()
                    .withAutoScalingGroupNames( "verbose", groupName )
            ).getAutoScalingGroups();
            int groupsSize = groups==null ? 0 : groups.size();
            assertThat( groupsSize == 1, "Unexpected group count: " + groupsSize );
            final String groupArn = groups.get( 0 ).getAutoScalingGroupARN();

            // Create policy
            final String policyName = "Policy1";
            print( "Creating policy: " + policyName );
            as_user.putScalingPolicy(new PutScalingPolicyRequest()
                    .withAdjustmentType("ExactCapacity")
                    .withScalingAdjustment(2)
                    .withAutoScalingGroupName(groupName)
                    .withPolicyName(policyName)
            );
            cleanupTasks.add( new Runnable() {
                @Override
                public void run() {
                    print( "Deleting policy: " + policyName );
                    as_user.deletePolicy(new DeletePolicyRequest().withAutoScalingGroupName(groupName).withPolicyName(policyName));
                }
            } );

            // List policies
            print( "Testing admin listing for policies" );
            final List<ScalingPolicy> policies = as.describePolicies( new DescribePoliciesRequest()
                    .withPolicyNames( "verbose", policyName )
            ).getScalingPolicies();
            int policySize = policies==null ? 0 : policies.size();
            assertThat(policySize == 1, "Unexpected policy count: " + policySize);
            final String policyArn = policies.get(0).getPolicyARN();

            // Test administrative updates
            print( "Testing admin metrics collection update" );
            as_user.disableMetricsCollection(new DisableMetricsCollectionRequest().withAutoScalingGroupName(groupArn));
            AutoScalingGroup group = getGroup( as, groupArn );
            assertThat(group != null && group.getEnabledMetrics().isEmpty(), "Expected no enabled metrics");
            as_user.enableMetricsCollection(new EnableMetricsCollectionRequest().withAutoScalingGroupName(groupArn).withGranularity("1Minute"));
            group = getGroup( as, groupArn );
            assertThat(group != null && !group.getEnabledMetrics().isEmpty(), "Expected enabled metrics");
            as_user.disableMetricsCollection(new DisableMetricsCollectionRequest().withAutoScalingGroupName(groupArn));
            group = getGroup( as, groupArn );
            assertThat(group != null && group.getEnabledMetrics().isEmpty(), "Expected no enabled metrics");

            print("Testing admin process suspend");
            assertThat( group!=null && group.getSuspendedProcesses().isEmpty(), "Expected no suspended processes" );
            as_user.suspendProcesses(new SuspendProcessesRequest().withAutoScalingGroupName(groupArn));
            group = getGroup( as, groupArn );
            assertThat(group != null && !group.getSuspendedProcesses().isEmpty(), "Expected suspended processes");

            print("Testing admin set desired capacity");
            assertThat( group!=null && 0==group.getDesiredCapacity(), "Expected group size 0" );
            as_user.setDesiredCapacity(new SetDesiredCapacityRequest().withAutoScalingGroupName(groupArn).withDesiredCapacity(1));
            group = getGroup( as, groupArn );
            assertThat(group != null && 1 == group.getDesiredCapacity(), "Expected group size 1");

            print("Testing admin policy execution");
            as_user.executePolicy(new ExecutePolicyRequest().withPolicyName(policyArn));
            group = getGroup( as, groupArn );
            assertThat(group != null && 2 == group.getDesiredCapacity(), "Expected group size 2");

            print("Testing admin group update");
            as_user.updateAutoScalingGroup(new UpdateAutoScalingGroupRequest().withAutoScalingGroupName(groupArn).withDesiredCapacity(0));
            group = getGroup( as, groupArn );
            assertThat(group != null && 0 == group.getDesiredCapacity(), "Expected group size 0");

            print("Testing admin process resume");
            as_user.resumeProcesses(new ResumeProcessesRequest().withAutoScalingGroupName(groupArn));
            group = getGroup( as, groupArn );
            assertThat(group != null && group.getSuspendedProcesses().isEmpty(), "Expected no suspended processes");

            // Test administrative deletion
            print("Deleting policy as admin: " + policyName);
            as.deletePolicy( new DeletePolicyRequest( ).withPolicyName( policyArn ) );

            System.out.println("************** policy arn: " + policyArn);
            final List<ScalingPolicy> policies2 = as.describePolicies( new DescribePoliciesRequest()
                    .withPolicyNames( "verbose", policyName )
            ).getScalingPolicies();
            int policySize2 = policies2==null ? 0 : policies2.size();
            assertThat( policySize2 == 0, "Expected empty response" );

            print("Deleting group as admin: " + groupName);
            as.deleteAutoScalingGroup( new DeleteAutoScalingGroupRequest().withAutoScalingGroupName( groupArn ).withForceDelete( true ) );
            final List<AutoScalingGroup> groups2 = as.describeAutoScalingGroups( new DescribeAutoScalingGroupsRequest()
                    .withAutoScalingGroupNames( "verbose", groupName )
            ).getAutoScalingGroups();
            int groupsSize2 = groups2==null ? 0 : groups2.size();
            assertThat(groupsSize2 == 0, "Expected empty response");

            print( "Deleting launch configuration as admin: " + launchConfigurationName );
            as.deleteLaunchConfiguration(new DeleteLaunchConfigurationRequest().withLaunchConfigurationName(configArn));
            final List<LaunchConfiguration> configurations2 = as.describeLaunchConfigurations( new DescribeLaunchConfigurationsRequest()
                    .withLaunchConfigurationNames( "verbose", launchConfigurationName )
            ).getLaunchConfigurations( );
            int size2 = configurations2==null ? 0 : configurations2.size();
            assertThat( size2==0, "Expected empty response" );

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

    private static AutoScalingGroup getGroup( AmazonAutoScaling as, String groupNameOrArn ) {
        final List<AutoScalingGroup> groups = as.describeAutoScalingGroups( new DescribeAutoScalingGroupsRequest().withAutoScalingGroupNames( "verbose", groupNameOrArn ) ).getAutoScalingGroups();
        return groups.size()==1 ? groups.get( 0 ) : null;
    }
}
