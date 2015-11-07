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
import com.amazonaws.services.s3.model.ListObjectsRequest
import com.amazonaws.services.s3.model.ListVersionsRequest
import com.amazonaws.services.s3.model.ObjectMetadata
import com.amazonaws.services.s3.model.S3ObjectSummary
import com.amazonaws.services.s3.model.S3VersionSummary
import com.amazonaws.services.s3.model.SetBucketVersioningConfigurationRequest
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
 * Tests IAM prefix and delimiter condition keys for S3.
 *
 * Related issues:
 *   https://eucalyptus.atlassian.net/browse/EUCA-8582
 *   https://eucalyptus.atlassian.net/browse/EUCA-11010
 *
 * Related AWS doc:
 *   http://docs.aws.amazon.com/AmazonS3/latest/dev/amazon-s3-policy-keys.html
 *   http://docs.aws.amazon.com/AmazonS3/latest/dev/ListingKeysHierarchy.html
 *   http://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_variables.html
 *   http://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_examples.html#iam-policy-example-s3-home-directory
 */
class TestS3IAMConditionKeysPrefixAndDelimiter {

  private final String host
  private final AWSCredentialsProvider credentials

  TestS3IAMConditionKeysPrefixAndDelimiter( ) {
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
  void testS3IAMConditionKeysPrefixAndDelimiterTest( ) throws Exception {
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
          print( "Deleting object versions from bucket ${bucketName}" )
          listVersions( bucketName, null ).with {
            versionSummaries.each { S3VersionSummary version ->
              deleteVersion( bucketName, version.key, version.versionId )
            }
          }

          print( "Deleting bucket ${bucketName}" )
          deleteBucket( bucketName )
        }

        print( "Creating bucket ${bucketName}" )
        createBucket( bucketName )

        cleanupTasks.add {
          ['foo', 'bar', 'dir/foo', 'dir/bar', 'comma,foo', 'comma,bar'].each { String key ->
            print("Deleting ${key} object from ${bucketName}")
            deleteObject( bucketName, key );
          }
        }

        [ 'foo', 'bar', 'dir/foo', 'dir/bar', 'comma,foo', 'comma,bar' ].each{ String key ->
          print( "Putting ${key} object to ${bucketName}" )
          putObject( bucketName, key, new ByteArrayInputStream( "${key} data".getBytes( StandardCharsets.UTF_8 ) ), new ObjectMetadata( ) );
        }

        cleanupTasks.add{
          print( "Disabling versioning for bucket: ${bucketName}"  )
          setBucketVersioningConfiguration( new SetBucketVersioningConfigurationRequest(
              bucketName,
              new BucketVersioningConfiguration( BucketVersioningConfiguration.SUSPENDED )
          ) )
        }

        print( "Enabling versioning for bucket: ${bucketName}"  )
        setBucketVersioningConfiguration( new SetBucketVersioningConfigurationRequest(
            bucketName,
            new BucketVersioningConfiguration( BucketVersioningConfiguration.ENABLED )
        ) )
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
                      "s3:ListBucket",
                      "s3:ListBucketVersions"
                    ],
                    "Resource": "arn:aws:s3:::${bucketName}",
                    "Condition": {
                      "StringEquals": {
                        "s3:prefix": [ "comma,", "dir/" ],
                        "s3:delimiter": [ ",", "/" ]
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
        print( "Listing objects for ${bucketName} with prefix dir/ and delimiter /" )
        listObjects( new ListObjectsRequest( bucketName, 'dir/', null, '/', null ) ).with {
          print( objectSummaries*.key )
          assertTrue( objectSummaries.size( ) == 2, "Expected two objects but was: ${objectSummaries.size( )}" )
        }

        print( "Listing object versions for ${bucketName} with prefix comma, and delimiter ," )
        listVersions( new ListVersionsRequest( bucketName, 'comma,', null, null, ',', null ) ).with {
          print( versionSummaries*.key )
          assertTrue( versionSummaries.size( ) == 2, "Expected two object versions but was: ${versionSummaries.size( )}" )
        }

        print( "Listing objects for ${bucketName} without prefix (should fail)" )
        try { // Ensure fails with missing prefix
          listObjects( new ListObjectsRequest( bucketName, null, null, '/', null ) )
          assertTrue( false, "Expected failure due to missing delimiter" )
        } catch ( AmazonServiceException e ) {
          print( "Expected failure: ${e}" )
        }

        print( "Listing objects for ${bucketName} with invalid prefix (should fail)" )
        try { // Ensure fails with incorrect prefix
          listObjects( new ListObjectsRequest( bucketName, 'invalid', null, '/', null ) )
          assertTrue( false, "Expected failure due to incorrect delimiter" )
        } catch ( AmazonServiceException e ) {
          print( "Expected failure: ${e}" )
        }

        print( "Listing objects for ${bucketName} with missing delimiter (should fail)" )
        try { // Ensure fails with missing delimiter
          listObjects( bucketName, 'dir' )
          assertTrue( false, "Expected failure due to missing delimiter" )
        } catch ( AmazonServiceException e ) {
          print( "Expected failure: ${e}" )
        }

        print( "Listing objects for ${bucketName} with invalid delimiter (should fail)" )
        try { // Ensure fails with incorrect delimiter
          listObjects( new ListObjectsRequest( bucketName, 'dir', null, '_', null ) )
          assertTrue( false, "Expected failure due to incorrect delimiter" )
        } catch ( AmazonServiceException e ) {
          print( "Expected failure: ${e}" )
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

  @Test
  void testS3IAMConditionKeyPrefixAndPolicyVariablesTest( ) throws Exception {
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
                      "s3:ListAllMyBuckets",
                      "s3:GetBucketLocation"
                    ],
                    "Resource": "arn:aws:s3:::*"
                  },
                  {
                    "Effect": "Allow",
                    "Action": "s3:ListBucket",
                    "Resource": "arn:aws:s3:::${bucketName}",
                    "Condition": {"StringLike": {"s3:prefix": [
                        "",
                        "home/",
                        "home/\${aws:username}/"
                    ]}}
                  },
                  {
                    "Effect": "Allow",
                    "Action": "s3:*",
                    "Resource": [
                      "arn:aws:s3:::${bucketName}/home/\${aws:username}",
                      "arn:aws:s3:::${bucketName}/home/\${aws:username}/*"
                    ]
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

      getS3Client( adminCredentials ).with {
        print( "Creating bucket ${bucketName}" )
        createBucket( bucketName )

        cleanupTasks.add{
          print( "Deleting bucket ${bucketName}" )
          deleteBucket( bucketName )
        }
      }

      getS3Client( userCredentials ).with {
        print( "Putting foo1 object to ${bucketName} home directory" )
        putObject( bucketName, "home/${userName}/foo1", new ByteArrayInputStream( "DATA".getBytes( "utf-8" ) ), new ObjectMetadata( ) );

        print( "Copying object foo1 to copy1 in ${bucketName} home directory" )
        copyObject( bucketName, "home/${userName}/foo1", bucketName, "home/${userName}/copy1" );

        [ null, '', 'home/', "home/${userName}/" ].each{ String prefix ->
          print( "Listing bucket with prefix ${prefix?:'<NONE>'}" )
          listObjects( new ListObjectsRequest(
              bucketName: bucketName,
              prefix: prefix
          ) ).with {
            objectSummaries?.each { final S3ObjectSummary summary ->
              print( "- ${summary.key}" )
            }
          }
        }

        [ "/", 'nothome/', "nothome/${userName}/", 'home/otheruser/' ].each{ String prefix ->
          print( "Listing bucket with prefix ${prefix?:'<NONE>'}, expect failure due to no permission for prefix" )
          try {
            listObjects( new ListObjectsRequest(
                bucketName: bucketName,
                prefix: prefix
            ) )
            assertThat( false, "Expected failure for listing objects with prefix ${prefix}" )
          } catch ( AmazonServiceException e ) {
            print( "Expected error listing objects for prefix ${prefix} without permission: ${e}" )
          }
        }

        print( "Deleting object foo1 from ${bucketName} home directory" )
        deleteObject( bucketName, "home/${userName}/foo1"  );

        print( "Deleting object copy1 from ${bucketName} home directory" )
        deleteObject( bucketName, "home/${userName}/copy1"  );

        try {
          print( "Putting object to ${bucketName} outside of home directory, should fail" )
          putObject( bucketName, "foo1", new ByteArrayInputStream( "DATA".getBytes( "utf-8" ) ), new ObjectMetadata( ) );
          assertThat( false, "Expected put object to fail for admin user due to permissions" )
        } catch ( AmazonServiceException e ) {
          print( "Expected error putting object without permission: ${e}" )
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
          print( "Entity not found during cleanup." )
        } catch ( AmazonServiceException e ) {
          print( "Service error during cleanup; code: ${e.errorCode}, message: ${e.message}" )
        } catch ( Exception e ) {
          e.printStackTrace()
        }
      }
    }
  }
}
