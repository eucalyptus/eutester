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
 * This application tests EC2 VPC security group egress rules functionality.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9611
 */
class TestEC2VPCSecurityGroupEgressRules {

    private final String host;
    private final AWSCredentialsProvider credentials


    public static void main(String[] args) throws Exception {
        new TestEC2VPCSecurityGroupEgressRules().EC2VPCSecurityGroupEgressRulesTest()
    }

    public TestEC2VPCSecurityGroupEgressRules() {
        minimalInit()
        this.host= HOST_IP
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
    public void EC2VPCSecurityGroupEgressRulesTest() throws Exception {
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

                print("Verifying security group rules for VPC ${vpcId} default group ${defaultSecurityGroupId}")
                describeSecurityGroups(new DescribeSecurityGroupsRequest(groupIds: [defaultSecurityGroupId])).with {
                    assertThat(securityGroups != null && securityGroups.size() == 1, "Expected one security group, but found: ${securityGroups?.size()}")
                    securityGroups[0].with {
                        assertThat(ipPermissionsEgress != null && ipPermissionsEgress.size() == 1, "Expected one egress rule, but was: ${ipPermissionsEgress?.size()}")
                        ipPermissionsEgress[0].with {
                            assertThat(ipProtocol == '-1', "Expected all protocols (-1), but was: ${ipProtocol}")
                            assertThat(fromPort == null, "Expected no from port, but was: ${fromPort}")
                            assertThat(toPort == null, "Expected no to port, but was: ${toPort}")
                            assertThat(userIdGroupPairs == null || userIdGroupPairs.isEmpty(), "Expected no source groups")
                            assertThat(ipRanges != null && ipRanges.size() == 1, "Expected one ip range, but was: ${ipRanges?.size()}")
                            assertThat(ipRanges[0] == '0.0.0.0/0', "Expected cidr '0.0.0.0/0', but was: ${ipRanges[0]}")
                        }
                    }
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
                        print("Authorizing for protocol ${protocol} from port ${fromPort} to port ${toPort} cidr ${cidrs} with security group ${securityGroupId1}")
                        authorizeSecurityGroupEgress(new AuthorizeSecurityGroupEgressRequest(
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

                        print("Verifying rule added for ${protocol} from port ${fromPort} to port ${toPort} cidr ${cidrs} with security group ${securityGroupId1}")
                        describeSecurityGroups(new DescribeSecurityGroupsRequest(
                                groupIds: [securityGroupId1],
                                filters: [
                                        new Filter(name: 'ip-permission.cidr', values: cidrs)
                                ]
                        )).with {
                            assertThat(securityGroups != null && securityGroups.size() == 1, "Group not found with expected cidr.")
                        }

                        print("Revoking authorization for protocol ${protocol} from port ${fromPort} to port ${toPort} cidr ${cidrs} with security group ${securityGroupId1}")
                        revokeSecurityGroupEgress(new RevokeSecurityGroupEgressRequest(
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

                        print("Verifying rule removed for ${protocol} from port ${fromPort} to port ${toPort} cidr ${cidrs} with security group ${securityGroupId1}")
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
                    authorizeSecurityGroupEgress(new AuthorizeSecurityGroupEgressRequest(
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
                    print("Expected failure: " + e)
                }

                print("Authorizing from VPC group ${securityGroupId2} with security group ${securityGroupId1}")
                authorizeSecurityGroupEgress(new AuthorizeSecurityGroupEgressRequest(
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
                revokeSecurityGroupEgress(new RevokeSecurityGroupEgressRequest(
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
