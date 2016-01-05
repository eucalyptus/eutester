package com.eucalyptus.tests.awssdk

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
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.EC2_ENDPOINT

/**
 * This application tests EC2 VPC route functionality.
 *
 * Related JIRA issues:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-10821
 */
class TestEC2VPCRoutes {

  private final AWSCredentialsProvider credentials

  public static void main( String[] args ) throws Exception {
    new TestEC2VPCRoutes().EC2VPCRoutesTest( )
  }

  public TestEC2VPCRoutes( ) {
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
  public void EC2VPCRoutesTest( ) throws Exception {
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

        print( "Creating network interface in subnet ${subnetId}" )
        String networkInterfaceId = createNetworkInterface( new CreateNetworkInterfaceRequest(
            subnetId: subnetId
        ) ).with {
          networkInterface?.networkInterfaceId
        }
        print( "Created network interface ${networkInterfaceId}" )
        cleanupTasks.add{
          print( "Deleting network interface ${networkInterfaceId}" )
          deleteNetworkInterface( new DeleteNetworkInterfaceRequest( networkInterfaceId: networkInterfaceId ) )
        }

        print( "Running instance with specified network interface ${networkInterfaceId}" )
        String instanceId = runInstances( new RunInstancesRequest(
            minCount: 1,
            maxCount: 1,
            imageId: imageId,
            keyName: keyName,
            networkInterfaces: [
                new InstanceNetworkInterfaceSpecification(
                    deviceIndex: 0,
                    deleteOnTermination: true,
                    networkInterfaceId: networkInterfaceId
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

        print( "Creating route table in VPC ${vpcId}" )
        String routeTableId = createRouteTable( new CreateRouteTableRequest(
          vpcId: vpcId
        ) ).with {
          routeTable?.routeTableId
        }
        cleanupTasks.add{
          print( "Deleting route table ${routeTableId}" )
          deleteRouteTable( new DeleteRouteTableRequest( routeTableId: routeTableId ) )
        }
        print( "Created route table ${routeTableId}" )

        print( "Creating route for internet gateway" )
        createRoute( new CreateRouteRequest(
            routeTableId: routeTableId,
            destinationCidrBlock: '0.0.0.0/0',
            gatewayId: internetGatewayId
        ) )

        print( "Creating route for network interface" )
        createRoute( new CreateRouteRequest(
            routeTableId: routeTableId,
            destinationCidrBlock: '1.1.1.1/32',
            networkInterfaceId: networkInterfaceId
        ) )

        print( "Creating route for instance" )
        createRoute( new CreateRouteRequest(
            routeTableId: routeTableId,
            destinationCidrBlock: '1.1.1.2/32',
            instanceId: instanceId
        ) )

        print( "Verifying routes" )
        describeRouteTables( new DescribeRouteTablesRequest(
            routeTableIds: [ routeTableId ]
        ) ).with {
          assertThat( routeTables != null && routeTables.size( ) == 1, "Expected route table" )
          routeTables[0].with {
            assertThat( routes.size( ) == 4, "Expected 4 routes, but was: ${routes.size( )}" )
            routes.each { Route route ->
              switch ( route.destinationCidrBlock ) {
                case '10.10.10.0/24':
                  assertThat( route.gatewayId == 'local', "Expected local destination for ${route.destinationCidrBlock}" )
                  break;
                case '0.0.0.0/0':
                  assertThat( route.gatewayId == internetGatewayId, "Expected ${internetGatewayId} destination for ${route.destinationCidrBlock}" )
                  break;
                case '1.1.1.1/32':
                  assertThat( route.networkInterfaceId == networkInterfaceId, "Expected ${networkInterfaceId} destination for ${route.destinationCidrBlock}" )
                  assertThat( route.instanceId == instanceId, "Expected ${instanceId} destination for ${route.destinationCidrBlock}" )
                  break;
                case '1.1.1.2/32':
                  assertThat( route.networkInterfaceId == networkInterfaceId, "Expected ${networkInterfaceId} destination for ${route.destinationCidrBlock}" )
                  assertThat( route.instanceId == instanceId, "Expected ${instanceId} destination for ${route.destinationCidrBlock}" )
                  break;
              }
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
        } catch ( Exception e ) {
          // Some not-found errors are expected here so may need to be suppressed
          e.printStackTrace()
        }
      }
    }
  }
}
