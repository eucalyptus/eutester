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
import com.amazonaws.services.identitymanagement.model.*
import com.amazonaws.services.s3.AmazonS3
import com.amazonaws.services.s3.AmazonS3Client
import com.amazonaws.services.s3.S3ClientOptions
import com.amazonaws.services.s3.model.*
import com.github.sjones4.youcan.youare.YouAre
import com.github.sjones4.youcan.youare.YouAreClient
import com.github.sjones4.youcan.youare.model.CreateAccountRequest
import com.github.sjones4.youcan.youare.model.DeleteAccountRequest
import org.testng.Assert
import org.testng.annotations.Test

import java.nio.charset.StandardCharsets

import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP
import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY

/**
 * Tests IAM x-amz-copy-source and x-amz-metadata-directive condition keys for S3.
 *
 * Related issues:
 *   https://eucalyptus.atlassian.net/browse/EUCA-11010
 *
 * Related AWS doc:
 *   http://docs.aws.amazon.com/AmazonS3/latest/dev/amazon-s3-policy-keys.html
 */
class TestS3IAMConditionKeysForPutObject {

  private final String host
  private final AWSCredentialsProvider credentials

  TestS3IAMConditionKeysForPutObject( ) {
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

  private boolean assertTrue( boolean condition,
                              String message ){
    Assert.assertTrue( condition, message )
    true
  }

  private void print( String text ) {
    System.out.println( text )
  }

  @Test
  void testS3IAMConditionKeysForPutObjectTest( ) throws Exception {
    final String namePrefix = UUID.randomUUID().toString().substring(0,8) + "-"
    print( "Using resource prefix for test: ${namePrefix}" )

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

        print( "Creating bucket ${bucketName}" )
        createBucket( bucketName )

        cleanupTasks.add {
          [ 'foo', 'foo-2', 'foo-copy-1' ].each { String key ->
            print("Deleting ${key} object from ${bucketName}")
            deleteObject( bucketName, key );
          }
        }

        [ 'foo', 'foo-2' ].each{ String key ->
          print( "Putting ${key} object to ${bucketName}" )
          putObject( bucketName, key, new ByteArrayInputStream( "${key} data".getBytes( StandardCharsets.UTF_8 ) ), new ObjectMetadata( ) );
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
                      "s3:GetObject"
                  ],
                    "Resource": "arn:aws:s3:::${bucketName}/foo"
                  },
                  {
                    "Effect": "Allow",
                    "Action": [
                      "s3:PutObject"
                    ],
                    "Resource": "arn:aws:s3:::${bucketName}/*",
                    "Condition": {
                      "StringEquals": {
                        "s3:x-amz-metadata-directive": "REPLACE",
                        "s3:x-amz-copy-source": "/${bucketName}/foo"
                      }
                    }
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
        print( "Copying object foo with replacement metadata" )
        copyObject( new CopyObjectRequest( bucketName, 'foo', bucketName, 'foo-copy-1' )
            .withNewObjectMetadata( new ObjectMetadata(
              lastModified: new Date( )
            ) )
        )

        print( "Copying object foo without replacing metadata (should fail)" )
        try {
          copyObject( new CopyObjectRequest( bucketName, 'foo', bucketName, 'foo-copy-2' ) )
          assertTrue( false, 'Expected failure due to metadata not replaced' )
        } catch ( AmazonServiceException e ) {
          print( "Expected error for copy failure: ${e}" )
        }

        print( "Copying object foo-2 (should fail)" )
        try {
          copyObject( new CopyObjectRequest( bucketName, 'foo-2', bucketName, 'foo-2-copy-1' )
              .withNewObjectMetadata( new ObjectMetadata(
              lastModified: new Date( )
          ) )
          )
          assertTrue( false, 'Expected failure due to copy source not permitted' )
        } catch ( AmazonServiceException e ) {
          print( "Expected error for copy failure: ${e}" )
        }

        print( "Putting object bar (should fail)" )
        try {
          putObject( bucketName, 'bar', new ByteArrayInputStream( "bar data".getBytes( StandardCharsets.UTF_8 ) ), new ObjectMetadata( ) );
          assertTrue( false, 'Expected failure due to no copy source' )
        } catch ( AmazonServiceException e ) {
          print( "Expected error for copy failure: ${e}" )
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
