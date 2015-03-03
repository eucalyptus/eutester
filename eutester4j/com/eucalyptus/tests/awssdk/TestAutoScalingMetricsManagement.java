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
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;


/**
 * This application tests metrics management for auto scaling groups.
 * <p/>
 * This is verification for the story:
 * <p/>
 * https://eucalyptus.atlassian.net/browse/EUCA-5354
 */
public class TestAutoScalingMetricsManagement {
    @Test
    public void AutoScalingMetricsManagementTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // Register cleanup for launch configs
            final String configName = NAME_PREFIX + "MetricsTest";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting launch configuration: " + configName);
                    as.deleteLaunchConfiguration(new DeleteLaunchConfigurationRequest().withLaunchConfigurationName(configName));
                }
            });

            // Create launch configuration
            print("Creating launch configuration: " + configName);
            as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
                    .withLaunchConfigurationName(configName)
                    .withImageId(IMAGE_ID)
                    .withInstanceType(INSTANCE_TYPE));

            // Register cleanup for auto scaling groups
            final String groupName = NAME_PREFIX + "MetricsTest";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting group: " + groupName);
                    as.deleteAutoScalingGroup(new DeleteAutoScalingGroupRequest().withAutoScalingGroupName(groupName).withForceDelete(true));
                }
            });

            // Create scaling group
            print("Creating auto scaling group: " + groupName);
            as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
                    .withAutoScalingGroupName(groupName)
                    .withLaunchConfigurationName(configName)
                    .withMinSize(0)
                    .withMaxSize(0)
                    .withAvailabilityZones(AVAILABILITY_ZONE));

            // Describe metrics collection types
            print("Describing metric collection types");
            final DescribeMetricCollectionTypesResult collectionTypesResult = as.describeMetricCollectionTypes();
            print(collectionTypesResult.toString());
            assertThat(collectionTypesResult.getGranularities() != null, "Expected granularities");
            assertThat(collectionTypesResult.getGranularities().size() == 1, "Expected one granularity");
            assertThat("1Minute".equals(collectionTypesResult.getGranularities().get(0).getGranularity()), "Unexpected granularity");
            assertThat(collectionTypesResult.getMetrics() != null, "Expected granularities");
            assertThat(collectionTypesResult.getMetrics().size() == 7, "Expected 7 granularities");
            assertThat("GroupDesiredCapacity".equals(collectionTypesResult.getMetrics().get(0).getMetric()), "Unexpected metric");
            assertThat("GroupInServiceInstances".equals(collectionTypesResult.getMetrics().get(1).getMetric()), "Unexpected metric");
            assertThat("GroupMaxSize".equals(collectionTypesResult.getMetrics().get(2).getMetric()), "Unexpected metric");
            assertThat("GroupMinSize".equals(collectionTypesResult.getMetrics().get(3).getMetric()), "Unexpected metric");
            assertThat("GroupPendingInstances".equals(collectionTypesResult.getMetrics().get(4).getMetric()), "Unexpected metric");
            assertThat("GroupTerminatingInstances".equals(collectionTypesResult.getMetrics().get(5).getMetric()), "Unexpected metric");
            assertThat("GroupTotalInstances".equals(collectionTypesResult.getMetrics().get(6).getMetric()), "Unexpected metric");

            // Describe group to check no metrics enabled
            print("Checking no enabled metrics for group: " + groupName);
            {
                final DescribeAutoScalingGroupsResult groupResult = as.describeAutoScalingGroups(new DescribeAutoScalingGroupsRequest().withAutoScalingGroupNames(groupName));
                assertThat(groupResult.getAutoScalingGroups() != null, "Expected groups");
                assertThat(groupResult.getAutoScalingGroups().size() == 1, "Expected 1 group");
                assertThat(groupResult.getAutoScalingGroups().get(0).getEnabledMetrics() == null ||
                        groupResult.getAutoScalingGroups().get(0).getEnabledMetrics().isEmpty(), "Expected no metrics enabled.");
            }

            // Enable all metrics
            print("Enabling all metrics for group: " + groupName);
            as.enableMetricsCollection(new EnableMetricsCollectionRequest().withAutoScalingGroupName(groupName).withGranularity("1Minute"));

            // Describe group to check metrics enabled
            print("Checking all metrics enabled for group: " + groupName);
            {
                final DescribeAutoScalingGroupsResult groupResult = as.describeAutoScalingGroups(new DescribeAutoScalingGroupsRequest().withAutoScalingGroupNames(groupName));
                assertThat(groupResult.getAutoScalingGroups() != null, "Expected groups");
                assertThat(groupResult.getAutoScalingGroups().size() == 1, "Expected 1 group");
                assertThat(groupResult.getAutoScalingGroups().get(0).getEnabledMetrics() != null &&
                        groupResult.getAutoScalingGroups().get(0).getEnabledMetrics().size() == 7, "Expected 1 metric enabled.");
                assertThat("GroupDesiredCapacity".equals(groupResult.getAutoScalingGroups().get(0).getEnabledMetrics().get(0).getMetric()), "Unexpected metric");
                assertThat("GroupInServiceInstances".equals(groupResult.getAutoScalingGroups().get(0).getEnabledMetrics().get(1).getMetric()), "Unexpected metric");
                assertThat("GroupMaxSize".equals(groupResult.getAutoScalingGroups().get(0).getEnabledMetrics().get(2).getMetric()), "Unexpected metric");
                assertThat("GroupMinSize".equals(groupResult.getAutoScalingGroups().get(0).getEnabledMetrics().get(3).getMetric()), "Unexpected metric");
                assertThat("GroupPendingInstances".equals(groupResult.getAutoScalingGroups().get(0).getEnabledMetrics().get(4).getMetric()), "Unexpected metric");
                assertThat("GroupTerminatingInstances".equals(groupResult.getAutoScalingGroups().get(0).getEnabledMetrics().get(5).getMetric()), "Unexpected metric");
                assertThat("GroupTotalInstances".equals(groupResult.getAutoScalingGroups().get(0).getEnabledMetrics().get(6).getMetric()), "Unexpected metric");
            }

            // Disable all metrics
            print("Disabling all metrics for group: " + groupName);
            as.disableMetricsCollection(new DisableMetricsCollectionRequest().withAutoScalingGroupName(groupName));

            // Describe group to check no metrics enabled
            print("Checking no enabled metrics for group: " + groupName);
            {
                final DescribeAutoScalingGroupsResult groupResult = as.describeAutoScalingGroups(new DescribeAutoScalingGroupsRequest().withAutoScalingGroupNames(groupName));
                assertThat(groupResult.getAutoScalingGroups() != null, "Expected groups");
                assertThat(groupResult.getAutoScalingGroups().size() == 1, "Expected 1 group");
                assertThat(groupResult.getAutoScalingGroups().get(0).getEnabledMetrics() == null ||
                        groupResult.getAutoScalingGroups().get(0).getEnabledMetrics().isEmpty(), "Expected no metrics enabled.");
            }

            // Enable single metric
            print("Enabling GroupInServiceInstances metric for group: " + groupName);
            as.enableMetricsCollection(new EnableMetricsCollectionRequest().withAutoScalingGroupName(groupName).withMetrics("GroupInServiceInstances").withGranularity("1Minute"));

            // Describe group to check single enabled
            print("Checking GroupInServiceInstances metric enabled for group: " + groupName);
            {
                final DescribeAutoScalingGroupsResult groupResult = as.describeAutoScalingGroups(new DescribeAutoScalingGroupsRequest().withAutoScalingGroupNames(groupName));
                assertThat(groupResult.getAutoScalingGroups() != null, "Expected groups");
                assertThat(groupResult.getAutoScalingGroups().size() == 1, "Expected 1 group");
                assertThat(groupResult.getAutoScalingGroups().get(0).getEnabledMetrics() != null &&
                        groupResult.getAutoScalingGroups().get(0).getEnabledMetrics().size() == 1, "Expected 1 metric enabled.");
                assertThat("GroupInServiceInstances".equals(groupResult.getAutoScalingGroups().get(0).getEnabledMetrics().get(0).getMetric()), "Expected 1 metric enabled.");
                assertThat("1Minute".equals(groupResult.getAutoScalingGroups().get(0).getEnabledMetrics().get(0).getGranularity()), "Expected granularity for enabled metric.");
            }

            // Disable single metric
            print("Disabling GroupInServiceInstances metric for group: " + groupName);
            as.disableMetricsCollection(new DisableMetricsCollectionRequest().withAutoScalingGroupName(groupName).withMetrics("GroupInServiceInstances"));

            // Describe group to check no metrics enabled
            print("Checking no enabled metrics for group: " + groupName);
            {
                final DescribeAutoScalingGroupsResult groupResult = as.describeAutoScalingGroups(new DescribeAutoScalingGroupsRequest().withAutoScalingGroupNames(groupName));
                assertThat(groupResult.getAutoScalingGroups() != null, "Expected groups");
                assertThat(groupResult.getAutoScalingGroups().size() == 1, "Expected 1 group");
                assertThat(groupResult.getAutoScalingGroups().get(0).getEnabledMetrics() == null ||
                        groupResult.getAutoScalingGroups().get(0).getEnabledMetrics().isEmpty(), "Expected no metrics enabled.");
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
