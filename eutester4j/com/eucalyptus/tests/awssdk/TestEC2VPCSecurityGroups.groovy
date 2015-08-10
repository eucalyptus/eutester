package com.eucalyptus.tests.awssdk

import com.amazonaws.AmazonServiceException
import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.*
import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit


/**
 * This application tests EC2 VPC security group functionality.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9608
 */
class TestEC2VPCSecurityGroups {

    private final String host;
    private final AWSCredentialsProvider credentials


    public static void main(String[] args) throws Exception {
        new TestEC2VPCSecurityGroups().EC2VPCSecurityGroupsTest()
    }


    public TestEC2VPCSecurityGroups() {
        minimalInit()
        this.host=HOST_IP
        this.credentials = new StaticCredentialsProvider(new BasicAWSCredentials(ACCESS_KEY, SECRET_KEY))
    }

    private String cloudUri(String servicePath) {
        URI.create("http://" + host + ":8773/")
                .resolve(servicePath)
                .toString()
    }

    private AmazonEC2 getEC2Client(final AWSCredentialsProvider credentials) {
        final AmazonEC2 ec2 = new AmazonEC2Client(credentials)
        ec2.setEndpoint(cloudUri("/services/compute"))
        ec2
    }

    private boolean assertThat(boolean condition,
                               String message) {
        assert condition: message
        true
    }

    private void print(String text) {
        System.out.println(text)
    }

    @Test
    public void EC2VPCSecurityGroupsTest() throws Exception {
        final AmazonEC2 ec2 = getEC2Client(credentials)

        final List<Runnable> cleanupTasks = [] as List<Runnable>
        try {
            ec2.with {
                print('Creating VPC')
                String vpcId = createVpc(new CreateVpcRequest(cidrBlock: '172.30.0.0/24')).with {
                    vpc.with {
                        vpcId
                    }
                }
                print("Created VPC with id ${vpcId}")
                cleanupTasks.add {
                    print("Deleting VPC ${vpcId}")
                    deleteVpc(new DeleteVpcRequest(vpcId: vpcId))
                }

                print("Finding default security group for VPC ${vpcId}")
                String defaultSecurityGroupId = describeSecurityGroups(new DescribeSecurityGroupsRequest(
                        filters: [new Filter(name: "vpc-id", values: [vpcId])]
                )).with {
                    securityGroups?.getAt(0)?.groupId
                }
                assertThat(defaultSecurityGroupId != null, "Expected default security group for VPC")
                print("Found default security group ${defaultSecurityGroupId}")

                print("Verifying that default security group ${defaultSecurityGroupId} for vpc ${vpcId} cannot be deleted")
                try {
                    deleteSecurityGroup(new DeleteSecurityGroupRequest(groupId: defaultSecurityGroupId))
                    assertThat(false, "Expected deletion failure for default security group")
                } catch (AmazonServiceException e) {
                    assertThat('CannotDelete' == e.errorCode, "Expected CannotDelete error code, but was: ${e.errorCode}")
                }

                print("Verifying security group rules for VPC ${vpcId} default group ${defaultSecurityGroupId}")
                describeSecurityGroups(new DescribeSecurityGroupsRequest(groupIds: [defaultSecurityGroupId])).with {
                    assertThat(securityGroups != null && securityGroups.size() == 1, "Expected one security group, but found: ${securityGroups?.size()}")
                    securityGroups[0].with {
                        String expectedUserId = ownerId
                        assertThat(groupId == defaultSecurityGroupId, "Expected group id ${defaultSecurityGroupId}, but was: ${groupId}")
                        assertThat(description == 'default VPC security group', "Expected description 'default VPC security group', but was: ${description}")
                        assertThat(ipPermissions != null && ipPermissions.size() == 1, "Expected one ingress rule, but was: ${ipPermissions?.size()}")
                        ipPermissions[0].with {
                            assertThat(ipProtocol == '-1', "Expected all protocols (-1), but was: ${ipProtocol}")
                            assertThat(fromPort == null, "Expected no from port, but was: ${fromPort}")
                            assertThat(toPort == null, "Expected no to port, but was: ${toPort}")
                            assertThat(userIdGroupPairs != null && userIdGroupPairs.size() == 1, "Expected one source group, but was: ${userIdGroupPairs?.size()}")
                            assertThat(ipRanges == null || ipRanges.isEmpty(), "Expected no ip ranges, but was: ${ipRanges?.size()}")
                            userIdGroupPairs[0].with {
                                assertThat(expectedUserId == userId, "Expected user ${expectedUserId}, but was: ${userId}")
                                assertThat(defaultSecurityGroupId == groupId, "Expected user ${defaultSecurityGroupId}, but was: ${groupId}")
                            }
                        }
                    }
                }

                try {
                    print("Verifying that VPC security group cannot be created with unsupported characters in name")
                    createSecurityGroup(new CreateSecurityGroupRequest(
                            groupName: "```security-group-failure-1-${vpcId}",
                            description: "Tests security group 1 for VPC ${vpcId}",
                            vpcId: vpcId
                    ))
                    assertThat(false, "Expected creation failure due to unsupported characters in name")
                } catch (AmazonServiceException e) {
                    assertThat('InvalidParameterValue' == e.errorCode, "Expected InvalidParameterValue error code, but was: ${e.errorCode}")
                }

                try {
                    print("Verifying that VPC security group cannot be created with unsupported characters in description")
                    createSecurityGroup(new CreateSecurityGroupRequest(
                            groupName: "security-group-failure-2-${vpcId}",
                            description: "```Tests security group 1 for VPC ${vpcId}",
                            vpcId: vpcId
                    ))
                    assertThat(false, "Expected creation failure due to unsupported characters in description")
                } catch (AmazonServiceException e) {
                    assertThat('InvalidParameterValue' == e.errorCode, "Expected InvalidParameterValue error code, but was: ${e.errorCode}")
                }

                print("Creating security groups in VPC ${vpcId}")
                String securityGroupId1 = createSecurityGroup(new CreateSecurityGroupRequest(
                        groupName: "security-group-1-${vpcId}",
                        description: "Test security group 1 for VPC ${vpcId}",
                        vpcId: vpcId
                )).with {
                    groupId
                }
                print("Created security group ${securityGroupId1} in VPC ${vpcId}")
                cleanupTasks.add {
                    print("Deleting security group ${securityGroupId1}")
                    deleteSecurityGroup(new DeleteSecurityGroupRequest(groupId: securityGroupId1))
                }

                String securityGroupId2 = createSecurityGroup(new CreateSecurityGroupRequest(
                        groupName: "security-group-2-${vpcId}",
                        description: "Test security group 2 for VPC ${vpcId}",
                        vpcId: vpcId
                )).with {
                    groupId
                }
                print("Created security group ${securityGroupId2} in VPC ${vpcId}")
                cleanupTasks.add {
                    print("Deleting security group ${securityGroupId2}")
                    deleteSecurityGroup(new DeleteSecurityGroupRequest(groupId: securityGroupId2))
                }

                String securityGroupId3 = createSecurityGroup(new CreateSecurityGroupRequest(
                        groupName: "security-group-3-${vpcId}",
                        description: "Test security group 3",
                )).with {
                    groupId
                }
                print("Created security group ${securityGroupId3} (default / no VPC)")
                cleanupTasks.add {
                    print("Deleting security group ${securityGroupId3}")
                    deleteSecurityGroup(new DeleteSecurityGroupRequest(groupId: securityGroupId3))
                }

                [
                        [null, null, ['-1', '0', '67', '113', '255'], ['1.1.1.1/32']],
                        [1, 100, ['6', '17', 'tcp', 'udp'], ['1.1.1.1/32']],
                        [2, 4, ["1", "icmp"], ['1.1.1.1/32']],
                        [null, null, ['0'], ['255.255.255.255/24', '1.0.0.0/32']],
                ].each { fromPort, toPort, protocols, cidrs ->
                    protocols.each { String protocol ->
                        print("Authorizing for protocol ${protocol} with security group ${securityGroupId1}")
                        authorizeSecurityGroupIngress(new AuthorizeSecurityGroupIngressRequest(
                                groupId: securityGroupId1,
                                ipPermissions: [
                                        new IpPermission(
                                                ipProtocol: protocol,
                                                fromPort: fromPort,
                                                toPort: toPort,
                                                ipRanges: cidrs
                                        )
                                ]
                        ))

                        print("Verifying rule added for ${protocol} with security group ${securityGroupId1}")
                        describeSecurityGroups(new DescribeSecurityGroupsRequest(
                                groupIds: [securityGroupId1],
                                filters: [
                                        new Filter(name: 'ip-permission.cidr', values: cidrs)
                                ]
                        )).with {
                            assertThat(securityGroups != null && securityGroups.size() == 1, "Group not found with expected cidr.")
                        }

                        print("Revoking authorization for protocol ${protocol} with security group ${securityGroupId1}")
                        revokeSecurityGroupIngress(new RevokeSecurityGroupIngressRequest(
                                groupId: securityGroupId1,
                                ipPermissions: [
                                        new IpPermission(
                                                ipProtocol: protocol,
                                                fromPort: fromPort,
                                                toPort: toPort,
                                                ipRanges: cidrs
                                        )
                                ]
                        ))

                        print("Verifying rule removed for ${protocol} with security group ${securityGroupId1}")
                        describeSecurityGroups(new DescribeSecurityGroupsRequest(
                                groupIds: [securityGroupId1],
                                filters: [
                                        new Filter(name: 'ip-permission.cidr', values: cidrs)
                                ]
                        )).with {
                            assertThat(securityGroups == null || securityGroups.isEmpty(), "Group found with cidr.")
                        }
                    }
                }

                print("Verifying authorization fails for non-VPC group rule")
                try {
                    authorizeSecurityGroupIngress(new AuthorizeSecurityGroupIngressRequest(
                            groupId: securityGroupId1,
                            ipPermissions: [
                                    new IpPermission(
                                            ipProtocol: 'tcp',
                                            fromPort: 22,
                                            toPort: 22,
                                            userIdGroupPairs: [
                                                    new UserIdGroupPair(
                                                            groupId: securityGroupId3
                                                    )
                                            ]
                                    )
                            ]
                    ))
                    assertThat(false, 'Expected failure when authorizing from non-VPC group')
                } catch (AmazonServiceException e) {
                }


                print("Authorizing from VPC group ${securityGroupId2} with security group ${securityGroupId1}")
                authorizeSecurityGroupIngress(new AuthorizeSecurityGroupIngressRequest(
                        groupId: securityGroupId1,
                        ipPermissions: [
                                new IpPermission(
                                        ipProtocol: 'tcp',
                                        fromPort: 22,
                                        toPort: 22,
                                        userIdGroupPairs: [
                                                new UserIdGroupPair(
                                                        groupId: securityGroupId2
                                                )
                                        ]
                                )
                        ]
                ))

                print("Verifying rule added for VPC group ${securityGroupId2} with security group ${securityGroupId1}")
                describeSecurityGroups(new DescribeSecurityGroupsRequest(
                        groupIds: [securityGroupId1],
                        filters: [
                                new Filter(name: 'ip-permission.group-id', values: [securityGroupId2])
                        ]
                )).with {
                    assertThat(securityGroups != null && securityGroups.size() == 1, "Group not found with expected source group.")
                }

                print("Revoking authorization for VPC group ${securityGroupId2} with security group ${securityGroupId1}")
                revokeSecurityGroupIngress(new RevokeSecurityGroupIngressRequest(
                        groupId: securityGroupId1,
                        ipPermissions: [
                                new IpPermission(
                                        ipProtocol: 'tcp',
                                        fromPort: 22,
                                        toPort: 22,
                                        userIdGroupPairs: [
                                                new UserIdGroupPair(
                                                        groupId: securityGroupId2
                                                )
                                        ]
                                )
                        ]
                ))

                print("Verifying rule removed for VPC group ${securityGroupId2} with security group ${securityGroupId1}")
                describeSecurityGroups(new DescribeSecurityGroupsRequest(
                        groupIds: [securityGroupId1],
                        filters: [
                                new Filter(name: 'ip-permission.group-id', values: [securityGroupId2])
                        ]
                )).with {
                    assertThat(securityGroups == null || securityGroups.isEmpty(), "Group found with source group.")
                }
            }

            print("Test complete")
        } finally {
            // Attempt to clean up anything we created
            cleanupTasks.reverseEach { Runnable cleanupTask ->
                try {
                    cleanupTask.run()
                } catch (Exception e) {
                    // Some not-found errors are expected here so may need to be suppressed
                    e.printStackTrace()
                }
            }
        }
    }
}
