/*************************************************************************
 * Copyright 2009-2013 Eucalyptus Systems, Inc.
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see http://www.gnu.org/licenses/.
 *
 * Please contact Eucalyptus Systems, Inc., 6755 Hollister Ave., Goleta
 * CA 93117, USA or visit http://www.eucalyptus.com/licenses/ if you need
 * additional information or have any questions.
 ************************************************************************/
package com.eucalyptus.tests.awssdk

import com.amazonaws.AmazonServiceException
import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.regions.Regions
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.*

import org.testng.annotations.Test

import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit

/**
 * This application tests EC2 VPC security group functionality.
 *
 * The tests covers running instances with security groups and modifying group
 * membership via instance and network interface attributes.
 *
 * This is verification for the issue:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-10004
 */
class TestEC2VPCSecurityGroupsInstancesAttributes {

  private final String host
  private final AWSCredentialsProvider credentials
  private final List<String> imageOwners

  public static void main( String[] args ) throws Exception {
    new TestEC2VPCSecurityGroupsInstancesAttributes( ).test( )
  }

  public TestEC2VPCSecurityGroupsInstancesAttributes() {
      minimalInit()
      this.host=HOST_IP
      this.credentials = new StaticCredentialsProvider(new BasicAWSCredentials(ACCESS_KEY, SECRET_KEY))
      this.imageOwners = imageOwners
  }

  private String cloudUri( String servicePath ) {
    URI.create( "http://" + host + ":8773/" )
        .resolve( servicePath )
        .toString()
  }

  private AmazonEC2 getEC2Client( final AWSCredentialsProvider credentials ) {
    final AmazonEC2 ec2 = new AmazonEC2Client( credentials )
    if ( host ) {
      ec2.setEndpoint( cloudUri("/services/compute") )
    } else {
      ec2.setRegion( com.amazonaws.regions.Region.getRegion( Regions.US_WEST_1 ) )
    }
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
  public void test( ) throws Exception {
    final AmazonEC2 ec2 = getEC2Client( credentials )

    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      ec2.with{
        // Find an image to use
        final String imageId = ec2.describeImages( new DescribeImagesRequest(
            owners: imageOwners,
            filters: [
                new Filter( name: "image-type", values: ["machine"] ),
                new Filter( name: "root-device-type", values: ["instance-store"] ),
                new Filter( name: "is-public", values: ["true"] ),
                new Filter( name: "virtualization-type", values: ["hvm"] ),
            ]
        ) ).with {
          images?.getAt( 0 )?.with {
            imageId
          }
        }
        assertThat( imageId != null , "Image not found)" )
        print( "Using image: ${imageId}" )

        // Discover SSH key
        final String keyName = ec2.describeKeyPairs().with {
          keyPairs?.getAt(0)?.keyName
        }
        print( "Using key pair: " + keyName );

        print( 'Creating VPC' )
        String vpcId = createVpc( new CreateVpcRequest( cidrBlock: '172.30.0.0/24' ) ).with {
          vpc?.vpcId
        }
        print( "Created VPC with id ${vpcId}" )
        cleanupTasks.add{
          print( "Deleting VPC ${vpcId}" )
          deleteVpc( new DeleteVpcRequest( vpcId: vpcId ) )
        }

        print( "Creating subnet in vpc ${vpcId}" )
        String subnetId = createSubnet( new CreateSubnetRequest( vpcId: vpcId, cidrBlock: '172.30.0.0/24' ) ).with {
          subnet?.subnetId
        }
        print( "Created subnet with id ${subnetId}" )
        cleanupTasks.add{
          print( "Deleting subnet ${subnetId}" )
          deleteSubnet( new DeleteSubnetRequest( subnetId: subnetId ) )
        }

        print( "Creating security group in VPC ${vpcId}" )
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

        print( "Creating security group in VPC ${vpcId}" )
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

        [ securityGroupId1, securityGroupId2 ].each { String groupId ->
          print( "Authorizing tcp:22 ingress for security group ${groupId} in VPC ${vpcId}" )
          authorizeSecurityGroupIngress( new AuthorizeSecurityGroupIngressRequest(
              groupId: groupId,
              ipPermissions: [
                  new IpPermission(
                      ipProtocol: 'tcp',
                      fromPort: 22,
                      toPort: 22,
                      ipRanges: ['0.0.0.0/0' ]
                  )
              ]
          ))
        }

        print( "Running instance with invalid parameters (dupe security groups)" )
        try {
          String instanceId = runInstances(new RunInstancesRequest(
              minCount: 1,
              maxCount: 1,
              instanceType: 'm1.small',
              imageId: imageId,
              securityGroupIds: [securityGroupId1],
              networkInterfaces: [
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 0,
                      groups: [securityGroupId1],
                      subnetId: subnetId
                  )
              ]
          )).with {
            reservation?.instances?.getAt(0)?.instanceId
          }

          print( "Launched instance ${instanceId} (terminating)" )
          terminateInstances( new TerminateInstancesRequest(instanceIds: [instanceId ] ))
          assertThat( false, "Expected instance launch failure")
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          assertThat( 'InvalidParameterCombination' == e.errorCode, "Expected InvalidParameterCombination error code, but was: ${e.errorCode}" )
        }

        print( "Running instance with invalid parameters (dupe subnetId)" )
        try {
          String instanceId = runInstances(new RunInstancesRequest(
              minCount: 1,
              maxCount: 1,
              instanceType: 'm1.small',
              imageId: imageId,
              subnetId: subnetId,
              networkInterfaces: [
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 0,
                      groups: [securityGroupId1],
                      subnetId: subnetId
                  )
              ]
          )).with {
            reservation?.instances?.getAt(0)?.instanceId
          }

          print( "Launched instance ${instanceId} (terminating)" )
          terminateInstances( new TerminateInstancesRequest(instanceIds: [instanceId ] ))
          assertThat( false, "Expected instance launch failure")
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          assertThat( 'InvalidParameterCombination' == e.errorCode, "Expected InvalidParameterCombination error code, but was: ${e.errorCode}" )
        }

        print( "Running instance with invalid parameters (dupe private IP)" )
        try {
          String instanceId = runInstances(new RunInstancesRequest(
              minCount: 1,
              maxCount: 1,
              instanceType: 'm1.small',
              imageId: imageId,
              privateIpAddress: '172.30.0.10',
              networkInterfaces: [
                  new InstanceNetworkInterfaceSpecification(
                      deviceIndex: 0,
                      groups: [securityGroupId1],
                      privateIpAddress: '172.30.0.10',
                      subnetId: subnetId
                  )
              ]
          )).with {
            reservation?.instances?.getAt(0)?.instanceId
          }

          print( "Launched instance ${instanceId} (terminating)" )
          terminateInstances( new TerminateInstancesRequest(instanceIds: [instanceId ] ))
          assertThat( false, "Expected instance launch failure")
        } catch ( AmazonServiceException e ) {
          print( e.toString( ) )
          assertThat( 'InvalidParameterCombination' == e.errorCode, "Expected InvalidParameterCombination error code, but was: ${e.errorCode}" )
        }

        print( "Running instance in vpc ${vpcId} with group ${securityGroupId1}" )
        String networkInterfaceId = null
        String instanceId = runInstances(new RunInstancesRequest(
            minCount: 1,
            maxCount: 1,
            instanceType: 'm1.small',
            imageId: imageId,
            networkInterfaces: [
                new InstanceNetworkInterfaceSpecification(
                    deviceIndex: 0,
                    groups: [ securityGroupId1 ],
                    subnetId: subnetId
                )
            ]
        )).with {
          reservation?.instances?.getAt(0)?.with{
            cleanupTasks.add{
              print( "Terminating instance ${instanceId}" )
              terminateInstances( new TerminateInstancesRequest(instanceIds: [instanceId ] ))

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

            List<String> instanceGroupIds = securityGroups.collect{ GroupIdentifier gid -> gid.groupId } as List<String>
            assertThat( [ securityGroupId1 ] == instanceGroupIds,
                "Expected security groups [ ${securityGroupId1} ], but was: ${instanceGroupIds}" )

            List<String> interfaceGroupIds = networkInterfaces.find{ InstanceNetworkInterface ini -> ini.attachment.deviceIndex == 0 }?.groups?.collect{ GroupIdentifier gid -> gid.groupId } as List<String>
            assertThat( [ securityGroupId1 ] == interfaceGroupIds,
                "Expected security groups [ ${securityGroupId1} ], but was: ${interfaceGroupIds}" )

            networkInterfaceId = networkInterfaces.find{ InstanceNetworkInterface ini -> ini.attachment.deviceIndex == 0 }?.networkInterfaceId

            instanceId
          }
        }
        print( "Launched instance ${instanceId} with eni ${networkInterfaceId}" )

        print( "Verifying security groups for ENI ${networkInterfaceId}" )
        describeNetworkInterfaces( new DescribeNetworkInterfacesRequest(
            networkInterfaceIds: [ networkInterfaceId ]
        ) ).with {
          networkInterfaces?.getAt( 0 )?.with {
            List<String> interfaceGroupIds = groups?.collect{ GroupIdentifier gid -> gid.groupId } as List<String>
            assertThat( [ securityGroupId1 ] == interfaceGroupIds,
                "Expected security groups [ ${securityGroupId1} ], but was: ${interfaceGroupIds}" )
          }
        }

        print( "Modifying instance ${instanceId} security group attribute" )
        modifyInstanceAttribute( new ModifyInstanceAttributeRequest(
            instanceId: instanceId,
            groups: [
              securityGroupId2
            ]
        ) )

        print( "Verifying modified security groups for instance ${instanceId}" )
        describeInstances( new DescribeInstancesRequest(
          instanceIds: [ instanceId ]
        ) ).with {
          reservations?.getAt( 0 )?.instances?.getAt( 0 )?.with {
            List<String> instanceGroupIds = securityGroups.collect{ GroupIdentifier gid -> gid.groupId } as List<String>
            assertThat( [ securityGroupId2 ] == instanceGroupIds,
                "Expected security groups [ ${securityGroupId2} ], but was: ${instanceGroupIds}" )

            List<String> interfaceGroupIds = networkInterfaces.find{ InstanceNetworkInterface ini -> ini.attachment.deviceIndex == 0 }?.groups?.collect{ GroupIdentifier gid -> gid.groupId } as List<String>
            assertThat( [ securityGroupId2 ] == interfaceGroupIds,
                "Expected security groups [ ${securityGroupId2} ], but was: ${interfaceGroupIds}" )
          }
        }

        print( "Verifying modified security groups for ENI ${networkInterfaceId}" )
        describeNetworkInterfaces( new DescribeNetworkInterfacesRequest(
            networkInterfaceIds: [ networkInterfaceId ]
        ) ).with {
          networkInterfaces?.getAt( 0 )?.with {
            List<String> interfaceGroupIds = groups?.collect{ GroupIdentifier gid -> gid.groupId } as List<String>
            assertThat( [ securityGroupId2 ] == interfaceGroupIds,
                "Expected security groups [ ${securityGroupId2} ], but was: ${interfaceGroupIds}" )
          }
        }

        print( "Modifying network interface ${networkInterfaceId} security group attribute" )
        modifyNetworkInterfaceAttribute( new ModifyNetworkInterfaceAttributeRequest(
            networkInterfaceId: networkInterfaceId,
            groups: [
                securityGroupId1, securityGroupId2
            ]
        ) )

        print( "Verifying modified security groups for instance ${instanceId}" )
        describeInstances( new DescribeInstancesRequest(
            instanceIds: [ instanceId ]
        ) ).with {
          reservations?.getAt( 0 )?.instances?.getAt( 0 )?.with {
            Set<String> instanceGroupIds = securityGroups.collect{ GroupIdentifier gid -> gid.groupId } as Set<String>
            assertThat( [ securityGroupId1, securityGroupId2 ] as Set<String> == instanceGroupIds,
                "Expected security groups [ ${securityGroupId1}, ${securityGroupId2} ], but was: ${instanceGroupIds}" )

            Set<String> interfaceGroupIds = networkInterfaces.find{ InstanceNetworkInterface ini -> ini.attachment.deviceIndex == 0 }?.groups?.collect{ GroupIdentifier gid -> gid.groupId } as Set<String>
            assertThat( [ securityGroupId1, securityGroupId2 ] as Set<String> == interfaceGroupIds,
                "Expected security groups [ ${securityGroupId1}, ${securityGroupId2} ], but was: ${interfaceGroupIds}" )
          }
        }

        print( "Verifying modified security groups for ENI ${networkInterfaceId}" )
        describeNetworkInterfaces( new DescribeNetworkInterfacesRequest(
            networkInterfaceIds: [ networkInterfaceId ]
        ) ).with {
          networkInterfaces?.getAt( 0 )?.with {
            Set<String> interfaceGroupIds = groups?.collect{ GroupIdentifier gid -> gid.groupId } as Set<String>
            assertThat( [ securityGroupId1, securityGroupId2 ] as Set<String> == interfaceGroupIds,
                "Expected security groups [ ${securityGroupId1}, ${securityGroupId2} ], but was: ${interfaceGroupIds}" )
          }
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
