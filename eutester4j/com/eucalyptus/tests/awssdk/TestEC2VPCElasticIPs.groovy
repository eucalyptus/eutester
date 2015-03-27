package com.eucalyptus.tests.awssdk

import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.*

import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.EC2_ENDPOINT
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit

/**
 * This application tests EC2 VPC elastic IP functionality.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9730
 */
class TestEC2VPCElasticIPs {

  private final String host
  private final AWSCredentialsProvider credentials

  public static void main( String[] args ) throws Exception {
    new TestEC2VPCElasticIPs( ).EC2VPCElasticIPsTest( )
  }

  public TestEC2VPCElasticIPs( ) {
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
  public void EC2VPCElasticIPsTest( ) throws Exception {
    final AmazonEC2 ec2 = getEC2Client( credentials )

    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      ec2.with{
        print( 'Creating VPC' )
        String vpcId = createVpc( new CreateVpcRequest( cidrBlock: '172.30.0.0/24' ) ).with {
          vpc.with {
            vpcId
          }
        }
        print( "Created VPC with id ${vpcId}" )
        cleanupTasks.add{
          print( "Deleting VPC ${vpcId}" )
          deleteVpc( new DeleteVpcRequest( vpcId: vpcId ) )
        }

        print( 'Creating subnet' )
        String subnetId = createSubnet( new CreateSubnetRequest( vpcId: vpcId, cidrBlock: '172.30.0.0/24' ) ).with {
          subnet.with {
            subnetId
          }
        }
        print( "Created subnet with id ${subnetId}" )
        cleanupTasks.add{
          print( "Deleting subnet ${subnetId}" )
          deleteSubnet( new DeleteSubnetRequest( subnetId: subnetId ) )
        }

        print( "Creating internet gateway" )
        String internetGatewayId = createInternetGateway( ).with {
          internetGateway?.internetGatewayId
        }
        print( "Created internet gateway ${internetGatewayId}" )
        cleanupTasks.add{
          print( "Deleting internet gateway ${internetGatewayId}" )
          deleteInternetGateway( new DeleteInternetGatewayRequest( internetGatewayId: internetGatewayId ) )
        }

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

/*
 This section is for EC2 classic "standard" domain elastic ip allocation and association. It is not applicable in a
 VPC environment
 */
//        print( 'Testing standard address allocation and release' )
//        String eip = allocateAddress( ).with {
//          assertThat( domain == 'standard', "Expected domain 'standard', but was: ${domain}" )
//          assertThat( allocationId == null, "Unexpected allocation id: ${allocationId}" )
//          assertThat( publicIp != null, 'Expected public ip' )
//          publicIp
//        }
//        print( "Allocated address ${eip}" )
//        print( "Verifiying address allocation ${eip}" )
//        describeAddresses( new DescribeAddressesRequest( publicIps: [ eip ]  ) ).with {
//          assertThat( addresses != null && addresses.size( )==1, "Expected 1 address, but was: ${addresses.size()}" )
//        }
//        print( "Releasing address ${eip}" )
//        releaseAddress( new ReleaseAddressRequest( publicIp: eip ) )
//        print( "Verifiying address released ${eip}" )
//        describeAddresses( new DescribeAddressesRequest( publicIps: [ eip ]  ) ).with {
//          assertThat( addresses == null || addresses.isEmpty( ), "Expected no addresses, but was: ${addresses.size()}" )
//        }

        print( 'Testing vpc address allocation and release' )
        String allocationId1 = allocateAddress( new AllocateAddressRequest( domain: 'vpc' ) ).with {
          assertThat( domain == 'vpc', "Expected domain 'vpc', but was: ${domain}" )
          assertThat( allocationId != null, 'Expected allocation id' )
          assertThat( publicIp != null, 'Expected public ip' )
          allocationId
        }
        print( "Allocated address with allocation id ${allocationId1}" )
        print( "Verifiying address allocation ${allocationId1}" )
        describeAddresses( new DescribeAddressesRequest( allocationIds: [ allocationId1 ]  ) ).with {
          assertThat( addresses != null && addresses.size( )==1, "Expected 1 address, but was: ${addresses.size()}" )
        }
        print( "Releasing address ${allocationId1}" )
        releaseAddress( new ReleaseAddressRequest( allocationId: allocationId1 ) )
        print( "Verifiying address released ${allocationId1}" )
        describeAddresses( new DescribeAddressesRequest( allocationIds: [ allocationId1 ]  ) ).with {
          assertThat( addresses == null || addresses.isEmpty( ), "Expected no addresses, but was: ${addresses.size()}" )
        }

        print( "Creating network interface for VPC ${vpcId} subnet ${subnetId}" )
        String networkInterfaceId = createNetworkInterface( new CreateNetworkInterfaceRequest( subnetId: subnetId ) ).with {
          networkInterface.with {
            assertThat( association == null, 'Expected no association' )
            assertThat( privateIpAddress != null, 'Expected private IP for network interface' )
            networkInterfaceId
          }
        }
        print( "Created network interface with id ${networkInterfaceId}" )
        cleanupTasks.add{
          print( "Deleting network interface ${networkInterfaceId}" )
          deleteNetworkInterface( new DeleteNetworkInterfaceRequest( networkInterfaceId: networkInterfaceId ) )
        }

        print( "Allocating vpc address for assignement to ${networkInterfaceId}" )
        String allocationId2 = allocateAddress( new AllocateAddressRequest( domain: 'vpc' ) ).with {
          allocationId
        }
        print( "Allocated address ${allocationId2}" )
        cleanupTasks.add{
          print( "Releasing address ${allocationId2}" )
          releaseAddress( new ReleaseAddressRequest( allocationId: allocationId2 ) )
        }

        print( "Associating address ${allocationId2}" )
        String assocationId2 = associateAddress( new AssociateAddressRequest(
            allocationId: allocationId2,
            networkInterfaceId: networkInterfaceId
        ) ).with {
          assertThat( associationId != null, 'Expected association identifier' )
          associationId
        }
        print( "Associated address identifier ${assocationId2}" )

        print( "Verifying address association via eni ${networkInterfaceId}" )
        describeNetworkInterfaces( new DescribeNetworkInterfacesRequest(
            filters: [ new Filter( name: 'association.association-id', values: [ assocationId2 ] ) ]
        ) ).with {
          assertThat( networkInterfaces != null && networkInterfaces.size( )==1, "Expected one network interface, but was: ${networkInterfaces.size()}" )
        }

        print( "Verifying address association via eip ${allocationId2}" )
        describeAddresses( new DescribeAddressesRequest(
            filters: [ new Filter( name: 'association-id', values: [ assocationId2 ] ) ]
        ) ).with {
          assertThat( addresses != null && addresses.size( )==1, "Expected one address, but was: ${addresses.size()}" )
        }

        print( "Disassociating address ${assocationId2}" )
        disassociateAddress( new DisassociateAddressRequest( associationId: assocationId2 ) )

        print( "Verifying address disassociation via eni ${networkInterfaceId}" )
        describeNetworkInterfaces( new DescribeNetworkInterfacesRequest(
            filters: [ new Filter( name: 'association.association-id', values: [ assocationId2 ] ) ]
        ) ).with {
          assertThat( networkInterfaces == null || networkInterfaces.isEmpty( ), "Expected no network interfaces, but was: ${networkInterfaces.size()}" )
        }

        print( "Verifying address disassociation via eip ${allocationId2}" )
        describeAddresses( new DescribeAddressesRequest(
            filters: [ new Filter( name: 'association-id', values: [ assocationId2 ] ) ]
        ) ).with {
          assertThat( addresses == null || addresses.isEmpty( ), "Expected no addresses, but was: ${addresses.size()}" )
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
