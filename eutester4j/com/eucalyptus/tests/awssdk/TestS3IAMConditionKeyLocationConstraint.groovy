package com.eucalyptus.tests.awssdk

import com.amazonaws.AmazonServiceException
import com.amazonaws.ClientConfiguration
import com.amazonaws.Request
import com.amazonaws.auth.AWSCredentialsProvider
import com.amazonaws.auth.BasicAWSCredentials
import com.amazonaws.handlers.AbstractRequestHandler
import com.amazonaws.internal.StaticCredentialsProvider
import com.amazonaws.regions.Region
import com.amazonaws.regions.Regions
import com.amazonaws.services.ec2.AmazonEC2
import com.amazonaws.services.ec2.AmazonEC2Client
import com.amazonaws.services.identitymanagement.model.*
import com.amazonaws.services.s3.AmazonS3
import com.amazonaws.services.s3.AmazonS3Client
import com.amazonaws.services.s3.S3ClientOptions
import com.amazonaws.services.s3.model.CreateBucketRequest
import com.github.sjones4.youcan.youare.YouAre
import com.github.sjones4.youcan.youare.YouAreClient
import com.github.sjones4.youcan.youare.model.CreateAccountRequest
import com.github.sjones4.youcan.youare.model.DeleteAccountRequest
import org.testng.Assert
import org.testng.annotations.Test

import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit;
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP;
import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY;
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY;

/**
 * Tests IAM locationConstraint condition key for S3.
 *
 * Related issues:
 *   https://eucalyptus.atlassian.net/browse/EUCA-11010
 *
 * Related AWS doc:
 *   http://docs.aws.amazon.com/AmazonS3/latest/dev/amazon-s3-policy-keys.html
 */
class TestS3IAMConditionKeyLocationConstraint {

  private final String host
  private final AWSCredentialsProvider credentials

  TestS3IAMConditionKeyLocationConstraint( ) {
    minimalInit()
    this.host = HOST_IP
    this.credentials = new StaticCredentialsProvider( new BasicAWSCredentials( ACCESS_KEY, SECRET_KEY ) )
  }

  private String cloudUri( String host, String servicePath ) {
    URI.create( "http://${host}:8773/" )
        .resolve( servicePath )
        .toString( )
  }

  private YouAreClient getYouAreClient( final AWSCredentialsProvider credentials  ) {
    final YouAreClient euare = new YouAreClient( credentials )
    if ( host ) {
      euare.setEndpoint( cloudUri( host, '/services/Euare' ) )
    } else {
      euare.setRegion( Region.getRegion( Regions.US_EAST_1 ) )
    }
    euare
  }

  private AmazonS3 getS3Client( final AWSCredentialsProvider credentials ) {
    final ClientConfiguration clientConfiguration = new ClientConfiguration( )
    clientConfiguration.signerOverride = 'S3SignerType'
    final AmazonS3Client s3 = new AmazonS3Client( credentials, clientConfiguration )
    if ( host ) {
      s3.setEndpoint( cloudUri( host, '/services/objectstorage' ) )
      s3.setS3ClientOptions( new S3ClientOptions( ).withPathStyleAccess( true ) )
    }
    return s3;
  }

  private AmazonEC2 getEC2Client( final AWSCredentialsProvider credentials ) {
    final AmazonEC2 ec2 = new AmazonEC2Client( credentials )
    if ( host ) {
      ec2.setEndpoint( cloudUri( host, '/services/compute' ) )
    }
    return ec2;
  }

  private boolean assertTrue( boolean condition,
                              String message ){
    Assert.assertTrue( condition, message )
    true
  }

  private void print( String text ) {
    System.out.println( text )
  }

  @Test
  void testS3IAMConditionKeyLocationConstraintTest( ) throws Exception {
    final String namePrefix = UUID.randomUUID().toString().substring(0,8) + "-"
    print( "Using resource prefix for test: ${namePrefix}" )

    final Collection<String> regions = getEC2Client( credentials ).with {
      describeRegions( ).with {
        regions*.regionName
      }
    }
    assertTrue( !regions.isEmpty( ), 'No regions found' )
    print( "Detected regions: ${regions}" )

    final List<Runnable> cleanupTasks = [] as List<Runnable>
    String userName = "${namePrefix}user1"
    String bucketName = "${namePrefix}bucket1"
    try {
      AWSCredentialsProvider adminCredentials = null
      adminCredentials = getYouAreClient( credentials ).with {
        // Create account to use for test
        final String accountName = "${namePrefix}account1"
        print("Creating test account: ${accountName}")
        String adminAccountNumber = createAccount(new CreateAccountRequest(accountName: accountName)).with {
          account?.accountId
        }
        assertTrue(adminAccountNumber != null, "Expected account number")
        print("Created test account with number: ${adminAccountNumber}")
        cleanupTasks.add {
          print("Deleting test account: ${accountName}")
          deleteAccount(new DeleteAccountRequest(accountName: accountName, recursive: true))
        }

        // Get credentials for admin account
        print("Creating access key for test account admin user: ${accountName}")
        YouAre adminIam = getYouAreClient( credentials )
        adminIam.addRequestHandler(new AbstractRequestHandler() {
          public void beforeRequest(final Request<?> request) {
            request.addParameter("DelegateAccount", accountName)
          }
        })
        adminCredentials = adminIam.with {
          createAccessKey(new CreateAccessKeyRequest(userName: "admin")).with {
            accessKey?.with {
              new StaticCredentialsProvider(new BasicAWSCredentials(accessKeyId, secretAccessKey))
            }
          }
        }
        assertTrue(adminCredentials != null, "Expected test acount admin user credentials")
        print("Created test acount admin user access key: ${adminCredentials.credentials.AWSAccessKeyId}")

        adminCredentials
      }

      getS3Client( adminCredentials ).with {
        cleanupTasks.add{
          print( "Deleting bucket ${bucketName}" )
          deleteBucket( bucketName )
        }
      }

      AWSCredentialsProvider userCredentials = getYouAreClient( adminCredentials ).with {
        cleanupTasks.add{
          println( "Deleting user ${userName}" )
          deleteUser( new DeleteUserRequest(
              userName: userName
          ) )
        }
        print( "Creating user ${userName}" )
        createUser( new CreateUserRequest(
            userName: userName,
            path: '/'
        ) )

        String policyName = "${namePrefix}policy1"
        print( "Creating user policy ${policyName}" )
        putUserPolicy( new PutUserPolicyRequest(
            userName: userName,
            policyName: policyName,
            policyDocument: """\
              {
                "Version": "2012-10-17",
                "Statement": [
                  {
                    "Effect": "Allow",
                    "Action": [
                      "s3:CreateBucket"
                    ],
                    "Resource": "*",
                    "Condition": {"StringLike": {"s3:LocationConstraint": [ "${regions.join('","')}" ]}}
                  }
                ]
              }
              """.stripIndent( )
        ) )

        cleanupTasks.add{
          print( "Deleting user policy ${policyName}" )
          deleteUserPolicy( new DeleteUserPolicyRequest(
              userName: userName,
              policyName: policyName
          ) )
        }

        print( "Creating access key for user ${userName}" )
        AWSCredentialsProvider userCredentials = createAccessKey( new CreateAccessKeyRequest(
            userName: userName
        ) ).with {
          accessKey.with {
            new StaticCredentialsProvider( new BasicAWSCredentials( accessKeyId, secretAccessKey ) )
          }
        }

        cleanupTasks.add {
          print( "Deleting access key for user ${userName}" )
          deleteAccessKey( new DeleteAccessKeyRequest(
              userName: userName,
              accessKeyId: userCredentials.credentials.AWSAccessKeyId
          ) )
        }

        userCredentials
      }

      getS3Client( userCredentials ).with {
        String region = regions.iterator( ).next( )
        print( "Creating bucket in permitted region ${region}" )
        createBucket( new CreateBucketRequest( bucketName, region ) )

        print( "Creating bucket in non-permitted region invalid-region (should fail)" )
        try {
          createBucket( bucketName + "-invalid", 'invalid-region' )
          assertTrue( false, 'Expected bucket creation to fail for non-permitted region' )
        } catch (AmazonServiceException e) {
          print( "Expected bucket creation failure: ${e}" )
        }

        void
      }

      print( "Test complete" )
    } finally {
      // Attempt to clean up anything we created
      cleanupTasks.reverseEach { Runnable cleanupTask ->
        try {
          cleanupTask.run()
        } catch ( NoSuchEntityException e ) {
          print( "Entity not found during cleanup" )
        } catch ( AmazonServiceException e ) {
          print( "Service error during cleanup; code: ${e.errorCode}, message: ${e.message}" )
        } catch ( Exception e ) {
          e.printStackTrace()
        }
      }
    }
  }
}
