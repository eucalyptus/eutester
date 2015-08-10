package com.eucalyptus.tests.awssdk

import com.amazonaws.AmazonWebServiceRequest
import com.amazonaws.Request
import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.handlers.RequestHandler
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.*
import com.amazonaws.util.TimingInfo

import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.EC2_ENDPOINT
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit

/**
 * This application tests management of attributes EC2 VPC.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9612
 */
class TestEC2VPCAttributeManagement {

  private final String host;
  private final AWSCredentialsProvider credentials

  public static void main( String[] args ) throws Exception {
    new TestEC2VPCAttributeManagement( ).EC2VPCAttributeManagementTest( )
  }

  public TestEC2VPCAttributeManagement(){
    minimalInit()
    this.credentials = new StaticCredentialsProvider( new BasicAWSCredentials( ACCESS_KEY, SECRET_KEY ) )
  }

  private AmazonEC2Client getEC2Client( final AWSCredentialsProvider credentials ) {
    final AmazonEC2Client ec2 = new AmazonEC2Client( credentials )
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
  public void EC2VPCAttributeManagementTest( ) throws Exception {
    final AmazonEC2Client ec2 = getEC2Client( credentials )

    // Find an AZ to use
    final DescribeAvailabilityZonesResult azResult = ec2.describeAvailabilityZones();

    assertThat( azResult.getAvailabilityZones().size() > 0, "Availability zone not found" );

    final String availabilityZone = azResult.getAvailabilityZones().get( 0 ).getZoneName();
    print( "Using availability zone: " + availabilityZone );

    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      ec2.with{
        print( 'Creating VPC' )
        String vpcId = createVpc( new CreateVpcRequest( cidrBlock: '10.100.215.0/27' ) ).with {
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
        String subnetId = createSubnet( new CreateSubnetRequest( vpcId: vpcId, cidrBlock: '10.100.215.0/28' ) ).with {
          subnet.with {
            assertThat( !mapPublicIpOnLaunch, 'Expected public ip not mapped on launch' )
            subnetId
          }
        }
        print( "Created subnet with id ${subnetId}" )
        cleanupTasks.add{
          print( "Deleting subnet ${subnetId}" )
          deleteSubnet( new DeleteSubnetRequest( subnetId: subnetId ) )
        }

        print( 'Creating network interface' )
        String networkInterfaceId = createNetworkInterface( new CreateNetworkInterfaceRequest(
            subnetId: subnetId,
            description: 'a network interface',
            privateIpAddress: '10.100.215.10' ) ).with {
          networkInterface.with {
            assertThat( description == 'a network interface', "Expected 'a network interface', but was: ${description}" )
            assertThat( sourceDestCheck, "Expected source dest check true" )
            networkInterfaceId
          }
        }
        print( "Created network interface with id ${networkInterfaceId}" )
        cleanupTasks.add{
          print( "Deleting network interface ${networkInterfaceId}" )
          deleteNetworkInterface( new DeleteNetworkInterfaceRequest( networkInterfaceId: networkInterfaceId ) )
        }

        print( 'Verifying account attributes for EC2' )
        describeAccountAttributes( ).with {
          assertThat( accountAttributes != null, 'Expected account attributes' )
          assertThat( !accountAttributes.isEmpty( ), 'Expected non-empty account attributes' )
          for ( AccountAttribute accountAttribute : accountAttributes ) {
            switch( accountAttribute.attributeName ) {
              case 'supported-platforms':
                assertThat( !accountAttribute.attributeValues.isEmpty( ) &&
                    accountAttribute.attributeValues.size( ) <= 2, "Expected 1-2 values for supported-platforms" )
                assertThat( !(accountAttribute.attributeValues.collect{ AccountAttributeValue value -> value.attributeValue } as Set<String>).retainAll(
                    [ 'VPC', 'EC2' ]
                ), "Expected values 'VPC', 'EC2'" )
                break;
              case 'default-vpc':
                assertThat( accountAttribute.attributeValues.size( ) == 1, "Expected one value for default-vpc" )
                assertThat(
                    accountAttribute.attributeValues[0].attributeValue == 'none' ||
                    accountAttribute.attributeValues[0].attributeValue.startsWith('vpc-'),
                    "Expected 'none' or 'vpc-...' for default-vpc" )
                break;
            }
          }
        }

        print( "Verifying initial attributes for VPC ${vpcId}" )
        String expectedVpcId = vpcId
        describeVpcAttribute( new DescribeVpcAttributeRequest( vpcId: vpcId, attribute: 'enableDnsSupport'  ) ).with {
          assertThat( vpcId == expectedVpcId, "Expected VPC id ${expectedVpcId}, but was: ${vpcId}" )
          assertThat( enableDnsSupport, "Expected enableDnsSupport" )
        }
        describeVpcAttribute( new DescribeVpcAttributeRequest( vpcId: vpcId, attribute: 'enableDnsHostnames'  ) ).with {
          assertThat( vpcId == expectedVpcId, "Expected VPC id ${expectedVpcId}, but was: ${vpcId}" )
          assertThat( !enableDnsHostnames, "Expected !enableDnsHostnames" )
        }

        print( "Modifying vpc attribute enableDnsSupport ${vpcId}" )
        modifyVpcAttribute( new ModifyVpcAttributeRequest( vpcId: vpcId, enableDnsSupport: false ) )

        print( "Modifying vpc attribute enableDnsHostnames ${vpcId}" )
        modifyVpcAttribute( new ModifyVpcAttributeRequest( vpcId: vpcId, enableDnsHostnames: true ) )

        print( "Verifying updated attributes for VPC ${vpcId}" )
        describeVpcAttribute( new DescribeVpcAttributeRequest( vpcId: vpcId, attribute: 'enableDnsSupport'  ) ).with {
          assertThat( vpcId == expectedVpcId, "Expected VPC id ${expectedVpcId}, but was: ${vpcId}" )
          assertThat( !enableDnsSupport, "Expected !enableDnsSupport" )
        }
        describeVpcAttribute( new DescribeVpcAttributeRequest( vpcId: vpcId, attribute: 'enableDnsHostnames'  ) ).with {
          assertThat( vpcId == expectedVpcId, "Expected VPC id ${expectedVpcId}, but was: ${vpcId}" )
          assertThat( enableDnsHostnames, "Expected enableDnsHostnames" )
        }

        print( "SKIPPING - FIXME (needs 1.8.14 AWS SDK for Java)" )
        print( "SKIPPING - FIXME" )
        print( "SKIPPING - FIXME - Modifying subnet attribute mapPublicIpOnLaunch ${subnetId}" )
        //TODO Implement when 1.8.14 AWS SDK for Java is available

        print( "SKIPPING - FIXME - Verifying updated attributes for subnet ${subnetId}" )
        //TODO Implement when 1.8.14 AWS SDK for Java is available
        print( "SKIPPING - FIXME" )
        print( "SKIPPING - FIXME" )

        //
        // Some hackery is required here as the AWS SDK for Java does not currently
        // implement the DescribeNetworkInterfaceAttribute and ResetNetworkInterfaceAttributes
        // as per the EC2 API Documentation
        //
        // https://github.com/aws/aws-sdk-java/issues/252
        //
        print( "Verifying initial attributes for network interface ${networkInterfaceId}" )
        final String[] attributeHolder = { 'description' }
        addRequestHandler( new RequestHandler( ) {
          @Override
          void beforeRequest( final Request<?> request ) {
            AmazonWebServiceRequest originalRequest = request.getOriginalRequest();
            if ( originalRequest instanceof DescribeNetworkInterfaceAttributeRequest ||
                originalRequest instanceof ResetNetworkInterfaceAttributeRequest ) {
              request.addParameter( "Attribute", attributeHolder[0] )
            }
          }

          @Override void afterResponse(final Request<?> request, final Object response, final TimingInfo timingInfo) { }
          @Override void afterError(final Request<?> request, final Exception e) { }
        } )
        attributeHolder[0] = 'description'
        String expectedNetworkInterfaceId = networkInterfaceId
        describeNetworkInterfaceAttribute( new DescribeNetworkInterfaceAttributeRequest( networkInterfaceId: networkInterfaceId ) ).with {
          assertThat( networkInterfaceId == expectedNetworkInterfaceId, "Expected ENI id ${expectedNetworkInterfaceId}, but was: ${networkInterfaceId}" )
          assertThat( description == 'a network interface', "Expected description 'a network interface', but was: ${description}" )
        }
        attributeHolder[0] = 'sourceDestCheck'
        describeNetworkInterfaceAttribute( new DescribeNetworkInterfaceAttributeRequest( networkInterfaceId: networkInterfaceId ) ).with {
          assertThat( networkInterfaceId == expectedNetworkInterfaceId, "Expected ENI id ${expectedNetworkInterfaceId}, but was: ${networkInterfaceId}" )
          assertThat( sourceDestCheck, "Expected sourceDestCheck" )
        }

        print( "Modifying network interface attribute description ${networkInterfaceId}" )
        modifyNetworkInterfaceAttribute( new ModifyNetworkInterfaceAttributeRequest(
            networkInterfaceId: networkInterfaceId,
            description: 'updated description'
        ) )

        print( "Modifying network interface attribute sourceDestCheck ${networkInterfaceId}" )
        modifyNetworkInterfaceAttribute( new ModifyNetworkInterfaceAttributeRequest(
            networkInterfaceId: networkInterfaceId,
            sourceDestCheck: false
        ) )

        print( "Verifying updated attributes for network interface ${networkInterfaceId}" )
        attributeHolder[0] = 'description'
        describeNetworkInterfaceAttribute( new DescribeNetworkInterfaceAttributeRequest( networkInterfaceId: networkInterfaceId ) ).with {
          assertThat( networkInterfaceId == expectedNetworkInterfaceId, "Expected ENI id ${expectedNetworkInterfaceId}, but was: ${networkInterfaceId}" )
          assertThat( description == 'updated description', "Expected description 'updated description', but was: ${description}" )
        }
        attributeHolder[0] = 'sourceDestCheck'
        describeNetworkInterfaceAttribute( new DescribeNetworkInterfaceAttributeRequest( networkInterfaceId: networkInterfaceId ) ).with {
          assertThat( networkInterfaceId == expectedNetworkInterfaceId, "Expected ENI id ${expectedNetworkInterfaceId}, but was: ${networkInterfaceId}" )
          assertThat( !sourceDestCheck, "Expected !sourceDestCheck" )
        }

        //TODO Could test ENI delete on terminate attribute once running an instance in a VPC is implemented

        //TODO Could test changing (VPC) security groups for the ENI once security groups for ENIs implemented

        print( "Resetting attribute for network interface ${networkInterfaceId}" )
        attributeHolder[0] = 'sourceDestCheck'
        resetNetworkInterfaceAttribute( new ResetNetworkInterfaceAttributeRequest( networkInterfaceId: networkInterfaceId ) )

        print( "Verifying reset attribute for network interface ${networkInterfaceId}" )
        attributeHolder[0] = 'sourceDestCheck'
        describeNetworkInterfaceAttribute( new DescribeNetworkInterfaceAttributeRequest( networkInterfaceId: networkInterfaceId ) ).with {
          assertThat( networkInterfaceId == expectedNetworkInterfaceId, "Expected ENI id ${expectedNetworkInterfaceId}, but was: ${networkInterfaceId}" )
          assertThat( sourceDestCheck, "Expected sourceDestCheck" )
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
