package com.eucalyptus.tests.awssdk;

import com.amazonaws.services.cloudwatch.model.SetAlarmStateRequest;
import com.amazonaws.services.cloudwatch.model.StateValue;
import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

public class CloudWatchStateChangeTest {
    @Test
    public void CloudWatchStateChange() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        for (int i = 0; i < 100; i++) {
            {
                SetAlarmStateRequest setAlarmStateRequest = new SetAlarmStateRequest();
                setAlarmStateRequest.setAlarmName("My Name 2");
                setAlarmStateRequest.setStateValue(StateValue.OK);
                setAlarmStateRequest.setStateReason("state reason");
                setAlarmStateRequest.setStateReasonData("{\"a\":5}");
                cw.setAlarmState(setAlarmStateRequest);
            }
            {
                SetAlarmStateRequest setAlarmStateRequest = new SetAlarmStateRequest();
                setAlarmStateRequest.setAlarmName("My Name 2");
                setAlarmStateRequest.setStateValue(StateValue.ALARM);
                setAlarmStateRequest.setStateReason("state reason");
                setAlarmStateRequest.setStateReasonData("{\"a\":5}");
                cw.setAlarmState(setAlarmStateRequest);
            }
            {
                SetAlarmStateRequest setAlarmStateRequest = new SetAlarmStateRequest();
                setAlarmStateRequest.setAlarmName("My Name 2");
                setAlarmStateRequest.setStateValue(StateValue.INSUFFICIENT_DATA);
                setAlarmStateRequest.setStateReason("state reason");
                setAlarmStateRequest.setStateReasonData("{\"a\":5}");
                cw.setAlarmState(setAlarmStateRequest);
            }
        }
    }
}
