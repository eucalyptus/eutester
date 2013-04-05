package com.eucalyptus.tests.awssdk;

import com.amazonaws.services.cloudwatch.model.DisableAlarmActionsRequest;
import org.testng.annotations.Test;

import java.util.Arrays;
import java.util.Collection;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

public class CloudWatchDisableAlarmActionsTest {
    @Test
    public void TestCloudWatchDisableAlarmActions() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        DisableAlarmActionsRequest disableAlarmActionsRequest = new DisableAlarmActionsRequest();
//Too many alarms
//      ArrayList<String> alarmNames = new ArrayList<String>();
//      for (int i=0;i<101;i++) {
//        alarmNames.add(" " + i);
//      }
        Collection<String> alarmNames = Arrays.asList(new String[]{"My Name", "My Name 2"});
        disableAlarmActionsRequest.setAlarmNames(alarmNames);
        cw.disableAlarmActions(disableAlarmActionsRequest);
    }
}
