package com.eucalyptus.tests.awssdk;

import com.amazonaws.services.cloudwatch.model.Dimension;
import com.amazonaws.services.cloudwatch.model.MetricDatum;
import com.amazonaws.services.cloudwatch.model.PutMetricDataRequest;
import com.amazonaws.services.cloudwatch.model.StatisticSet;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Date;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

public class CloudWatchPutMetricDataTest {
    @Test
    public void CloudWatchPutMetricData() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        PutMetricDataRequest putMetricDataRequest = new PutMetricDataRequest();
        putMetricDataRequest.setNamespace("/AWS/TestMetric");
        MetricDatum metricDatum1 = new MetricDatum();
        metricDatum1.setMetricName("Metric10");
        metricDatum1.setTimestamp(new Date(System.currentTimeMillis()));
        metricDatum1.setValue((double) -5000.0);
        metricDatum1.setUnit("");
//        StatisticSet statisticValues = new StatisticSet();
//        statisticValues.setSum(5.0);
//        statisticValues.setMaximum(12.0);
//        statisticValues.setMinimum(5.0);
//        statisticValues.setSampleCount(-0.1);
//        statisticValues.setSum(5.0);
//        metricDatum1.setStatisticValues(statisticValues);
        Collection<Dimension> dimensions = new ArrayList<Dimension>();
        for (int i = 1; i <= 10; i++) {
            Dimension d = new Dimension();
            d.setName("dim" + i);
            d.setValue("dim" + i);
            dimensions.add(d);
        }
        metricDatum1.setDimensions(dimensions);
//    metricDatum1.setUnit("Count/Second");
        putMetricDataRequest.getMetricData().add(new MetricDatum());
        putMetricDataRequest.getMetricData().add(metricDatum1);
        cw.putMetricData(putMetricDataRequest);
    }
}
