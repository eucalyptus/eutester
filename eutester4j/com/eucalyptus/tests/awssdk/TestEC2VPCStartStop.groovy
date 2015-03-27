package com.eucalyptus.tests.awssdk

import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.*
import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit

/**
 * This application tests VPC start/stop for ebs instances in a VPC.
 *
 * This is verification for the story:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-9824
 */
class TestEC2VPCStartStop {

  private final String host
  private final AWSCredentialsProvider credentials
  private final String cidrPrefix = '172.26.64'

  public static void main( String[] args ) throws Exception {
    new TestEC2VPCStartStop( ).EC2VPCStartStopTest( )
  }

  public TestEC2VPCStartStop( ) {
    minimalInit()
    this.host = HOST_IP
    this.credentials = new StaticCredentialsProvider( new BasicAWSCredentials( ACCESS_KEY, SECRET_KEY ) )
  }

  private String cloudUri( String servicePath ) {
    URI.create( "http://" + host + ":8773/" )
        .resolve( servicePath )
        .toString()
  }

  private AmazonEC2 getEC2Client( final AWSCredentialsProvider credentials ) {
    final AmazonEC2 ec2 = new AmazonEC2Client( credentials )
    ec2.setEndpoint( cloudUri( "/services/compute" ) )
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
  public void EC2VPCStartStopTest( ) throws Exception {
    final AmazonEC2 ec2 = getEC2Client( credentials )

    // Find an image to use
    final String imageId = ec2.describeImages( new DescribeImagesRequest(
        filters: [
            new Filter( name: "image-type", values: ["machine"] ),
            new Filter( name: "root-device-type", values: ["ebs"] ),
        ]
    ) ).with {
      images?.getAt( 0 )?.imageId
    }
    assertThat( imageId != null , "Image not found (ebs)" )
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

        print( "Allocating address" )
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

        print( "Running instance in subnet ${subnetId}" )
        String expectedPrivateIp = "${cidrPrefix}.100"
        String instanceId = runInstances( new RunInstancesRequest(
            minCount: 1,
            maxCount: 1,
            imageId: imageId,
            keyName: keyName,
            subnetId: subnetId,
            privateIpAddress: expectedPrivateIp
        )).with {
          reservation?.with {
            instances?.getAt( 0 )?.with{
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

        print( "Describing instance ${instanceId} to get ENI identifier" )
        String networkInterfaceId = describeInstances( new DescribeInstancesRequest(
            instanceIds: [ instanceId ]
        ) ).with {
          reservations?.getAt( 0 )?.instances?.getAt( 0 )?.networkInterfaces?.getAt( 0 )?.with{
            networkInterfaceId
          }
        }

        print( "Associating IP ${allocationPublicIp} with instance ${instanceId} network interface ${networkInterfaceId}" )
        associateAddress( new AssociateAddressRequest(
            allocationId: allocationId,
            networkInterfaceId: networkInterfaceId
        ) )

        print( "Verifying instance details" )
        describeInstances( new DescribeInstancesRequest(
            instanceIds: [ instanceId ]
        ) ).with {
          reservations?.getAt( 0 )?.instances?.getAt( 0 )?.with {
            assertThat( instanceId == it.instanceId, "Expected instance id ${instanceId}, but was: ${it.instanceId}" )
            networkInterfaces?.getAt( 0 )?.with {
              assertThat( networkInterfaceId == it.networkInterfaceId, "Expected network interface id ${networkInterfaceId}, but was: ${it.networkInterfaceId}" )
            }
            assertThat( expectedPrivateIp == privateIpAddress, "Expected private IP ${expectedPrivateIp}, but was: ${privateIpAddress}" )
            assertThat( allocationPublicIp == publicIpAddress, "Expected public IP ${allocationPublicIp}, but was: ${publicIpAddress}" )
          }
        }

        print( "Stopping instance ${instanceId}" )
        stopInstances( new StopInstancesRequest( instanceIds: [ instanceId ] ) )

        print( "Waiting for instance ${instanceId} to stop" )
        ( 1..25 ).find{
          sleep 5000
          print( "Waiting for instance ${instanceId} to stop, waited ${it*5}s" )
          describeInstances( new DescribeInstancesRequest(
              instanceIds: [ instanceId ],
              filters: [ new Filter( name: "instance-state-name", values: [ "stopped" ] ) ]
          ) ).with {
            reservations?.getAt( 0 )?.instances?.getAt( 0 )?.instanceId == instanceId
          }
        }

        print( "Starting instance ${instanceId}" )
        startInstances( new StartInstancesRequest( instanceIds: [ instanceId ] ) )

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

        print( "Verifying instance details" )
        describeInstances( new DescribeInstancesRequest(
            instanceIds: [ instanceId ]
        ) ).with {
          reservations?.getAt( 0 )?.instances?.getAt( 0 )?.with {
            assertThat( instanceId == it.instanceId, "Expected instance id ${instanceId}, but was: ${it.instanceId}" )
            networkInterfaces?.getAt( 0 )?.with {
              assertThat( networkInterfaceId == it.networkInterfaceId, "Expected network interface id ${networkInterfaceId}, but was: ${it.networkInterfaceId}" )
            }
            assertThat( expectedPrivateIp == privateIpAddress, "Expected private IP ${expectedPrivateIp}, but was: ${privateIpAddress}" )
            assertThat( allocationPublicIp == publicIpAddress, "Expected public IP ${allocationPublicIp}, but was: ${publicIpAddress}" )
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
