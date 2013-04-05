package com.eucalyptus.tests.awssdk;

import com.amazonaws.services.cloudwatch.model.AlarmHistoryItem;
import com.amazonaws.services.cloudwatch.model.DescribeAlarmHistoryRequest;
import com.amazonaws.services.cloudwatch.model.DescribeAlarmHistoryResult;
import com.amazonaws.services.cloudwatch.model.HistoryItemType;
import org.testng.annotations.Test;

import java.text.SimpleDateFormat;
import java.util.Collection;

import static com.eucalyptus.tests.awssdk.Eutester4j.cw;
import static com.eucalyptus.tests.awssdk.Eutester4j.getCloudInfo;

public class CloudWatchDescribeAlarmHistoryTest {
    @Test
    public void TestCloudWatchDescribeAlarmHistory() throws Exception {
        SimpleDateFormat sdf = new SimpleDateFormat("EEE MMM dd HH:mm:ss z yyyy");
        getCloudInfo();
        DescribeAlarmHistoryRequest describeAlarmHistoryRequest = new DescribeAlarmHistoryRequest();
        describeAlarmHistoryRequest.setAlarmName("foo");
//    describeAlarmHistoryRequest.setStartDate(sdf.parse("Thu Mar 07 07:50:00 PST 2015"));
//    describeAlarmHistoryRequest.setEndDate(sdf.parse("Thu Mar 07 12:26:48 PST 2011"));
        describeAlarmHistoryRequest.setHistoryItemType(HistoryItemType.ConfigurationUpdate);//HistoryItemType.ConfigurationUpdate);
        describeAlarmHistoryRequest.setMaxRecords(5);
//    describeAlarmHistoryRequest.setNextToken("doofus");
//        DescribeAlarmHistoryResult describeAlarmHistoryResults = cw.describeAlarmHistory(describeAlarmHistoryRequest);

        DescribeAlarmHistoryResult describeAlarmHistoryResults = cw.describeAlarmHistory();
        Collection<AlarmHistoryItem> results = describeAlarmHistoryResults.getAlarmHistoryItems();
        for (AlarmHistoryItem alarmHistoryItem : results) {
            System.out.println(alarmHistoryItem);
        }
        System.out.println(results.size());
        System.out.println(describeAlarmHistoryResults.getNextToken());


    }

}
