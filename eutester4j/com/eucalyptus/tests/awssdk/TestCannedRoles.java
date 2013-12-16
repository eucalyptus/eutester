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

import com.amazonaws.Request;
import com.amazonaws.auth.AWSCredentials;
import com.amazonaws.auth.AWSCredentialsProvider;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.auth.BasicSessionCredentials;
import com.amazonaws.handlers.AbstractRequestHandler;
import com.amazonaws.internal.StaticCredentialsProvider;
import com.amazonaws.services.ec2.AmazonEC2;
import com.amazonaws.services.ec2.AmazonEC2Client;
import com.amazonaws.services.ec2.model.CreateKeyPairRequest;
import com.amazonaws.services.ec2.model.DescribeKeyPairsRequest;
import com.amazonaws.services.ec2.model.KeyPairInfo;
import com.amazonaws.services.identitymanagement.model.*;
import com.amazonaws.services.securitytoken.AWSSecurityTokenService;
import com.amazonaws.services.securitytoken.AWSSecurityTokenServiceClient;
import com.amazonaws.services.securitytoken.model.AssumeRoleRequest;
import com.amazonaws.services.securitytoken.model.AssumeRoleResult;
import com.github.sjones4.youcan.youare.YouAreClient;
import com.github.sjones4.youcan.youare.model.Account;
import com.github.sjones4.youcan.youare.model.CreateAccountRequest;
import com.github.sjones4.youcan.youconfig.YouConfigClient;
import com.github.sjones4.youcan.youconfig.model.ComponentInfo;
import com.github.sjones4.youcan.youprop.YouPropClient;
import com.github.sjones4.youcan.youprop.model.Property;
import com.github.sjones4.youcan.youserv.YouServClient;
import com.github.sjones4.youcan.youserv.model.DescribeServicesRequest;
import com.github.sjones4.youcan.youserv.model.ServiceStatus;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;
import static com.eucalyptus.tests.awssdk.Eutester4j.youAre;

/**
 * This test verifies the functionality of https://eucalyptus.atlassian.net/browse/EUCA-8156, EUCA-8157, and EUCA-8158
 * "Canned Roles": resource-admin, infrastructure-admin and account-admin
 */
public class TestCannedRoles {

    private AWSCredentialsProvider credentialsProvider(final String roleArn,
                                                       final String sessionName,
                                                       final String accesskey,
                                                       final String secretkey) {
        final AWSCredentialsProvider creds = new AWSCredentialsProvider() {
            @Override
            public AWSCredentials getCredentials() {
                final AWSSecurityTokenService sts = new AWSSecurityTokenServiceClient(new BasicAWSCredentials(accesskey, secretkey));
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
        };
        return creds;
    }

    private YouAreClient getYouAreClient(final AWSCredentialsProvider credentials) {
        final YouAreClient euare = new YouAreClient(credentials);
        euare.setEndpoint(IAM_ENDPOINT);
        return euare;
    }

    private AmazonEC2 getEc2Client(final AWSCredentialsProvider credentials) {
        final AmazonEC2 ec2 = new AmazonEC2Client(credentials);
        ec2.setEndpoint(EC2_ENDPOINT);
        return ec2;
    }

    public String getAccountID(String account) {
        String accountId = null;
        List<Account> accounts = youAre.listAccounts().getAccounts();
        for (Account a : accounts) {
            if (a.getAccountName().equals(account)) {
                accountId = a.getAccountId();
            }
        }
        return accountId;
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

    @Test
    public void test() throws Exception {

        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        final String account = NAME_PREFIX + "account";

        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // create an account and a user
            createAccount(account);

            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    deleteAccount(account);
                }
            });

            // Update default roles to permit account
            final String aaAssumeRolePolicy = youAre.getRole(new GetRoleRequest().withRoleName("AccountAdministrator")).getRole().getAssumeRolePolicyDocument();
            assertThat(aaAssumeRolePolicy != null, "Expected assume role policy for account administrator");
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Resetting assume role policy for account administrator");
                    youAre.updateAssumeRolePolicy(new UpdateAssumeRolePolicyRequest()
                            .withRoleName("AccountAdministrator")
                            .withPolicyDocument(aaAssumeRolePolicy));
                }
            });

            final String iaAssumeRolePolicy = youAre.getRole(new GetRoleRequest().withRoleName("InfrastructureAdministrator")).getRole().getAssumeRolePolicyDocument();
            assertThat(aaAssumeRolePolicy != null, "Expected assume role policy for account administrator");
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Resetting assume role policy for infrastructure administrator");
                    youAre.updateAssumeRolePolicy(new UpdateAssumeRolePolicyRequest()
                            .withRoleName("InfrastructureAdministrator")
                            .withPolicyDocument(iaAssumeRolePolicy));
                }
            });

            final String raAssumeRolePolicy = youAre.getRole(new GetRoleRequest().withRoleName("ResourceAdministrator")).getRole().getAssumeRolePolicyDocument();
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Resetting assume role policy for resource administrator");
                    youAre.updateAssumeRolePolicy(new UpdateAssumeRolePolicyRequest()
                            .withRoleName("ResourceAdministrator")
                            .withPolicyDocument(raAssumeRolePolicy));
                }
            });

            print("Updating assume role policy for default roles.");
            final String assumeRolePolicy = getAssumeRolePolicy(getAccountID(account));
            youAre.updateAssumeRolePolicy(new UpdateAssumeRolePolicyRequest()
                    .withRoleName("AccountAdministrator")
                    .withPolicyDocument(assumeRolePolicy));
            youAre.updateAssumeRolePolicy(new UpdateAssumeRolePolicyRequest()
                    .withRoleName("InfrastructureAdministrator")
                    .withPolicyDocument(assumeRolePolicy));
            youAre.updateAssumeRolePolicy(new UpdateAssumeRolePolicyRequest()
                    .withRoleName("ResourceAdministrator")
                    .withPolicyDocument(assumeRolePolicy));

            Map<String,String> accessKeys = getUserKeys("eucalyptus","admin");
            final String accessKey = accessKeys.get("ak");
            final String secretKey = accessKeys.get("sk");
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Removing user key for account " + account);
                    youAre.deleteAccessKey(new DeleteAccessKeyRequest(accessKey));
                }
            });

            // Test Admin Role
            final String testadminRoleAccount = NAME_PREFIX + "admin-role-account";
            YouAreClient euare = getYouAreClient(credentialsProvider("arn:aws:iam::eucalyptus:role/eucalyptus/AccountAdministrator", "session-name-here", accessKey, secretKey));
            euare.createAccount(new CreateAccountRequest().withAccountName(testadminRoleAccount));
            assertThat(getAccountID(testadminRoleAccount) != null, "Expected account ID");

            List<Account> result = new ArrayList<>();
            List<Account> accounts = euare.listAccounts().getAccounts();
            for (Account a : accounts) {
                if (a.getAccountName().equals(testadminRoleAccount)) {
                    result.add(a);
                }
            }
            assertThat(!result.isEmpty(), "expected account " + testadminRoleAccount);

            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    deleteAccount(testadminRoleAccount);
                }
            });

            // Test Infrastructure Admin Role
            final YouServClient youServ = new YouServClient(credentialsProvider("arn:aws:iam::eucalyptus:role/eucalyptus/InfrastructureAdministrator", "session-name-here", accessKey, secretKey));
            youServ.setEndpoint(EC2_ENDPOINT.substring(0, EC2_ENDPOINT.length() - 21) + "/services/Empyrean/");
            List<ServiceStatus> serviceStatuses = youServ.describeServices(new DescribeServicesRequest()).getServiceStatuses();
            assertThat(!serviceStatuses.isEmpty(), "Expected Services");

            final YouPropClient youProp = new YouPropClient(credentialsProvider("arn:aws:iam::eucalyptus:role/eucalyptus/InfrastructureAdministrator", "session-name-here", accessKey, secretKey));
            youProp.setEndpoint(EC2_ENDPOINT.substring(0, EC2_ENDPOINT.length() - 21) + "/services/Properties/");
            List<Property> properties = youProp.describeProperties().getProperties();
            assertThat(!properties.isEmpty(), "Expected Properties");

            final YouConfigClient youConfig = new YouConfigClient(credentialsProvider("arn:aws:iam::eucalyptus:role/eucalyptus/InfrastructureAdministrator", "session-name-here", accessKey, secretKey));
            youConfig.setEndpoint(EC2_ENDPOINT.substring(0, EC2_ENDPOINT.length() - 21) + "/services/Configuration/");
            List<ComponentInfo> components = youConfig.describeComponents().getComponentInfos();
            assertThat(!components.isEmpty(), "Expected Components");

            // Test Resource Admin Role  first create an account and add a keypair
            final String resourceAccount = NAME_PREFIX + "resource-account";
            final String keyName = NAME_PREFIX + "resource-key";
            createAccount(resourceAccount);

            print("Creating credentials for " + resourceAccount);
            AWSCredentialsProvider awsCredentialsProvider = new StaticCredentialsProvider( new BasicAWSCredentials(ACCESS_KEY, SECRET_KEY));
            final YouAreClient youAre = new YouAreClient(awsCredentialsProvider);
            youAre.setEndpoint(IAM_ENDPOINT);

            youAre.addRequestHandler(new AbstractRequestHandler() {
                public void beforeRequest(final Request<?> request) {
                    request.addParameter("DelegateAccount", resourceAccount);
                }
            });
            youAre.createAccessKey(new CreateAccessKeyRequest().withUserName("admin"));
            assertThat(awsCredentialsProvider != null, "Expected resource account credentials");

            AmazonEC2 ec2client = getEc2Client(awsCredentialsProvider);
            ec2client.createKeyPair(new CreateKeyPairRequest(keyName));
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting keypair in resource account: " + resourceAccount);
                    deleteKeyPair(keyName);
                }
            });

            AmazonEC2 userEc2client = getEc2Client(credentialsProvider("arn:aws:iam::eucalyptus:role/eucalyptus/ResourceAdministrator", "session-name-here", accessKey, secretKey));
            List<KeyPairInfo> found = new ArrayList<>();
            List<KeyPairInfo> keypairResult = userEc2client.describeKeyPairs(new DescribeKeyPairsRequest().withKeyNames(keyName)).getKeyPairs();
            for(KeyPairInfo k : keypairResult){
                if (k.getKeyName().equals(keyName)){
                    found.add(k);
                }
            }
            assertThat(!found.isEmpty(),"Expected keypair");


            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    deleteAccount(resourceAccount);
                }
            });

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
}