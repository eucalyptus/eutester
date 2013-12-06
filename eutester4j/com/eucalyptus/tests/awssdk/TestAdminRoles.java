/*************************************************************************
* Copyright 2009-2013 Eucalyptus Systems, Inc.
*
* This program is free software: you can redistribute it and/or modify
* it under the terms of the GNU General Public License as published by
* the Free Software Foundation; version 3 of the License.
*
* This program is distributed in the hope that it will be useful,
* but WITHOUT ANY WARRANTY; without even the implied warranty of
* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
* GNU General Public License for more details.
*
* You should have received a copy of the GNU General Public License
* along with this program.  If not, see http://www.gnu.org/licenses/.
*
* Please contact Eucalyptus Systems, Inc., 6755 Hollister Ave., Goleta
* CA 93117, USA or visit http://www.eucalyptus.com/licenses/ if you need
* additional information or have any questions.
************************************************************************/
package com.eucalyptus.tests.awssdk;

import com.amazonaws.auth.AWSCredentials;
import com.amazonaws.auth.AWSCredentialsProvider;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.auth.BasicSessionCredentials;
import com.amazonaws.services.ec2.AmazonEC2;
import com.amazonaws.services.ec2.AmazonEC2Client;
import com.amazonaws.services.ec2.model.*;
import com.amazonaws.services.identitymanagement.model.*;
import com.amazonaws.services.securitytoken.AWSSecurityTokenService;
import com.amazonaws.services.securitytoken.AWSSecurityTokenServiceClient;
import com.amazonaws.services.securitytoken.model.AssumeRoleRequest;
import com.amazonaws.services.securitytoken.model.AssumeRoleResult;
import com.github.sjones4.youcan.youare.model.Account;
import org.testng.annotations.Test;
import static com.eucalyptus.tests.awssdk.Eutester4j.*;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * NOTE: This test may stop working if we limit access to the Eucalyptus account
 * test verifies the functionality of https://eucalyptus.atlassian.net/browse/EUCA-8164
 * Policies associated with roles in the "eucalyptus" account now allow access to resources across accounts
 * test shows how this is configured (role and policy creation) and used (assume role, perform action)
*/
public class TestAdminRoles {

    private final String ec2Policy = "{\n" +
            "   \"Statement\":[{\n" +
            "      \"Effect\":\"Allow\",\n" +
            "      \"Action\":\"ec2:*\",\n" +
            "      \"Resource\":\"*\"\n" +
            "   }]\n" +
            "}";

    private AmazonEC2 getEc2ClientUsingRole(final String roleArn,
                                            final String sessionName,
                                            final String accessKey,
                                            final String secretKey) {
        final AmazonEC2 ec2 = new AmazonEC2Client(new AWSCredentialsProvider() {
            @Override
            public AWSCredentials getCredentials() {
                final AWSSecurityTokenService sts = new AWSSecurityTokenServiceClient(new BasicAWSCredentials(accessKey, secretKey));
                sts.setEndpoint(TOKENS_ENDPOINT);
                final AssumeRoleResult assumeRoleResult = sts.assumeRole(new AssumeRoleRequest()
                        .withRoleArn(roleArn)
                        .withRoleSessionName(sessionName)
                );

                assertThat(assumeRoleResult.getAssumedRoleUser().getAssumedRoleId().endsWith(sessionName), "Unexpected assumed role id: " + assumeRoleResult.getAssumedRoleUser().getAssumedRoleId());
                assertThat(assumeRoleResult.getAssumedRoleUser().getArn().endsWith(sessionName), "Unexpected assumed role arn: " + assumeRoleResult.getAssumedRoleUser().getArn());

                return new BasicSessionCredentials(
                        assumeRoleResult.getCredentials().getAccessKeyId(),
                        assumeRoleResult.getCredentials().getSecretAccessKey(),
                        assumeRoleResult.getCredentials().getSessionToken()
                );
            }

            @Override
            public void refresh() {
            }
        });
        ec2.setEndpoint(EC2_ENDPOINT);
        return ec2;
    }

    @Test
    public void test() throws Exception {

        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        final String user = NAME_PREFIX + "user";
        final String account = NAME_PREFIX + "account";

        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // create an account and user
            createAccount(account);
            createUser(account, user);
            createIAMPolicy(account, user, NAME_PREFIX + "policy", null);
            final AmazonEC2 ec2User = new AmazonEC2Client(getUserCreds(account, user));
            ec2User.setEndpoint(EC2_ENDPOINT);

            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting account " + account);
                    deleteAccount(account);
                }
            });

            // Set up administrative role
            final String roleName = NAME_PREFIX + "resource-admin";
            print("Creating role with name: " + roleName);
            final String roleArn = youAre.createRole(new CreateRoleRequest()
                    .withRoleName(roleName)
                    .withAssumeRolePolicyDocument(getAssumeRolePolicy(getAccountID("eucalyptus")))
            ).getRole().getArn();
            print("Created role with ARN " + roleArn);

            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting role " + roleName);
                    youAre.deleteRole(new DeleteRoleRequest().withRoleName(roleName));
                }
            });

            final String policyName = "ec2";
            print("Adding policy to role " + roleName);
            youAre.putRolePolicy(new PutRolePolicyRequest()
                    .withRoleName(roleName)
                    .withPolicyName(policyName)
                    .withPolicyDocument(ec2Policy)
            );

            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting policy for role " + roleName);
                    youAre.deleteRolePolicy(new DeleteRolePolicyRequest().withRoleName(roleName).withPolicyName(policyName));
                }
            });

            // Create resource to test cross-account access
            print("Creating volume as user");
            final String volumeId = ec2User.createVolume(new CreateVolumeRequest().withAvailabilityZone(AVAILABILITY_ZONE).withSize(1)).getVolume().getVolumeId();
            print("Created volume: " + volumeId);

            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting volume for user: " + volumeId);
                    ec2User.deleteVolume(new DeleteVolumeRequest().withVolumeId(volumeId));
                }
            });

            print("Waiting until volume available:" + volumeId);
            for (int i = 0; i < 120; i++) {
                Thread.sleep(1000);
                final int volumeCount = ec2User.describeVolumes(new DescribeVolumesRequest().withVolumeIds(volumeId).withFilters(new Filter().withName("status").withValues("available"))).getVolumes().size();
                if (volumeCount == 1) break;
            }
            final int volumeCount1 = ec2User.describeVolumes(new DescribeVolumesRequest().withVolumeIds(volumeId).withFilters(new Filter().withName("status").withValues("available"))).getVolumes().size();
            assertThat(volumeCount1 == 1, "Expected volume available: " + volumeId);

            // Delete volume with assumed role
            print("Deleting volume using admin role: " + roleArn);
            final AmazonEC2 ec2role = getEc2ClientUsingRole(roleArn, "session-name-here", ACCESS_KEY, SECRET_KEY);
            ec2role.deleteVolume(new DeleteVolumeRequest().withVolumeId(volumeId));

            // Verify volume deleted
            print("Verifying volume no longer present: " + volumeId);
            final int volumeCount = ec2User.describeVolumes(new DescribeVolumesRequest().withVolumeIds(volumeId).withFilters(new Filter().withName("status").withValues("available"))).getVolumes().size();
            assertThat(volumeCount == 0, "Expected volume deleted: " + volumeId);

            print("Test complete");
        } finally {
            // Attempt to clean up anything we created
            Collections.reverse(cleanupTasks);
            for (final Runnable cleanupTask : cleanupTasks) {
                try {
                    cleanupTask.run();
                } catch (NoSuchEntityException e) {
                    print("Entity not found during cleanup.");
                } catch (Exception e) {
                    e.printStackTrace();
                }
            }
        }
    }

    public String getAccountID(String account){
        String accountId = null;

        List<Account> accounts = youAre.listAccounts().getAccounts();
        for (Account a : accounts) {
            if (a.getAccountName().equals(account)){
                accountId = a.getAccountId();
            }
        }
        return accountId == null ?  "no account named " + account + " was found." :  accountId;
    }

    public String getAssumeRolePolicy(String accountId){
        return "{\n" +
                "    \"Statement\": [ {\n" +
                "      \"Effect\": \"Allow\",\n" +
                "      \"Principal\": {\n" +
                "         \"AWS\": [ \"arn:aws:iam::" + accountId + ":user/admin\" ]\n" +
                "      },\n" +
                "      \"Action\": [ \"sts:AssumeRole\" ]\n" +
                "    } ]\n" +
                "}";
    }

}