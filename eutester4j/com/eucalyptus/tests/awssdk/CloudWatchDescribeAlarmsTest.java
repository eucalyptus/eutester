package com.eucalyptus.tests.awssdk;

import com.amazonaws.services.cloudwatch.model.DescribeAlarmsRequest;
import com.amazonaws.services.cloudwatch.model.DescribeAlarmsResult;
import com.amazonaws.services.cloudwatch.model.MetricAlarm;
import com.amazonaws.services.cloudwatch.model.StateValue;
import org.testng.annotations.Test;

import java.util.Arrays;
import java.util.Collection;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

public class CloudWatchDescribeAlarmsTest {
    @Test
    public void TestCloudWatchDescribeAlarms() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        DescribeAlarmsRequest describeAlarmsRequest = new DescribeAlarmsRequest();
//        TODO: This may be a bug
//        describeAlarmsRequest.setAlarmNamePrefix("My ");
        describeAlarmsRequest.setStateValue(StateValue.ALARM);
        describeAlarmsRequest.setAlarmNames(Arrays.asList(new String[]{"My Name", "My Name 2"}));
        describeAlarmsRequest.setActionPrefix("ins");
        describeAlarmsRequest.setMaxRecords(5);
//        describeAlarmsRequest.setNextToken("c1e5bd0d-4f11-40bb-8cf8-9d82e1376dd7");
        DescribeAlarmsResult describeAlarmResult = cw.describeAlarms(describeAlarmsRequest);
        // DescribeAlarmsResult describeAlarmResult = cw.describeAlarms();
        Collection<MetricAlarm> results = describeAlarmResult.getMetricAlarms();
        for (MetricAlarm metricAlarm : results) {
            System.out.println(metricAlarm);
        }
        System.out.println(results.size());
        System.out.println(describeAlarmResult.getNextToken());
    }
}
