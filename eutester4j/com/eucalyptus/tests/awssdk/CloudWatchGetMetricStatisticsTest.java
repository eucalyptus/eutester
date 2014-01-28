package com.eucalyptus.tests.awssdk;

import com.amazonaws.services.cloudwatch.model.Dimension;
import com.amazonaws.services.cloudwatch.model.GetMetricStatisticsRequest;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Date;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

public class CloudWatchGetMetricStatisticsTest {
    @Test
    public void TestCloudWatchGetMetricStatistics() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        GetMetricStatisticsRequest getMetricStatisticsRequest = new GetMetricStatisticsRequest();
        getMetricStatisticsRequest.setPeriod(60);
        getMetricStatisticsRequest.setMetricName("Metric10");
        getMetricStatisticsRequest.setNamespace("/AWS/TestMetric");
        Collection<Dimension> dimensions = new ArrayList<Dimension>();
        for (int i = 1; i <= 10; i++) {
            Dimension d = new Dimension();
            d.setName("dim" + i);
            d.setValue("dim" + i);
            dimensions.add(d);
        }
        getMetricStatisticsRequest.setDimensions(dimensions);
        Date endTime = new Date(System.currentTimeMillis());
        Date startTime = new Date(endTime.getTime() - 60 * 60 * 1000L);
        getMetricStatisticsRequest.setEndTime(endTime);
        Collection<String> statistics = new ArrayList<String>();
        statistics.add("Maximum");
        getMetricStatisticsRequest.setStatistics(statistics);
        getMetricStatisticsRequest.setStartTime(startTime);
        System.out.println(cw.getMetricStatistics(getMetricStatisticsRequest));

    }

}
