package com.eucalyptus.tests.awssdk;

import com.amazonaws.services.cloudwatch.model.EnableAlarmActionsRequest;
import org.testng.annotations.Test;

import java.util.Arrays;
import java.util.Collection;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

public class CloudWatchEnableAlarmActionsTest {
    @Test
    public void TestCloudWatchEnableAlarmActions() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        EnableAlarmActionsRequest enableAlarmActionsRequest = new EnableAlarmActionsRequest();
        Collection<String> alarmNames = Arrays.asList(new String[]{"foo", "My Name 2"});
        enableAlarmActionsRequest.setAlarmNames(alarmNames);
        cw.enableAlarmActions(enableAlarmActionsRequest);
    }
}
