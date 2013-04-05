package com.eucalyptus.tests.awssdk;

import com.amazonaws.services.cloudwatch.model.DimensionFilter;
import com.amazonaws.services.cloudwatch.model.ListMetricsRequest;
import com.amazonaws.services.cloudwatch.model.ListMetricsResult;
import com.amazonaws.services.cloudwatch.model.Metric;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collection;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

public class CloudWatchListMetricsTest {
    @Test
    public void TestCloudWatchListMetrics() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();

        ListMetricsRequest listMetricsRequest = new ListMetricsRequest();
        listMetricsRequest.setMetricName("Test");
        listMetricsRequest.setNamespace("/test/namespace");
//        listMetricsRequest.setNextToken("e6c3f445-9d1b-47ca-a75d-cf5b12e579bc");
        Collection<DimensionFilter> dimensions = new ArrayList<DimensionFilter>();
        for (int i = 1; i <= 10; i++) {
            DimensionFilter d = new DimensionFilter();
//      if (i != 1) {
            d.setName("dim" + i);
//      }
            d.setValue("dim" + i);

            dimensions.add(d);
        }
        listMetricsRequest.setDimensions(dimensions);

        ListMetricsResult result = cw.listMetrics(listMetricsRequest);

        for (Metric metric : result.getMetrics()) {
            System.out.println(metric);
        }


        System.out.println(result.getMetrics().size());

        // check for get next token
        System.out.println(result.getNextToken());

    }
}
