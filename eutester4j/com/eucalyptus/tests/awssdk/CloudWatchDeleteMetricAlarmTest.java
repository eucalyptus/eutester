package com.eucalyptus.tests.awssdk;


import com.amazonaws.services.cloudwatch.model.DeleteAlarmsRequest;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collection;

import static com.eucalyptus.tests.awssdk.Eutester4j.cw;
import static com.eucalyptus.tests.awssdk.Eutester4j.getCloudInfo;

public class CloudWatchDeleteMetricAlarmTest {
    @Test
    public void TestCloudWatchDeleteMetricAlarm() throws Exception {
        getCloudInfo();
        DeleteAlarmsRequest deleteAlarmsRequest = new DeleteAlarmsRequest();
        Collection<String> alarmNames = new ArrayList<String>();
        alarmNames.add("My Name 1");
        deleteAlarmsRequest.setAlarmNames(alarmNames);
        cw.deleteAlarms(deleteAlarmsRequest);
    }
}
