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
import com.amazonaws.services.cloudwatch.model.Datapoint;
import com.amazonaws.services.cloudwatch.model.Dimension;
import com.amazonaws.services.cloudwatch.model.GetMetricStatisticsRequest;
import com.amazonaws.services.cloudwatch.model.GetMetricStatisticsResult;
import org.testng.annotations.Test;

import java.util.*;
import java.util.concurrent.TimeUnit;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

/**
 * This application tests submitting auto scaling metrics to CloudWatch.
 * <p/>
 * This is verification for the story:
 * <p/>
 * https://eucalyptus.atlassian.net/browse/EUCA-5413
 */
public class TestAutoScalingMetricsSubmission {
    @Test
    public void AutoScalingMetricsSubmissionTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();

        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // Register cleanup for launch config
            final String configName = NAME_PREFIX + "SubmitMetrics";
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
                    .withInstanceType(INSTANCE_TYPE)
                    .withInstanceMonitoring(new InstanceMonitoring().withEnabled(true)));

            // Register cleanup for auto scaling group
            final String groupName = NAME_PREFIX + "SubmitMetrics";
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
                    .withMaxSize(10)
                    .withHealthCheckGracePeriod(300)
                    .withAvailabilityZones(AVAILABILITY_ZONE)
            );

            // Enable single metric
            print("Enabling GroupMaxSize metric for group: " + groupName);
            as.enableMetricsCollection(new EnableMetricsCollectionRequest()
                    .withAutoScalingGroupName(groupName)
                    .withMetrics("GroupMaxSize")
                    .withGranularity("1Minute"));

            // Sleep a minute to ensure metric submitted
            print("Waiting 2 minutes to allow metric submission");
            Thread.sleep(130000);

            // Check metric available
            print("Getting metric GroupMaxSize for group: " + groupName);
            {
                final GetMetricStatisticsResult metricsResult = cw.getMetricStatistics(new GetMetricStatisticsRequest()
                        .withNamespace("AWS/AutoScaling")
                        .withDimensions(new Dimension().withName("AutoScalingGroupName").withValue(groupName))
                        .withStartTime(new Date(System.currentTimeMillis() - TimeUnit.MINUTES.toMillis(2)))
                        .withEndTime(new Date())
                        .withMetricName("GroupMaxSize")
                        .withPeriod(60)
                        .withStatistics(Arrays.asList("Average", "Sum", "SampleCount", "Maximum", "Minimum"))
                );
                print(metricsResult.toString());
                assertThat("GroupMaxSize".equals(metricsResult.getLabel()), "Unexpected label: " + metricsResult.getLabel());
                assertThat(metricsResult.getDatapoints() != null, "Expected datapoints");
                assertThat(metricsResult.getDatapoints().size() > 0, "Expected at least one datapoint");
                for (final Datapoint datapoint : metricsResult.getDatapoints()) {
                    final int expected = 10;
                    assertThat(datapoint.getSampleCount() == 1, "Unexpected sample count: " + datapoint.getSampleCount());
                    assertThat("None".equals(datapoint.getUnit()), "Unexpected unit: " + datapoint.getUnit());
                    assertThat(datapoint.getAverage() == expected, "Unexpected average: " + datapoint.getAverage());
                    assertThat(datapoint.getSum() == expected, "Unexpected sum: " + datapoint.getSum());
                    assertThat(datapoint.getMinimum() == expected, "Unexpected minimum: " + datapoint.getMinimum());
                    assertThat(datapoint.getMaximum() == expected, "Unexpected maximum: " + datapoint.getMaximum());
                }
            }

            // Enable single metric
            print("Enabling all metrics for group: " + groupName);
            as.enableMetricsCollection(new EnableMetricsCollectionRequest()
                    .withAutoScalingGroupName(groupName)
                    .withGranularity("1Minute"));

            // Sleep a minute to ensure metric submitted
            print("Waiting 2 minutes to allow metric submission");
            Thread.sleep(130000);

            // Check metric available
            print("Getting metrics for group: " + groupName);
            for (final String metric : Arrays.asList("GroupMinSize", "GroupMaxSize", "GroupDesiredCapacity", "GroupInServiceInstances", "GroupPendingInstances", "GroupTerminatingInstances", "GroupTotalInstances")) {
                final GetMetricStatisticsResult metricsResult = cw.getMetricStatistics(new GetMetricStatisticsRequest()
                        .withNamespace("AWS/AutoScaling")
                        .withDimensions(new Dimension().withName("AutoScalingGroupName").withValue(groupName))
                        .withStartTime(new Date(System.currentTimeMillis() - TimeUnit.MINUTES.toMillis(2)))
                        .withEndTime(new Date())
                        .withMetricName(metric)
                        .withPeriod(60)
                        .withStatistics(Arrays.asList("Average", "Sum", "SampleCount", "Maximum", "Minimum"))
                );
                print(metricsResult.toString());
                assertThat(metric.equals(metricsResult.getLabel()), "Unexpected label: " + metricsResult.getLabel());
                assertThat(metricsResult.getDatapoints() != null, "Expected datapoints");
                assertThat(metricsResult.getDatapoints().size() > 0, "Expected at least one datapoint");
                for (final Datapoint datapoint : metricsResult.getDatapoints()) {
                    final int expected = "GroupMaxSize".equals(metric) ? 10 : 0;
                    assertThat(datapoint.getSampleCount() == 1, "Unexpected sample count: " + datapoint.getSampleCount());
                    assertThat("None".equals(datapoint.getUnit()), "Unexpected unit: " + datapoint.getUnit());
                    assertThat(datapoint.getAverage() == expected, "Unexpected average: " + datapoint.getAverage());
                    assertThat(datapoint.getSum() == expected, "Unexpected sum: " + datapoint.getSum());
                    assertThat(datapoint.getMinimum() == expected, "Unexpected minimum: " + datapoint.getMinimum());
                    assertThat(datapoint.getMaximum() == expected, "Unexpected maximum: " + datapoint.getMaximum());
                }
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
