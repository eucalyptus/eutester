package com.eucalyptus.tests.awssdk

import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.*

import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.EC2_ENDPOINT
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit

/**
 * This application tests DNS names for EC2 VPC instances / enis.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9826
 */
class TestEC2VPCDnsNames {

  private final AWSCredentialsProvider credentials

  public static void main( String[] args ) throws Exception {
    new TestEC2VPCDnsNames( ).EC2VPCDnsNamesTest( )
  }

  public TestEC2VPCDnsNames( ) {
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
  public void EC2VPCDnsNamesTest( ) throws Exception {
    final AmazonEC2Client ec2 = getEC2Client( credentials )

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

    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      Map<String,Boolean> vpcIdToDnsHostnamesEnabled = [:]
      Set<String> instanceIds = []
      [ true, false ].each { boolean enableDnsHostnames ->
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

          print( "Verifying initial attributes for VPC ${vpcId}" )
          String expectedVpcId = vpcId
          describeVpcAttribute( new DescribeVpcAttributeRequest( vpcId: vpcId, attribute: 'enableDnsSupport'  ) ).with {
            assertThat( vpcId == expectedVpcId, "Expected VPC id ${expectedVpcId}, but was: ${vpcId}" )
            assertThat( enableDnsSupport, "Expected enableDnsSupport" )
          }
          describeVpcAttribute( new DescribeVpcAttributeRequest( vpcId: vpcId, attribute: 'enableDnsHostnames'  ) ).with {
            assertThat( vpcId == expectedVpcId, "Expected VPC id ${expectedVpcId}, but was: ${vpcId}" )
            assertThat( !it.enableDnsHostnames, "Expected !enableDnsHostnames" )
          }

          if ( enableDnsHostnames ) {
            print( "Modifying vpc attribute enableDnsHostnames ${vpcId}" )
            modifyVpcAttribute( new ModifyVpcAttributeRequest( vpcId: vpcId, enableDnsHostnames: true ) )

            print( "Verifying updated attribute for VPC ${vpcId}" )
            describeVpcAttribute( new DescribeVpcAttributeRequest( vpcId: vpcId, attribute: 'enableDnsHostnames'  ) ).with {
              assertThat( vpcId == expectedVpcId, "Expected VPC id ${expectedVpcId}, but was: ${vpcId}" )
              assertThat( enableDnsHostnames, "Expected enableDnsHostnames" )
            }
          }

          print( "Running instance in subnet ${subnetId}" )
          String instanceId = runInstances( new RunInstancesRequest(
              minCount: 1,
              maxCount: 1,
              imageId: imageId,
              keyName: keyName,
              networkInterfaces: [
                new InstanceNetworkInterfaceSpecification(
                    deviceIndex: 0,
                    subnetId: subnetId,
                    associatePublicIpAddress: true
                )
              ]

          )).with {
            reservation?.with {
              instances?.getAt( 0 )?.instanceId
            }
          }
          instanceIds << instanceId

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

          vpcIdToDnsHostnamesEnabled.put( vpcId, enableDnsHostnames )
        }
      }

      ec2.with {
        instanceIds.each { String instanceId ->
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

          print( "Verifying host names for ${instanceId}" )
          String eniId = describeInstances( new DescribeInstancesRequest(
              instanceIds: [ instanceId ]
          ) ).with {
            reservations?.getAt( 0 )?.instances?.getAt( 0 )?.with {
              boolean enableDnsHostnames = vpcIdToDnsHostnamesEnabled.get( vpcId ) ?: false
              assertThat( publicIpAddress != null && !publicIpAddress.isEmpty( ), "Expected public IP address" )
              if ( enableDnsHostnames ) {
                assertThat( privateDnsName != null && privateDnsName.contains( privateIpAddress.replace('.','-') )
                    && privateDnsName.contains('internal'), "Invalid private DNS name: ${privateDnsName}" )
                assertThat( publicDnsName != null && publicDnsName.contains( publicIpAddress.replace('.','-') ),
                    "Invalid public DNS name: ${publicDnsName}" )

                networkInterfaces?.getAt( 0 )?.with {
                  assertThat( privateDnsName != null && privateDnsName.contains( privateIpAddress.replace('.','-') )
                      && privateDnsName.contains('internal'), "Invalid ENI private DNS name: ${privateDnsName}" )
                  assertThat( publicDnsName != null && publicDnsName.contains( publicIpAddress.replace('.','-') ),
                      "Invalid ENI public DNS name: ${publicDnsName}" )

                  privateIpAddresses?.getAt( 0 )?.with {
                    assertThat( privateDnsName != null && privateDnsName.contains( privateIpAddress.replace('.','-') )
                        && privateDnsName.contains('internal'), "Invalid ENI private DNS name: ${privateDnsName}" )
                  }

                  association?.with {
                    assertThat( publicDnsName != null && publicDnsName.contains( publicIpAddress.replace('.','-') ),
                        "Invalid ENI public DNS name: ${publicDnsName}" )
                  }
                }
              } else {
                assertThat( privateDnsName == null || privateDnsName.isEmpty( ), "Unexpected private DNS name: ${privateDnsName}" )
                assertThat( publicDnsName == null || publicDnsName.isEmpty( ), "Unexpected public DNS name: ${publicDnsName}" )
                networkInterfaces?.getAt( 0 )?.with {
                  assertThat( privateDnsName == null || privateDnsName.isEmpty( ), "Unexpected ENI private DNS name: ${privateDnsName}" )
                  assertThat( publicDnsName == null || publicDnsName.isEmpty( ), "Unexpected ENI public DNS name: ${publicDnsName}" )
                  privateIpAddresses?.getAt( 0 )?.with {
                    assertThat( privateDnsName == null || privateDnsName.isEmpty( ), "Unexpected ENI private DNS name: ${privateDnsName}" )
                  }
                  association?.with {
                    assertThat( publicDnsName == null || publicDnsName.isEmpty( ), "Unexpected ENI public DNS name: ${publicDnsName}" )
                  }
                }
              }
              networkInterfaces?.getAt( 0 )?.networkInterfaceId
            }
          }

          print( "Verifying host names for ${instanceId} network interface ${eniId}" )
          describeNetworkInterfaces( new DescribeNetworkInterfacesRequest(
            networkInterfaceIds: [ eniId ]
          ) ).with {
            networkInterfaces?.getAt( 0 )?.with {
              boolean enableDnsHostnames = vpcIdToDnsHostnamesEnabled.get(vpcId) ?: false
              if ( enableDnsHostnames ) {
                assertThat(privateDnsName != null && privateDnsName.contains(privateIpAddress.replace('.', '-'))
                    && privateDnsName.contains('internal'), "Invalid private DNS name: ${privateDnsName}")

                privateIpAddresses?.getAt(0)?.with {
                  assertThat(privateDnsName != null && privateDnsName.contains(privateIpAddress.replace('.', '-'))
                      && privateDnsName.contains('internal'), "Invalid private DNS name: ${privateDnsName}")
                }
              } else {
                assertThat( privateDnsName == null || privateDnsName.isEmpty( ), "Unexpected ENI private DNS name: ${privateDnsName}" )
                privateIpAddresses?.getAt(0)?.with {
                  assertThat( privateDnsName == null || privateDnsName.isEmpty( ), "Unexpected ENI private DNS name: ${privateDnsName}" )
                }
              }

              association?.with {
                assertThat( publicIp != null && !publicIp.isEmpty( ), "Expected public IP address" )
              }
            }
          }
        }

        print( "Terminating instances: ${instanceIds}" )
        terminateInstances( new TerminateInstancesRequest( instanceIds: instanceIds ) )
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
