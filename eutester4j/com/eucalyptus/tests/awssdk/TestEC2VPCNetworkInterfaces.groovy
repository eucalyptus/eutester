package com.eucalyptus.tests.awssdk

import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.*

import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.EC2_ENDPOINT
import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit

/**
 * This application tests EC2 VPC network interface functionality.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9609
 */
class TestEC2VPCNetworkInterfaces {

  private final AWSCredentialsProvider credentials
  private final String cidrPrefix = '172.30.0'

  public static void main( String[] args ) throws Exception {
    new TestEC2VPCNetworkInterfaces().EC2VPCNetworkInterfacesTest( )
  }

  public TestEC2VPCNetworkInterfaces() {
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
  public void EC2VPCNetworkInterfacesTest( ) throws Exception {
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
      ec2.with{
        print( 'Creating VPC' )
        String vpcId = createVpc( new CreateVpcRequest( cidrBlock: "${cidrPrefix}.0/24" ) ).with {
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
        String subnetId = createSubnet( new CreateSubnetRequest( vpcId: vpcId, cidrBlock: "${cidrPrefix}.0/24" ) ).with {
          subnet.with {
            subnetId
          }
        }
        print( "Created subnet with id ${subnetId}" )
        cleanupTasks.add{
          print( "Deleting subnet ${subnetId}" )
          deleteSubnet( new DeleteSubnetRequest( subnetId: subnetId ) )
        }

        print( "Creating security groups in VPC ${vpcId}" )
        String securityGroupId1 = createSecurityGroup( new CreateSecurityGroupRequest(
          groupName: "security-group-1-${vpcId}",
          description: "Test security group 1 for VPC ${vpcId}",
          vpcId: vpcId
        ) ).with {
          groupId
        }
        print( "Created security group ${securityGroupId1} in VPC ${vpcId}" )
        cleanupTasks.add{
          print( "Deleting security group ${securityGroupId1}" )
          deleteSecurityGroup( new DeleteSecurityGroupRequest( groupId: securityGroupId1 ) )
        }

        String securityGroupId2 = createSecurityGroup( new CreateSecurityGroupRequest(
            groupName: "security-group-2-${vpcId}",
            description: "Test security group 2 for VPC ${vpcId}",
            vpcId: vpcId
        ) ).with {
          groupId
        }
        print( "Created security group ${securityGroupId2} in VPC ${vpcId}" )
        cleanupTasks.add{
          print( "Deleting security group ${securityGroupId2}" )
          deleteSecurityGroup( new DeleteSecurityGroupRequest( groupId: securityGroupId2 ) )
        }

        print( "Creating network interface in subnet ${subnetId}" )
        String networkInterfaceId = createNetworkInterface( new CreateNetworkInterfaceRequest(
            subnetId: subnetId,
            groups: [ securityGroupId1 ]
        ) ).with {
          networkInterface?.networkInterfaceId
        }
        print( "Created network interface ${networkInterfaceId}" )
        cleanupTasks.add{
          print( "Deleting network interface ${networkInterfaceId}" )
          deleteNetworkInterface( new DeleteNetworkInterfaceRequest( networkInterfaceId: networkInterfaceId ) )
        }

        print( "Verifying network interface network group filters" )
        describeNetworkInterfaces( new DescribeNetworkInterfacesRequest(
            filters: [ new Filter( name: 'group-id', values: [ securityGroupId1 ] ) ]
        ) ).with{
          assertThat( 1 == networkInterfaces?.size( ), "Expected one network interface, but was: ${networkInterfaces?.size( )}" )
        }
        describeNetworkInterfaces( new DescribeNetworkInterfacesRequest(
            filters: [
                new Filter( name: 'group-name', values: [ "security-group-1-${vpcId}" as String ] ),
                new Filter( name: 'vpc-id', values: [ vpcId ] )
            ]
        ) ).with{
          assertThat( 1 == networkInterfaces?.size( ), "Expected one network interface, but was: ${networkInterfaces?.size( )}" )
        }

        print( "Modifying security groups for network interface ${networkInterfaceId}" )
        modifyNetworkInterfaceAttribute( new ModifyNetworkInterfaceAttributeRequest(
            networkInterfaceId: networkInterfaceId,
            groups: [ securityGroupId2 ]
        ) )

        print( "Verifying network interface network groups updated" )
        describeNetworkInterfaces( new DescribeNetworkInterfacesRequest(
            filters: [ new Filter( name: 'group-id', values: [ securityGroupId2 ] ) ]
        ) ).with{
          assertThat( 1 == networkInterfaces?.size( ), "Expected one network interface, but was: ${networkInterfaces?.size( )}" )
        }
        describeNetworkInterfaces( new DescribeNetworkInterfacesRequest(
            filters: [
                new Filter( name: 'group-name', values: [ "security-group-2-${vpcId}" as String ] ),
                new Filter( name: 'vpc-id', values: [ vpcId ] )
            ]
        ) ).with{
          assertThat( 1 == networkInterfaces?.size( ), "Expected one network interface, but was: ${networkInterfaces?.size( )}" )
        }

        //TODO
        //TODO
        //TODO Enable when instances can be run in a VPC
        //TODO
        //TODO
        print( "SKIPPING - FIXME (needs support for running instance in VPC)" )
        print( "SKIPPING - FIXME" )
        print( "SKIPPING - FIXME - Running instance with specified network interface ${networkInterfaceId}" )
//        String instanceId = runInstances( new RunInstancesRequest(
//            minCount: 1,
//            maxCount: 1,
//            imageId: imageId,
//            keyName: keyName,
//            networkInterfaces: [
//                new InstanceNetworkInterfaceSpecification(
//                    deviceIndex: 0,
//                    deleteOnTermination: false,
//                    networkInterfaceId: networkInterfaceId
//                )
//            ]
//        )).with {
//          reservation?.with {
//            instances?.getAt( 0 )?.instanceId
//          }
//        }
//
//        print( "Instance running with identifier ${instanceId}" )
//        cleanupTasks.add{
//          print( "Terminating instance ${instanceId}" )
//          terminateInstances( new TerminateInstancesRequest( instanceIds: [ instanceId ] ) )
//
//          print( "Waiting for instance ${instanceId} to terminate" )
//          ( 1..25 ).find{
//            sleep 5000
//            print( "Waiting for instance ${instanceId} to terminate, waited ${it*5}s" )
//            describeInstances( new DescribeInstancesRequest(
//                instanceIds: [ instanceId ],
//                filters: [ new Filter( name: "instance-state-name", values: [ "terminated" ] ) ]
//            ) ).with {
//              reservations?.getAt( 0 )?.instances?.getAt( 0 )?.instanceId == instanceId
//            }
//          }
//        }
//
//        print( "Waiting for instance ${instanceId} to start" )
//        ( 1..25 ).find{
//          sleep 5000
//          print( "Waiting for instance ${instanceId} to start, waited ${it*5}s" )
//          describeInstances( new DescribeInstancesRequest(
//              instanceIds: [ instanceId ],
//              filters: [ new Filter( name: "instance-state-name", values: [ "running" ] ) ]
//          ) ).with {
//            reservations?.getAt( 0 )?.instances?.getAt( 0 )?.instanceId == instanceId
//          }
//        }
//
//        print( "Verifying network interface attachment via instance ${instanceId}" )
//        describeInstances( new DescribeInstancesRequest( instanceIds: [ instanceId ] ) ).with {
//          assertThat( 1 == reservations?.size( ), "Expected one reservation, but was: ${reservations?.size()}" )
//          reservations[0].with{
//            assertThat( 1 == instances?.size(), "Expected one instance, but was: ${instances?.size()}" )
//            instances[0].with {
//              assertThat( 1 == networkInterfaces?.size(), "Expected one network interface, but was: ${networkInterfaces?.size()}" )
//              assertThat( networkInterfaceId == networkInterfaces[0].networkInterfaceId, "Expected network interface ${networkInterfaceId}, but was: ${networkInterfaces[0].networkInterfaceId}" )
//              assertThat( 1 == networkInterfaces[0]?.groups?.size(), "Expected security groups" )
//              assertThat( securityGroupId2 == networkInterfaces[0].groups[0].groupId, "Unexpected security group id: ${networkInterfaces[0].groups[0].groupId}" )
//            }
//          }
//        }
//
//        print( "Verifying network interface attachment via network interface ${networkInterfaceId}" )
//        describeNetworkInterfaces( new DescribeNetworkInterfacesRequest(
//            networkInterfaceIds: [networkInterfaceId]
//        ) ).with {
//          assertThat( 1 == networkInterfaces?.size( ), "Expected one network interface, but was: ${networkInterfaces?.size()}" )
//          assertThat( vpcId == networkInterfaces[0].vpcId, "Unexpected vpcId ${networkInterfaces[0].vpcId}" )
//          assertThat( subnetId == networkInterfaces[0].subnetId, "Unexpected subnetId ${networkInterfaces[0].subnetId}" )
//          assertThat( 'in-use' == networkInterfaces[0].status, "Expected status 'in-use', but was: ${networkInterfaces[0].status}" )
//          assertThat( networkInterfaces[0].attachment != null, "Expected attachment" )
//          assertThat( networkInterfaces[0].attachment.attachmentId != null, "Expected attachment id" )
//          assertThat( instanceId == networkInterfaces[0].attachment.instanceId, "Expected attachment instance id ${instanceId}, but was: ${networkInterfaces[0].attachment.instanceId}" )
//          assertThat( !networkInterfaces[0].attachment.deleteOnTermination, "Expected attachment !deleteOnTermination" )
//          assertThat( 1 == networkInterfaces[0]?.groups?.size() , "Expected security groups" )
//          assertThat( securityGroupId2 == networkInterfaces[0].groups[0].groupId, "Unexpected security group id: ${networkInterfaces[0].groups[0].groupId}" )
//        }
//
//        print( "Verifying network interface security group filtering for instance" )
//        describeInstances( new DescribeInstancesRequest(
//            filters: [ new Filter( name: 'network-interface.group-id', values: [ securityGroupId2 ] ) ]
//        ) ).with {
//          assertThat( 1 == reservations?.size( ), "Expected one reservation, but was: ${reservations?.size( )}" )
//        }
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
