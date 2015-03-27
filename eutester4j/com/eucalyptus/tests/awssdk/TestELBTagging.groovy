package com.eucalyptus.tests.awssdk

import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.regions.Region
import com.amazonaws.regions.Regions
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.ec2.model.DescribeAvailabilityZonesResult
import com.amazonaws.services.elasticloadbalancing.AmazonElasticLoadBalancing
import com.amazonaws.services.elasticloadbalancing.AmazonElasticLoadBalancingClient
import com.amazonaws.services.elasticloadbalancing.model.AddTagsRequest
import com.amazonaws.services.elasticloadbalancing.model.CreateLoadBalancerRequest
import com.amazonaws.services.elasticloadbalancing.model.DeleteLoadBalancerRequest
import com.amazonaws.services.elasticloadbalancing.model.DescribeLoadBalancersRequest
import com.amazonaws.services.elasticloadbalancing.model.DescribeLoadBalancersResult
import com.amazonaws.services.elasticloadbalancing.model.DescribeTagsRequest
import com.amazonaws.services.elasticloadbalancing.model.Listener
import com.amazonaws.services.elasticloadbalancing.model.RemoveTagsRequest
import com.amazonaws.services.elasticloadbalancing.model.Tag
import com.amazonaws.services.elasticloadbalancing.model.TagKeyOnly

import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit

/**
 *
 */
class TestELBTagging {

  private final String host;
  private final AWSCredentialsProvider credentials;

  public static void main( String[] args ) throws Exception {
    new TestELBTagging( ).ELBTaggingTest( )
  }

  public TestELBTagging( ) {
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
  public void ELBTaggingTest( ) throws Exception {
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
            availabilityZones: [ availabilityZone ],
            tags: [
                new Tag( key: 'one', value: '1' ),
                new Tag( key: 'two', value: '2' ),
                new Tag( key: 'three', value: '3' ),
            ]
        ) )
        cleanupTasks.add {
          print( "Deleting load balancer: ${loadBalancerName}" )
          deleteLoadBalancer( new DeleteLoadBalancerRequest( loadBalancerName: loadBalancerName ) )
        }

        println( "Created load balancer: ${loadBalancerName}" )
        describeLoadBalancers( new DescribeLoadBalancersRequest(
          loadBalancerNames: [ loadBalancerName ]
        ) ).with {
          println( loadBalancerDescriptions.toString( ) )
        }

        print( "Describing tags for load balancer: ${loadBalancerName}" )
        describeTags( new DescribeTagsRequest( loadBalancerNames: [ loadBalancerName ] ) ).with {
          println( tagDescriptions.toString( ) )
          assertThat( tagDescriptions.size( ) == 1, "Expected one load balancer, but was: ${tagDescriptions.size( )}" )
          tagDescriptions.get( 0 ).with {
            assertThat( loadBalancerName == getLoadBalancerName( ), "Unexpected load balancer name: ${getLoadBalancerName( )}" )
            assertThat( tags.size( ) == 3, "Expected three tags, but was: ${tags.size( )}")
          }
        }

        print( "Adding tags for load balancer: ${loadBalancerName}" )
        addTags( new AddTagsRequest(
          loadBalancerNames: [ loadBalancerName ],
          tags: [
              new Tag( key: 'four', value: '4' ),
              new Tag( key: 'five', value: '5' ),
          ]
        ))

        print( "Describing tags for load balancer: ${loadBalancerName}" )
        describeTags( new DescribeTagsRequest( loadBalancerNames: [ loadBalancerName ] ) ).with {
          println( tagDescriptions.toString( ) )
          assertThat( tagDescriptions.size( ) == 1, "Expected one load balancer, but was: ${tagDescriptions.size( )}" )
          tagDescriptions.get( 0 ).with {
            assertThat( loadBalancerName == getLoadBalancerName( ), "Unexpected load balancer name: ${getLoadBalancerName( )}" )
            assertThat( tags.size( ) == 5, "Expected five tags, but was: ${tags.size( )}")
          }
        }

        print( "Removing tags for load balancer: ${loadBalancerName}" )
        removeTags( new RemoveTagsRequest(
            loadBalancerNames: [ loadBalancerName ],
            tags: [
                new TagKeyOnly( key: 'one' ),
                new TagKeyOnly( key: 'three' ),
                new TagKeyOnly( key: 'five' ),
            ]
        ))

        print( "Describing tags for load balancer: ${loadBalancerName}" )
        describeTags( new DescribeTagsRequest( loadBalancerNames: [ loadBalancerName ] ) ).with {
          println( tagDescriptions.toString( ) )
          assertThat( tagDescriptions.size( ) == 1, "Expected one load balancer, but was: ${tagDescriptions.size( )}" )
          tagDescriptions.get( 0 ).with {
            assertThat( loadBalancerName == getLoadBalancerName( ), "Unexpected load balancer name: ${getLoadBalancerName( )}" )
            assertThat( tags.size( ) == 2, "Expected two tags, but was: ${tags.size( )}")
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
