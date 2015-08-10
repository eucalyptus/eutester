package com.eucalyptus.tests.awssdk

import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.*
import org.testng.annotations.Test

import static com.eucalyptus.tests.awssdk.Eutester4j.*

/**
 * This application tests tagging and filtering for EC2 VPC resources.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9607
 */
class TestEC2VPCTaggingFiltering {

    private final AWSCredentialsProvider credentials


    public static void main(String[] args) throws Exception {
        new TestEC2VPCTaggingFiltering().TestEC2VPCTaggingFilteringTest()
    }


    public TestEC2VPCTaggingFiltering() {
        minimalInit()
        this.credentials = new StaticCredentialsProvider(new BasicAWSCredentials(ACCESS_KEY, SECRET_KEY))
    }

    private AmazonEC2 getEC2Client(final AWSCredentialsProvider credentials) {
        final AmazonEC2 ec2 = new AmazonEC2Client(credentials)
        ec2.setEndpoint(EC2_ENDPOINT)
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
    public void TestEC2VPCTaggingFilteringTest() throws Exception {
        final AmazonEC2 ec2 = getEC2Client(credentials)

        // Find an AZ to use
        final DescribeAvailabilityZonesResult azResult = ec2.describeAvailabilityZones();

        assertThat(azResult.getAvailabilityZones().size() > 0, "Availability zone not found");

        final String availabilityZone = azResult.getAvailabilityZones().get(0).getZoneName();
        print("Using availability zone: " + availabilityZone);

        final List<Runnable> cleanupTasks = [] as List<Runnable>
        try {
            ec2.with {
                print('Creating internet gateway')
                String internetGatewayId = createInternetGateway(new CreateInternetGatewayRequest()).with {
                    internetGateway.internetGatewayId
                }
                print("Created internet gateway with id ${internetGatewayId}")
                cleanupTasks.add {
                    print("Deleting internet gateway ${internetGatewayId}")
                    deleteInternetGateway(new DeleteInternetGatewayRequest(internetGatewayId: internetGatewayId))
                }

                print('Creating VPC')
                String defaultDhcpOptionsId = null
                String vpcId = createVpc(new CreateVpcRequest(cidrBlock: '10.1.2.0/24')).with {
                    vpc.with {
                        defaultDhcpOptionsId = dhcpOptionsId
                        vpcId
                    }
                }
                print("Created VPC with id ${vpcId} and dhcp options id ${defaultDhcpOptionsId}")
                cleanupTasks.add {
                    print("Deleting VPC ${vpcId}")
                    deleteVpc(new DeleteVpcRequest(vpcId: vpcId))
                }

                print("Attaching internet gateway ${internetGatewayId} to VPC ${vpcId}")
                attachInternetGateway(new AttachInternetGatewayRequest(internetGatewayId: internetGatewayId, vpcId: vpcId))
                cleanupTasks.add {
                    print("Detaching internet gateway ${internetGatewayId} from VPC ${vpcId}")
                    detachInternetGateway(new DetachInternetGatewayRequest(internetGatewayId: internetGatewayId, vpcId: vpcId))
                }

                print('Creating subnet')
                String subnetId = createSubnet(new CreateSubnetRequest(vpcId: vpcId, availabilityZone: availabilityZone, cidrBlock: '10.1.2.0/24')).with {
                    subnet.with {
                        subnetId
                    }
                }
                print("Created subnet with id ${subnetId}")
                cleanupTasks.add {
                    print("Deleting subnet ${subnetId}")
                    deleteSubnet(new DeleteSubnetRequest(subnetId: subnetId))
                }

                print("Finding default route table for VPC ${vpcId}")
                String defaultRouteTableId = describeRouteTables(new DescribeRouteTablesRequest(
                        filters: [new Filter(name: "vpc-id", values: [vpcId])]
                )).with {
                    routeTables?.getAt(0)?.routeTableId
                }
                assertThat(defaultRouteTableId != null, "Expected default route table for VPC")
                print("Found default route table ${defaultRouteTableId}")

                print("Finding default nework ACL for VPC ${vpcId}")
                String defaultNetworkAclId = describeNetworkAcls(new DescribeNetworkAclsRequest(
                        filters: [new Filter(name: "vpc-id", values: [vpcId])]
                )).with {
                    networkAcls?.getAt(0)?.networkAclId
                }
                assertThat(defaultNetworkAclId != null, "Expected default network ACL for VPC")
                print("Found default network ACL ${defaultNetworkAclId}")

                print('Creating network interface')
                String networkInterfaceId = createNetworkInterface(new CreateNetworkInterfaceRequest(subnetId: subnetId, description: 'a network interface', privateIpAddress: '10.1.2.10')).with {
                    networkInterface.with {
                        networkInterfaceId
                    }
                }
                print("Created network interface with id ${networkInterfaceId}")
                cleanupTasks.add {
                    print("Deleting network interface ${networkInterfaceId}")
                    deleteNetworkInterface(new DeleteNetworkInterfaceRequest(networkInterfaceId: networkInterfaceId))
                }

                print("Creating vpc=${vpcId} tag on VPC resources")
                createTags(new CreateTagsRequest(
                        resources: [defaultDhcpOptionsId, internetGatewayId, defaultNetworkAclId, defaultRouteTableId, networkInterfaceId, subnetId, vpcId],
                        tags: [new Tag(key: 'vpc', value: vpcId)]
                ))

                print('Verifying via describe tags')
                describeTags(new DescribeTagsRequest(
                        filters: [new Filter(name: 'value', values: [vpcId])]
                )).with {
                    assertThat(tags != null, 'Expected tags collection')
                    assertThat(!tags.isEmpty(), 'Expected tags')
                    Collection<String> expectedResources = [defaultDhcpOptionsId, internetGatewayId, defaultNetworkAclId, defaultRouteTableId, networkInterfaceId, subnetId, vpcId]
                    tags.each { TagDescription tagDescription ->
                        assertThat(tagDescription.key == 'vpc', "Expected tag key 'vpc', but was: ${tagDescription.key}")
                        assertThat(tagDescription.value == vpcId, "Expected tag value ${vpcId}, but was: ${tagDescription.value}")
                        assertThat(expectedResources.remove(tagDescription.resourceId), 'Unexpected resource identifier')
                    }
                }

                print("Verifying DHCP options tag filtering")
                describeDhcpOptions(new DescribeDhcpOptionsRequest(
                        filters: [new Filter(name: 'tag:vpc', values: [vpcId])]
                )).with {
                    assertThat(dhcpOptions != null, 'Expected DHCP options')
                    assertThat(dhcpOptions.size() == 1, 'Expected one DHCP options')
                    assertThat(dhcpOptions?.getAt(0)?.dhcpOptionsId == defaultDhcpOptionsId, "Expected DHCP options ${defaultDhcpOptionsId}, but was: ${dhcpOptions?.getAt(0)?.dhcpOptionsId}")
                }

                print("Verifying internet gateway tag filtering")
                describeInternetGateways(new DescribeInternetGatewaysRequest(
                        filters: [new Filter(name: 'tag:vpc', values: [vpcId])]
                )).with {
                    assertThat(internetGateways != null, 'Expected internet gateways')
                    assertThat(internetGateways.size() == 1, 'Expected one internet gateway')
                    assertThat(internetGateways?.getAt(0)?.internetGatewayId == internetGatewayId, "Expected internet gateway ${internetGatewayId}, but was: ${internetGateways?.getAt(0)?.internetGatewayId}")
                }

                print("Verifying network ACL tag filtering")
                describeNetworkAcls(new DescribeNetworkAclsRequest(
                        filters: [new Filter(name: 'tag:vpc', values: [vpcId])]
                )).with {
                    assertThat(networkAcls != null, 'Expected network acls')
                    assertThat(networkAcls.size() == 1, 'Expected one network acl')
                    assertThat(networkAcls?.getAt(0)?.networkAclId == defaultNetworkAclId, "Expected network ACL ${defaultNetworkAclId}, but was: ${networkAcls?.getAt(0)?.networkAclId}")
                }

                print("Verifying route table tag filtering")
                describeRouteTables(new DescribeRouteTablesRequest(
                        filters: [new Filter(name: 'tag:vpc', values: [vpcId])]
                )).with {
                    assertThat(routeTables != null, 'Expected route tables')
                    assertThat(routeTables.size() == 1, 'Expected one route table')
                    assertThat(routeTables?.getAt(0)?.routeTableId == defaultRouteTableId, "Expected route table ${defaultRouteTableId}, but was: ${routeTables?.getAt(0)?.routeTableId}")
                }

                print("Verifying network interface tag filtering")
                describeNetworkInterfaces(new DescribeNetworkInterfacesRequest(
                        filters: [new Filter(name: 'tag:vpc', values: [vpcId])]
                )).with {
                    assertThat(networkInterfaces != null, 'Expected network interfaces')
                    assertThat(networkInterfaces.size() == 1, 'Expected one network interface')
                    assertThat(networkInterfaces?.getAt(0)?.networkInterfaceId == networkInterfaceId, "Expected network interface ${networkInterfaceId}, but was: ${networkInterfaces?.getAt(0)?.networkInterfaceId}")
                }

                print("Verifying subnet tag filtering")
                describeSubnets(new DescribeSubnetsRequest(
                        filters: [new Filter(name: 'tag:vpc', values: [vpcId])]
                )).with {
                    assertThat(subnets != null, 'Expected subnets')
                    assertThat(subnets.size() == 1, 'Expected one subnet')
                    assertThat(subnets?.getAt(0)?.subnetId == subnetId, "Expected subnet ${subnetId}, but was: ${subnets?.getAt(0)?.subnetId}")
                }

                print("Verifying vpc tag filtering")
                describeVpcs(new DescribeVpcsRequest(
                        filters: [new Filter(name: 'tag:vpc', values: [vpcId])]
                )).with {
                    assertThat(vpcs != null, 'Expected vpcs')
                    assertThat(vpcs.size() == 1, 'Expected one vpc')
                    assertThat(vpcs?.getAt(0)?.vpcId == vpcId, "Expected vpc ${vpcId}, but was: ${vpcs?.getAt(0)?.vpcId}")
                }

                print("Deleting vpc=${vpcId} tag from VPC resources")
                deleteTags(new DeleteTagsRequest(
                        resources: [defaultDhcpOptionsId, internetGatewayId, defaultNetworkAclId, defaultRouteTableId, networkInterfaceId, subnetId, vpcId],
                        tags: [new Tag(key: 'vpc', value: vpcId)]
                ))

                print('Verifying tags deleted')
                describeTags(new DescribeTagsRequest(
                        filters: [new Filter(name: 'value', values: [vpcId])]
                )).with {
                    assertThat(tags != null, 'Expected tags collection')
                    assertThat(tags.isEmpty(), 'Expected no tags')
                }

                print("Verifying filters for dhcp options ${defaultDhcpOptionsId}")
                describeDhcpOptions(new DescribeDhcpOptionsRequest(
                        filters: [
                                new Filter(name: 'dhcp-options-id', values: [defaultDhcpOptionsId]),
                                new Filter(name: 'key', values: ['domain-name-servers']),
                                new Filter(name: 'value', values: ['AmazonProvidedDNS']),
                        ]
                )).with {
                    assertThat(dhcpOptions != null, 'Expected DHCP options')
                    assertThat(dhcpOptions.size() == 1, 'Expected one DHCP options')
                    assertThat(dhcpOptions?.getAt(0)?.dhcpOptionsId == defaultDhcpOptionsId, "Expected DHCP options ${defaultDhcpOptionsId}, but was: ${dhcpOptions?.getAt(0)?.dhcpOptionsId}")
                }

                print("Verifying filtering for dhcp options ${defaultDhcpOptionsId}")
                describeDhcpOptions(new DescribeDhcpOptionsRequest(
                        filters: [
                                new Filter(name: 'dhcp-options-id', values: [defaultDhcpOptionsId]),
                                new Filter(name: 'key', values: ['domain-name-servers']),
                                new Filter(name: 'value', values: ['INVALID']),
                        ]
                )).with {
                    assertThat(dhcpOptions != null, 'Expected DHCP options collection')
                    assertThat(dhcpOptions.isEmpty(), 'Expected no DHCP options')
                }

                print("Verifying filters for internet gateways ${internetGatewayId}")
                describeInternetGateways(new DescribeInternetGatewaysRequest(
                        filters: [
                                new Filter(name: 'internet-gateway-id', values: [internetGatewayId]),
                                new Filter(name: 'attachment.state', values: ['available']),
                                new Filter(name: 'attachment.vpc-id', values: [vpcId]),
                        ]
                )).with {
                    assertThat(internetGateways != null, 'Expected internet gateways')
                    assertThat(internetGateways.size() == 1, 'Expected one internet gateway')
                    assertThat(internetGateways?.getAt(0)?.internetGatewayId == internetGatewayId, "Expected internet gateway ${internetGatewayId}, but was: ${internetGateways?.getAt(0)?.internetGatewayId}")
                }

                print("Verifying filtering for internet gateways ${internetGatewayId}")
                describeInternetGateways(new DescribeInternetGatewaysRequest(
                        filters: [
                                new Filter(name: 'internet-gateway-id', values: [internetGatewayId]),
                                new Filter(name: 'attachment.state', values: ['INVALID']),
                                new Filter(name: 'attachment.vpc-id', values: [vpcId]),
                        ]
                )).with {
                    assertThat(internetGateways != null, 'Expected internet gateways collection')
                    assertThat(internetGateways.isEmpty(), 'Expected no internet gateways')
                }

                print("Verifying filters for network ACL ${defaultNetworkAclId}")
                describeNetworkAcls(new DescribeNetworkAclsRequest(
                        filters: [
                                new Filter(name: 'association.network-acl-id', values: [defaultNetworkAclId]),
                                new Filter(name: 'association.subnet-id', values: [subnetId]),
                                new Filter(name: 'default', values: ['true']),
                                new Filter(name: 'entry.cidr', values: ['0.0.0.0/0']),
                                new Filter(name: 'entry.egress', values: ['true']),
                                new Filter(name: 'entry.rule-action', values: ['allow']),
                                new Filter(name: 'entry.rule-number', values: ['100']),
                                new Filter(name: 'network-acl-id', values: [defaultNetworkAclId]),
                                new Filter(name: 'vpc-id', values: [vpcId]),
                        ]
                )).with {
                    assertThat(networkAcls != null, 'Expected internet gateways')
                    assertThat(networkAcls.size() == 1, 'Expected one internet gateway')
                    assertThat(networkAcls?.getAt(0)?.networkAclId == defaultNetworkAclId, "Expected network ACL ${defaultNetworkAclId}, but was: ${networkAcls?.getAt(0)?.networkAclId}")
                }

                print("Verifying filtering for network ACL ${defaultNetworkAclId}")
                describeNetworkAcls(new DescribeNetworkAclsRequest(
                        filters: [
                                new Filter(name: 'association.network-acl-id', values: [defaultNetworkAclId]),
                                new Filter(name: 'association.subnet-id', values: [subnetId]),
                                new Filter(name: 'default', values: ['true']),
                                new Filter(name: 'entry.cidr', values: ['0.0.0.0/0']),
                                new Filter(name: 'entry.egress', values: ['true']),
                                new Filter(name: 'entry.rule-action', values: ['INVALID']),
                                new Filter(name: 'entry.rule-number', values: ['100']),
                                new Filter(name: 'network-acl-id', values: [defaultNetworkAclId]),
                                new Filter(name: 'vpc-id', values: [vpcId]),
                        ]
                )).with {
                    assertThat(networkAcls != null, 'Expected network acls')
                    assertThat(networkAcls.isEmpty(), 'Expected no network acls')
                }

                print("Verifying filters for route table ${defaultRouteTableId}")
                describeRouteTables(new DescribeRouteTablesRequest(
                        filters: [
                                new Filter(name: 'association.route-table-id', values: [defaultRouteTableId]),
                                new Filter(name: 'association.subnet-id', values: [subnetId]),
                                new Filter(name: 'association.main', values: ['true']),
                                new Filter(name: 'route-table-id', values: [defaultRouteTableId]),
                                new Filter(name: 'route.destination-cidr-block', values: ['10.1.2.0/24']),
                                new Filter(name: 'route.origin', values: ['CreateRouteTable']),
                                new Filter(name: 'route.state', values: ['active']),
                                new Filter(name: 'vpc-id', values: [vpcId]),
                        ]
                )).with {
                    assertThat(routeTables != null, 'Expected route tables')
                    assertThat(routeTables.size() == 1, 'Expected one route table')
                    assertThat(routeTables?.getAt(0)?.routeTableId == defaultRouteTableId, "Expected route table ${defaultRouteTableId}, but was: ${routeTables?.getAt(0)?.routeTableId}")
                }

                print("Verifying filtering for route table ${defaultRouteTableId}")
                describeRouteTables(new DescribeRouteTablesRequest(
                        filters: [
                                new Filter(name: 'association.route-table-id', values: [defaultRouteTableId]),
                                new Filter(name: 'association.subnet-id', values: [subnetId]),
                                new Filter(name: 'association.main', values: ['true']),
                                new Filter(name: 'route-table-id', values: [defaultRouteTableId]),
                                new Filter(name: 'route.destination-cidr-block', values: ['10.1.2.0/24']),
                                new Filter(name: 'route.origin', values: ['INVALID']),
                                new Filter(name: 'route.state', values: ['active']),
                                new Filter(name: 'vpc-id', values: [vpcId]),
                        ]
                )).with {
                    assertThat(routeTables != null, 'Expected route tables')
                    assertThat(routeTables.isEmpty(), 'Expected no route tables')
                }

                print("Verifying filters for network interface ${networkInterfaceId}")
                describeNetworkInterfaces(new DescribeNetworkInterfacesRequest(
                        filters: [
                                new Filter(name: 'availability-zone', values: [availabilityZone]),
                                new Filter(name: 'description', values: ['a network interface']),
                                new Filter(name: 'network-interface-id', values: [networkInterfaceId]),
                                new Filter(name: 'private-ip-address', values: ['10.1.2.10']),
                                new Filter(name: 'requester-managed', values: ['false']),
                                new Filter(name: 'source-dest-check', values: ['true']),
                                new Filter(name: 'status', values: ['available']),
                                new Filter(name: 'subnet-id', values: [subnetId]),
                                new Filter(name: 'vpc-id', values: [vpcId]),
                        ]
                )).with {
                    assertThat(networkInterfaces != null, 'Expected network interfaces')
                    assertThat(networkInterfaces.size() == 1, 'Expected one network interface')
                    assertThat(networkInterfaces?.getAt(0)?.networkInterfaceId == networkInterfaceId, "Expected network interface ${networkInterfaceId}, but was: ${networkInterfaces?.getAt(0)?.networkInterfaceId}")
                }

                print("Verifying filtering for network interface ${networkInterfaceId}")
                describeNetworkInterfaces(new DescribeNetworkInterfacesRequest(
                        filters: [
                                new Filter(name: 'availability-zone', values: [availabilityZone]),
                                new Filter(name: 'description', values: ['a network interface']),
                                new Filter(name: 'network-interface-id', values: [networkInterfaceId]),
                                new Filter(name: 'private-ip-address', values: ['10.1.2.10']),
                                new Filter(name: 'requester-managed', values: ['false']),
                                new Filter(name: 'source-dest-check', values: ['true']),
                                new Filter(name: 'status', values: ['INVALID']),
                                new Filter(name: 'subnet-id', values: [subnetId]),
                                new Filter(name: 'vpc-id', values: [vpcId]),
                        ]
                )).with {
                    assertThat(networkInterfaces != null, 'Expected network interfaces')
                    assertThat(networkInterfaces.isEmpty(), 'Expected no network interfaces')
                }

                print("Verifying filters for subnet ${subnetId}")
                describeSubnets(new DescribeSubnetsRequest(
                        filters: [
                                new Filter(name: 'availability-zone', values: [availabilityZone]),
                                new Filter(name: 'available-ip-address-count', values: ['251']),
                                new Filter(name: 'cidr-block', values: ['10.1.2.0/24']),
                                new Filter(name: 'default-for-az', values: ['false']),
                                new Filter(name: 'state', values: ['available']),
                                new Filter(name: 'subnet-id', values: [subnetId]),
                                new Filter(name: 'vpc-id', values: [vpcId]),
                        ]
                )).with {
                    assertThat(subnets != null, 'Expected subnets')
                    assertThat(subnets.size() == 1, 'Expected one subnet')
                    assertThat(subnets?.getAt(0)?.subnetId == subnetId, "Expected subnet ${subnetId}, but was: ${subnets?.getAt(0)?.subnetId}")
                }

                print("Verifying filtering for subnet ${subnetId}")
                describeSubnets(new DescribeSubnetsRequest(
                        filters: [
                                new Filter(name: 'availability-zone', values: [availabilityZone]),
                                new Filter(name: 'available-ip-address-count', values: ['251']),
                                new Filter(name: 'cidr-block', values: ['10.1.2.0/24']),
                                new Filter(name: 'default-for-az', values: ['false']),
                                new Filter(name: 'state', values: ['INVALID']),
                                new Filter(name: 'subnet-id', values: [subnetId]),
                                new Filter(name: 'vpc-id', values: [vpcId]),
                        ]
                )).with {
                    assertThat(subnets != null, 'Expected subnets')
                    assertThat(subnets.isEmpty(), 'Expected no subnets')
                }

                print("Verifying filters for vpc ${vpcId}")
                describeVpcs(new DescribeVpcsRequest(
                        filters: [
                                new Filter(name: 'cidr', values: ['10.1.2.0/24']),
                                new Filter(name: 'dhcp-options-id', values: [defaultDhcpOptionsId]),
                                new Filter(name: 'isDefault', values: ['false']),
                                new Filter(name: 'state', values: ['available']),
                                new Filter(name: 'vpc-id', values: [vpcId]),
                        ]
                )).with {
                    assertThat(vpcs != null, 'Expected vpcs')
                    assertThat(vpcs.size() == 1, 'Expected one vpc')
                    assertThat(vpcs?.getAt(0)?.vpcId == vpcId, "Expected vpc ${vpcId}, but was: ${vpcs?.getAt(0)?.vpcId}")
                }

                print("Verifying filtering for vpc ${vpcId}")
                describeVpcs(new DescribeVpcsRequest(
                        filters: [
                                new Filter(name: 'cidr', values: ['10.1.2.0/24']),
                                new Filter(name: 'dhcp-options-id', values: [defaultDhcpOptionsId]),
                                new Filter(name: 'isDefault', values: ['false']),
                                new Filter(name: 'state', values: ['INVALID']),
                                new Filter(name: 'vpc-id', values: [vpcId]),
                        ]
                )).with {
                    assertThat(vpcs != null, 'Expected vpcs')
                    assertThat(vpcs.isEmpty(), 'Expected no vpcs')
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
