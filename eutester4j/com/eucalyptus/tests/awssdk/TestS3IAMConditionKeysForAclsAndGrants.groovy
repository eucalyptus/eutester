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
import com.amazonaws.services.s3.model.AccessControlList
import com.amazonaws.services.s3.model.CannedAccessControlList
import com.amazonaws.services.s3.model.CanonicalGrantee
import com.amazonaws.services.s3.model.CreateBucketRequest
import com.amazonaws.services.s3.model.ObjectMetadata
import com.amazonaws.services.s3.model.Owner
import com.amazonaws.services.s3.model.Permission
import com.amazonaws.services.s3.model.PutObjectRequest
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
 * Tests IAM x-amz-acl and x-amz-grant-* condition keys for S3.
 *
 * Related issues:
 *   https://eucalyptus.atlassian.net/browse/EUCA-11010
 *
 * Related AWS doc:
 *   http://docs.aws.amazon.com/AmazonS3/latest/dev/amazon-s3-policy-keys.html
 */
class TestS3IAMConditionKeysForAclsAndGrants {

  private final String host
  private final AWSCredentialsProvider credentials

  TestS3IAMConditionKeysForAclsAndGrants( ) {
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
  void testS3IAMConditionKeysForAclsTest( ) throws Exception {
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

        cleanupTasks.add {
          [ 'foo' ].each { String key ->
            print("Deleting ${key} object from ${bucketName}")
            deleteObject( bucketName, key );
          }
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
                    "Condition": {
                      "StringEquals": {
                        "s3:x-amz-acl": "public-read"
                      }
                    }
                  },
                  {
                    "Effect": "Allow",
                    "Action": [
                      "s3:PutBucketAcl",
                      "s3:PutObject",
                      "s3:PutObjectAcl"
                    ],
                    "Resource": [
                      "arn:aws:s3:::${bucketName}",
                      "arn:aws:s3:::${bucketName}/*"
                    ],
                    "Condition": {
                      "StringEquals": {
                        "s3:x-amz-acl": "public-read"
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
        print( "Creating bucket ${bucketName} with public-read predefined ACL" )
        createBucket( new CreateBucketRequest( bucketName )
            .withCannedAcl( CannedAccessControlList.PublicRead ) )

        print( "Creating bucket ${bucketName}-2 with bucket-owner-full-control predefined ACL (should fail)" )
        try {
          createBucket( new CreateBucketRequest( "${bucketName}-2" )
              .withCannedAcl( CannedAccessControlList.BucketOwnerFullControl ) )
          assertTrue( false, 'Expected failure due to incorrect canned ACL' )
        } catch ( AmazonServiceException e ) {
          print( "Expected error for create bucket failure: ${e}" )
        }

        print( "Putting bucket ${bucketName} ACL with public-read predefined ACL" )
        setBucketAcl( bucketName, CannedAccessControlList.PublicRead )

        print( "Putting bucket ${bucketName} ACL with bucket-owner-full-control predefined ACL  (should fail)" )
        try {
          setBucketAcl( bucketName, CannedAccessControlList.BucketOwnerFullControl )
          assertTrue( false, 'Expected failure due to incorrect canned ACL' )
        } catch ( AmazonServiceException e ) {
          print( "Expected error for put bucket ACL failure: ${e}" )
        }

        print( "Putting object ${bucketName}/foo with public-read predefined ACL" )
        putObject( new PutObjectRequest(
            bucketName,
            'foo',
            new ByteArrayInputStream( "foo data".getBytes( StandardCharsets.UTF_8 ) ),
            new ObjectMetadata( ) ).withCannedAcl( CannedAccessControlList.PublicRead )
        );

        print( "Putting object bar with bucket-owner-full-control predefined ACL (should fail)" )
        try {
          putObject( new PutObjectRequest(
              bucketName,
              'bar',
              new ByteArrayInputStream( "foo data".getBytes( StandardCharsets.UTF_8 ) ),
              new ObjectMetadata( ) ).withCannedAcl( CannedAccessControlList.BucketOwnerFullControl )
          );
          assertTrue( false, 'Expected failure due to incorrect canned ACL' )
        } catch ( AmazonServiceException e ) {
          print( "Expected error for put failure: ${e}" )
        }

        print( "Putting object ${bucketName}/foo ACL with public-read predefined ACL" )
        setObjectAcl( bucketName, 'foo', CannedAccessControlList.PublicRead )

        print( "Putting object ${bucketName}/foo ACL with bucket-owner-full-control predefined ACL (should fail)" )
        try {
          setObjectAcl( bucketName, 'foo', CannedAccessControlList.BucketOwnerFullControl )
          assertTrue( false, 'Expected failure due to incorrect canned ACL' )
        } catch ( AmazonServiceException e ) {
          print( "Expected error for put object ACL failure: ${e}" )
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
  void testS3IAMConditionKeysForGrantsTest( ) throws Exception {
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

      String granteeAccountCanonicalId = null
      getS3Client( credentials ).with {
        cleanupTasks.add{
          print( "Deleting bucket ${bucketName}-admin" )
          deleteBucket( "${bucketName}-admin" )
        }

        createBucket( "${bucketName}-admin" )

        granteeAccountCanonicalId = getBucketAcl( "${bucketName}-admin" ).with { AccessControlList acl ->
          acl?.owner?.id
        }

        deleteBucket( "${bucketName}-admin" )
      }
      assertTrue( granteeAccountCanonicalId != null, "Expected granteeAccountCanonicalId but was null" )

      String adminAccountCanonicalId = null
      getS3Client( adminCredentials ).with {
        cleanupTasks.add{
          print( "Deleting bucket ${bucketName}" )
          deleteBucket( bucketName )
        }

        cleanupTasks.add {
          [ 'foo' ].each { String key ->
            print("Deleting ${key} object from ${bucketName}")
            deleteObject( bucketName, key );
          }
        }

        createBucket( bucketName )

        adminAccountCanonicalId = getBucketAcl( bucketName ).with { AccessControlList acl ->
          acl?.owner?.id
        }

        deleteBucket( bucketName )

        void
      }
      assertTrue( adminAccountCanonicalId != null, "Expected adminAccountCanonicalId but was null" )

      String policyName = "${namePrefix}policy1"
      AWSCredentialsProvider userCredentials = getYouAreClient( adminCredentials ).with {
        cleanupTasks.add {
          println("Deleting user ${userName}")
          deleteUser(new DeleteUserRequest(
              userName: userName
          ))
        }
        print("Creating user ${userName}")
        createUser(new CreateUserRequest(
            userName: userName,
            path: '/'
        ))

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

      [ 'read', 'write', 'read-acp', 'write-acp', 'full-control' ].each { String permission ->
        String invalidPermission = permission == 'read' ? 'write' : 'read'
        getYouAreClient( adminCredentials ).with {
          print( "Setting user policy ${policyName}" )
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
                    "Condition": {
                      "StringEquals": {
                        "s3:x-amz-grant-${permission}": "id=${granteeAccountCanonicalId}"
                      }
                    }
                  },
                  {
                    "Effect": "Allow",
                    "Action": [
                      "s3:PutBucketAcl",
                      "s3:PutObject",
                      "s3:PutObjectAcl"
                    ],
                    "Resource": [
                      "arn:aws:s3:::${bucketName}",
                      "arn:aws:s3:::${bucketName}/*"
                    ],
                    "Condition": {
                      "StringEquals": {
                        "s3:x-amz-grant-${permission}": "id=${granteeAccountCanonicalId}"
                      }
                    }
                  }
                ]
              }
              """.stripIndent( )
          ) )
        }

        println( "Sleeping to ensure policy applied" )
        sleep( 5000 )

        getS3Client( userCredentials ).with {
          print( "Creating bucket ${bucketName} with x-amz-grant-${permission} for ${granteeAccountCanonicalId} ACL" )
          createBucket( new CreateBucketRequest( bucketName )
              .withAccessControlList( acl( adminAccountCanonicalId, granteeAccountCanonicalId, permission ) ) )

          print( "Creating bucket ${bucketName}-2 with x-amz-grant-${invalidPermission} for ${granteeAccountCanonicalId} ACL (should fail)" )
          try {
            createBucket( new CreateBucketRequest( bucketName )
                .withAccessControlList( acl( adminAccountCanonicalId, granteeAccountCanonicalId, invalidPermission ) ) )
            assertTrue( false, 'Expected failure due to incorrect ACL permission' )
          } catch ( AmazonServiceException e ) {
            print( "Expected error for create bucket failure: ${e}" )
          }

          print( "Putting bucket ${bucketName} ACL with x-amz-grant-${permission} for ${granteeAccountCanonicalId} ACL" )
          setBucketAcl( bucketName, acl( adminAccountCanonicalId, granteeAccountCanonicalId, permission ) )

          print( "Putting bucket ${bucketName} ACL with x-amz-grant-${invalidPermission} for ${granteeAccountCanonicalId} ACL (should fail)" )
          try {
            setBucketAcl( bucketName, acl( adminAccountCanonicalId, granteeAccountCanonicalId, invalidPermission ) )
            assertTrue( false, 'Expected failure due to incorrect ACL permission' )
          } catch ( AmazonServiceException e ) {
            print( "Expected error for put bucket ACL failure: ${e}" )
          }

          print( "Putting object ${bucketName}/foo with x-amz-grant-${permission} for ${granteeAccountCanonicalId} ACL" )
          putObject( new PutObjectRequest(
              bucketName,
              'foo',
              new ByteArrayInputStream( "foo data".getBytes( StandardCharsets.UTF_8 ) ),
              new ObjectMetadata( ) ).withAccessControlList( acl( adminAccountCanonicalId, granteeAccountCanonicalId, permission ) )
          );

          print( "Putting object ${bucketName}/bar with with x-amz-grant-${invalidPermission} for ${granteeAccountCanonicalId} ACL (should fail)" )
          try {
            putObject( new PutObjectRequest(
                bucketName,
                'bar',
                new ByteArrayInputStream( "foo data".getBytes( StandardCharsets.UTF_8 ) ),
                new ObjectMetadata( ) ).withAccessControlList( acl( adminAccountCanonicalId, granteeAccountCanonicalId, invalidPermission ) )
            );
            assertTrue( false, 'Expected failure due to incorrect ACL permission' )
          } catch ( AmazonServiceException e ) {
            print( "Expected error for put failure: ${e}" )
          }

          print( "Putting object ${bucketName}/foo ACL with x-amz-grant-${permission} for ${granteeAccountCanonicalId} ACL" )
          setObjectAcl( bucketName, 'foo', acl( adminAccountCanonicalId, granteeAccountCanonicalId, permission ) )

          print( "Putting object ${bucketName}/foo ACL with x-amz-grant-${invalidPermission} for ${granteeAccountCanonicalId} ACL (should fail)" )
          try {
            setObjectAcl( bucketName, 'foo', acl( adminAccountCanonicalId, granteeAccountCanonicalId, invalidPermission ) )
            assertTrue( false, 'Expected failure due to incorrect ACL permission' )
          } catch ( AmazonServiceException e ) {
            print( "Expected error for put object ACL failure: ${e}" )
          }

          void
        }

        getS3Client( adminCredentials ).with {
          [ 'foo' ].each { String key ->
            print("Deleting ${key} object from ${bucketName}")
            deleteObject( bucketName, key );
          }

          print( "Deleting bucket ${bucketName}" )
          deleteBucket( bucketName )
        }
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

  private static AccessControlList acl( String ownerId, String granteeId, String permission ) {
    new AccessControlList( ).with{ AccessControlList acl ->
      setOwner( new Owner( id: ownerId ) )
      grantPermission(
          new CanonicalGrantee( granteeId ),
          Permission.values( ).find{ Permission perm -> perm.headerName == ("x-amz-grant-${permission}" as String) } )
      acl
    }
  }
}
