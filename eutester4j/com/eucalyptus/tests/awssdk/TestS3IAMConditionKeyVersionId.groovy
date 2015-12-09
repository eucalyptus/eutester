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
import com.amazonaws.services.s3.model.BucketVersioningConfiguration
import com.amazonaws.services.s3.model.ObjectMetadata
import com.amazonaws.services.s3.model.S3VersionSummary
import com.amazonaws.services.s3.model.SetBucketVersioningConfigurationRequest
import com.github.sjones4.youcan.youare.YouAre
import com.github.sjones4.youcan.youare.YouAreClient
import com.github.sjones4.youcan.youare.model.CreateAccountRequest
import com.github.sjones4.youcan.youare.model.DeleteAccountRequest
import org.testng.Assert
import org.testng.annotations.Test

import java.nio.charset.StandardCharsets

import static com.eucalyptus.tests.awssdk.Eutester4j.minimalInit;
import static com.eucalyptus.tests.awssdk.Eutester4j.HOST_IP;
import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY;
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY;

/**
 * Tests IAM versionId condition key for S3.
 *
 * Related issues:
 *   https://eucalyptus.atlassian.net/browse/EUCA-11010
 *
 * Related AWS doc:
 *   http://docs.aws.amazon.com/AmazonS3/latest/dev/amazon-s3-policy-keys.html
 */
class TestS3IAMConditionKeyVersionId {

  private final String host
  private final AWSCredentialsProvider credentials

  TestS3IAMConditionKeyVersionId( ) {
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
  void testS3IAMConditionKeyVersionIdTest( ) throws Exception {
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

      String version1 = null
      String version2 = null
      String version3 = null
      getS3Client( adminCredentials ).with {
        cleanupTasks.add{
          print( "Deleting bucket ${bucketName}" )
          deleteBucket( bucketName )
        }

        print( "Creating bucket ${bucketName}" )
        createBucket( bucketName )

        print( "Enabling versioning for bucket: ${bucketName}" )
        setBucketVersioningConfiguration( new SetBucketVersioningConfigurationRequest(
            bucketName,
            new BucketVersioningConfiguration( BucketVersioningConfiguration.ENABLED )
        ) )

        print( "Putting foo object version to ${bucketName}" )
        putObject( bucketName, 'foo', new ByteArrayInputStream( "Data version 1".getBytes( StandardCharsets.UTF_8 ) ), new ObjectMetadata( ) );

        print( "Putting foo object version to ${bucketName}" )
        putObject( bucketName, 'foo', new ByteArrayInputStream( "Data version 2".getBytes( StandardCharsets.UTF_8 ) ), new ObjectMetadata( ) );

        print( "Deleting foo object from ${bucketName}" )  // create delete marker as v3
        deleteObject( bucketName, 'foo' );

        print( "Listing foo object versions" )
        listVersions( bucketName, 'foo' ).with {
          versionSummaries.each { S3VersionSummary versionSummary ->
            print( "${versionSummary.bucketName}/${versionSummary.key} ${versionSummary.versionId}" )
            cleanupTasks.add {
              print( "Deleting object foo with version ${versionSummary.versionId} from bucket ${bucketName}" )
              deleteVersion( bucketName, 'foo', versionSummary.versionId )
            }
          }
          assertTrue( versionSummaries.size() == 3, "Expected 3 versions but was ${versionSummaries.size()}" )
          version1 = versionSummaries[0].versionId
          version2 = versionSummaries[1].versionId
          version3 = versionSummaries[2].versionId
        }
      }
      assertTrue( version1 != null, "Expected version 1" )
      assertTrue( version2 != null, "Expected version 2" )
      assertTrue( version3 != null, "Expected version 3" )

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
                      "s3:GetObjectVersion",
                      "s3:GetObjectVersionAcl",
                      "s3:PutObjectVersionAcl",
                      "s3:DeleteObjectVersion"
                    ],
                    "Resource": "arn:aws:s3:::${bucketName}/foo",
                    "Condition": {"StringLike": {"s3:VersionId": [ "${version2}" ]}}
                  },
                  {
                    "Effect": "Allow",
                    "Action": [
                      "s3:DeleteObjectVersion"
                    ],
                    "Resource": "arn:aws:s3:::${bucketName}/foo",
                    "Condition": {"StringEquals": {"s3:VersionId": [ "${version3}" ]}}
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
        print( "******************************************************" )
        print( "TODO: Enable tests for GetObjectVersion when supported" )
        print( "******************************************************" )
//        print( "Getting object foo version ${version2} from ${bucketName}" )
//        getObject( new GetObjectRequest( bucketName, 'foo', version2 ) ).with {
//          print( "Got object ${key}" )
//        }
//
//        try {
//          print( "Getting object foo version ${version1} from ${bucketName}, should fail" )
//          getObject( new GetObjectRequest( bucketName, 'foo', version1 ) ).with {
//            print( "Got object ${key}" )
//            assertTrue( false, "Expected get object version to fail for user due to permissions" )
//          }
//        } catch ( AmazonServiceException e ) {
//          print( "Expected error getting object version without permission: ${e}" )
//        }
//
//        try {
//          print( "Getting object foo ${version1} from ${bucketName}, should fail" )
//          getObject( new GetObjectRequest( bucketName, 'foo' ) ).with {
//            print( "Got object ${key}" )
//            assertTrue( false, "Expected get object to fail for user due to permissions" )
//          }
//        } catch ( AmazonServiceException e ) {
//          print( "Expected error getting object without permission: ${e}" )
//        }

        print( "**************************************************************************" )
        print( "TODO: Add tests for PutObjectVersionAcl/GetObjectVersionAcl when supported" )
        print( "**************************************************************************" )

        print( "Deleting object foo version ${version3} from ${bucketName}" )
        deleteVersion( bucketName, 'foo', version3 );

        print( "Deleting object foo version ${version2} from ${bucketName}" )
        deleteVersion( bucketName, 'foo', version2 );

        try {
          print( "Deleting object foo version ${version1} from ${bucketName}, should fail" )
          deleteVersion( bucketName, 'foo', version1  );
          assertTrue( false, "Expected delete object version to fail for user due to permissions" )
        } catch ( AmazonServiceException e ) {
          print( "Expected error deleting object version without permission: ${e}" )
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
