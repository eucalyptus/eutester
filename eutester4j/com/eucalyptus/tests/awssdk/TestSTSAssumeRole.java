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

import com.amazonaws.AmazonServiceException;
import com.amazonaws.auth.AWSCredentials;
import com.amazonaws.auth.AWSCredentialsProvider;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.auth.BasicSessionCredentials;
import com.amazonaws.services.ec2.AmazonEC2;
import com.amazonaws.services.ec2.AmazonEC2Client;
import com.amazonaws.services.ec2.model.DescribeImagesRequest;
import com.amazonaws.services.ec2.model.DescribeImagesResult;
import com.amazonaws.services.ec2.model.Filter;
import com.amazonaws.services.identitymanagement.model.*;
import com.amazonaws.services.securitytoken.AWSSecurityTokenService;
import com.amazonaws.services.securitytoken.AWSSecurityTokenServiceClient;
import com.amazonaws.services.securitytoken.model.AssumeRoleRequest;
import com.amazonaws.services.securitytoken.model.AssumeRoleResult;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

/**
 * This application tests assuming an IAM role using STS and consuming EC2 with the role.
 * <p/>
 * This is verification for the story:
 * <p/>
 * https://eucalyptus.atlassian.net/browse/EUCA-5250
 * <p/>
 * Prerequisites:
 * <p/>
 * - This test must be run as a user outside the cloud administrator account.
 */
public class TestSTSAssumeRole {

    @Test
    public void STSAssumeRoleTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();

        final GetUserResult userResult = youAre.getUser(new GetUserRequest());
        assertThat(userResult.getUser() != null, "Expected current user info");
        assertThat(userResult.getUser().getArn() != null, "Expected current user ARN");
        final String userArn = userResult.getUser().getArn();
        print("Got user ARN (will convert account alias to ID if necessary): " + userArn);

        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // Create role to get a client id
            final String accountId;
            {
                final String roleNameA = NAME_PREFIX + "AssumeRoleTestA";
                print("Creating role to determine account number: " + roleNameA);
                final CreateRoleResult roleResult = youAre.createRole(new CreateRoleRequest()
                        .withRoleName(roleNameA)
                        .withAssumeRolePolicyDocument(
                                "{\n" +
                                        "    \"Statement\": [ {\n" +
                                        "      \"Effect\": \"Allow\",\n" +
                                        "      \"Principal\": {\n" +
                                        "         \"AWS\": [ \"" + userArn + "\" ]\n" +
                                        "      },\n" +
                                        "      \"Action\": [ \"sts:AssumeRole\" ],\n" +
                                        "      \"Condition\": {" +
                                        "         \"StringEquals\": {" +
                                        "           \"sts:ExternalId\": \"222222222222\"" +
                                        "         }" +
                                        "      }" +
                                        "    } ]\n" +
                                        "}"));
                cleanupTasks.add(new Runnable() {
                    @Override
                    public void run() {
                        print("Deleting role: " + roleNameA);
                        youAre.deleteRole(new DeleteRoleRequest()
                                .withRoleName(roleNameA));
                    }
                });
                assertThat(roleResult.getRole() != null, "Expected role");
                assertThat(roleResult.getRole().getArn() != null, "Expected role ARN");
                assertThat(roleResult.getRole().getArn().length() > 25, "Expected role ARN length to exceed 25 characters");
                final String roleArn = roleResult.getRole().getArn();
                accountId = roleArn.substring(13, 25);
            }
            final String userCleanedArn = "arn:aws:iam::" + accountId + ":" + userArn.substring(userArn.lastIndexOf(':') + 1);
            print("Using account id: " + accountId);
            print("Using user ARN in assume role policy: " + userCleanedArn);

            // Create role
            final String roleName = NAME_PREFIX + "AssumeRoleTest";
            print("Creating role: " + roleName);
            youAre.createRole(new CreateRoleRequest()
                    .withRoleName(roleName)
                    .withPath("/path")
                    .withAssumeRolePolicyDocument(
                            "{\n" +
                                    "    \"Statement\": [ {\n" +
                                    "      \"Effect\": \"Allow\",\n" +
                                    "      \"Principal\": {\n" +
                                    "         \"AWS\": [ \"" + userCleanedArn + "\" ]\n" +
                                    "      },\n" +
                                    "      \"Action\": [ \"sts:AssumeRole\" ],\n" +
                                    "      \"Condition\": {" +
                                    "         \"StringEquals\": {" +
                                    "           \"sts:ExternalId\": \"222222222222\"" +
                                    "         }" +
                                    "      }" +
                                    "    } ]\n" +
                                    "}"));
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting role: " + roleName);
                    youAre.deleteRole(new DeleteRoleRequest()
                            .withRoleName(roleName));
                }
            });

            // Get role info
            print("Getting role: " + roleName);
            final GetRoleResult result = youAre.getRole(new GetRoleRequest().withRoleName(roleName));
            assertThat(result.getRole() != null, "Expected role");
            assertThat(result.getRole().getArn() != null, "Expected role ARN");
            final String roleArn = result.getRole().getArn();

            // Describe images using role, no permissions so should see nothing
            print("Describing images to ensure no permission with role: " + roleName);
            {
                final DescribeImagesResult imagesResult = getImagesUsingRole(roleName, roleArn, "222222222222");
                assertThat(imagesResult.getImages().size() == 0, "Image found when using role with no permissions");
            }

            // Add policy to role
            final String policyName = NAME_PREFIX + "AssumeRoleTest";
            print("Adding policy: " + policyName + " to role: " + roleName);
            youAre.putRolePolicy(new PutRolePolicyRequest()
                    .withRoleName(roleName)
                    .withPolicyName(policyName)
                    .withPolicyDocument(
                            "{\n" +
                                    "   \"Statement\":[{\n" +
                                    "      \"Effect\":\"Allow\",\n" +
                                    "      \"Action\":\"ec2:*\",\n" +
                                    "      \"Resource\":\"*\"\n" +
                                    "   }]\n" +
                                    "}"));
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Removing policy: " + policyName + ", from role: " + roleName);
                    youAre.deleteRolePolicy(new DeleteRolePolicyRequest().withRoleName(roleName).withPolicyName(policyName));
                }
            });

            // Describe images using role
            {
                final DescribeImagesResult imagesResult = getImagesUsingRole(roleName, roleArn, "222222222222");
                assertThat(imagesResult.getImages().size() > 0, "Image not found when using role");
                final String imageId = imagesResult.getImages().get(0).getImageId();
                print("Found image: " + imageId);
            }

            // Describe images using role with incorrect external id
            print("Ensuring listing images fails when incorrect external id used with role: " + roleName);
            try {
                getImagesUsingRole(roleName, roleArn, "222222222221");
                assertThat(false, "Expected error due to incorrect external id when assuming role (test must not be run as cloud admin)");
            } catch (AmazonServiceException e) {
                print("Received expected exception: " + e);
            }

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

    private AmazonEC2 getEc2ClientUsingRole(final String roleArn,
                                            final String externalId,
                                            final String sessionName) {
        final AmazonEC2 ec2 = new AmazonEC2Client(new AWSCredentialsProvider() {
            @Override
            public AWSCredentials getCredentials() {
                AWSCredentials creds = new BasicAWSCredentials(ACCESS_KEY, SECRET_KEY);
                final AWSSecurityTokenService sts = new AWSSecurityTokenServiceClient(creds);
                sts.setEndpoint(TOKENS_ENDPOINT);
                final AssumeRoleResult assumeRoleResult = sts.assumeRole(new AssumeRoleRequest()
                        .withRoleArn(roleArn)
                        .withExternalId(externalId)
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

    private DescribeImagesResult getImagesUsingRole(final String roleName, final String roleArn, String externalId) {
        final AmazonEC2 ec2 = getEc2ClientUsingRole(roleArn, externalId, "session-name-here");

        print("Searching images using role: " + roleName);
        return ec2.describeImages(new DescribeImagesRequest().withFilters(
                new Filter().withName("image-type").withValues("machine"),
                new Filter().withName("root-device-type").withValues("instance-store")
        ));
    }
}
