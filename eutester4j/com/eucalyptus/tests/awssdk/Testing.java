package com.eucalyptus.tests.awssdk;


import static com.eucalyptus.tests.awssdk.Eutester4j.*;
import static com.eucalyptus.tests.awssdk.Eutester4j.EC2_ENDPOINT;

import com.amazonaws.services.ec2.model.DescribeVolumesResult;
import com.amazonaws.services.ec2.model.Volume;
import com.amazonaws.services.identitymanagement.model.*;
import com.github.sjones4.youcan.youare.model.Account;
import org.testng.annotations.Test;

import java.util.List;

/**
 * Created with IntelliJ IDEA.
 * User: tony
 * Date: 11/25/13
 * Time: 1:22 PM
 * To change this template use File | Settings | File Templates.
 */
public class Testing  {

    @Test
    public void youAreTest() throws Exception {
        getCloudInfo();
//        String accountName = NAME_PREFIX + "account";
//        String userName = NAME_PREFIX + "user";
//
//        print("CLOUD URI: " + EC2_ENDPOINT.substring(0, EC2_ENDPOINT.length() - 21) + "/services/Empyrean/");
//        GetRoleResult res = youAre.getRole(new GetRoleRequest().withRoleName("AccountAdministrator"));
//        final String aaAssumeRolePolicy =  res.getRole().getAssumeRolePolicyDocument();
//        print("aaAssumeRolePolicy: " + aaAssumeRolePolicy);

//        createAccount(accountName);
//        createUser(accountName, userName);
//        print("Account ID: " + getAccountID(accountName));
//        deleteAccount(accountName);
        final DescribeVolumesResult result = ec2.describeVolumes();
        print("Volume count = " + result.getVolumes().size());
        for (final Volume volume : result.getVolumes()) {
            deleteVolume(volume.getVolumeId());
        }
    }

    public String getAccountID(String account){
        String accountId = null;
        String secret;
        List<Account> accounts = youAre.listAccounts().getAccounts();
        for (Account a : accounts) {
            if (a.getAccountName().equals(account)){
                accountId = a.getAccountId();
            }
        }

        return accountId == null ?  "no account named " + account + " was found." :  accountId;
    }
}
