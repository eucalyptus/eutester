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
 * This application tests VPC filtering for non-VPC specific EC2 resources.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9614
 */
class TestEC2VPCFilteringNonVPCResources {

  private final AWSCredentialsProvider credentials
  private final String cidrPrefix = '172.27.192'

  public static void main( String[] args ) throws Exception {
    new TestEC2VPCFilteringNonVPCResources( ).EC2VPCFilteringNonVPCResourcesTest( )
  }

  public TestEC2VPCFilteringNonVPCResources() {
      minimalInit()
      this.credentials = new StaticCredentialsProvider(new BasicAWSCredentials(ACCESS_KEY, SECRET_KEY))
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
  public void EC2VPCFilteringNonVPCResourcesTest( ) throws Exception {
    final AmazonEC2 ec2 = getEC2Client( credentials )

    // Find an image to use
    final String imageId = ec2.describeImages( new DescribeImagesRequest(
        filters: [
            new Filter( name: "image-type", values: ["machine"] ),
            new Filter( name: "root-device-type", values: ["instance-store"] ),
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
        String vpcId = createVpc(new CreateVpcRequest(cidrBlock: "${cidrPrefix}.0/24")).with {
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
        String subnetId = createSubnet(new CreateSubnetRequest(vpcId: vpcId, cidrBlock: "${cidrPrefix}.0/24")).with {
          subnet.with {
            subnetId
          }
        }
        print("Created subnet with id ${subnetId}")
        cleanupTasks.add {
          print("Deleting subnet ${subnetId}")
          deleteSubnet(new DeleteSubnetRequest(subnetId: subnetId))
        }

        print( "verifying VPC filters for security groups" )
        describeSecurityGroups( new DescribeSecurityGroupsRequest(
          filters: [ new Filter( name: 'vpc-id', values: [ vpcId ] ) ]
        ) ).with {
          assertThat( securityGroups != null && securityGroups.size( ) == 1, "Expected 1 group, but was: ${securityGroups?.size()}" )
        }
        describeSecurityGroups( new DescribeSecurityGroupsRequest(
            filters: [ new Filter( name: 'vpc-id', values: [ 'INVALID' ] ) ]
        ) ).with {
          assertThat( securityGroups == null || securityGroups.size( ) == 0, "Expected no groups, but was: ${securityGroups?.size()}" )
        }

        print( "Creating network interface to test address filtering" )
        String networkInterfaceId = createNetworkInterface( new CreateNetworkInterfaceRequest(
          description: 'foo',
          subnetId: subnetId,
          privateIpAddress: "${cidrPrefix}.10"
        ) ).with {
          networkInterface?.networkInterfaceId
        }
        print( "Created network interface ${networkInterfaceId}" )
        cleanupTasks.add{
          print( "Deleting network interface ${networkInterfaceId}" )
          deleteNetworkInterface( new DeleteNetworkInterfaceRequest( networkInterfaceId: networkInterfaceId ) )
        }

        print( "Allocating address to test address filtering" )
        String allocationPublicIp = ''
        String allocationId = allocateAddress( new AllocateAddressRequest( domain: 'vpc' )).with {
          allocationPublicIp = publicIp
          allocationId
        }
        print( "Allocated address ${allocationId}" )
        cleanupTasks.add{
          print( "Releasing address ${allocationId}" )
          releaseAddress( new ReleaseAddressRequest( allocationId: allocationId ))
        }

        print( "Associating address ${allocationId} with network interface ${networkInterfaceId}" )
        String associationId = associateAddress( new AssociateAddressRequest(
            allocationId: allocationId,
            networkInterfaceId: networkInterfaceId
        ) ).with {
          associationId
        }
        print( "Association id ${associationId}" )
        cleanupTasks.add{
          print( "Disassociating address ${associationId}" )
          disassociateAddress( new DisassociateAddressRequest( associationId: associationId ) )
        }

        print( "Verifying VPC filters for addresses" )
        describeAddresses( new DescribeAddressesRequest(
            filters: [
                new Filter( name: 'domain', values: [ 'vpc' ] ),
                new Filter( name: 'public-ip', values: [ allocationPublicIp ] ),
                new Filter( name: 'allocation-id', values: [ allocationId ] ),
                new Filter( name: 'association-id', values: [ associationId ] ),
                new Filter( name: 'network-interface-id', values: [ networkInterfaceId ] ),
                new Filter( name: 'private-ip-address', values: [ "${cidrPrefix}.10" as String ] ),
            ]
        ) ).with {
          assertThat( addresses != null && addresses.size( ) == 1, "Expected 1 address, but was: ${addresses?.size()}" )
        }
        describeAddresses( new DescribeAddressesRequest(
            filters: [
                new Filter( name: 'domain', values: [ 'INVALID' ] ),
                new Filter( name: 'public-ip', values: [ allocationPublicIp ] ),
                new Filter( name: 'allocation-id', values: [ allocationId ] ),
                new Filter( name: 'association-id', values: [ associationId ] ),
                new Filter( name: 'network-interface-id', values: [ networkInterfaceId ] ),
                new Filter( name: 'private-ip-address', values: [ "${cidrPrefix}.10" as String ] ),
            ]
        ) ).with {
          assertThat( addresses == null || addresses.isEmpty( ), "Expected no address, but was: ${addresses?.size()}" )
        }

        print( "Running instance in subnet ${subnetId} to testing instance filtering" )
        String expectedNetworkInterfaceId = ''
        String expectedNetworkInterfaceOwnerId = ''
        String expectedNetworkInterfaceZone = ''
        String expectedNetworkInterfacePrivateIp = ''
        String expectedNetworkInterfacePublicIp = ''
        String expectedNetworkInterfaceAttachmentId = ''
        String instanceId = runInstances( new RunInstancesRequest(
            minCount: 1,
            maxCount: 1,
            imageId: imageId,
            keyName: keyName,
            subnetId: subnetId
        )).with {
          reservation?.with {
            instances?.getAt( 0 )?.with{
              networkInterfaces?.getAt( 0 )?.with { InstanceNetworkInterface eni ->
                expectedNetworkInterfaceId = eni.networkInterfaceId
                expectedNetworkInterfaceOwnerId = ownerId
                expectedNetworkInterfacePrivateIp = privateIpAddress
                expectedNetworkInterfacePublicIp = association?.publicIp
                expectedNetworkInterfaceAttachmentId = attachment.attachmentId
              }
              expectedNetworkInterfaceZone = placement?.availabilityZone
              instanceId
            }
          }
        }

        print( "Instance running with identifier ${instanceId}" )
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

        print( "Verifying VPC filters for instances" )
        describeInstances( new DescribeInstancesRequest(
            filters: [
                new Filter( name: 'subnet-id', values: [ subnetId ] ),
                new Filter( name: 'vpc-id', values: [ vpcId ] ),
                new Filter( name: 'tenancy', values: [ 'default' ] ),
                new Filter( name: 'network-interface.description', values: [ 'Primary network interface' ] ),
                new Filter( name: 'network-interface.subnet-id', values: [ subnetId ] ),
                new Filter( name: 'network-interface.vpc-id', values: [ vpcId ] ),
                new Filter( name: 'network-interface.network-interface.id', values: [ expectedNetworkInterfaceId ] ),
                new Filter( name: 'network-interface.owner-id', values: [ expectedNetworkInterfaceOwnerId ] ),
                new Filter( name: 'network-interface.availability-zone', values: [ expectedNetworkInterfaceZone ] ),
                new Filter( name: 'network-interface.status', values: [ 'in-use' ] ),
                new Filter( name: 'network-interface.source-destination-check', values: [ 'true' ] ),
                new Filter( name: 'network-interface.addresses.private-ip-address', values: [ expectedNetworkInterfacePrivateIp ] ),
                new Filter( name: 'network-interface.addresses.primary', values: [ 'true' ] ),
//                new Filter( name: 'network-interface.addresses.association.public-ip', values: [ expectedNetworkInterfacePublicIp ] ),
                new Filter( name: 'network-interface.attachment.attachment-id', values: [ expectedNetworkInterfaceAttachmentId ] ),
                new Filter( name: 'network-interface.attachment.instance-id', values: [ instanceId ] ),
                new Filter( name: 'network-interface.attachment.instance-owner-id', values: [ expectedNetworkInterfaceOwnerId ] ),
                new Filter( name: 'network-interface.attachment.device-index', values: [ '0' ] ),
                new Filter( name: 'network-interface.attachment.status', values: [ 'attached' ] ),
                new Filter( name: 'network-interface.attachment.delete-on-termination', values: [ 'true' ] ),
//                new Filter( name: 'association.public-ip', values: [ expectedNetworkInterfacePublicIp ] ),
            ]
        ) ).with {
          assertThat( reservations != null && reservations.size( ) == 1, "Expected 1 reservation, but was: ${reservations?.size()}" )
        }
        describeInstances( new DescribeInstancesRequest(
            filters: [
                new Filter( name: 'subnet-id', values: [ subnetId ] ),
                new Filter( name: 'vpc-id', values: [ vpcId ] ),
                new Filter( name: 'tenancy', values: [ 'default' ] ),
                new Filter( name: 'network-interface.description', values: [ 'INVALID' ] ),
                new Filter( name: 'network-interface.subnet-id', values: [ subnetId ] ),
                new Filter( name: 'network-interface.vpc-id', values: [ vpcId ] ),
                new Filter( name: 'network-interface.network-interface.id', values: [ expectedNetworkInterfaceId ] ),
                new Filter( name: 'network-interface.owner-id', values: [ expectedNetworkInterfaceOwnerId ] ),
                new Filter( name: 'network-interface.availability-zone', values: [ expectedNetworkInterfaceZone ] ),
                new Filter( name: 'network-interface.status', values: [ 'in-use' ] ),
                new Filter( name: 'network-interface.source-destination-check', values: [ 'true' ] ),
                new Filter( name: 'network-interface.addresses.private-ip-address', values: [ expectedNetworkInterfacePrivateIp ] ),
                new Filter( name: 'network-interface.addresses.primary', values: [ 'true' ] ),
                new Filter( name: 'network-interface.addresses.association.public-ip', values: [ expectedNetworkInterfacePublicIp ] ),
                new Filter( name: 'network-interface.attachment.attachment-id', values: [ expectedNetworkInterfaceAttachmentId ] ),
                new Filter( name: 'network-interface.attachment.instance-id', values: [ instanceId ] ),
                new Filter( name: 'network-interface.attachment.instance-owner-id', values: [ expectedNetworkInterfaceOwnerId ] ),
                new Filter( name: 'network-interface.attachment.device-index', values: [ '0' ] ),
                new Filter( name: 'network-interface.attachment.status', values: [ 'attached' ] ),
                new Filter( name: 'network-interface.attachment.delete-on-termination', values: [ 'true' ] ),
                new Filter( name: 'association.public-ip', values: [ expectedNetworkInterfacePublicIp ] ),
            ]
        ) ).with {
          assertThat( reservations == null || reservations.isEmpty(), "Expected no reservations, but was: ${reservations?.size()}" )
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
