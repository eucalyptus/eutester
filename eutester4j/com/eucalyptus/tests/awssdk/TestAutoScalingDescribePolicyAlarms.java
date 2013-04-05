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
import com.amazonaws.services.cloudwatch.model.ComparisonOperator;
import com.amazonaws.services.cloudwatch.model.DeleteAlarmsRequest;
import com.amazonaws.services.cloudwatch.model.PutMetricAlarmRequest;
import com.amazonaws.services.cloudwatch.model.Statistic;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

/**
 * This application tests listing CloudWatch alarms associated with auto scaling policies.
 * <p/>
 * This is verification for the story:
 * <p/>
 * https://eucalyptus.atlassian.net/browse/EUCA-5465
 */
public class TestAutoScalingDescribePolicyAlarms {

    @Test
    public void AutoScalingDescribePolicyAlarmsTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // Register cleanup for launch config
            final String configName = NAME_PREFIX + "PolicyAlarmTest";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting launch configuration: " + configName);
                    deleteLaunchConfig(configName);
                }
            });

            // Create launch configuration
            print("Creating launch configuration: " + configName);
            as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
                    .withLaunchConfigurationName(configName)
                    .withImageId(IMAGE_ID)
                    .withInstanceType(INSTANCE_TYPE));

            // Register cleanup for auto scaling group
            final String groupName = NAME_PREFIX + "PolicyAlarmTest";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting group: " + groupName);
                    deleteAutoScalingGroup(groupName, true);
                }
            });

            // Create scaling group
            print("Creating auto scaling group: " + groupName);
            as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
                    .withAutoScalingGroupName(groupName)
                    .withLaunchConfigurationName(configName)
                    .withMinSize(0)
                    .withMaxSize(1)
                    .withAvailabilityZones(AVAILABILITY_ZONE)
            );

            // Register cleanup for auto scaling group
            final String policyName = NAME_PREFIX + "PolicyAlarmTest";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting policy: " + policyName);
                    as.deletePolicy(new DeletePolicyRequest().withAutoScalingGroupName(groupName).withPolicyName(policyName));
                }
            });

            // Create policy
            print("Creating auto scaling policy " + policyName);
            final PutScalingPolicyResult putScalingPolicyResult =
                    as.putScalingPolicy(new PutScalingPolicyRequest()
                            .withAutoScalingGroupName(groupName)
                            .withPolicyName(policyName)
                            .withAdjustmentType("ExactCapacity")
                            .withScalingAdjustment(0));
            final String policyArn = putScalingPolicyResult.getPolicyARN();
            print("Using policy ARN: " + policyArn);

            // Register cleanup for metric alarm
            final String alarmName = NAME_PREFIX + "PolicyAlarmTest";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting alarm: " + policyName);
                    cw.deleteAlarms(new DeleteAlarmsRequest().withAlarmNames(alarmName));
                }
            });

            // Create alarm
            print("Creating alarm " + alarmName);
            cw.putMetricAlarm(new PutMetricAlarmRequest()
                    .withAlarmName(alarmName)
                    .withAlarmActions(policyArn)
                    .withNamespace("namespace")
                    .withMetricName("metric")
                    .withComparisonOperator(ComparisonOperator.GreaterThanThreshold)
                    .withEvaluationPeriods(60)
                    .withStatistic(Statistic.Average)
                    .withThreshold(100d)
                    .withPeriod(60)
                    .withActionsEnabled(false));

            // Describe policy and check for alarm info
            print("Describing policies for group to check for alarm.");
            final DescribePoliciesResult describePoliciesResult =
                    as.describePolicies(new DescribePoliciesRequest().withAutoScalingGroupName(groupName));
            print(describePoliciesResult.toString());
            assertThat(describePoliciesResult.getScalingPolicies() != null, "Expected scaling policies");
            assertThat(describePoliciesResult.getScalingPolicies().size() == 1, "Expected one scaling policy");
            assertThat(describePoliciesResult.getScalingPolicies().get(0) != null, "Expected scaling policy");
            assertThat(policyArn.equals(describePoliciesResult.getScalingPolicies().get(0).getPolicyARN()), "Unexpected policy ARN");
            assertThat(describePoliciesResult.getScalingPolicies().get(0).getAlarms() != null, "Expected alarms");
            assertThat(describePoliciesResult.getScalingPolicies().get(0).getAlarms().size() == 1, "Expected one alarm");
            assertThat(describePoliciesResult.getScalingPolicies().get(0).getAlarms().get(0) != null, "Expected alarm");
            assertThat(alarmName.equals(describePoliciesResult.getScalingPolicies().get(0).getAlarms().get(0).getAlarmName()), "Unexpected alarm name");

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
