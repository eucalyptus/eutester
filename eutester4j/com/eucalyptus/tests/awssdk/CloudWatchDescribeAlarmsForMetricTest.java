package com.eucalyptus.tests.awssdk;

import com.amazonaws.services.cloudwatch.model.*;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collection;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

public class CloudWatchDescribeAlarmsForMetricTest {
    @Test
    public void TestCloudWatchDescribeAlarmsForMetric() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        DescribeAlarmsForMetricRequest describeAlarmsForMetricRequest = new DescribeAlarmsForMetricRequest();
        describeAlarmsForMetricRequest.setNamespace("namespace1");
        describeAlarmsForMetricRequest.setMetricName("metric1");
        describeAlarmsForMetricRequest.setPeriod(60);
        describeAlarmsForMetricRequest.setUnit(StandardUnit.Kilobits);
        Dimension dim1 = new Dimension();
        dim1.setName("name1");
        dim1.setValue("value1");
        Dimension dim2 = new Dimension();
        dim2.setName("name2");
        dim2.setValue("value2");
        Dimension dim3 = new Dimension();
        dim3.setName("name3");
        dim3.setValue("value3");
        Collection<Dimension> dimensions = new ArrayList<Dimension>();
        dimensions.add(dim1);
        dimensions.add(dim3);
        dimensions.add(dim2);
        describeAlarmsForMetricRequest.setDimensions(dimensions);
        cw.describeAlarmsForMetric(describeAlarmsForMetricRequest);
        DescribeAlarmsForMetricResult describeAlarmForMetricsResult = cw.describeAlarmsForMetric(describeAlarmsForMetricRequest);
        for (MetricAlarm metricAlarm : describeAlarmForMetricsResult.getMetricAlarms()) {
            System.out.println(metricAlarm);
        }
    }

}
