package com.eucalyptus.tests.awssdk

import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.regions.Region
import com.amazonaws.regions.Regions
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.AuthorizeSecurityGroupIngressRequest
import com.amazonaws.services.ec2.model.CreateSecurityGroupRequest
import com.amazonaws.services.ec2.model.DeleteSecurityGroupRequest
import com.amazonaws.services.ec2.model.DescribeAvailabilityZonesResult
import com.amazonaws.services.ec2.model.DescribeImagesRequest
import com.amazonaws.services.ec2.model.DescribeInstancesRequest
import com.amazonaws.services.ec2.model.Filter
import com.amazonaws.services.ec2.model.IpPermission
import com.amazonaws.services.ec2.model.RunInstancesRequest
import com.amazonaws.services.ec2.model.TerminateInstancesRequest
import com.amazonaws.services.ec2.model.UserIdGroupPair
import com.amazonaws.services.elasticloadbalancing.AmazonElasticLoadBalancing
import com.amazonaws.services.elasticloadbalancing.AmazonElasticLoadBalancingClient
import com.amazonaws.services.elasticloadbalancing.model.*
import java.nio.charset.StandardCharsets
import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit;
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP;
import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY;
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY;

/**
 *
 */
class TestELBEC2Classic {

  private final String host;
  private final AWSCredentialsProvider credentials;

  public static void main( String[] args ) throws Exception {
    new TestELBEC2Classic( ).ELBEC2ClassicTest( )
  }

  public TestELBEC2Classic( ) {
    minimalInit()
    this.host=HOST_IP
    this.credentials = new StaticCredentialsProvider( new BasicAWSCredentials( ACCESS_KEY, SECRET_KEY ) )
  }

  private String cloudUri( String servicePath ) {
    URI.create( "http://" + host + ":8773/" )
        .resolve( servicePath )
        .toString()
  }

  private AmazonEC2 getEC2Client( final AWSCredentialsProvider credentials ) {
    final AmazonEC2 ec2 = new AmazonEC2Client( credentials )
    if ( host ) {
      ec2.setEndpoint( cloudUri( "/services/compute" ) )
    } else {
      ec2.setRegion(Region.getRegion( Regions.US_WEST_1 ) )
    }
    ec2
  }

  private AmazonElasticLoadBalancing getELBClient( final AWSCredentialsProvider credentials ) {
    final AmazonElasticLoadBalancing elb = new AmazonElasticLoadBalancingClient( credentials )
    if ( host ) {
      elb.setEndpoint( cloudUri( "/services/LoadBalancing" ) )
    } else {
      elb.setRegion(Region.getRegion( Regions.US_WEST_1 ) )
    }
    elb
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
  public void ELBEC2ClassicTest( ) throws Exception {
    final AmazonEC2 ec2 = getEC2Client( credentials )

    // Find an AZ to use
    final DescribeAvailabilityZonesResult azResult = ec2.describeAvailabilityZones();

    assertThat( azResult.getAvailabilityZones().size() > 0, "Availability zone not found" );

    final String availabilityZone = azResult.getAvailabilityZones().get( 0 ).getZoneName();
    print( "Using availability zone: " + availabilityZone );

    final String availabilityZone2 = azResult.getAvailabilityZones().getAt( 1 )?.getZoneName( );

    final String namePrefix = UUID.randomUUID().toString().substring(0, 13) + "-";
    print( "Using resource prefix for test: " + namePrefix );

    final AmazonElasticLoadBalancing elb = getELBClient( credentials )
    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      elb.with {
        String loadBalancerName = "${namePrefix}balancer1"
        print( "Creating load balancer: ${loadBalancerName}" )
        createLoadBalancer( new CreateLoadBalancerRequest(
            loadBalancerName: loadBalancerName,
            listeners: [ new Listener(
                loadBalancerPort: 9999,
                protocol: 'HTTP',
                instancePort: 9999,
                instanceProtocol: 'HTTP'
            ) ],
            availabilityZones: [ availabilityZone ]
        ) )
        cleanupTasks.add {
          print( "Deleting load balancer: ${loadBalancerName}" )
          deleteLoadBalancer( new DeleteLoadBalancerRequest( loadBalancerName: loadBalancerName ) )
        }

        println( "Created load balancer: ${loadBalancerName}" )
        String balancerHost = describeLoadBalancers( new DescribeLoadBalancersRequest( loadBalancerNames: [ loadBalancerName ] ) ).with {
          println( loadBalancerDescriptions.toString( ) )
          assertThat( loadBalancerDescriptions.size( ) == 1, "Expected one load balancer, but was: ${loadBalancerDescriptions.size( )}" )
          loadBalancerDescriptions.get( 0 ).with {
            assertThat( loadBalancerName == it.loadBalancerName, "Expected name ${loadBalancerName}, but was: ${it.loadBalancerName}" )
            assertThat( scheme == 'internet-facing', "Expected scheme internet-facing, but was: ${scheme}" )
            assertThat( VPCId == null, "Expected no vpc, but was: ${VPCId}" )
            assertThat( subnets == null || subnets.isEmpty( ), "Expected no subnets, but was: ${subnets}" )
            assertThat( securityGroups == null || securityGroups.isEmpty( ), "Expected no (VPC) security groups, but was: ${securityGroups}" )
            assertThat( availabilityZones == [ availabilityZone ], "Expected zones [ ${availabilityZone} ], but was: ${availabilityZones}" )
            assertThat( sourceSecurityGroup != null, "Expected source security group")
            sourceSecurityGroup.with {
              ec2.with {
                String authGroupName = "${namePrefix}elb-source-group-auth-test"
                println( "Creating security group to test elb source group authorization: ${authGroupName}" )
                String authGroupId = createSecurityGroup( new CreateSecurityGroupRequest(
                    groupName: authGroupName,
                    description: 'Test security group for validation of ELB source group authorization'
                ) ).with {
                  groupId
                }
                println( "Created security group ${authGroupName}, with id ${authGroupId}" )
                cleanupTasks.add{
                  println( "Deleting security group: ${authGroupName}/${authGroupId}" )
                  deleteSecurityGroup( new DeleteSecurityGroupRequest(
                      groupId: authGroupId
                  ) )
                }
                println( "Authorizing elb source group ${ownerAlias}/${groupName} for ${authGroupName}/${authGroupId}" )
                authorizeSecurityGroupIngress( new AuthorizeSecurityGroupIngressRequest(
                  groupId: authGroupId,
                  ipPermissions: [
                      new IpPermission(
                          ipProtocol: 'tcp',
                          fromPort: 9999,
                          toPort: 9999,
                          userIdGroupPairs: [
                              new UserIdGroupPair(
                                  userId: ownerAlias,
                                  groupName: groupName
                              )
                          ]
                      )
                  ]
                ))
              }
            }
            DNSName
          }
        }

        // test running an instance with an HTTP service
        if ( host ) ec2.with{
          // Find an image to use
          final String imageId = describeImages( new DescribeImagesRequest(
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
          final String keyName = describeKeyPairs( ).with {
            keyPairs?.getAt(0)?.keyName
          }
          print( "Using key pair: " + keyName )

          String instanceSecurityGroup = "${namePrefix}instance-group"
          print( "Creating security group with name: ${instanceSecurityGroup}" )
          String instanceGroupId = createSecurityGroup( new CreateSecurityGroupRequest(
            groupName: instanceSecurityGroup,
            description: 'Test security group for instances'
          ) ).with {
            groupId
          }

          println( "Authorizing instance security group ${instanceSecurityGroup}/${instanceGroupId}" )
          authorizeSecurityGroupIngress( new AuthorizeSecurityGroupIngressRequest(
              groupId: instanceGroupId,
              ipPermissions: [
                  new IpPermission(
                      ipProtocol: 'tcp',
                      fromPort: 22,
                      toPort: 22,
                      ipRanges: [ '0.0.0.0/0' ]
                  ),
                  new IpPermission(
                      ipProtocol: 'tcp',
                      fromPort: 9999,
                      toPort: 9999,
                      ipRanges: [ '0.0.0.0/0' ]
                  ),
              ]
          ))

          String userDataText = '''
          #!/usr/bin/python -tt
          import SimpleHTTPServer, BaseHTTPServer

          class StaticHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
            def do_GET(self):
              self.send_response( 200 )
              self.send_header('Content-Type', 'text/plain; charset=utf-8')
              self.end_headers( )
              self.wfile.write("Hello");
              self.wfile.close( );

          BaseHTTPServer.HTTPServer( ("", 9999), StaticHandler ).serve_forever( )
          '''.stripIndent( ).trim( )

          print( "Running instance to access via load balancer ${loadBalancerName}" )
          String instanceId = runInstances( new RunInstancesRequest(
              minCount: 1,
              maxCount: 1,
              imageId: imageId,
              keyName: keyName,
              securityGroupIds: [ instanceGroupId ],
              userData: Base64.encodeAsString( userDataText.getBytes( StandardCharsets.UTF_8 ) )
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

          String instancePublicIp;
          print( "Waiting for instance ${instanceId} to start" )
          ( 1..25 ).find{
            sleep 5000
            print( "Waiting for instance ${instanceId} to start, waited ${it*5}s" )
            describeInstances( new DescribeInstancesRequest(
                instanceIds: [ instanceId ],
                filters: [ new Filter( name: "instance-state-name", values: [ "running" ] ) ]
            ) ).with {
              instancePublicIp = reservations?.getAt( 0 )?.instances?.getAt( 0 )?.publicIpAddress
              reservations?.getAt( 0 )?.instances?.getAt( 0 )?.instanceId == instanceId
            }
          }
          assertThat( instancePublicIp != null, "Expected instance public ip" )

          print( "Registering instance ${instanceId} with load balancer ${loadBalancerName}" )
          registerInstancesWithLoadBalancer( new RegisterInstancesWithLoadBalancerRequest(
            loadBalancerName: loadBalancerName,
            instances: [ new Instance( instanceId ) ]
          ) )

          print( "Waiting for instance ${instanceId} to be healthy" )
          ( 1..50 ).find{
            sleep 5000
            print( "Waiting for instance ${instanceId} to be healthy, waited ${it*5}s" )
            describeInstanceHealth( new DescribeInstanceHealthRequest(
                loadBalancerName: loadBalancerName,
                instances: [ new Instance( instanceId ) ]
            ) ).with {
              'InService' == instanceStates?.getAt( 0 )?.state
            }
          }

          String instanceUrl = "http://${instancePublicIp}:9999/"
          print( "Accessing instance ${instanceUrl}" )
          String instanceResponse = new URL( instanceUrl ).
              getText( connectTimeout: 10000, readTimeout: 10000, useCaches: false, allowUserInteraction: false )
          assertThat( 'Hello' == instanceResponse, "Expected instance response Hello, but was: ${instanceResponse}" )

          String balancerUrl = "http://${balancerHost}:9999/"
          print( "Accessing instance via load balancer ${balancerUrl}" )
          String balancerResponse = new URL( balancerUrl ).
              getText( connectTimeout: 10000, readTimeout: 10000, useCaches: false, allowUserInteraction: false )
          assertThat( 'Hello' == balancerResponse, "Expected balancer response Hello, but was: ${balancerResponse}" )
        } else {
          print( "Skipping running instance test" )
        }

        // test changing zones
        if ( availabilityZone2 ) {
          println( "Enabling availability zone for balancer ${loadBalancerName}" )
          enableAvailabilityZonesForLoadBalancer( new EnableAvailabilityZonesForLoadBalancerRequest(
            loadBalancerName: loadBalancerName,
            availabilityZones: [ availabilityZone2 ]
          ) ).with {
            println( "Availability zones now ${availabilityZones}" )
          }
          println( describeLoadBalancers( ).toString( ) )
        } else {
          println( 'Only one zone found, skipping multi-zone test' )
        }
      }

      print( "Test complete" )
    } finally {
      // Attempt to clean up anything we created
      cleanupTasks.reverseEach { Runnable cleanupTask ->
        try {
          cleanupTask.run()
        } catch ( Exception e ) {
          e.printStackTrace()
        }
      }
    }
  }
}
