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
 * This application tests EC2 VPC network interface attach/detach functionality.
 *
 * Related JIRA issues:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-11864
 */
class TestEC2VPCNetworkInterfaceAttach {

  private final AWSCredentialsProvider credentials

  public static void main( final String[] args ) throws Exception {
    new TestEC2VPCNetworkInterfaceAttach( ).EC2VPCNetworkInterfaceAttachTest( )
  }

  public TestEC2VPCNetworkInterfaceAttach( ) {
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
  public void EC2VPCNetworkInterfaceAttachTest( ) throws Exception {
    final AmazonEC2 ec2 = getEC2Client( credentials )

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
        String vpcId = createVpc( new CreateVpcRequest( cidrBlock: "10.10.10.0/24" ) ).with {
          vpc.vpcId
        }
        print( "Created VPC with id ${vpcId}" )
        cleanupTasks.add{
          print( "Deleting VPC ${vpcId}" )
          deleteVpc( new DeleteVpcRequest( vpcId: vpcId ) )
        }

        print( 'Creating subnet' )
        String subnetId = createSubnet( new CreateSubnetRequest( vpcId: vpcId, cidrBlock: "10.10.10.0/24" ) ).with {
          subnet.subnetId
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

        print( "Allocating EIP for secondary network interface 1" )
        String eip_1 = allocateAddress( ).with{ publicIp }
        print( "Allocated EIP ${eip_1}" )
        cleanupTasks.add{
          print( "Releasing EIP ${eip_1}" )
          releaseAddress( new ReleaseAddressRequest( publicIp: eip_1 ) )
        }

        print( "Allocating EIP for secondary network interface 2" )
        String eip_2 = allocateAddress( ).with{ publicIp }
        print( "Allocated EIP ${eip_2}" )
        cleanupTasks.add{
          print( "Releasing EIP ${eip_2}" )
          releaseAddress( new ReleaseAddressRequest( publicIp: eip_2 ) )
        }

        print( "Allocating EIP for secondary network interface 3" )
        String eip_3 = allocateAddress( ).with{ publicIp }
        print( "Allocated EIP ${eip_3}" )
        cleanupTasks.add{
          print( "Releasing EIP ${eip_3}" )
          releaseAddress( new ReleaseAddressRequest( publicIp: eip_3 ) )
        }

        print( "Creating network interface in subnet ${subnetId}" )
        String primaryNetworkInterfacePrivateIp = '10.10.10.100'
        String primaryNetworkInterfaceId = createNetworkInterface( new CreateNetworkInterfaceRequest(
            subnetId: subnetId,
            privateIpAddress: primaryNetworkInterfacePrivateIp
        ) ).with {
          networkInterface?.networkInterfaceId
        }
        print( "Created network interface ${primaryNetworkInterfaceId}" )
        cleanupTasks.add{
          print( "Deleting network interface ${primaryNetworkInterfaceId}" )
          deleteNetworkInterface( new DeleteNetworkInterfaceRequest( networkInterfaceId: primaryNetworkInterfaceId ) )
        }

        print( "Creating network interface in subnet ${subnetId}" )
        String secondaryNetworkInterfacePrivateIp_1 = '10.10.10.101'
        String secondaryNetworkInterfaceId_1 = createNetworkInterface( new CreateNetworkInterfaceRequest(
            subnetId: subnetId,
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

        print( "Creating network interface in subnet ${subnetId}" )
        String secondaryNetworkInterfaceId_2 = createNetworkInterface( new CreateNetworkInterfaceRequest(
            subnetId: subnetId
        ) ).with {
          networkInterface?.networkInterfaceId
        }
        print( "Created network interface ${secondaryNetworkInterfaceId_2}" )
        cleanupTasks.add{
          print( "Deleting network interface ${secondaryNetworkInterfaceId_2}" )
          deleteNetworkInterface( new DeleteNetworkInterfaceRequest( networkInterfaceId: secondaryNetworkInterfaceId_2 ) )
        }

        print( "Creating network interface in subnet ${subnetId}" )
        String secondaryNetworkInterfaceId_3 = createNetworkInterface( new CreateNetworkInterfaceRequest(
            subnetId: subnetId
        ) ).with {
          networkInterface?.networkInterfaceId
        }
        print( "Created network interface ${secondaryNetworkInterfaceId_3}" )
        cleanupTasks.add{
          print( "Deleting network interface ${secondaryNetworkInterfaceId_3}" )
          deleteNetworkInterface( new DeleteNetworkInterfaceRequest( networkInterfaceId: secondaryNetworkInterfaceId_3 ) )
        }

        print( "Creating network interface in subnet ${subnetId}" )
        String secondaryNetworkInterfaceId_4 = createNetworkInterface( new CreateNetworkInterfaceRequest(
            subnetId: subnetId
        ) ).with {
          networkInterface?.networkInterfaceId
        }
        print( "Created network interface ${secondaryNetworkInterfaceId_4}" )
        cleanupTasks.add{
          print( "Deleting network interface ${secondaryNetworkInterfaceId_4}" )
          deleteNetworkInterface( new DeleteNetworkInterfaceRequest( networkInterfaceId: secondaryNetworkInterfaceId_4 ) )
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
                    deleteOnTermination: true,
                    networkInterfaceId: primaryNetworkInterfaceId
                )
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

        print( "Associating EIP 1 ${eip_1} with secondary network interface 1 ${secondaryNetworkInterfaceId_1}" )
        associateAddress( new AssociateAddressRequest(
          publicIp: eip_1,
          networkInterfaceId: secondaryNetworkInterfaceId_1
        ) )

        print( "Associating EIP 2 ${eip_2} with secondary network interface 2 ${secondaryNetworkInterfaceId_2}" )
        associateAddress( new AssociateAddressRequest(
            publicIp: eip_2,
            networkInterfaceId: secondaryNetworkInterfaceId_2
        ) )

        print( "Verifying EIP metadata" )
        describeAddresses( new DescribeAddressesRequest( publicIps: [ eip_1, eip_2, eip_3 ] ) ).with {
          assertThat( addresses != null && addresses.size( )==3, "Expected 3 addresses, but was: ${addresses.size( )}" )
          addresses.each { Address address ->
            assertThat( address.domain == 'vpc', "Expected address in vpc domain, but was: ${address.domain}")
            assertThat( address.allocationId != null, "Expected allocation id")
            switch ( address.publicIp ) {
              case eip_1:
                assertThat( address.associationId != null, "Expected assocation id")
                assertThat( address.instanceId==null, "Unexpected instance id ${address.instanceId}" )
                assertThat( address.networkInterfaceId==secondaryNetworkInterfaceId_1, "Expected network interface id ${secondaryNetworkInterfaceId_1}, but was ${address.networkInterfaceId}" )
                assertThat( address.networkInterfaceOwnerId != null, "Expected network interface owner id")
                assertThat( address.privateIpAddress == secondaryNetworkInterfacePrivateIp_1,
                    "Expected private address ${secondaryNetworkInterfacePrivateIp_1}, but was: ${address.privateIpAddress}" )
                break;
              case eip_2:
                assertThat( address.associationId != null, "Expected assocation id")
                assertThat( address.instanceId==null, "Unexpected instance id ${address.instanceId}" )
                assertThat( address.networkInterfaceId==secondaryNetworkInterfaceId_2, "Expected network interface id ${secondaryNetworkInterfaceId_2}, but was ${address.networkInterfaceId}" )
                assertThat( address.networkInterfaceOwnerId != null, "Expected network interface owner id")
                break;
              case eip_3:
                assertThat( address.associationId == null, "Expected no assocation id, but was: ${address.associationId}")
                assertThat( address.instanceId==null, "Unexpected instance id ${address.instanceId}" )
                assertThat( address.networkInterfaceId==null, "Unexpected network interface id ${address.networkInterfaceId}" )
                assertThat( address.networkInterfaceOwnerId==null, "Unexpected network interface owner id ${address.networkInterfaceOwnerId}")
                break;

            }
          }
        }

        print( "Attaching secondary network interface 1 ${secondaryNetworkInterfaceId_1} to instance ${instanceId}" )
        String secondaryNetworkInterfaceAttachmentId_1 = attachNetworkInterface( new AttachNetworkInterfaceRequest(
            instanceId: instanceId,
            networkInterfaceId: secondaryNetworkInterfaceId_1,
            deviceIndex: 1
        ) ).with { attachmentId }

        print( "Attaching secondary network interface 2 ${secondaryNetworkInterfaceId_2} to instance ${instanceId}" )
        String secondaryNetworkInterfaceAttachmentId_2 = attachNetworkInterface( new AttachNetworkInterfaceRequest(
            instanceId: instanceId,
            networkInterfaceId: secondaryNetworkInterfaceId_2,
            deviceIndex: 2,
        ) ).with { attachmentId }

        print( "Attaching secondary network interface 3 ${secondaryNetworkInterfaceId_3} to instance ${instanceId}" )
        String secondaryNetworkInterfaceAttachmentId_3 = attachNetworkInterface( new AttachNetworkInterfaceRequest(
            instanceId: instanceId,
            networkInterfaceId: secondaryNetworkInterfaceId_3,
            deviceIndex: 3
        ) ).with { attachmentId }

        print( "Attaching secondary network interface 4 ${secondaryNetworkInterfaceId_4} to instance ${instanceId}" )
        String secondaryNetworkInterfaceAttachmentId_4 = attachNetworkInterface( new AttachNetworkInterfaceRequest(
            instanceId: instanceId,
            networkInterfaceId: secondaryNetworkInterfaceId_4,
            deviceIndex: 4
        ) ).with { attachmentId }

        print( "Associating EIP 3 ${eip_3} with secondary network interface 3 ${secondaryNetworkInterfaceId_3}" )
        associateAddress( new AssociateAddressRequest(
            publicIp: eip_3,
            networkInterfaceId: secondaryNetworkInterfaceId_3
        ) )

        print( "Verifying EIP metadata" )
        describeAddresses( new DescribeAddressesRequest( publicIps: [ eip_1, eip_2, eip_3 ] ) ).with {
          assertThat( addresses != null && addresses.size( )==3, "Expected 3 addresses, but was: ${addresses.size( )}" )
          addresses.each { Address address ->
            assertThat( address.domain == 'vpc', "Expected address in vpc domain, but was: ${address.domain}")
            assertThat( address.associationId != null, "Expected assocation id")
            assertThat( address.allocationId != null, "Expected allocation id")
            assertThat( address.instanceId==instanceId, "Expected instance id ${instanceId}, but was ${address.instanceId}" )
            switch ( address.publicIp ) {
              case eip_1:
                assertThat( address.networkInterfaceId==secondaryNetworkInterfaceId_1, "Expected network interface id ${secondaryNetworkInterfaceId_1}, but was ${address.networkInterfaceId}" )
                assertThat( address.networkInterfaceOwnerId != null, "Expected network interface owner id")
                assertThat( address.privateIpAddress == secondaryNetworkInterfacePrivateIp_1,
                    "Expected private address ${secondaryNetworkInterfacePrivateIp_1}, but was: ${address.privateIpAddress}" )
                break;
              case eip_2:
                assertThat( address.networkInterfaceId==secondaryNetworkInterfaceId_2, "Expected network interface id ${secondaryNetworkInterfaceId_2}, but was ${address.networkInterfaceId}" )
                assertThat( address.networkInterfaceOwnerId != null, "Expected network interface owner id")
                break;
              case eip_3:
                assertThat( address.networkInterfaceId==secondaryNetworkInterfaceId_3, "Expected network interface id ${secondaryNetworkInterfaceId_3}, but was ${address.networkInterfaceId}" )
                assertThat( address.networkInterfaceOwnerId != null, "Expected network interface owner id")
                break;

            }
          }
        }

        print( "Setting secondary network interface 3 to delete on terminate" )
        modifyNetworkInterfaceAttribute( new ModifyNetworkInterfaceAttributeRequest(
            networkInterfaceId: secondaryNetworkInterfaceId_3,
            attachment: new NetworkInterfaceAttachmentChanges(
                attachmentId: secondaryNetworkInterfaceAttachmentId_3,
                deleteOnTermination: true
            )
        ) )

        print( "Verifying network interface metadata" )
        describeNetworkInterfaces( new DescribeNetworkInterfacesRequest( networkInterfaceIds: [
            primaryNetworkInterfaceId,
            secondaryNetworkInterfaceId_1,
            secondaryNetworkInterfaceId_2,
            secondaryNetworkInterfaceId_3,
            secondaryNetworkInterfaceId_4,
        ] ) ).with {
          assertThat( networkInterfaces != null && networkInterfaces.size( )==5, "Expected 5 network interfaces, but was: ${networkInterfaces.size( )}" )
          networkInterfaces.each { NetworkInterface networkInterface ->
            switch ( networkInterface.networkInterfaceId ) {
              case primaryNetworkInterfaceId:
                assertThat( networkInterface?.privateIpAddress == primaryNetworkInterfacePrivateIp, "Expected private address ${primaryNetworkInterfacePrivateIp}, but was: ${networkInterface.privateIpAddress}" )
                assertThat( networkInterface?.attachment?.attachmentId != null, "Expected attachment id" )
                assertThat( networkInterface?.attachment?.instanceId==instanceId, "Expected instance id ${instanceId}, but was: ${networkInterface.attachment.instanceId}" )
                assertThat( networkInterface?.attachment?.attachTime != null, "Expected attach time" )
                assertThat( networkInterface?.attachment?.deleteOnTermination, "Expected delete on terminate" )
                assertThat( networkInterface?.attachment?.deviceIndex == 0, "Expected device index 0, but was: ${networkInterface?.attachment?.deviceIndex}" )
                assertThat( 'attached' == networkInterface?.attachment?.status, "Expected status attached, but was: ${networkInterface?.attachment?.status}" )
                assertThat( networkInterface?.association?.allocationId == null, "Unexpected allocation id" )
                assertThat( networkInterface?.association?.associationId == null, "Unexpected association id" )
                assertThat( networkInterface?.association?.publicIp == null, "Unexpected public IP" )
                break
              case secondaryNetworkInterfaceId_1:
                assertThat( networkInterface?.privateIpAddress == secondaryNetworkInterfacePrivateIp_1, "Expected private address ${secondaryNetworkInterfacePrivateIp_1}, but was: ${networkInterface.privateIpAddress}" )
                assertThat( networkInterface?.attachment?.attachmentId == secondaryNetworkInterfaceAttachmentId_1, "Expected attachment id ${secondaryNetworkInterfaceAttachmentId_1}, but was: ${networkInterface?.attachment?.attachmentId}" )
                assertThat( networkInterface?.attachment?.instanceId==instanceId, "Expected instance id ${instanceId}, but was: ${networkInterface.attachment.instanceId}" )
                assertThat( networkInterface?.attachment?.attachTime != null, "Expected attach time" )
                assertThat( !networkInterface?.attachment?.deleteOnTermination, "Expected delete on terminate false" )
                assertThat( networkInterface?.attachment?.deviceIndex == 1, "Expected device index 1, but was: ${networkInterface?.attachment?.deviceIndex}" )
                assertThat( 'attached' == networkInterface?.attachment?.status, "Expected status attached, but was: ${networkInterface?.attachment?.status}" )
                assertThat( networkInterface?.association?.allocationId != null, "Expected allocation id" )
                assertThat( networkInterface?.association?.associationId != null, "Expected association id" )
                assertThat( networkInterface?.association?.ipOwnerId != null, "Expected ip owner id" )
                assertThat( networkInterface?.association?.publicIp == eip_1, "Expected public IP ${eip_1}, but was: ${networkInterface?.association?.publicIp}" )
                break
              case secondaryNetworkInterfaceId_2:
                assertThat( networkInterface?.attachment?.attachmentId == secondaryNetworkInterfaceAttachmentId_2, "Expected attachment id ${secondaryNetworkInterfaceAttachmentId_2}, but was: ${networkInterface?.attachment?.attachmentId}" )
                assertThat( networkInterface?.attachment?.instanceId==instanceId, "Expected instance id ${instanceId}, but was: ${networkInterface.attachment.instanceId}" )
                assertThat( networkInterface?.attachment?.attachTime != null, "Expected attach time" )
                assertThat( !networkInterface?.attachment?.deleteOnTermination, "Expected delete on terminate false" )
                assertThat( networkInterface?.attachment?.deviceIndex == 2, "Expected device index 1, but was: ${networkInterface?.attachment?.deviceIndex}" )
                assertThat( 'attached' == networkInterface?.attachment?.status, "Expected status attached, but was: ${networkInterface?.attachment?.status}" )
                assertThat( networkInterface?.association?.allocationId != null, "Expected allocation id" )
                assertThat( networkInterface?.association?.associationId != null, "Expected association id" )
                assertThat( networkInterface?.association?.ipOwnerId != null, "Expected ip owner id" )
                assertThat( networkInterface?.association?.publicIp == eip_2, "Expected public IP ${eip_2}, but was: ${networkInterface?.association?.publicIp}" )
                break
              case secondaryNetworkInterfaceId_3:
                assertThat( networkInterface?.attachment?.attachmentId == secondaryNetworkInterfaceAttachmentId_3, "Expected attachment id ${secondaryNetworkInterfaceAttachmentId_3}, but was: ${networkInterface?.attachment?.attachmentId}" )
                assertThat( networkInterface?.attachment?.instanceId==instanceId, "Expected instance id ${instanceId}, but was: ${networkInterface.attachment.instanceId}" )
                assertThat( networkInterface?.attachment?.attachTime != null, "Expected attach time" )
                assertThat( networkInterface?.attachment?.deleteOnTermination, "Expected delete on terminate" )
                assertThat( networkInterface?.attachment?.deviceIndex == 3, "Expected device index 1, but was: ${networkInterface?.attachment?.deviceIndex}" )
                assertThat( 'attached' == networkInterface?.attachment?.status, "Expected status attached, but was: ${networkInterface?.attachment?.status}" )
                assertThat( networkInterface?.association?.allocationId != null, "Expected allocation id" )
                assertThat( networkInterface?.association?.associationId != null, "Expected association id" )
                assertThat( networkInterface?.association?.ipOwnerId != null, "Expected ip owner id" )
                assertThat( networkInterface?.association?.publicIp == eip_3, "Expected public IP ${eip_3}, but was: ${networkInterface?.association?.publicIp}" )
                break
              case secondaryNetworkInterfaceId_4:
                assertThat( networkInterface?.attachment?.attachmentId == secondaryNetworkInterfaceAttachmentId_4, "Expected attachment id ${secondaryNetworkInterfaceAttachmentId_4}, but was: ${networkInterface?.attachment?.attachmentId}" )
                assertThat( networkInterface?.attachment?.instanceId==instanceId, "Expected instance id ${instanceId}, but was: ${networkInterface.attachment.instanceId}" )
                assertThat( networkInterface?.attachment?.attachTime != null, "Expected attach time" )
                assertThat( !networkInterface?.attachment?.deleteOnTermination, "Expected delete on terminate false" )
                assertThat( networkInterface?.attachment?.deviceIndex == 4, "Expected device index 1, but was: ${networkInterface?.attachment?.deviceIndex}" )
                assertThat( 'attached' == networkInterface?.attachment?.status, "Expected status attached, but was: ${networkInterface?.attachment?.status}" )
                assertThat( networkInterface?.association?.allocationId == null, "Unexpected allocation id" )
                assertThat( networkInterface?.association?.associationId == null, "Unexpected association id" )
                assertThat( networkInterface?.association?.ipOwnerId == null, "Unexpected ip owner id" )
                assertThat( networkInterface?.association?.publicIp == null, "Unexpected public IP ${networkInterface?.association?.publicIp}" )
                break
            }
          }
        }

        print( "Disassociating EIP 1 from network interface 1 prior to instance termination" )
        disassociateAddress( new DisassociateAddressRequest(
          publicIp: eip_1
        ) )

        print( "Detaching secondary network interface 2 from instance prior to instance termination" )
        detachNetworkInterface( new DetachNetworkInterfaceRequest( attachmentId: secondaryNetworkInterfaceAttachmentId_2 ) )

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

        print( "Verifying EIP metadata" )
        describeAddresses( new DescribeAddressesRequest( publicIps: [ eip_1, eip_2, eip_3 ] ) ).with {
          assertThat( addresses != null && addresses.size( )==3, "Expected 3 addresses, but was: ${addresses.size( )}" )
          addresses.each { Address address ->
            assertThat( address.domain == 'vpc', "Expected address in vpc domain, but was: ${address.domain}")
            assertThat( address.allocationId != null, "Expected allocation id")
            switch ( address.publicIp ) {
              case eip_1:
                assertThat( address.associationId == null, "Expected no assocation id, but was: ${address.associationId}")
                assertThat( address.instanceId==null, "Unexpected instance id ${address.instanceId}" )
                assertThat( address.networkInterfaceId==null, "Unexpected network interface id ${address.networkInterfaceId}" )
                assertThat( address.networkInterfaceOwnerId==null, "Unexpected network interface owner id ${address.networkInterfaceOwnerId}")
                assertThat( address.privateIpAddress == null, "Unexpected private address ${address.privateIpAddress}" )
                break;
              case eip_2:
                assertThat( address.associationId != null, "Expected assocation id")
                assertThat( address.instanceId==null, "Unexpected instance id ${address.instanceId}" )
                assertThat( address.networkInterfaceId==secondaryNetworkInterfaceId_2, "Expected network interface id ${secondaryNetworkInterfaceId_2}, but was ${address.networkInterfaceId}" )
                assertThat( address.networkInterfaceOwnerId != null, "Expected network interface owner id")
                break;
              case eip_3:
                assertThat( address.associationId == null, "Expected no assocation id, but was: ${address.associationId}")
                assertThat( address.instanceId==null, "Unexpected instance id ${address.instanceId}" )
                assertThat( address.networkInterfaceId==null, "Unexpected network interface id ${address.networkInterfaceId}" )
                assertThat( address.networkInterfaceOwnerId==null, "Unexpected network interface owner id ${address.networkInterfaceOwnerId}")
                assertThat( address.privateIpAddress == null, "Unexpected private address ${address.privateIpAddress}" )
                break;

            }
          }
        }

        print( "Disassociating EIP 2 from network interface 2" )
        disassociateAddress( new DisassociateAddressRequest(
            publicIp: eip_2
        ) )

        print( "Verifying EIP metadata" )
        describeAddresses( new DescribeAddressesRequest( publicIps: [ eip_1, eip_2, eip_3 ] ) ).with {
          assertThat( addresses != null && addresses.size( )==3, "Expected 3 addresses, but was: ${addresses.size( )}" )
          addresses.each { Address address ->
            assertThat( address.domain == 'vpc', "Expected address in vpc domain, but was: ${address.domain}")
            assertThat( address.allocationId != null, "Expected allocation id")
            switch ( address.publicIp ) {
              case eip_2:
                assertThat( address.associationId == null, "Expected no assocation id, but was: ${address.associationId}")
                assertThat( address.instanceId==null, "Unexpected instance id ${address.instanceId}" )
                assertThat( address.networkInterfaceId==null, "Unexpected network interface id ${address.networkInterfaceId}" )
                assertThat( address.networkInterfaceOwnerId==null, "Unexpected network interface owner id ${address.networkInterfaceOwnerId}")
                assertThat( address.privateIpAddress == null, "Unexpected private address ${address.privateIpAddress}" )
                break;
            }
          }
        }
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
