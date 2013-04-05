package com.eucalyptus.tests.awssdk;

import com.amazonaws.services.cloudwatch.model.ComparisonOperator;
import com.amazonaws.services.cloudwatch.model.PutMetricAlarmRequest;
import com.amazonaws.services.cloudwatch.model.Statistic;
import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

public class CloudWatchPutMetricAlarmTest {
    @Test
    public void CloudWatchPutMetricAlarm() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        PutMetricAlarmRequest putMetricAlarmRequest = new PutMetricAlarmRequest();
        putMetricAlarmRequest.setActionsEnabled(true);
        putMetricAlarmRequest.setAlarmDescription("desc2");
        putMetricAlarmRequest.setAlarmName("My Name 2");
        putMetricAlarmRequest.setComparisonOperator(ComparisonOperator.GreaterThanOrEqualToThreshold);
        putMetricAlarmRequest.setDimensions(null);
        putMetricAlarmRequest.setEvaluationPeriods(5);
        putMetricAlarmRequest.setMetricName("metric1");
        putMetricAlarmRequest.setNamespace("namespace1");
        putMetricAlarmRequest.setPeriod(60);
        putMetricAlarmRequest.setStatistic(Statistic.Maximum);
        putMetricAlarmRequest.setThreshold(20.0);
        cw.putMetricAlarm(putMetricAlarmRequest);
    }

//    TODO: Add validation for these?
//    putMetricAlarmRequest.setOKActions();
//    putMetricAlarmRequest.setAlarmActions();
//    putMetricAlarmRequest.setInsufficientDataActions();

}
