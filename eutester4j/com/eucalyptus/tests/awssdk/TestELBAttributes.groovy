package com.eucalyptus.tests.awssdk

import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.regions.Region
import com.amazonaws.regions.Regions
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.*
import com.amazonaws.services.elasticloadbalancing.AmazonElasticLoadBalancing
import com.amazonaws.services.elasticloadbalancing.AmazonElasticLoadBalancingClient
import com.amazonaws.services.elasticloadbalancing.model.ConnectionSettings
import com.amazonaws.services.elasticloadbalancing.model.CreateLoadBalancerRequest
import com.amazonaws.services.elasticloadbalancing.model.DeleteLoadBalancerRequest
import com.amazonaws.services.elasticloadbalancing.model.DescribeLoadBalancerAttributesRequest
import com.amazonaws.services.elasticloadbalancing.model.DescribeLoadBalancersResult
import com.amazonaws.services.elasticloadbalancing.model.Listener
import com.amazonaws.services.elasticloadbalancing.model.LoadBalancerAttributes
import com.amazonaws.services.elasticloadbalancing.model.ModifyLoadBalancerAttributesRequest

import org.testng.annotations.Test

import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP;
import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit;
import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY;
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY;

/**
 *
 */
class TestELBAttributes {

  private final String host;
  private final AWSCredentialsProvider credentials;

  public static void main( String[] args ) throws Exception {
    new TestELBAttributes( ).ELBAttributesTest( )
  }

  public TestELBAttributes(){
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
  public void ELBAttributesTest( ) throws Exception {
    final AmazonEC2 ec2 = getEC2Client( credentials )

    // Find an AZ to use
    final DescribeAvailabilityZonesResult azResult = ec2.describeAvailabilityZones();

    assertThat( azResult.getAvailabilityZones().size() > 0, "Availability zone not found" );

    final String availabilityZone = azResult.getAvailabilityZones().get( 0 ).getZoneName();
    print( "Using availability zone: " + availabilityZone );

    final String namePrefix = UUID.randomUUID().toString().substring(0, 13) + "-";
    print( "Using resource prefix for test: " + namePrefix );

    final AmazonElasticLoadBalancing elb = getELBClient( credentials )
    final List<Runnable> cleanupTasks = [] as List<Runnable>
    try {
      elb.with {
        String loadBalancerName = "${namePrefix}-balancer1"
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
        final DescribeLoadBalancersResult loadBalancersResult = describeLoadBalancers( )
        println( loadBalancersResult.toString( ) )

        println( "Describing load balancer attributes" )
        describeLoadBalancerAttributes( new DescribeLoadBalancerAttributesRequest(
          loadBalancerName: loadBalancerName
        ) ).with {
          println( loadBalancerAttributes.toString( ) )
          loadBalancerAttributes.with {
            connectionSettings.with {
              assertThat( 60 == idleTimeout, "Expected default idle timeout 60, but was: ${idleTimeout}" )
            }
          }
        }

        println( "Modifying load balancer attributes" )
        modifyLoadBalancerAttributes( new ModifyLoadBalancerAttributesRequest(
          loadBalancerName: loadBalancerName,
          loadBalancerAttributes: new LoadBalancerAttributes(
            connectionSettings: new ConnectionSettings(
              idleTimeout: 1000
            )
          )
        )).with {
          loadBalancerAttributes.with {
            connectionSettings.with {
              assertThat( 1000 == idleTimeout, "Expected idle timeout 1000, but was: ${idleTimeout}" )
            }
          }
        }

        println( "Describing load balancer attributes" )
        describeLoadBalancerAttributes( new DescribeLoadBalancerAttributesRequest(
            loadBalancerName: loadBalancerName
        ) ).with {
          println( loadBalancerAttributes.toString( ) )
          loadBalancerAttributes.with {
            connectionSettings.with {
              assertThat( 1000 == idleTimeout, "Expected idle timeout 1000, but was: ${idleTimeout}" )
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
          e.printStackTrace()
        }
      }
    }
  }
}
