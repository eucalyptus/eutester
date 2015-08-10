package com.eucalyptus.tests.awssdk

import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.*

import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit;
import static com.eucalyptus.tests.awssdk.Eutester4j.EC2_ENDPOINT;
import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY;
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY;

/**
 * This application tests management of resource associations for EC2 VPC.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9715
 */
class TestEC2VPCAssociationManagement {

  private final AWSCredentialsProvider credentials

  public static void main( String[] args ) throws Exception {
    new TestEC2VPCAssociationManagement( ).EC2VPCAssociationManagementTest( )
  }

  public TestEC2VPCAssociationManagement(){
    minimalInit()
    this.credentials = new StaticCredentialsProvider( new BasicAWSCredentials( ACCESS_KEY, SECRET_KEY ) )
  }

  private AmazonEC2 getEC2Client( final AWSCredentialsProvider credentials ) {
    final AmazonEC2 ec2 = new AmazonEC2Client( credentials )
    ec2.setEndpoint( EC2_ENDPOINT )
    ec2
  }

  private boolean assertThat( boolean condition,
                              String message ){
    assert condition : message
    true
  }

  private void print( String text ) {
    System.out.println( text )
  }

  @Test
  public void EC2VPCAssociationManagementTest( ) throws Exception {
    final AmazonEC2 ec2 = getEC2Client( credentials )

    // Find an AZ to use
    final DescribeAvailabilityZonesResult azResult = ec2.describeAvailabilityZones();

    assertThat( azResult.getAvailabilityZones().size() > 0, "Availability zone not found" );

    final String availabilityZone = azResult.getAvailabilityZones().get( 0 ).getZoneName();
    print( "Using availability zone: " + availabilityZone );

    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      ec2.with{
        print( 'Creating DHCP options' )
        Map<String,List<String>> dhcpConfig = [
            'domain-name-servers': [ '8.8.8.8' ],
            'domain-name': [ 'eucalyptus.internal' ],
        ]
        String dhcpOptionsId = createDhcpOptions( new CreateDhcpOptionsRequest( dhcpConfigurations: dhcpConfig.collect { String key, List<String> values ->
          new DhcpConfiguration(key: key, values: values)
        } ) ).with {
          dhcpOptions.with {
            dhcpOptionsId
          }
        }
        cleanupTasks.add{
          print( "Deleting DHCP options ${dhcpOptionsId}" )
          deleteDhcpOptions( new DeleteDhcpOptionsRequest( dhcpOptionsId: dhcpOptionsId ) )
        }
        print( "Created DHCP options ${dhcpOptionsId}" )

        print( 'Creating internet gateway' )
        String internetGatewayId = createInternetGateway( new CreateInternetGatewayRequest( ) ).with {
          internetGateway.internetGatewayId
        }
        print( "Created internet gateway with id ${internetGatewayId}" )
        cleanupTasks.add{
          print( "Deleting internet gateway ${internetGatewayId}" )
          deleteInternetGateway( new DeleteInternetGatewayRequest( internetGatewayId: internetGatewayId ) )
        }

        print( 'Creating VPC' )
        String defaultDhcpOptionsId = null
        String vpcId = createVpc( new CreateVpcRequest( cidrBlock: '10.1.2.0/24' ) ).with {
          vpc.with {
            defaultDhcpOptionsId = dhcpOptionsId
            vpcId
          }
        }
        print( "Created VPC with id ${vpcId} and dhcp options id ${defaultDhcpOptionsId}" )
        cleanupTasks.add{
          print( "Deleting VPC ${vpcId}" )
          deleteVpc( new DeleteVpcRequest( vpcId: vpcId ) )
        }

        print( 'Creating subnet' )
        String subnetId = createSubnet( new CreateSubnetRequest( vpcId: vpcId, availabilityZone: availabilityZone, cidrBlock: '10.1.2.0/24' ) ).with {
          subnet.with {
            subnetId
          }
        }
        print( "Created subnet with id ${subnetId}" )
        cleanupTasks.add{
          print( "Deleting subnet ${subnetId}" )
          deleteSubnet( new DeleteSubnetRequest( subnetId: subnetId ) )
        }

        print( "Finding network ACL association for subnet ${subnetId}" )
        String networkAclAssociationId = describeNetworkAcls( new DescribeNetworkAclsRequest(
            filters: [
                new Filter( name: 'default', values: [ 'true' ])
            ]
        ) ).with {
          assertThat( networkAcls?.getAt( 0 )?.networkAclId != null, 'Expected network ACL identifier' )
          String assocationId = networkAcls.inject( '' ){ String associationId, NetworkAcl networkAcl -> associationId ? associationId : networkAcl?.associations?.getAt( 0 )?.subnetId == subnetId ? networkAcl?.associations?.getAt( 0 )?.networkAclAssociationId : null }
          assertThat( assocationId != null, 'Expected network ACL association identifier' )
          assocationId
        }
        print( "Found network ACL association ${networkAclAssociationId} for subnet ${subnetId}" )

        print( 'Creating route table' )
        String routeTableId = createRouteTable( new CreateRouteTableRequest( vpcId: vpcId ) ).with {
          routeTable.routeTableId
        }
        print( "Created route table with id ${routeTableId}" )
        cleanupTasks.add{
          print( "Deleting route table ${routeTableId}" )
          deleteRouteTable( new DeleteRouteTableRequest( routeTableId: routeTableId ) )
        }

        print( 'Creating second route table' )
        String secondRouteTableId = createRouteTable( new CreateRouteTableRequest( vpcId: vpcId ) ).with {
          routeTable.routeTableId
        }
        print( "Created second route table with id ${secondRouteTableId}" )
        cleanupTasks.add{
          print( "Deleting second route table ${secondRouteTableId}" )
          deleteRouteTable( new DeleteRouteTableRequest( routeTableId: secondRouteTableId ) )
        }

        print( 'Creating network acl' )
        String networkAclVpcId = vpcId
        String networkAclId = createNetworkAcl( new CreateNetworkAclRequest( vpcId: vpcId ) ).with {
          networkAcl.with {
            assertThat( vpcId == networkAclVpcId, "Expected vpcId ${networkAclVpcId}, but was: ${vpcId}" )
            assertThat( !isDefault, "Expected non-default network acl" )
            networkAclId
          }
        }
        print( "Created network acl with id ${networkAclId}" )
        cleanupTasks.add{
          print( "Deleting network acl ${networkAclId}" )
          deleteNetworkAcl( new DeleteNetworkAclRequest( networkAclId: networkAclId ) )
        }

        print( "Associating DHCP options ${dhcpOptionsId} with vpc ${vpcId}" )
        associateDhcpOptions( new AssociateDhcpOptionsRequest(
          vpcId: vpcId,
          dhcpOptionsId: dhcpOptionsId
        ) )
        print( "Verifying DHCP options ${dhcpOptionsId} associated with vpc ${vpcId}" )
        describeVpcs( new DescribeVpcsRequest( vpcIds: [ vpcId ] ) ).with {
          assertThat( vpcs != null && !vpcs.isEmpty( ), "Expected vpc"  )
          assertThat( dhcpOptionsId ==  vpcs.getAt( 0 )?.dhcpOptionsId, "Expected dhcp options ${dhcpOptionsId}, but was: ${vpcs.getAt( 0 )?.dhcpOptionsId}" )
        }

        print( "Associating default DHCP options with vpc ${vpcId}" )
        associateDhcpOptions( new AssociateDhcpOptionsRequest(
            vpcId: vpcId,
            dhcpOptionsId: 'default'
        ) )
        print( "Verifying DHCP options ${dhcpOptionsId} no longer associated with vpc ${vpcId}" )
        describeVpcs( new DescribeVpcsRequest( vpcIds: [ vpcId ] ) ).with {
          assertThat( vpcs != null && !vpcs.isEmpty( ), "Expected vpc"  )
          assertThat( dhcpOptionsId !=  vpcs.getAt( 0 )?.dhcpOptionsId, "Expected dhcp options not ${dhcpOptionsId}" )
        }

        print( "Associating route table ${routeTableId} with subnet ${subnetId}" )
        String routeTableAssociationId = associateRouteTable( new AssociateRouteTableRequest(
          subnetId: subnetId,
          routeTableId: routeTableId
        ) ).with {
          assertThat( associationId != null, "Expected route table association identifier" )
          associationId
        }
        print( "Verifying route table ${routeTableId} association with subnet ${subnetId}" )
        describeRouteTables( new DescribeRouteTablesRequest(
            routeTableIds: [ routeTableId ]
        ) ).with {
          assertThat( routeTables?.getAt( 0 )?.getAssociations( )?.getAt( 0 )?.subnetId == subnetId, "Association not found for subnet ${subnetId} and route table ${routeTableId}" )
        }

        print( "Replacing route table association with ${secondRouteTableId}" )
        String secondRouteTableAssociationId = replaceRouteTableAssociation( new ReplaceRouteTableAssociationRequest(
            associationId: routeTableAssociationId,
            routeTableId: secondRouteTableId
        ) ).with {
          newAssociationId
        }
        print( "Verifying route table ${secondRouteTableId} association with subnet ${subnetId}" )
        describeRouteTables( new DescribeRouteTablesRequest(
            routeTableIds: [ secondRouteTableId ]
        ) ).with {
          assertThat( routeTables?.getAt( 0 )?.getAssociations( )?.getAt( 0 )?.subnetId == subnetId, "Association not found for subnet ${subnetId} and route table ${routeTableId}" )
        }

        print( "Dissassociating route table ${secondRouteTableId}" )
        disassociateRouteTable( new DisassociateRouteTableRequest(
          associationId: secondRouteTableAssociationId
        ) )

        print( "Replacing network ACL assocation ${networkAclAssociationId} for network acl ${networkAclId}" )
        replaceNetworkAclAssociation( new ReplaceNetworkAclAssociationRequest(
          associationId: networkAclAssociationId,
          networkAclId: networkAclId
        ) ).with {
          newAssociationId
        }
        print( "Verifying network ACL ${networkAclId} association with subnet ${subnetId}" )
        describeNetworkAcls( new DescribeNetworkAclsRequest(
            networkAclIds: [ networkAclId ]
        ) ).with {
          assertThat( networkAcls?.getAt( 0 )?.getAssociations( )?.getAt( 0 )?.subnetId == subnetId, "Association not found for subnet ${subnetId} and network ACL ${networkAclId}" )
        }

        print( "Attaching internet gateway ${internetGatewayId} to vpc ${vpcId}" )
        attachInternetGateway( new AttachInternetGatewayRequest(
            vpcId: vpcId,
            internetGatewayId: internetGatewayId
        ) )
        print( "Verifying internet gateway ${internetGatewayId} attached to vpc ${vpcId}" )
        describeInternetGateways( new DescribeInternetGatewaysRequest(
            internetGatewayIds: [ internetGatewayId ]
        ) ).with {
          assertThat( internetGateways?.getAt( 0 )?.getAttachments( )?.getAt( 0 )?.vpcId == vpcId, "Attachment not found for vpc ${vpcId} and internet gateway ${internetGatewayId}" )
        }

        print( "Detaching internet gateway ${internetGatewayId} from vpc ${vpcId}" )
        detachInternetGateway( new DetachInternetGatewayRequest(
            vpcId: vpcId,
            internetGatewayId: internetGatewayId
        ) )
        print( "Verifying internet gateway ${internetGatewayId} not attached to vpc ${vpcId}" )
        describeInternetGateways( new DescribeInternetGatewaysRequest(
            internetGatewayIds: [ internetGatewayId ]
        ) ).with {
          assertThat( internetGateways?.getAt( 0 )?.getAttachments( )?.getAt( 0 )?.vpcId != vpcId, "Attachment found for vpc ${vpcId} and internet gateway ${internetGatewayId}" )
        }
      }

      print( "Test complete" )
    } finally {
      // Attempt to clean up anything we created
      cleanupTasks.reverseEach { Runnable cleanupTask ->
        try {
          cleanupTask.run()
        } catch ( Exception e ) {
          // Some not-found errors are expected here so may need to be suppressed
          e.printStackTrace()
        }
      }
    }
  }
}
