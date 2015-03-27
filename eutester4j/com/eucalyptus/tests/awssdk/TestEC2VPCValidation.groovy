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
import static com.eucalyptus.tests.awssdk.Eutester4j.EC2_ENDPOINT
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit

/**
 * This application tests request message validation for EC2 VPC.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9820
 */
class TestEC2VPCValidation {

  private final AWSCredentialsProvider credentials

  public static void main( String[] args ) throws Exception {
    new TestEC2VPCValidation( ).EC2VPCValidationTest( )
  }

  public TestEC2VPCValidation() {
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
  public void EC2VPCValidationTest( ) throws Exception {
    final AmazonEC2 ec2 = getEC2Client( credentials )

    // Find an AZ to use
    final DescribeAvailabilityZonesResult azResult = ec2.describeAvailabilityZones();

    assertThat( azResult.getAvailabilityZones().size() > 0, "Availability zone not found" );

    final String availabilityZone = azResult.getAvailabilityZones().get( 0 ).getZoneName();
    print( "Using availability zone: " + availabilityZone );

    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      ec2.with{
        try {
          print( 'Creating DHCP options with invalid value' )
          String dhcpOptionsId = createDhcpOptions( new CreateDhcpOptionsRequest( dhcpConfigurations: [
              new DhcpConfiguration( key: 'domain-name-servers', values: [ 'i'.multiply(256) ] )
          ] ) ).with {
            dhcpOptions?.dhcpOptionsId
          }
          cleanupTasks.add{
            print( "Deleting DHCP options ${dhcpOptionsId}" )
            deleteDhcpOptions( new DeleteDhcpOptionsRequest( dhcpOptionsId: dhcpOptionsId ) )
          }
          assertThat( false, "Expected DHCP options create failure for invalid value")
        } catch ( AmazonServiceException e ) {
          println( e.toString( ) )
          assertThat( 'InvalidParameterValue' == e.errorCode, "Expected InvalidParameterValue code, but was: ${e.errorCode}" )
        }

        try {
          print( 'Creating VPC with invalid cidr' )
          String vpcId = createVpc( new CreateVpcRequest( cidrBlock: '10.1.2.0/120' ) ).with {
            vpc?.vpcId
          }
          print( "Created VPC with id ${vpcId}" )
          cleanupTasks.add{
            print( "Deleting VPC ${vpcId}" )
            deleteVpc( new DeleteVpcRequest( vpcId: vpcId ) )
          }
          assertThat( false, "Expected VPC create failure for invalid cidr")
        } catch ( AmazonServiceException e ) {
          println( e.toString( ) )
          assertThat( 'InvalidParameterValue' == e.errorCode, "Expected InvalidParameterValue code, but was: ${e.errorCode}" )
        }

        print( 'Creating VPC' )
        String vpcId = createVpc( new CreateVpcRequest( cidrBlock: '10.1.2.0/24' ) ).with {
          vpc?.vpcId
        }
        print( "Created VPC with id ${vpcId}" )
        cleanupTasks.add{
          print( "Deleting VPC ${vpcId}" )
          deleteVpc( new DeleteVpcRequest( vpcId: vpcId ) )
        }

        print( 'Creating network acl' )
        String networkAclId = createNetworkAcl( new CreateNetworkAclRequest( vpcId: vpcId ) ).with {
          networkAcl?.networkAclId
        }
        print( "Created network acl with id ${networkAclId}" )
        cleanupTasks.add{
          print( "Deleting network acl ${networkAclId}" )
          deleteNetworkAcl( new DeleteNetworkAclRequest( networkAclId: networkAclId ) )
        }

        try {
          print( "Creating entry with invalid protocol for network ACL ${networkAclId}" )
          createNetworkAclEntry( new CreateNetworkAclEntryRequest(
              networkAclId: networkAclId,
              ruleNumber: 300,
              ruleAction: 'allow',
              egress: false,
              cidrBlock: '0.0.0.0/0',
              protocol: 'foo',
              portRange: new PortRange(
                  from: 22,
                  to: 22
              )
          ) )
          assertThat( false, "Expected network acl entry create failure for invalid protocol")
        } catch ( AmazonServiceException e ) {
          println( e.toString( ) )
          assertThat( 'InvalidParameterValue' == e.errorCode, "Expected InvalidParameterValue code, but was: ${e.errorCode}" )
        }
      }

      print( "Test complete" )
    } finally {
      // Attempt to clean up anything we created
      cleanupTasks.reverseEach { Runnable cleanupTask ->
        try {
          cleanupTask.run()
        } catch ( Exception e ) {
          e.printStackTrace()
        }
      }
    }
  }
}
