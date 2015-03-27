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
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit

/**
 * This application tests EC2 VPC subnet free address tracking.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9786
 */
class TestEC2VPCSubnetAvailableAddresses {

  private final AWSCredentialsProvider credentials

  public static void main( String[] args ) throws Exception {
    new TestEC2VPCSubnetAvailableAddresses( ).EC2VPCSubnetAvailableAddressesTest( )
  }

  public TestEC2VPCSubnetAvailableAddresses() {
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
  public void EC2VPCSubnetAvailableAddressesTest( ) throws Exception {
    final AmazonEC2 ec2 = getEC2Client( credentials )

    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      ec2.with{
        print( 'Creating VPC' )
        String vpcId = createVpc( new CreateVpcRequest( cidrBlock: "10.100.100.0/24" ) ).with {
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
        String subnetId = createSubnet( new CreateSubnetRequest( vpcId: vpcId, cidrBlock: "10.100.100.0/24" ) ).with {
          subnet.with {
            subnetId
          }
        }
        print( "Created subnet with id ${subnetId}" )
        cleanupTasks.add{
          print( "Deleting subnet ${subnetId}" )
          deleteSubnet( new DeleteSubnetRequest( subnetId: subnetId ) )
        }

        print( "Verifying 251 available addresses for subnet ${subnetId}" )
        describeSubnets( new DescribeSubnetsRequest(
          subnetIds: [ subnetId ],
          filters: [
              new Filter( name: 'available-ip-address-count', values: [ '251' ] )
          ]
        ) ).with {
          assertThat( subnets != null && subnets.size( ) == 1, "Expected one subnet, but was: ${subnets?.size( )}" )
        }

        print( "Creating network interface in subnet ${subnetId}" )
        String networkInterfaceId = createNetworkInterface( new CreateNetworkInterfaceRequest(
            subnetId: subnetId,
        ) ).with {
          networkInterface?.networkInterfaceId
        }
        print( "Created network interface ${networkInterfaceId}" )
        cleanupTasks.add{
          print( "Deleting network interface ${networkInterfaceId}" )
          deleteNetworkInterface( new DeleteNetworkInterfaceRequest( networkInterfaceId: networkInterfaceId ) )
        }

        print( "Verifying 250 available addresses for subnet ${subnetId}" )
        describeSubnets( new DescribeSubnetsRequest(
            subnetIds: [ subnetId ],
            filters: [
                new Filter( name: 'available-ip-address-count', values: [ '250' ] )
            ]
        ) ).with {
          assertThat( subnets != null && subnets.size( ) == 1, "Expected one subnet, but was: ${subnets?.size( )}" )
        }

        print( "Deleting network interface ${networkInterfaceId}" )
        deleteNetworkInterface( new DeleteNetworkInterfaceRequest( networkInterfaceId: networkInterfaceId ) )

        print( "Verifying 251 available addresses for subnet ${subnetId}" )
        describeSubnets( new DescribeSubnetsRequest(
            subnetIds: [ subnetId ],
            filters: [
                new Filter( name: 'available-ip-address-count', values: [ '251' ] )
            ]
        ) ).with {
          assertThat( subnets != null && subnets.size( ) == 1, "Expected one subnet, but was: ${subnets?.size( )}" )
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
