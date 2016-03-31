package com.eucalyptus.tests.awssdk

import com.amazonaws.AmazonServiceException
import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.*
import org.testng.Assert
import org.testng.annotations.Test

import static com.eucalyptus.tests.awssdk.Eutester4j.*

/**
 * This application tests EC2 VPC NAT gateway management
 *
 * Related JIRA issues:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-11980
 */
class TestEC2VPCNATGatewayManagement {

  private final AWSCredentialsProvider credentials

  public static void main( final String[] args ) throws Exception {
    new TestEC2VPCNATGatewayManagement( ).EC2VPCNATGatewayManagementTest( )
  }

  public TestEC2VPCNATGatewayManagement( ) {
    minimalInit( )
    this.credentials = new StaticCredentialsProvider( new BasicAWSCredentials( ACCESS_KEY, SECRET_KEY ) )
  }

  private AmazonEC2 getEC2Client( final AWSCredentialsProvider credentials ) {
    final AmazonEC2 ec2 = new AmazonEC2Client( credentials )
    ec2.setEndpoint( EC2_ENDPOINT )
    ec2
  }

  private boolean assertThat( boolean condition,
                              String message ){
    Assert.assertTrue( condition, message )
    true
  }

  private void print( String text ) {
    System.out.println( text )
  }

  @Test
  public void EC2VPCNATGatewayManagementTest( ) throws Exception {
    final AmazonEC2 ec2 = getEC2Client( credentials )

    // Check if running in a VPC cloud
    print( 'Checking for VPC support' )
    final boolean vpcAvailable = ec2.describeAccountAttributes( ).with {
      accountAttributes.find{ AccountAttribute accountAttribute ->
        accountAttribute.attributeName == 'supported-platforms'
      }?.attributeValues*.attributeValue.contains( 'VPC' )
    }
    print( "VPC supported: ${vpcAvailable}" )
    if ( !vpcAvailable ) {
      print( "Skipping VPC test for non-VPC cloud" )
      return
    }

    // Find an image to use
    final String imageId = ec2.describeImages( new DescribeImagesRequest(
            filters: [
                    new Filter( name: "image-type", values: ["machine"] ),
                    new Filter( name: "root-device-type", values: ["instance-store"] ),
                    new Filter( name: "is-public", values: ["true"] ),
            ]
    ) ).with {
      images?.getAt( 0 )?.imageId
    }
    assertThat( imageId != null , "Image not found" )
    print( "Using image: ${imageId}" )

    // Discover SSH key
    final String keyName = ec2.describeKeyPairs().with {
      keyPairs?.getAt(0)?.keyName
    }
    print( "Using key pair: " + keyName );

    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      ec2.with{
        print( 'Creating VPC' )
        String vpcId = createVpc( new CreateVpcRequest( cidrBlock: "10.10.0.0/16" ) ).with {
          vpc.vpcId
        }
        print( "Created VPC with id ${vpcId}" )
        cleanupTasks.add{
          print( "Deleting VPC ${vpcId}" )
          deleteVpc( new DeleteVpcRequest( vpcId: vpcId ) )
        }

        print( 'Creating alternative VPC' )
        String vpcId_2 = createVpc( new CreateVpcRequest( cidrBlock: "10.10.0.0/16" ) ).with {
          vpc.vpcId
        }
        print( "Created VPC with id ${vpcId_2}" )
        cleanupTasks.add{
          print( "Deleting alternative VPC ${vpcId_2}" )
          deleteVpc( new DeleteVpcRequest( vpcId: vpcId_2 ) )
        }

        print( 'Creating subnet-1' )
        String subnetId_1 = createSubnet( new CreateSubnetRequest( vpcId: vpcId, cidrBlock: "10.10.10.0/28" ) ).with {
          subnet.subnetId
        }
        print( "Created subnet-1 with id ${subnetId_1}" )
        cleanupTasks.add{
          print( "Deleting subnet-1 ${subnetId_1}" )
          deleteSubnet( new DeleteSubnetRequest( subnetId: subnetId_1 ) )
        }

        print( 'Creating subnet-2' )
        String subnetId_2 = createSubnet( new CreateSubnetRequest( vpcId: vpcId, cidrBlock: "10.10.20.0/28" ) ).with {
          subnet.subnetId
        }
        print( "Created subnet-2 with id ${subnetId_2}" )
        cleanupTasks.add{
          print( "Deleting subnet-2 ${subnetId_2}" )
          deleteSubnet( new DeleteSubnetRequest( subnetId: subnetId_2 ) )
        }

        print( "Creating internet gateway" )
        String internetGatewayId = createInternetGateway( ).with {
          internetGateway?.internetGatewayId
        }
        cleanupTasks.add{
          print( "Deleting internet gateway ${internetGatewayId}" )
          deleteInternetGateway( new DeleteInternetGatewayRequest( internetGatewayId: internetGatewayId ) )
        }
        print( "Created internet gateway ${internetGatewayId}" )

        print( "Attaching internet gateway ${internetGatewayId} to vpc ${vpcId}" )
        attachInternetGateway( new AttachInternetGatewayRequest(
            internetGatewayId: internetGatewayId,
            vpcId: vpcId
        ) )
        cleanupTasks.add{
          print( "Detaching internet gateway ${internetGatewayId} from vpc ${vpcId}" )
          detachInternetGateway( new DetachInternetGatewayRequest(
              internetGatewayId: internetGatewayId,
              vpcId: vpcId
          ) )
        }

        print( "Allocating Elastic IP" )
        String allocationId = allocateAddress( new AllocateAddressRequest(
            domain: 'vpc'
        ) ).with {
          allocationId
        }
        assertThat( allocationId != null, "Expected allocation identifier")
        cleanupTasks.add{
          print( "Releasing Elastic IP ${allocationId}" )
          releaseAddress( new ReleaseAddressRequest(
              allocationId: allocationId
          ) )
        }
        print( "Allocated Elastic IP ${allocationId}" )

        // Error invalid subnet
        print( "Creating NAT gateway with invalid subnet (should fail)" )
        try {
          createNatGateway( new CreateNatGatewayRequest(
              subnetId: 'subnet-00000000',
              allocationId: allocationId
          ) )
          assertThat( false, 'Expected failure' )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          String expectedErrorCode = 'InvalidSubnetID.NotFound'
          assertThat( e.errorCode == expectedErrorCode, "Expected error code ${expectedErrorCode} but was: ${e.errorCode}" )
        }

        // Error invalid subnet syntax
        print( "Creating NAT gateway with malformed subnet (should fail)" )
        try {
          createNatGateway( new CreateNatGatewayRequest(
              subnetId: 'subnet-1',
              allocationId: allocationId
          ) )
          assertThat( false, 'Expected failure' )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
        }

        // Error invalid subnet syntax
        print( "Creating NAT gateway with malformed allocation (should fail)" )
        try {
          createNatGateway( new CreateNatGatewayRequest(
              subnetId: subnetId_1,
              allocationId: 'allllocation-id-0000000000000'
          ) )
          assertThat( false, 'Expected failure' )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
        }

        print( "Creating NAT gateway" )
        String natGatewayId = createNatGateway( new CreateNatGatewayRequest(
            subnetId: subnetId_1,
            allocationId: allocationId
        ) ).with {
          natGateway?.natGatewayId
        }
        assertThat( natGatewayId != null, "Expected NAT gateway identifier")
        cleanupTasks.add{
          print( "Deleting NAT gateway ${natGatewayId}" )
          deleteNatGateway( new DeleteNatGatewayRequest(
              natGatewayId: natGatewayId
          ) )
          print( "Waiting for NAT gateway ${natGatewayId} to be deleted" )
          try {
            ( 1..25 ).find{
              sleep 5
              print( "Waiting for NAT gateway ${natGatewayId} to be deleted, waited ${it*5}s" )
                describeNatGateways( new DescribeNatGatewaysRequest(
                    natGatewayIds: [ natGatewayId ],
                    filter: [ new Filter( name: "state", values: [ "deleted" ] ) ]
                ) ).with {
                  natGateways?.getAt( 0 )?.natGatewayId == natGatewayId
                }
            }
          } catch ( AmazonServiceException e ) {
            print( e.toString( ) )
          }
        }
        print( "Created NAT gateway ${allocationId}" )

        print( "Describing NAT gateways" )
        describeNatGateways( new DescribeNatGatewaysRequest(
            natGatewayIds: [ natGatewayId ]
        ) ).with {
          assertThat( natGateways != null, "Expected NAT gateways" )
          assertThat( natGateways.size( ) == 1, "Expected 1 NAT gateway but was: ${natGateways.size( )}")
          print( natGateways[0].toString( ) )
          assertThat( natGateways[0].natGatewayId == natGatewayId, "Expected NAT gateway id ${natGatewayId}, but was: ${natGateways[0].natGatewayId}" )
          assertThat( ['pending', 'available'].contains(natGateways[0].state), "Expected NAT gateway state 'pending' or 'available', but was: ${natGateways[0].state}" )
          assertThat( natGateways[0].vpcId == vpcId, "Expected NAT gateway VPC identifier ${vpcId}, but was: ${natGateways[0].vpcId}" )
          assertThat( natGateways[0].subnetId == subnetId_1, "Expected NAT gateway subnet identifier ${subnetId_1}, but was: ${natGateways[0].subnetId}" )
          assertThat( natGateways[0].createTime != null, "Expected NAT gateway create time" )
          assertThat( natGateways[0].deleteTime == null, "Unexpected NAT gateway deleteTime: ${natGateways[0].deleteTime}" )
          assertThat( natGateways[0].failureCode == null, "Unexpected NAT gateway failureCode: ${natGateways[0].failureCode}" )
          assertThat( natGateways[0].failureMessage == null, "Unexpected NAT gateway failureMessage: ${natGateways[0].failureMessage}" )
          assertThat( natGateways[0].natGatewayAddresses != null, "Expected NAT gateway addresses" )
          assertThat( natGateways[0].natGatewayAddresses.size( ) == 1, "Expected 1 NAT gateway addresses but was: ${natGateways[0].natGatewayAddresses.size( )}")
          natGateways[0].natGatewayAddresses[0].with { NatGatewayAddress natGatewayAddress ->
            assertThat(
                natGatewayAddress.allocationId == allocationId,
                "Expected NAT gateway address 0 allocation identifier ${allocationId}, but was: ${natGatewayAddress.allocationId}" )
          }
        }

        print( "Waiting for NAT gateway ${natGatewayId} to be available" )
        ( 1..25 ).find{
          sleep 5
          print( "Waiting for NAT gateway ${natGatewayId} to be available, waited ${it*5}s" )
          describeNatGateways( new DescribeNatGatewaysRequest(
              natGatewayIds: [ natGatewayId ],
              filter: [ new Filter( name: "state", values: [ "available" ] ) ]
          ) ).with {
            natGateways?.getAt( 0 )?.natGatewayId == natGatewayId
          }
        }
        describeNatGateways( new DescribeNatGatewaysRequest(
            natGatewayIds: [ natGatewayId ],
            filter: [ new Filter( name: "state", values: [ "available" ] ) ]
        ) ).with {
          assertThat( natGateways != null, "Expected NAT gateways" )
          assertThat( natGateways.size( ) == 1, "Expected 1 available NAT gateway but was: ${natGateways.size( )}")
        }

        print( "Creating NAT gateway with unavailable Elastic IP" )
        String natGatewayId_Failed = createNatGateway( new CreateNatGatewayRequest(
            subnetId: subnetId_1,
            allocationId: allocationId
        ) ).with {
          natGateway?.natGatewayId
        }
        print( "Waiting for NAT gateway ${natGatewayId_Failed} to be failed" )
        ( 1..25 ).find{
          sleep 5
          print( "Waiting for NAT gateway ${natGatewayId_Failed} to be failed, waited ${it*5}s" )
          describeNatGateways( new DescribeNatGatewaysRequest(
              natGatewayIds: [ natGatewayId_Failed ],
              filter: [ new Filter( name: "state", values: [ "failed" ] ) ]
          ) ).with {
            natGateways?.getAt( 0 )?.natGatewayId == natGatewayId_Failed
          }
        }
        describeNatGateways( new DescribeNatGatewaysRequest(
            natGatewayIds: [ natGatewayId_Failed ],
            filter: [ new Filter( name: "state", values: [ "failed" ] ) ]
        ) ).with {
          assertThat( natGateways != null, "Expected NAT gateways" )
          assertThat( natGateways.size( ) == 1, "Expected 1 available NAT gateway but was: ${natGateways.size( )}")
          print( natGateways[0].toString( ) )
          assertThat( natGateways[0].natGatewayId == natGatewayId_Failed, "Expected NAT gateway id ${natGatewayId_Failed}, but was: ${natGateways[0].natGatewayId}" )
          assertThat( natGateways[0].state == 'failed', "Expected NAT gateway state 'failed', but was: ${natGateways[0].state}" )
          assertThat( natGateways[0].vpcId == vpcId, "Expected NAT gateway VPC identifier ${vpcId}, but was: ${natGateways[0].vpcId}" )
          assertThat( natGateways[0].subnetId == subnetId_1, "Expected NAT gateway subnet identifier ${subnetId_1}, but was: ${natGateways[0].subnetId}" )
          assertThat( natGateways[0].failureCode != null, "Expected NAT gateway failureCode" )
          assertThat( natGateways[0].failureMessage != null, "Expected NAT gateway failureMessage" )
        }

        print( "Describing NAT gateways with filters" )
        [
            [ 'nat-gateway-id', natGatewayId ],
            [ 'state', 'available' ],
            [ 'subnet-id', subnetId_1 ],
            [ 'vpc-id', vpcId ],
        ].each { String name, String value ->
          final Collection<Filter> filters = [
              new Filter( name, [ value ] )
          ];
          if ( name != 'nat-gateway-id' ) {
            filters << new Filter( 'nat-gateway-id', [ natGatewayId ] )
          }
          print( "Describing NAT gateways with filters ${filters}" )
          describeNatGateways( new DescribeNatGatewaysRequest(
              filter: filters
          ) ).with {
            assertThat(natGateways != null, "Expected NAT gateways")
            assertThat(natGateways.size() == 1, "Expected 1 NAT gateway but was: ${natGateways.size()}")
            print(natGateways[0].toString())
            assertThat(natGateways[0].natGatewayId == natGatewayId, "Expected NAT gateway id ${natGatewayId}, but was: ${natGateways[0].natGatewayId}")
          }
        }

        print( "Describing NAT gateways with non-matching filters" )
        [
            [ 'nat-gateway-id', 'wilnotmatch' ],
            [ 'state', 'wilnotmatch' ],
            [ 'subnet-id', 'wilnotmatch' ],
            [ 'vpc-id', 'wilnotmatch' ],
        ].each { String name, String value ->
          final Collection<Filter> filters = [
              new Filter( name, [ value ] )
          ];
          print( "Describing NAT gateways with filters ${filters}" )
          describeNatGateways( new DescribeNatGatewaysRequest(
              filter: filters
          ) ).with {
            assertThat(natGateways == null || natGateways.isEmpty( ), "Unexpected NAT gateways")
          }
        }

        print( "Describing NAT gateway to get network interface identifier and Elastic IP" )
        String networkInterfaceId = null
        String publicIp = null
        String privateIp = null
        describeNatGateways( new DescribeNatGatewaysRequest(
            natGatewayIds: [ natGatewayId ]
        ) ).with {
          assertThat( natGateways != null, "Expected NAT gateways" )
          assertThat( natGateways.size( ) == 1, "Expected 1 NAT gateway but was: ${natGateways.size( )}")
          print( natGateways[0].toString( ) )
          assertThat( natGateways[0].natGatewayId == natGatewayId,
              "Expected NAT gateway id ${natGatewayId}, but was: ${natGateways[0].natGatewayId}" )
          assertThat( natGateways[0].natGatewayAddresses != null, "Expected NAT gateway addresses" )
          assertThat( natGateways[0].natGatewayAddresses.size( ) == 1,
              "Expected 1 NAT gateway addresses but was: ${natGateways[0].natGatewayAddresses.size( )}")
          networkInterfaceId = natGateways[0].natGatewayAddresses[0].networkInterfaceId
          publicIp = natGateways[0].natGatewayAddresses[0].publicIp
          privateIp = natGateways[0].natGatewayAddresses[0].privateIp
        }
        assertThat( networkInterfaceId != null, "Expected NAT gateway address 0 network interface identifier" )
        assertThat( publicIp != null, "Expected NAT gateway address 0 public IP" )
        assertThat( privateIp != null, "Expected NAT gateway address 0 private IP" )

        print( "Disassociating Elastic IP (${publicIp}) used by NAT gateway (should fail)" )
        try {
          disassociateAddress( new DisassociateAddressRequest( publicIp: publicIp  ) )
          assertThat( false, 'Expected failure' )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          String expectedErrorCode = 'InvalidIPAddress.InUse'
          assertThat( e.errorCode == expectedErrorCode, "Expected error code ${expectedErrorCode} but was: ${e.errorCode}" )
        }

        print( "Releasing Elastic IP (${publicIp}) used by NAT gateway (should fail)" )
        try {
          releaseAddress( new ReleaseAddressRequest( publicIp: publicIp  ) )
          assertThat( false, 'Expected failure' )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          String expectedErrorCode = 'InvalidIPAddress.InUse'
          assertThat( e.errorCode == expectedErrorCode, "Expected error code ${expectedErrorCode} but was: ${e.errorCode}" )
        }

        print( "Describing NAT gateway Elastic IP" )
        describeAddresses( new DescribeAddressesRequest( publicIps: [ publicIp ] )  ).with {
          assertThat( addresses != null, "Expected addresses" )
          assertThat( addresses.size( ) == 1, "Expected 1 address but was: ${addresses.size( )}")
          print( addresses[0].toString( ) )
          assertThat( addresses[0].privateIpAddress == privateIp,
              "Expected private IP ${privateIp}, but was: ${addresses[0].privateIpAddress}" )
          assertThat( addresses[0].publicIp == publicIp,
              "Expected public IP ${publicIp}, but was: ${addresses[0].publicIp}" )
          assertThat( addresses[0].networkInterfaceId == networkInterfaceId,
              "Expected network interface identifier ${networkInterfaceId}, but was: ${addresses[0].networkInterfaceId}" )
        }

        print( "Modifying network interface (${networkInterfaceId}) attribute for NAT gateway (should fail)" )
        try {
          modifyNetworkInterfaceAttribute( new ModifyNetworkInterfaceAttributeRequest(
              networkInterfaceId: networkInterfaceId,
              description: 'update'
          ) )
          assertThat( false, 'Expected failure' )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
        }

        print( "Describing NAT gateway network interface" )
        describeNetworkInterfaces(
            new DescribeNetworkInterfacesRequest( networkInterfaceIds: [ networkInterfaceId ] )
        ).with {
          assertThat( networkInterfaces != null, "Expected network interfaces" )
          assertThat( networkInterfaces.size( ) == 1, "Expected 1 network interface but was: ${networkInterfaces.size( )}")
          print( networkInterfaces[0].toString( ) )
          assertThat( networkInterfaces[0].networkInterfaceId == networkInterfaceId,
              "Expected network interface id ${networkInterfaceId}, but was: ${networkInterfaces[0].networkInterfaceId}" )
          assertThat( networkInterfaces[0].vpcId == vpcId,
              "Expected network interface subnet ${vpcId}, but was: ${networkInterfaces[0].vpcId}" )
          assertThat( networkInterfaces[0].subnetId == subnetId_1,
              "Expected network interface subnet ${subnetId_1}, but was: ${networkInterfaces[0].subnetId}" )
          assertThat( networkInterfaces[0].description.contains( natGatewayId ),
              "Expected network interface description to contain ${natGatewayId}, but was: ${networkInterfaces[0].description}" )
          assertThat( networkInterfaces[0].requesterId != null, "Expected network interface requester identifier" )
          assertThat( networkInterfaces[0].requesterManaged,
              "Expected network interface request managed to be true, but was: ${networkInterfaces[0].requesterManaged}" )
          assertThat( networkInterfaces[0].privateIpAddress == privateIp,
              "Expected network interface private IP ${privateIp}, but was: ${networkInterfaces[0].privateIpAddress}" )
          assertThat( Boolean.FALSE.equals( networkInterfaces[0].sourceDestCheck ),
              "Expected network interface source dest check to be false, but was: ${networkInterfaces[0].sourceDestCheck}" )
          assertThat( networkInterfaces[0].privateIpAddress == privateIp,
              "Expected network interface private IP ${privateIp}, but was: ${networkInterfaces[0].privateIpAddress}" )
          assertThat( networkInterfaces[0].groups == null || networkInterfaces[0].groups.isEmpty( ),
              "Expected no network interface security groups, but was: ${networkInterfaces[0].groups}" )
          assertThat( networkInterfaces[0].association == null,
              "Expected no network interface association, but was: ${networkInterfaces[0].association}" )
          assertThat( networkInterfaces[0].attachment != null, "Expected network interface attachment" )
          networkInterfaces[0].attachment.with {
            assertThat( attachmentId != null, "Expected network interface attachment attachment identifier" )
            assertThat( deviceIndex == 1, "Expected network interface attachment device index 1, but was: ${deviceIndex}" )
          }
        }

        //
        print( "Describing NAT gateway network interface with filter attachment.nat-gateway-id=${natGatewayId}" )
        describeNetworkInterfaces(
            new DescribeNetworkInterfacesRequest( filters: [
              new Filter( 'attachment.nat-gateway-id', [ natGatewayId ] )
            ] )
        ).with {
          assertThat(networkInterfaces != null, "Expected network interfaces")
          assertThat(networkInterfaces.size() == 1, "Expected 1 network interface but was: ${networkInterfaces.size()}")
          print(networkInterfaces[0].toString())
          assertThat(networkInterfaces[0].networkInterfaceId == networkInterfaceId,
              "Expected network interface id ${networkInterfaceId}, but was: ${networkInterfaces[0].networkInterfaceId}")
        }

        print( "Creating route table in vpc ${vpcId}" )
        String routeTableVpcId = vpcId
        String routeTableId = createRouteTable( new CreateRouteTableRequest( vpcId: vpcId ) ).with {
          routeTable.with {
            assertThat( vpcId == routeTableVpcId, "Expected vpcId ${routeTableVpcId}, but was: ${vpcId}" )
            routeTableId
          }
        }
        print( "Created route table with id ${routeTableId}" )
        cleanupTasks.add{
          print( "Deleting route table ${routeTableId}" )
          deleteRouteTable( new DeleteRouteTableRequest( routeTableId: routeTableId ) )
        }

        print( "Creating route for NAT gateway in route table ${routeTableId}" )
        createRoute( new CreateRouteRequest(
            routeTableId: routeTableId,
            destinationCidrBlock: '1.1.1.1/32',
            natGatewayId: natGatewayId
        ) )

        print( "Describing route table ${routeTableId}" )
        describeRouteTables( new DescribeRouteTablesRequest( routeTableIds: [ routeTableId ] )).with {
          assertThat( routeTables.size()==1, "Expected one route table" )
          routeTables.get( 0 ).with {
            assertThat( vpcId == routeTableVpcId, "Expected vpcId ${routeTableVpcId}, but was: ${vpcId}" )
            assertThat( routes.size( ) == 2, "Expected two routes" )
            assertThat( routes*.natGatewayId.contains( natGatewayId ), "Expected route for nat gateway" )
          }
        }

        print( "Describing route table ${routeTableId} using filter route.nat-gateway-id=${natGatewayId}" )
        describeRouteTables( new DescribeRouteTablesRequest(
            filters: [ new Filter( 'route.nat-gateway-id', [ natGatewayId ] ) ]
        )).with {
          assertThat( routeTables != null && routeTables.size()==1, "Expected one route table" )
        }

        print( "Replacing route table ${routeTableId} route 1.1.1.1/32 with ENI ${networkInterfaceId}" )
        replaceRoute( new ReplaceRouteRequest(
            routeTableId: routeTableId,
            destinationCidrBlock: '1.1.1.1/32',
            networkInterfaceId: networkInterfaceId
        ) )

        print( "Describing route table ${routeTableId} to verify route replacement" )
        describeRouteTables( new DescribeRouteTablesRequest(
            routeTableIds: [ routeTableId ]
        )).with {
          assertThat( routeTables != null && routeTables.size()==1, "Expected one route table" )
          routeTables.get( 0 ).with {
            assertThat( routes.size( ) == 2, "Expected two routes" )
            assertThat( routes*.networkInterfaceId.contains( networkInterfaceId ), "Expected route for network interface" )
          }
        }

        print( "Replacing route table ${routeTableId} route 1.1.1.1/32 with NAT gateway ${natGatewayId}" )
        replaceRoute( new ReplaceRouteRequest(
            routeTableId: routeTableId,
            destinationCidrBlock: '1.1.1.1/32',
            natGatewayId: natGatewayId
        ) )

        print( "Describing route table ${routeTableId} to verify route replacement" )
        describeRouteTables( new DescribeRouteTablesRequest(
            filters: [ new Filter( 'route.nat-gateway-id', [ natGatewayId ] ) ]
        )).with {
          assertThat( routeTables != null && routeTables.size()==1, "Expected one route table" )
        }

        print( "Deleting NAT gateway ${natGatewayId}" )
        deleteNatGateway( new DeleteNatGatewayRequest(
            natGatewayId: natGatewayId
        ) )

        print( "Waiting for NAT gateway ${natGatewayId} to be deleted" )
        ( 1..25 ).find{
          sleep 5
          print( "Waiting for NAT gateway ${natGatewayId} to be deleted, waited ${it*5}s" )
          describeNatGateways( new DescribeNatGatewaysRequest(
              natGatewayIds: [ natGatewayId ],
              filter: [ new Filter( name: "state", values: [ "deleted" ] ) ]
          ) ).with {
            natGateways?.getAt( 0 )?.natGatewayId == natGatewayId
          }
        }

        print( "Describing NAT gateways" )
        describeNatGateways( new DescribeNatGatewaysRequest(
            natGatewayIds: [ natGatewayId ]
        ) ).with {
          assertThat( natGateways != null, "Expected NAT gateways" )
          assertThat( natGateways.size( ) == 1, "Expected 1 NAT gateway but was: ${natGateways.size( )}")
          print( natGateways[0].toString( ) )
          assertThat( natGateways[0].natGatewayId == natGatewayId, "Expected NAT gateway id ${natGatewayId}, but was: ${natGateways[0].natGatewayId}" )
          assertThat( ['deleted'].contains(natGateways[0].state), "Expected NAT gateway state 'deleted', but was: ${natGateways[0].state}" )
          assertThat( natGateways[0].vpcId == vpcId, "Expected NAT gateway VPC identifier ${vpcId}, but was: ${natGateways[0].vpcId}" )
          assertThat( natGateways[0].subnetId == subnetId_1, "Expected NAT gateway subnet identifier ${subnetId_1}, but was: ${natGateways[0].subnetId}" )
          assertThat( natGateways[0].createTime != null, "Expected NAT gateway create time" )
          assertThat( natGateways[0].deleteTime != null, "Expected NAT gateway delete time" )
          assertThat( natGateways[0].failureCode == null, "Unexpected NAT gateway failureCode: ${natGateways[0].failureCode}" )
          assertThat( natGateways[0].failureMessage == null, "Unexpected NAT gateway failureMessage: ${natGateways[0].failureMessage}" )
          assertThat( natGateways[0].natGatewayAddresses != null, "Expected NAT gateway addresses" )
          assertThat( natGateways[0].natGatewayAddresses.size( ) == 1, "Expected 1 NAT gateway addresses but was: ${natGateways[0].natGatewayAddresses.size( )}")
          natGateways[0].natGatewayAddresses[0].with { NatGatewayAddress natGatewayAddress ->
            assertThat(
                natGatewayAddress.allocationId == allocationId,
                "Expected NAT gateway address 0 allocation identifier ${allocationId}, but was: ${natGatewayAddress.allocationId}" )
          }
        }

        print( "Describing NAT gateway network interface (should be not found)" )
        try {
          describeNetworkInterfaces( new DescribeNetworkInterfacesRequest( networkInterfaceIds: [ networkInterfaceId ] ) )
          assertThat( false, "Expected failure" )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          String expectedErrorCode = 'InvalidNetworkInterfaceID.NotFound'
          assertThat( e.errorCode == expectedErrorCode, "Expected error code ${expectedErrorCode} but was: ${e.errorCode}" )
        }

        print( "Describing Elastic IP to verify allocated" )
        describeAddresses( new DescribeAddressesRequest( publicIps: [ publicIp ] )  ).with {
          assertThat( addresses != null, "Expected addresses" )
          assertThat( addresses.size( ) == 1, "Expected 1 address but was: ${addresses.size( )}")
          print( addresses[0].toString( ) )
          assertThat( addresses[0].publicIp == publicIp,
              "Expected public IP ${publicIp}, but was: ${addresses[0].publicIp}" )
          assertThat( addresses[0].allocationId == allocationId,
              "Expected allocation identifier ${allocationId}, but was: ${addresses[0].allocationId}" )
          assertThat( addresses[0].associationId == null,
              "Unexpected association identifier ${addresses[0].associationId}" )
          assertThat( addresses[0].privateIpAddress == null,
              "Unexpected private IP ${addresses[0].privateIpAddress}" )
          assertThat( addresses[0].networkInterfaceId == null,
              "Unexpected network interface identifier ${addresses[0].networkInterfaceId}" )
        }

        void
      }

      print( "Test complete" )
    } finally {
      // Attempt to clean up anything we created
      cleanupTasks.reverseEach { Runnable cleanupTask ->
        try {
          cleanupTask.run()
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
        } catch ( Exception e ) {
          e.printStackTrace()
        }
      }
    }
  }
}
