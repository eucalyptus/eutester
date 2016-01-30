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

import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit
import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.EC2_ENDPOINT
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY

/**
 * This application tests EC2 VPC run instance with multiple network interfaces.
 *
 * Related JIRA issues:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-11800
 *   https://eucalyptus.atlassian.net/browse/EUCA-11863
 */
class TestEC2VPCRunInstanceNetworkInterfaces {

  private final AWSCredentialsProvider credentials

  public static void main( final String[] args ) throws Exception {
    new TestEC2VPCRunInstanceNetworkInterfaces( ).EC2VPCRunInstanceNetworkInterfacesTest( )
  }

  public TestEC2VPCRunInstanceNetworkInterfaces( ) {
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
  public void EC2VPCRunInstanceNetworkInterfacesTest( ) throws Exception {
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
      print( "Skipping test" )
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

        print( "Creating security group 1" )
        String securityGroupId_1 = createSecurityGroup( new CreateSecurityGroupRequest(
            groupName: 'security group 1',
            description: 'security group 1',
            vpcId: vpcId
        ) ).with {
          groupId
        }
        print( "Created security group 1 with id ${securityGroupId_1}" )
        cleanupTasks.add{
          print( "Deleting security group 1  ${securityGroupId_1}" )
          deleteSecurityGroup( new DeleteSecurityGroupRequest( groupId: securityGroupId_1 ) )
        }

        print( "Creating security group in alternative VPC ${vpcId_2}" )
        String vpc2_securityGroupId = createSecurityGroup( new CreateSecurityGroupRequest(
            groupName: 'alternative security group',
            description: 'alternative security group',
            vpcId: vpcId_2
        ) ).with {
          groupId
        }
        print( "Created security group with id ${vpc2_securityGroupId}" )
        cleanupTasks.add{
          print( "Deleting alternative security group  ${vpc2_securityGroupId}" )
          deleteSecurityGroup( new DeleteSecurityGroupRequest( groupId: vpc2_securityGroupId ) )
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

        print( "Creating network interface in subnet-1 ${subnetId_1}" )
        String primaryNetworkInterfacePrivateIp = '10.10.10.10'
        String primaryNetworkInterfaceId = createNetworkInterface( new CreateNetworkInterfaceRequest(
            subnetId: subnetId_1,
            privateIpAddress: primaryNetworkInterfacePrivateIp
        ) ).with {
          networkInterface?.networkInterfaceId
        }
        print( "Created network interface ${primaryNetworkInterfaceId}" )
        cleanupTasks.add{
          print( "Deleting network interface ${primaryNetworkInterfaceId}" )
          deleteNetworkInterface( new DeleteNetworkInterfaceRequest( networkInterfaceId: primaryNetworkInterfaceId ) )
        }

        print( "Creating network interface in subnet-2 ${subnetId_2}" )
        String secondaryNetworkInterfacePrivateIp_1 = '10.10.20.10'
        String secondaryNetworkInterfaceId_1 = createNetworkInterface( new CreateNetworkInterfaceRequest(
            subnetId: subnetId_2,
            privateIpAddresses: [
                new PrivateIpAddressSpecification(
                    privateIpAddress: secondaryNetworkInterfacePrivateIp_1,
                    primary: true
                )
            ]
        ) ).with {
          networkInterface?.networkInterfaceId
        }
        print( "Created secondary network interface ${secondaryNetworkInterfaceId_1}" )
        cleanupTasks.add{
          print( "Deleting network interface ${secondaryNetworkInterfaceId_1}" )
          deleteNetworkInterface( new DeleteNetworkInterfaceRequest( networkInterfaceId: secondaryNetworkInterfaceId_1 ) )
        }

        print( "Creating network interface in subnet ${subnetId_1}" )
        String secondaryNetworkInterfaceId_2 = createNetworkInterface( new CreateNetworkInterfaceRequest(
            subnetId: subnetId_1
        ) ).with {
          networkInterface?.networkInterfaceId
        }
        print( "Created network interface ${secondaryNetworkInterfaceId_2}" )
        cleanupTasks.add{
          print( "Deleting network interface ${secondaryNetworkInterfaceId_2}" )
          deleteNetworkInterface( new DeleteNetworkInterfaceRequest( networkInterfaceId: secondaryNetworkInterfaceId_2 ) )
        }

        def runInstancesWithDefaults = { RunInstancesRequest request ->
          request.minCount = request.minCount ?: 1
          request.maxCount = request.maxCount ?: 1
          request.imageId = request.imageId ?: imageId
          request.keyName = request.keyName ?: keyName
          runInstances( request )
        }

        // Error case invalid security group ID
        print( "Running instance with invalid security group identifier (should fail)" )
        try {
          runInstancesWithDefaults( new RunInstancesRequest(
              networkInterfaces: [
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 0,
                      subnetId: subnetId_1,
                      groups: [ securityGroupId_1 ]
                  ),
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 1,
                      subnetId: subnetId_2,
                      groups: [ 'sg-00000000' ]
                  ),
              ]
          )).with {
            reservation?.with {
              instances?.getAt( 0 )?.instanceId
            }
          }
          assertThat( false, 'Expected failure' )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          String expectedErrorCode = 'InvalidGroup.NotFound'
          assertThat( e.errorCode == expectedErrorCode, "Expected error code ${expectedErrorCode} but was: ${e.errorCode}" )
        }

        // Error case invalid subnet ID
        print( "Running instance with invalid subnet identifier (should fail)" )
        try {
          runInstancesWithDefaults( new RunInstancesRequest(
              networkInterfaces: [
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 0,
                      subnetId: subnetId_1,
                      groups: [ securityGroupId_1 ]
                  ),
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 1,
                      subnetId: 'subnet-00000000',
                      groups: [ securityGroupId_1 ]
                  ),
              ]
          )).with {
            reservation?.with {
              instances?.getAt( 0 )?.instanceId
            }
          }
          assertThat( false, 'Expected failure' )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          String expectedErrorCode = 'InvalidSubnetID.NotFound'
          assertThat( e.errorCode == expectedErrorCode, "Expected error code ${expectedErrorCode} but was: ${e.errorCode}" )
        }


        // Error case invalid ENI ID
        print( "Running instance with invalid network interface identifier (should fail)" )
        try {
          runInstancesWithDefaults( new RunInstancesRequest(
              networkInterfaces: [
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 0,
                      networkInterfaceId: primaryNetworkInterfaceId,
                  ),
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 1,
                      networkInterfaceId: 'eni-00000000'
                  ),
              ]
          )).with {
            reservation?.with {
              instances?.getAt( 0 )?.instanceId
            }
          }
          assertThat( false, 'Expected failure' )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          String expectedErrorCode = 'InvalidNetworkInterfaceID.NotFound'
          assertThat( e.errorCode == expectedErrorCode, "Expected error code ${expectedErrorCode} but was: ${e.errorCode}" )
        }

        // Error case security group(s) for wrong VPC
        print( "Running instance with security group in wrong VPC (should fail)" )
        try {
          runInstancesWithDefaults( new RunInstancesRequest(
              networkInterfaces: [
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 0,
                      subnetId: subnetId_1,
                      groups: [ securityGroupId_1 ]
                  ),
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 1,
                      subnetId: subnetId_2,
                      groups: [ vpc2_securityGroupId ]
                  ),
              ]
          )).with {
            reservation?.with {
              instances?.getAt( 0 )?.instanceId
            }
          }
          assertThat( false, 'Expected failure' )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          String expectedErrorCode = 'InvalidParameterValue'
          assertThat( e.errorCode == expectedErrorCode, "Expected error code ${expectedErrorCode} but was: ${e.errorCode}" )
        }

        // Error case specifying ENI identifier when running multiple instances
        print( "Running multiple instances with specified ENI (should fail)" )
        try {
          runInstancesWithDefaults( new RunInstancesRequest(
              minCount: 2,
              maxCount: 2,
              networkInterfaces: [
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 0,
                      subnetId: subnetId_1,
                      groups: [ securityGroupId_1 ]
                  ),
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 1,
                      networkInterfaceId: secondaryNetworkInterfaceId_1
                  ),

              ]
          )).with {
            reservation?.with {
              instances?.getAt( 0 )?.instanceId
            }
          }
          assertThat( false, 'Expected failure' )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          String expectedErrorCode = 'InvalidParameterValue'
          assertThat( e.errorCode == expectedErrorCode, "Expected error code ${expectedErrorCode} but was: ${e.errorCode}" )
        }

        // Error case duplicate device index
        print( "Running instance with duplicated device index (should fail)" )
        try {
          runInstancesWithDefaults( new RunInstancesRequest(
              networkInterfaces: [
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 0,
                      networkInterfaceId: primaryNetworkInterfaceId,
                  ),
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 1,
                      networkInterfaceId: secondaryNetworkInterfaceId_1
                  ),
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 1,
                      networkInterfaceId: secondaryNetworkInterfaceId_2
                  ),
              ]
          )).with {
            reservation?.with {
              instances?.getAt( 0 )?.instanceId
            }
          }
          assertThat( false, 'Expected failure' )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          String expectedErrorCode = 'InvalidParameterValue'
          assertThat( e.errorCode == expectedErrorCode, "Expected error code ${expectedErrorCode} but was: ${e.errorCode}" )
        }

        // Error invalid device index for instance type
        print( "Running instance with invalid device index (should fail)" )
        try {
          runInstancesWithDefaults( new RunInstancesRequest(
              networkInterfaces: [
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 0,
                      networkInterfaceId: primaryNetworkInterfaceId,
                  ),
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 12,
                      networkInterfaceId: secondaryNetworkInterfaceId_1
                  ),
              ]
          )).with {
            reservation?.with {
              instances?.getAt( 0 )?.instanceId
            }
          }
          assertThat( false, 'Expected failure' )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          String expectedErrorCode = 'InvalidParameterValue'
          assertThat( e.errorCode == expectedErrorCode, "Expected error code ${expectedErrorCode} but was: ${e.errorCode}" )
        }

        // Error duplicate private address
        print( "Running instance with duplicate private addresses (should fail)" )
        try {
          runInstancesWithDefaults( new RunInstancesRequest(
              networkInterfaces: [
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 0,
                      subnetId: subnetId_1,
                      privateIpAddress: '10.10.10.5'
                  ),
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 1,
                      subnetId: subnetId_1,
                      privateIpAddresses: [
                          new PrivateIpAddressSpecification(
                              primary: true,
                              privateIpAddress: '10.10.10.5'
                          )
                      ]
                  ),
              ]
          )).with {
            reservation?.with {
              instances?.getAt( 0 )?.instanceId
            }
          }
          assertThat( false, 'Expected failure' )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          String expectedErrorCode = 'InvalidParameterValue'
          assertThat( e.errorCode == expectedErrorCode, "Expected error code ${expectedErrorCode} but was: ${e.errorCode}" )
        }

        // Error private address in use
        print( "Running instance with unavailable private address (should fail)" )
        try {
          runInstancesWithDefaults( new RunInstancesRequest(
              networkInterfaces: [
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 0,
                      subnetId: subnetId_1,
                  ),
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 1,
                      subnetId: subnetId_1,
                      privateIpAddress: '10.10.10.10'
                  ),
              ]
          )).with {
            reservation?.with {
              instances?.getAt( 0 )?.instanceId
            }
          }
          assertThat( false, 'Expected failure' )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          String expectedErrorCode = 'InvalidIPAddress.InUse'
          assertThat( e.errorCode == expectedErrorCode, "Expected error code ${expectedErrorCode} but was: ${e.errorCode}" )
        }

        // Error invalid private address for subnet
        print( "Running instance with invalid private address for subnet (should fail)" )
        try {
          runInstancesWithDefaults( new RunInstancesRequest(
              networkInterfaces: [
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 0,
                      subnetId: subnetId_1
                  ),
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 1,
                      subnetId: subnetId_1,
                      privateIpAddress: '10.10.10.1'
                  ),
              ]
          )).with {
            reservation?.with {
              instances?.getAt( 0 )?.instanceId
            }
          }
          assertThat( false, 'Expected failure' )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          String expectedErrorCode = 'InvalidParameterValue'
          assertThat( e.errorCode == expectedErrorCode, "Expected error code ${expectedErrorCode} but was: ${e.errorCode}" )
        }

        // Error specified private address when running multiple instances
        print( "Running multiple instances with specified private address for subnet (should fail)" )
        try {
          runInstancesWithDefaults( new RunInstancesRequest(
              minCount: 2,
              maxCount: 2,
              networkInterfaces: [
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 0,
                      subnetId: subnetId_1
                  ),
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 1,
                      subnetId: subnetId_1,
                      privateIpAddress: '10.10.10.10'
                  ),
              ]
          )).with {
            reservation?.with {
              instances?.getAt( 0 )?.instanceId
            }
          }
          assertThat( false, 'Expected failure' )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          String expectedErrorCode = 'InvalidParameterValue'
          assertThat( e.errorCode == expectedErrorCode, "Expected error code ${expectedErrorCode} but was: ${e.errorCode}" )
        }

        // Error not enough addresses in subnet
        print( "Running multiple instances exceeding available private addresses for subnet (should fail)" )
        try {
          runInstancesWithDefaults( new RunInstancesRequest(
              minCount: 6,
              maxCount: 6,
              networkInterfaces: [
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 0,
                      subnetId: subnetId_1
                  ),
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 1,
                      subnetId: subnetId_1
                  ),
              ]
          )).with {
            reservation?.with {
              instances?.getAt( 0 )?.instanceId
            }
          }
          assertThat( false, 'Expected failure' )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          String expectedErrorCode = 'InsufficientFreeAddressesInSubnet'
          assertThat( e.errorCode == expectedErrorCode, "Expected error code ${expectedErrorCode} but was: ${e.errorCode}" )
        }

        print( "Running instance with specified network interface ${primaryNetworkInterfaceId}" )
        String instanceId = runInstances( new RunInstancesRequest(
            minCount: 1,
            maxCount: 1,
            imageId: imageId,
            keyName: keyName,
            networkInterfaces: [
                new InstanceNetworkInterfaceSpecification(
                    deviceIndex: 0,
                    deleteOnTermination: false,
                    networkInterfaceId: primaryNetworkInterfaceId
                ),
                new InstanceNetworkInterfaceSpecification(
                    deviceIndex: 1,
                    deleteOnTermination: true,
                    networkInterfaceId: secondaryNetworkInterfaceId_1
                ),
            ]
        )).with {
          reservation?.with {
            instances?.getAt( 0 )?.instanceId
          }
        }

        print( "Instance launched with identifier ${instanceId}" )
        cleanupTasks.add{
          print( "Terminating instance ${instanceId}" )
          terminateInstances( new TerminateInstancesRequest( instanceIds: [ instanceId ] ) )

          print( "Waiting for instance ${instanceId} to terminate" )
          ( 1..25 ).find{
            sleep 5000
            print( "Waiting for instance ${instanceId} to terminate, waited ${it*5}s" )
            describeInstances( new DescribeInstancesRequest(
                instanceIds: [ instanceId ],
                filters: [ new Filter( name: "instance-state-name", values: [ "terminated" ] ) ]
            ) ).with {
              reservations?.getAt( 0 )?.instances?.getAt( 0 )?.instanceId == instanceId
            }
          }
        }

        print( "Waiting for instance ${instanceId} to start" )
        ( 1..25 ).find{
          sleep 5000
          print( "Waiting for instance ${instanceId} to start, waited ${it*5}s" )
          describeInstances( new DescribeInstancesRequest(
              instanceIds: [ instanceId ],
              filters: [ new Filter( name: "instance-state-name", values: [ "running" ] ) ]
          ) ).with {
            reservations?.getAt( 0 )?.instances?.getAt( 0 )?.instanceId == instanceId
          }
        }

        print( "Verifying network interface metadata" )
        describeNetworkInterfaces( new DescribeNetworkInterfacesRequest( networkInterfaceIds: [
            primaryNetworkInterfaceId,
            secondaryNetworkInterfaceId_1,
        ] ) ).with {
          assertThat( networkInterfaces != null && networkInterfaces.size( )==2, "Expected 2 network interfaces, but was: ${networkInterfaces.size( )}" )
          networkInterfaces.each { NetworkInterface networkInterface ->
            assertThat( networkInterface?.attachment?.attachmentId != null, "Expected attachment id" )
            assertThat( networkInterface?.association?.allocationId == null, "Unexpected allocation id" )
            assertThat( networkInterface?.association?.associationId == null, "Unexpected association id" )
            assertThat( networkInterface?.association?.publicIp == null, "Unexpected public IP" )
            switch ( networkInterface.networkInterfaceId ) {
              case primaryNetworkInterfaceId:
                assertThat( networkInterface?.privateIpAddress == primaryNetworkInterfacePrivateIp, "Expected private address ${primaryNetworkInterfacePrivateIp}, but was: ${networkInterface.privateIpAddress}" )
                assertThat( networkInterface?.attachment?.instanceId==instanceId, "Expected instance id ${instanceId}, but was: ${networkInterface.attachment.instanceId}" )
                assertThat( networkInterface?.attachment?.attachTime != null, "Expected attach time" )
                assertThat( !networkInterface?.attachment?.deleteOnTermination, "Expected delete on terminate false" )
                assertThat( networkInterface?.attachment?.deviceIndex == 0, "Expected device index 0, but was: ${networkInterface?.attachment?.deviceIndex}" )
                assertThat( 'attached' == networkInterface?.attachment?.status, "Expected status attached, but was: ${networkInterface?.attachment?.status}" )
                break
              case secondaryNetworkInterfaceId_1:
                assertThat( networkInterface?.privateIpAddress == secondaryNetworkInterfacePrivateIp_1, "Expected private address ${secondaryNetworkInterfacePrivateIp_1}, but was: ${networkInterface.privateIpAddress}" )
                assertThat( networkInterface?.attachment?.instanceId==instanceId, "Expected instance id ${instanceId}, but was: ${networkInterface.attachment.instanceId}" )
                assertThat( networkInterface?.attachment?.attachTime != null, "Expected attach time" )
                assertThat( networkInterface?.attachment?.deleteOnTermination, "Expected delete on terminate" )
                assertThat( networkInterface?.attachment?.deviceIndex == 1, "Expected device index 1, but was: ${networkInterface?.attachment?.deviceIndex}" )
                assertThat( 'attached' == networkInterface?.attachment?.status, "Expected status attached, but was: ${networkInterface?.attachment?.status}" )
                break
            }
          }
        }

        // Error ENI in use
        print( "Running instance with attached ENI (should fail)" )
        try {
          runInstancesWithDefaults( new RunInstancesRequest(
              networkInterfaces: [
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 0,
                      subnetId: subnetId_1
                  ),
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 1,
                      networkInterfaceId: secondaryNetworkInterfaceId_1
                  ),
              ]
          )).with {
            reservation?.with {
              instances?.getAt( 0 )?.instanceId
            }
          }
          assertThat( false, 'Expected failure' )
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          String expectedErrorCode = 'InvalidNetworkInterface.InUse'
          assertThat( e.errorCode == expectedErrorCode, "Expected error code ${expectedErrorCode} but was: ${e.errorCode}" )
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
          if ( e.errorCode == 'InvalidInstanceID.NotFound' ) {
            print( e.toString( ) )
          } else {
            e.printStackTrace()
          }
        } catch ( Exception e ) {
          // Some not-found errors are expected here so may need to be suppressed
          e.printStackTrace()
        }
      }
    }
  }
}
