package com.eucalyptus.tests.awssdk

import com.amazonaws.AmazonServiceException
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
import com.amazonaws.services.elasticloadbalancing.model.*
import com.amazonaws.services.identitymanagement.AmazonIdentityManagement
import com.amazonaws.services.identitymanagement.AmazonIdentityManagementClient
import com.amazonaws.services.identitymanagement.model.CreateAccessKeyRequest
import com.amazonaws.services.identitymanagement.model.CreateUserRequest
import com.amazonaws.services.identitymanagement.model.DeleteAccessKeyRequest
import com.amazonaws.services.identitymanagement.model.DeleteUserPolicyRequest
import com.amazonaws.services.identitymanagement.model.DeleteUserRequest
import com.amazonaws.services.identitymanagement.model.GetUserPolicyRequest
import com.amazonaws.services.identitymanagement.model.PutUserPolicyRequest
import org.testng.annotations.Test;

import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit

/**
 * This application tests IAM policy resource ARNs for ELB load balancers.
 *
 * This is verification for the issue:
 *
 *   https://eucalyptus.atlassian.net/browse/EUCA-10052
 */
class TestELBIAMResource {

  private final String host
  private final AWSCredentialsProvider credentials

  public static void main( String[] args ) throws Exception {
    new TestELBIAMResource( ).ELBIAMResourceTest( )
  }

  public TestELBIAMResource() {
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

  private AmazonElasticLoadBalancing getELBClient( final AWSCredentialsProvider credentials ) {
    final AmazonElasticLoadBalancing elb = new AmazonElasticLoadBalancingClient( credentials )
    if ( host ) {
      elb.setEndpoint( cloudUri( "/services/LoadBalancing" ) )
    } else {
      elb.setRegion(Region.getRegion( Regions.US_WEST_1 ) )
    }
    elb
  }

  private AmazonIdentityManagement getIAMClient( final AWSCredentialsProvider credentials  ) {
    final AmazonIdentityManagementClient iam = new AmazonIdentityManagementClient( credentials )
    if ( host ) {
      iam.setEndpoint( cloudUri( "/services/Euare" ) )
    }
    iam
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
  public void ELBIAMResourceTest( ) throws Exception {
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
      String loadBalancerName1 = "${namePrefix}balancer1"
      String loadBalancerName2 = "${namePrefix}balancer2"
      AWSCredentialsProvider userCredentials = null

      getIAMClient( credentials ).with {
        String accountNumber = user?.user?.arn?.substring( 13, 25 )
        print( "Detected account number: ${accountNumber}" )

        String userName = "${namePrefix}user1"
        print( "Creating user for IAM policy testing: ${userName}" )
        String userId = createUser( new CreateUserRequest(
          userName: userName,
          path: '/'
        ) ).with {
          user?.userId
        }
        print( "Created user with ID: ${userId}" )
        cleanupTasks.add{
          print( "Deleting user: ${userName}" )
          deleteUser( new DeleteUserRequest( userName: userName ) )
        }

        String policyName = "${namePrefix}policy1"
        print( "Authorizing user for all actions on ${loadBalancerName1}" )
        putUserPolicy( new PutUserPolicyRequest(
          userName: userName,
          policyName: policyName,
          policyDocument: """
            {
              "Statement":[ {
                "Effect":"Allow",
                "Action":"elasticloadbalancing:*",
                "Resource": [
                  "arn:aws:elasticloadbalancing::${accountNumber}:loadbalancer/${loadBalancerName1}",
                  "arn:aws:elasticloadbalancing::${accountNumber}:loadbalancer/${loadBalancerName2.replace('balancer2','Balancer2')}"
                ]
              } ]
            }
            """.stripMargin( ).trim( )
        ) )
        cleanupTasks.add{
          print( "Deleting user ${userName} policy ${policyName}" )
          deleteUserPolicy( new DeleteUserPolicyRequest( userName: userName, policyName: policyName ) )
        }
        getUserPolicy( new GetUserPolicyRequest(  userName: userName, policyName: policyName ) ).with {
          print( policyDocument )
        }

        print( "Creating access key for user ${userName}" )
        userCredentials = createAccessKey( new CreateAccessKeyRequest( userName: userName ) ).with {
          accessKey?.with {
            new StaticCredentialsProvider( new BasicAWSCredentials( accessKeyId, secretAccessKey ) )
          }
        }
        cleanupTasks.add{
          print( "Deleting access key for user ${userName}" )
          deleteAccessKey( new DeleteAccessKeyRequest(
              userName: userName,
              accessKeyId: userCredentials.credentials.AWSAccessKeyId
          ) )
        }
      }

      elb.with {
        [ loadBalancerName1, loadBalancerName2 ].each { String loadBalancerName ->
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
          describeLoadBalancers( new DescribeLoadBalancersRequest(
              loadBalancerNames: [ loadBalancerName ]
          ) ).with {
            println( loadBalancerDescriptions.toString( ) )
          }
        }
      }

//      print( "Waiting a while for user credentials to propagate .." )
//      sleep( 30000 )

      getELBClient( userCredentials ).with {
        print( "Adding tag to load balancer as user with specific resource permissions: ${loadBalancerName1}" )
        addTags( new AddTagsRequest(
            loadBalancerNames: [ loadBalancerName1 ],
            tags: [
                new Tag( key: 'a', value: 'tag' ),
            ]
        ))
        print( "Added tag to ${loadBalancerName1}" )

        print( "Adding tag to load balancer as user with specific resource permissions: ${loadBalancerName2}" )
        try {
          addTags( new AddTagsRequest(
              loadBalancerNames: [ loadBalancerName2 ],
              tags: [
                  new Tag( key: 'a', value: 'tag' ),
              ]
          ))
          assertThat( true, "Expected add tags to fail due to no permissions on ${loadBalancerName2}" )
        } catch( AmazonServiceException e ) {
          print( "Caught expected exception: ${e}" )
        }
        void
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
