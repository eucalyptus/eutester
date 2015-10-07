package com.eucalyptus.tests.awssdk;

import static com.eucalyptus.tests.awssdk.Eutester4j.assertThat;
import static com.eucalyptus.tests.awssdk.Eutester4j.eucaUUID;
import static com.eucalyptus.tests.awssdk.Eutester4j.initS3ClientWithNewAccount;
import static com.eucalyptus.tests.awssdk.Eutester4j.print;
import static com.eucalyptus.tests.awssdk.Eutester4j.testInfo;
import static org.testng.AssertJUnit.assertTrue;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;

import org.testng.annotations.AfterClass;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import com.amazonaws.AmazonServiceException;
import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.model.AccessControlList;
import com.amazonaws.services.s3.model.AmazonS3Exception;
import com.amazonaws.services.s3.model.Bucket;
import com.amazonaws.services.s3.model.BucketLoggingConfiguration;
import com.amazonaws.services.s3.model.BucketTaggingConfiguration;
import com.amazonaws.services.s3.model.BucketVersioningConfiguration;
import com.amazonaws.services.s3.model.CannedAccessControlList;
import com.amazonaws.services.s3.model.CanonicalGrantee;
import com.amazonaws.services.s3.model.Grant;
import com.amazonaws.services.s3.model.GroupGrantee;
import com.amazonaws.services.s3.model.Owner;
import com.amazonaws.services.s3.model.Permission;
import com.amazonaws.services.s3.model.SetBucketLoggingConfigurationRequest;
import com.amazonaws.services.s3.model.SetBucketVersioningConfigurationRequest;
import com.amazonaws.services.s3.model.TagSet;

/**
 * <p>
 * This class contains tests for basic operations on S3 buckets.
 * </p>
 * 
 * <p>
 * {@link #versioningConfiguration()} fails against Walrus due to <a href="https://eucalyptus.atlassian.net/browse/EUCA-7635">EUCA-7635</a>
 * </p>
 * 
 * <p>
 * {@link #unimplementedOps()} passes only against Walrus as the APIs are not implemented by Walrus
 * 
 * @author Swathi Gangisetty
 * 
 */
public class S3BucketTests {

  private static String bucketName = null;
  private static List<Runnable> cleanupTasks = null;
  private static AmazonS3 s3 = null;
  private static String account = null;
  private static Owner owner = null;
  private static String ownerName = null;
  private static String ownerId = null;

  @BeforeClass
  public void init() throws Exception {
    print("### PRE SUITE SETUP - " + this.getClass().getSimpleName());
    try {
      account = this.getClass().getSimpleName().toLowerCase();
      s3 = initS3ClientWithNewAccount(account, "admin");
    } catch (Exception e) {
      try {
        teardown();
      } catch (Exception ie) {
      }
      throw e;
    }

    owner = s3.getS3AccountOwner();
    ownerName = owner.getDisplayName();
    ownerId = owner.getId();
  }

  @AfterClass
  public void teardown() throws Exception {
    print("### POST SUITE CLEANUP - " + this.getClass().getSimpleName());
    Eutester4j.deleteAccount(account);
    s3 = null;
  }

  @BeforeMethod
  public void setup() throws Exception {
    bucketName = eucaUUID();
    cleanupTasks = new ArrayList<Runnable>();
    Bucket bucket = S3Utils.createBucket(s3, account, bucketName, S3Utils.BUCKET_CREATION_RETRIES);
    cleanupTasks.add(new Runnable() {
      @Override
      public void run() {
        print(account + ": Deleting bucket " + bucketName);
        s3.deleteBucket(bucketName);
      }
    });

    assertTrue("Invalid reference to bucket", bucket != null);
    assertTrue("Mismatch in bucket names. Expected bucket name to be " + bucketName + ", but got " + bucket.getName(),
        bucketName.equals(bucket.getName()));
  }

  @AfterMethod
  public void cleanup() throws Exception {
    Collections.reverse(cleanupTasks);
    for (final Runnable cleanupTask : cleanupTasks) {
      try {
        cleanupTask.run();
      } catch (Exception e) {
        print("Unable to run clean up task: " + e);
      }
    }
  }

  /**
   * Tests for the following S3 APIs
   * 
   * <li>createBucket</li> <li>deleteBucket</li> <li>listBuckets</li> <li>doesBucketExist</li> <li>getBucketLocation</li> <li>
   * getBucketLoggingConfiguration</li> <li>getBucketVersioningConfiguration</li>
   */
  @Test
  public void bucketBasics() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - bucketBasics");

    try {
      print(account + ": Listing all buckets");
      List<Bucket> bucketList = s3.listBuckets();
      assertTrue("Invalid or empty bucket list", bucketList != null && !bucketList.isEmpty());
      boolean found = false;
      for (Bucket buck : bucketList) {
        if (buck.getName().equals(bucketName)) {
          found = true;
          break;
        }
      }
      assertTrue("Expected newly created bucket to be listed in the buckets but did not", found);

      print(account + ": Checking if the bucket " + bucketName + " exists");
      assertTrue("Expected to find " + bucketName + ", but the bucket was not found", s3.doesBucketExist(bucketName));

      print(account + ": Fetching bucket location for " + bucketName);
      String location = s3.getBucketLocation(bucketName);
      assertTrue("Invalid result for bucket location, expected a string", location != null && !location.isEmpty());

      print(account + ": Fetching bucket logging configuration for " + bucketName);
      BucketLoggingConfiguration loggingConfig = s3.getBucketLoggingConfiguration(bucketName);
      assertTrue("Invalid result for bucket logging configuration", loggingConfig != null);
      assertTrue("Expected bucket logging to be disabled, but got enabled", !loggingConfig.isLoggingEnabled());
      assertTrue("Expected destination bucket to be null, but got " + loggingConfig.getDestinationBucketName(),
          loggingConfig.getDestinationBucketName() == null);
      assertTrue("Expected log file prefix to be null, but got " + loggingConfig.getLogFilePrefix(), loggingConfig.getLogFilePrefix() == null);

      print(account + ": Fetching bucket versioning configuration for " + bucketName);
      BucketVersioningConfiguration versioning = s3.getBucketVersioningConfiguration(bucketName);
      assertTrue("Invalid result for bucket versioning configuration", versioning != null);
      assertTrue("Expected bucket versioning configuration to be OFF, but found it to be " + versioning.getStatus(),
          versioning.getStatus().equals(BucketVersioningConfiguration.OFF));
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run bucketBasics");
    }
  }

  /**
   * Tests for S3 operations that are not implemented by Walrus. It should fail against S3 and pass against Walrus. Every unimplemented operation
   * should return a 501 NotImplemented error response
   */
  @Test
  public void unimplementedOps() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - notImplementedOps");

    boolean error;

    error = false;
    try {
      print(account + ": Fetching bucket cors for " + bucketName);
      s3.getBucketCrossOriginConfiguration(bucketName);
    } catch (AmazonServiceException ase) {
      verifyException(ase);
      error = true;
    } finally {
      assertTrue("Expected to receive a 501 NotImplemented error but did not", error);
    }

    error = false;
    try {
      print(account + ": Fetching bucket policy for " + bucketName);
      s3.getBucketPolicy(bucketName);
    } catch (AmazonServiceException ase) {
      verifyException(ase);
      error = true;
    } finally {
      assertTrue("Expected to receive a 501 NotImplemented error but did not", error);
    }

    error = false;
    try {
      print(account + ": Fetching bucket notification configuration for " + bucketName);
      s3.getBucketNotificationConfiguration(bucketName);
    } catch (AmazonServiceException ase) {
      verifyException(ase);
      error = true;
    } finally {
      assertTrue("Expected to receive a 501 NotImplemented error but did not", error);
    }

    error = false;
    try {
      print(account + ": Fetching bucket website configuration for " + bucketName);
      s3.getBucketWebsiteConfiguration(bucketName);
    } catch (AmazonServiceException ase) {
      verifyException(ase);
      error = true;
    } finally {
      assertTrue("Expected to receive a 501 NotImplemented error but did not", error);
    }

  }

  /**
   * Test for changing logging configuration of a bucket and verifying it.
   */
  @Test(enabled = false)
  public void loggingConfiguration() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - loggingConfiguration");

    try {
      print(account + ": Fetching bucket logging configuration for " + bucketName);
      BucketLoggingConfiguration loggingConfig = s3.getBucketLoggingConfiguration(bucketName);
      assertTrue("Invalid result for bucket logging configuration", loggingConfig != null);
      assertTrue("Expected bucket logging to be disabled, but got enabled", !loggingConfig.isLoggingEnabled());

      boolean error = false;
      try {
        print(account + ": Setting bucket logging configuration before assigning log-delivery group WRITE and READ_ACP permissions for " + bucketName);
        s3.setBucketLoggingConfiguration(new SetBucketLoggingConfigurationRequest(bucketName, new BucketLoggingConfiguration(bucketName, bucketName)));
      } catch (AmazonS3Exception ex) {
        assertTrue("Expected error code to be 400, but got " + ex.getStatusCode(), ex.getStatusCode() == 400);
        error = true;
      } finally {
        assertTrue(
            "Expected AmazonS3Exception for enabling bucket logging configuration before assigning log-delivery group appropriate permissions", error);
      }

      print(account + ": Setting canned ACL log-delivery-write for " + bucketName);
      s3.setBucketAcl(bucketName, CannedAccessControlList.LogDeliveryWrite);

      print(account + ": Getting ACL for bucket " + bucketName);
      AccessControlList acl = s3.getBucketAcl(bucketName);
      assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 3 but got " + acl.getGrants().size(), acl.getGrants().size() == 3);

      Iterator<Grant> iterator = acl.getGrants().iterator();
      while (iterator.hasNext()) {
        Grant grant = iterator.next();
        if (grant.getGrantee() instanceof CanonicalGrantee) {
          assertTrue("Expected grantee to be bucket owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
              .getGrantee().getIdentifier().equals(acl.getOwner().getId()));
          assertTrue("Grantee should have full control", grant.getPermission().equals(Permission.FullControl));
        } else {
          assertTrue("Grantee of type GroupGrantee not found", grant.getGrantee() instanceof GroupGrantee);
          assertTrue("Expected grantee to be LogDelivery but found " + ((GroupGrantee) grant.getGrantee()),
              ((GroupGrantee) grant.getGrantee()).equals(GroupGrantee.LogDelivery));
          assertTrue("Grantee does not have " + Permission.Write.toString() + " and/or " + grant.getPermission().equals(Permission.ReadAcp)
              + " privileges", grant.getPermission().equals(Permission.Write) || grant.getPermission().equals(Permission.ReadAcp));
        }
      }

      print(account + ": Setting bucket logging configuration after assigning log-delivery group WRITE and READ_ACP permissions for " + bucketName);
      s3.setBucketLoggingConfiguration(new SetBucketLoggingConfigurationRequest(bucketName, new BucketLoggingConfiguration(bucketName, bucketName)));

      print(account + ": Fetching bucket logging configuration for " + bucketName);
      loggingConfig = s3.getBucketLoggingConfiguration(bucketName);
      assertTrue("Invalid result for bucket logging configuration", loggingConfig != null);
      assertTrue("Expected bucket logging to be enabled, but got disabled", loggingConfig.isLoggingEnabled());
      assertTrue("Expected destination bucket to be " + bucketName + ", but got " + loggingConfig.getDestinationBucketName(), loggingConfig
          .getDestinationBucketName().equals(bucketName));
      assertTrue("Expected log file prefix to be " + bucketName + ", but got " + loggingConfig.getLogFilePrefix(), loggingConfig.getLogFilePrefix()
          .equals(bucketName));

    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run loggingConfiguration");
    }
  }

  /**
   * Test for changing versioning configuration of a bucket and verifying it.
   * 
   * Test failed against Walrus. Versioning configuration cannot be turned OFF once its ENABLED/SUSPENDED on a bucket. While S3 throws an exception
   * for such a request, Walrus does not. The versioning configuration remains unchanged but no error is received.</p>
   * 
   * @see <a href="https://eucalyptus.atlassian.net/browse/EUCA-7635">EUCA-7635</a>
   */
  @Test
  public void versioningConfiguration() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - versioningConfiguration");

    try {
      print(account + ": Fetching bucket versioning configuration for the newly created bucket " + bucketName);
      BucketVersioningConfiguration versioning = s3.getBucketVersioningConfiguration(bucketName);
      assertTrue("Invalid result for bucket versioning configuration", versioning != null);
      assertTrue("Expected bucket versioning configuration to be OFF, but found it to be " + versioning.getStatus(),
          versioning.getStatus().equals(BucketVersioningConfiguration.OFF));

      print(account + ": Setting bucket versioning configuration to ENABLED");
      s3.setBucketVersioningConfiguration(new SetBucketVersioningConfigurationRequest(bucketName, new BucketVersioningConfiguration()
          .withStatus(BucketVersioningConfiguration.ENABLED)));

      print(account + ": Fetching bucket versioning configuration after setting it to ENABLED");
      versioning = s3.getBucketVersioningConfiguration(bucketName);
      assertTrue("Invalid result for bucket versioning configuration", versioning != null);
      assertTrue("Expected bucket versioning configuration to be ENABLED, but found it to be " + versioning.getStatus(), versioning.getStatus()
          .equals(BucketVersioningConfiguration.ENABLED));

      print(account + ": Setting bucket versioning configuration to SUSPENDED");
      s3.setBucketVersioningConfiguration(new SetBucketVersioningConfigurationRequest(bucketName, new BucketVersioningConfiguration()
          .withStatus(BucketVersioningConfiguration.SUSPENDED)));

      print(account + ": Fetching bucket versioning configuration after setting it to SUSPENDED");
      versioning = s3.getBucketVersioningConfiguration(bucketName);
      assertTrue("Invalid result for bucket versioning configuration", versioning != null);
      assertTrue("Expected bucket versioning configuration to be SUSPENDED, but found it to be " + versioning.getStatus(), versioning.getStatus()
          .equals(BucketVersioningConfiguration.SUSPENDED));

      boolean error = false;
      try {
        s3.setBucketVersioningConfiguration(new SetBucketVersioningConfigurationRequest(bucketName, new BucketVersioningConfiguration()
            .withStatus(BucketVersioningConfiguration.OFF)));
      } catch (AmazonS3Exception ex) {
        assertTrue("Expected error code to be 400, but got " + ex.getStatusCode(), ex.getStatusCode() == 400);
        error = true;
      } finally {
        assertTrue("Expected AmazonS3Exception for setting bucket versioning configuration to OFF", error);
      }

    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run versioningConfiguration");
    }
  }

  @Test
  public void testBucketTagging() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - buckettagging");

    BucketTaggingConfiguration bucketTaggingConfiguration = new BucketTaggingConfiguration();

    print(account + ": Getting TagSets for bucket '" + bucketName + "' when there is none");
    s3.getBucketTaggingConfiguration(bucketName);

    print(account + ": Setting TagSets for bucket '" + bucketName + "'");
    TagSet tagSet1 = new TagSet();
    for (int j = 0; j < 5; j++) {
      tagSet1.setTag("keytag" + j, "valuetag" + j);
    }
    List<TagSet> tagSetList = new ArrayList<TagSet>();
    tagSetList.add(tagSet1);
    bucketTaggingConfiguration.setTagSets(tagSetList);
    s3.setBucketTaggingConfiguration(bucketName, bucketTaggingConfiguration);

    print(account + ": Getting TagSets for bucket '" + bucketName + "'");
    List<TagSet> tagSets = bucketTaggingConfiguration.getAllTagSets();
    assertTrue("Expected 3 TagSets from bucket '" + bucketName + "', got " + tagSets.size(), tagSets.size() != 3);

    print(account + ": Deleting TagSets for bucket '" + bucketName + "'");
    s3.deleteBucketTaggingConfiguration(bucketName);

    print(account + ": Trying to set empty TagSets for bucket '" + bucketName + "'");
    bucketTaggingConfiguration = new BucketTaggingConfiguration();
    List<TagSet> negativeTagSetList = new ArrayList<TagSet>();
    TagSet negativeTagSet = new TagSet();
    tagSetList.add(negativeTagSet);
    bucketTaggingConfiguration.setTagSets(negativeTagSetList);
    try {
      s3.setBucketTaggingConfiguration(bucketName, bucketTaggingConfiguration);
    } catch (AmazonS3Exception e) {
      assertTrue("Expected StatusCode 400 found: " + e.getStatusCode(), e.getStatusCode() == 400);
      assertTrue("Expected StatusCode MalformedXML found: " + e.getErrorCode(), e.getErrorCode().equals("MalformedXML"));
    }

    print(account + ": Trying to set wrong xml TagSets for bucket '" + bucketName + "'");
    bucketTaggingConfiguration = new BucketTaggingConfiguration();
    negativeTagSetList = new ArrayList<TagSet>();
    TagSet negativeTagSet1 = new TagSet();
    negativeTagSet1.setTag("keytag1", "valuetag1");
    negativeTagSetList.add(negativeTagSet1);
    TagSet negativeTagSet2 = new TagSet();
    negativeTagSet2.setTag("keytag2", "valuetag2");
    negativeTagSetList.add(negativeTagSet2);
    bucketTaggingConfiguration.setTagSets(negativeTagSetList);
    try {
      s3.setBucketTaggingConfiguration(bucketName, bucketTaggingConfiguration);
    } catch (AmazonS3Exception e) {
      assertTrue("Expected StatusCode 400 found: " + e.getStatusCode(), e.getStatusCode() == 400);
      assertTrue("Expected StatusCode MalformedXML found: " + e.getErrorCode(), e.getErrorCode().equals("MalformedXML"));
    }

    print(account + ": Trying to set too many TagSets for bucket '" + bucketName + "'");
    List<TagSet> tooManyTagSetList = new ArrayList<>();
    TagSet tooManyTagSet = new TagSet();
    for (int j = 0; j < 11; j++) {
      tooManyTagSet.setTag("keytag" + j, "valuetag" + j);
    }
    tooManyTagSetList.add(tooManyTagSet);
    bucketTaggingConfiguration.setTagSets(tooManyTagSetList);
    try {
      s3.setBucketTaggingConfiguration(bucketName, bucketTaggingConfiguration);
    } catch (AmazonS3Exception e) {
      assertTrue("Expected StatusCode 400 found: " + e.getStatusCode(), e.getStatusCode() == 400);
      assertTrue("Expected StatusCode MalformedXML found: " + e.getErrorCode(), e.getErrorCode().equals("MalformedXML"));
    }
  }

  private void printException(AmazonServiceException ase) {
    ase.printStackTrace();
    print("Caught Exception: " + ase.getMessage());
    print("HTTP Status Code: " + ase.getStatusCode());
    print("Amazon Error Code: " + ase.getErrorCode());
    print("Request ID: " + ase.getRequestId());
  }

  private void verifyException(AmazonServiceException ase) {
    print("Caught Exception: " + ase.getMessage());
    print("HTTP Status Code: " + ase.getStatusCode());
    print("Amazon Error Code: " + ase.getErrorCode());
    print("Request ID: " + ase.getRequestId());
    assertTrue("Expected HTTP status code to be 501 but got " + ase.getStatusCode(), ase.getStatusCode() == 501);
    assertTrue("Expected AWS error code to be NotImplemented bug got " + ase.getErrorCode(), ase.getErrorCode().equals("NotImplemented"));
    assertTrue("Invalid or blank message", ase.getMessage() != null || !ase.getMessage().isEmpty());
    assertTrue("Invalid or blank request ID", ase.getRequestId() != null || !ase.getRequestId().isEmpty());
  }
}
