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
 * This application tests modification of instance security groups in EC2 VPC.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9615
 */
class TestEC2VPCModifyInstanceSecurityGroups {

  private final AWSCredentialsProvider credentials

  public static void main( String[] args ) throws Exception {
    new TestEC2VPCModifyInstanceSecurityGroups( ).EC2VPCModifyInstanceSecurityGroupsTest( )
  }

  public TestEC2VPCModifyInstanceSecurityGroups(){
    minimalInit()
//
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
  public void EC2VPCModifyInstanceSecurityGroupsTest( ) throws Exception {
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

        print( "Finding default security group for VPC ${vpcId}" )
        String defaultSecurityGroupId = describeSecurityGroups( new DescribeSecurityGroupsRequest(
            filters: [ new Filter( name: "vpc-id", values: [ vpcId ] ) ]
        ) ).with {
          securityGroups?.getAt( 0 )?.groupId
        }
        assertThat( defaultSecurityGroupId != null, "Expected default security group for VPC" )
        print( "Found default security group ${defaultSecurityGroupId}" )

        print( "Creating security groups in VPC ${vpcId}" )
        String securityGroupId1 = createSecurityGroup( new CreateSecurityGroupRequest(
          groupName: "security-group-1-${vpcId}",
          description: "Tests security group 1 for VPC ${vpcId}",
          vpcId: vpcId
        ) ).with {
          groupId
        }
        print( "Created security group ${securityGroupId1}" )
        cleanupTasks.add{
          print( "Deleting security group ${securityGroupId1}" )
          deleteSecurityGroup( new DeleteSecurityGroupRequest( groupId: securityGroupId1 ) )
        }

        String securityGroupId2 = createSecurityGroup( new CreateSecurityGroupRequest(
            groupName: "security-group-2-${vpcId}",
            description: "Tests security group 2 for VPC ${vpcId}",
            vpcId: vpcId
        ) ).with {
          groupId
        }
        print( "Created security group ${securityGroupId2}" )
        cleanupTasks.add{
          print( "Deleting security group ${securityGroupId2}" )
          deleteSecurityGroup( new DeleteSecurityGroupRequest( groupId: securityGroupId2 ) )
        }

        print( "Running instance in subnet ${subnetId}" )
        String instanceId = runInstances( new RunInstancesRequest(
            minCount: 1,
            maxCount: 1,
            imageId: imageId,
            keyName: keyName,
            subnetId: subnetId
        )).with {
          reservation?.with {
            instances?.getAt( 0 )?.instanceId
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

        print( "Verifying instance ${instanceId} in default security group ${defaultSecurityGroupId}" )
        describeInstanceAttribute( new DescribeInstanceAttributeRequest( instanceId: instanceId, attribute: "groupSet" ) ).with {
          String id = instanceAttribute?.groups?.getAt( 0 )?.groupId
          assertThat( id == defaultSecurityGroupId, "Expected default security group, but was: ${id}" )
        }

        print( "Updating instance ${instanceId} to use security group ${securityGroupId1}" )
        modifyInstanceAttribute( new ModifyInstanceAttributeRequest( instanceId: instanceId, groups: [ securityGroupId1 ] ) )

        print( "Verifying instance ${instanceId} in security group ${securityGroupId1}" )
        describeInstanceAttribute( new DescribeInstanceAttributeRequest( instanceId: instanceId, attribute: "groupSet" ) ).with {
          String id = instanceAttribute?.groups?.getAt( 0 )?.groupId
          assertThat( id == securityGroupId1, "Expected security group ${securityGroupId1}, but was: ${id}" )
        }

        print( "Updating instance ${instanceId} to use security groups ${securityGroupId1}, ${securityGroupId2}" )
        modifyInstanceAttribute( new ModifyInstanceAttributeRequest( instanceId: instanceId, groups: [ securityGroupId1, securityGroupId2 ] ) )

        print( "Verifying instance ${instanceId} in security groups ${securityGroupId1}, ${securityGroupId2}" )
        describeInstanceAttribute( new DescribeInstanceAttributeRequest( instanceId: instanceId, attribute: "groupSet" ) ).with {
          assertThat( instanceAttribute?.groups?.size( ) == 2, "Expected two security groups, but was ${instanceAttribute?.groups?.size( )}" )
          Collection<String> expectedGroups = [ securityGroupId1, securityGroupId2 ]
          assertThat( expectedGroups.remove( instanceAttribute?.groups?.getAt( 0 )?.groupId ),
              "Unexpected security group membership: ${instanceAttribute?.groups?.getAt( 0 )?.groupId}" )
          assertThat( expectedGroups.remove( instanceAttribute?.groups?.getAt( 1 )?.groupId ),
              "Unexpected security group membership: ${instanceAttribute?.groups?.getAt( 1 )?.groupId}" )
        }

        print( "Verifying security groups correct when describing instance ${instanceId}" )
        describeInstances( new DescribeInstancesRequest( instanceIds: [ instanceId ] ) ).with {
          List<GroupIdentifier> groups = reservations?.getAt( 0 )?.instances?.getAt( 0 )?.securityGroups
          assertThat( groups != null, "Expected security groups" )
          assertThat( groups.size() == 2, "Expected two security groups, but was: ${groups.size()}" )
          Collection<String> expectedGroups = [ securityGroupId1, securityGroupId2 ]
          assertThat( expectedGroups.remove( groups?.getAt( 0 )?.groupId ),
              "Unexpected security group membership: ${groups?.getAt( 0 )?.groupId }" )
          assertThat( expectedGroups.remove( groups?.getAt( 1 )?.groupId ),
              "Unexpected security group membership: ${groups?.getAt( 1 )?.groupId }" )
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
