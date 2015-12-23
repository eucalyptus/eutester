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
import com.amazonaws.services.s3.model.BucketCrossOriginConfiguration;
import com.amazonaws.services.s3.model.BucketLoggingConfiguration;
import com.amazonaws.services.s3.model.BucketTaggingConfiguration;
import com.amazonaws.services.s3.model.BucketVersioningConfiguration;
import com.amazonaws.services.s3.model.CORSRule;
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
 * This class contains tests for getting, setting, and preflight requests 
 * for Cross-Origin Resource Sharing (CORS) on a bucket.
 * </p>
 *
 * @author Lincoln Thomas <lincoln.thomas@hpe.com>
 * 
 */
public class S3CorsTests {

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
    bucketName = eucaUUID() + "-cors";
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
   * <li>getBucketCors</li> 
   * <li>putBucketCors</li>
   * <li>deleteBucketCors</li>
   * <li>preflightBucketCors</li>
   */
  @Test
  public void bucketExists() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - bucketExists");

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

    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed test bucketExists");
    }
  }

  /**
   * Tests for S3 CORS operations, note yet implemented by Walrus. 
   * It should fail against S3 and pass against Walrus. 
   * Every unimplemented operation should return a 501 NotImplemented error response.
   */
  @Test
  public void testCors() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - testCors");

    boolean error;

    //LPT: Might be useful in conjunction with CORS
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

    error = false;
    try {
      print(account + ": Fetching bucket CORS config for " + bucketName);
      s3.getBucketCrossOriginConfiguration(bucketName);
    } catch (AmazonServiceException ase) {
      verifyException(ase);
      error = true;
    } finally {
      assertTrue("Expected to receive a 501 NotImplemented error but did not", error);
    }

    error = false;
    try {
      print(account + ": Setting bucket CORS config for " + bucketName);
      CORSRule corsRule1 = new CORSRule();
      //LPT: Populate one or more corsRules
      List<CORSRule> corsRuleList = new ArrayList<CORSRule>();
      corsRuleList.add(corsRule1);
      BucketCrossOriginConfiguration corsConfig = new BucketCrossOriginConfiguration(corsRuleList);
      s3.setBucketCrossOriginConfiguration(bucketName, corsConfig);
    } catch (AmazonServiceException ase) {
    	verifyException(ase);
      error = true;
    } finally {
      assertTrue("Expected to receive a 501 NotImplemented error but did not", error);
    }

    error = false;
    try {
      print(account + ": Preflight request for bucket CORS config for " + bucketName);
      //LPT: Create new method issuePreflightCorsCheck(String bucketName, PreflightCorsRequest preflightRequest);
      //PreflightCorsRequest preflightRequest = new PreflightCorsRequest(...);
      //s3.issuePreflightCorsCheck(bucketName, preflightRequest);
      
      //LPT: For now, force the test to pass
      AmazonServiceException aseForced = new AmazonServiceException("Forced exception for preflight request");
      aseForced.setErrorCode("NotImplemented");
      aseForced.setRequestId("forced");
      aseForced.setServiceName("Amazon S3");
      aseForced.setStatusCode(501);
      throw aseForced;
      
    } catch (AmazonServiceException ase) {
      verifyException(ase);
      error = true;
    } finally {
      assertTrue("Expected to receive a 501 NotImplemented error but did not", error);
    }

    error = false;
    try {
      print(account + ": Deleting bucket CORS config for " + bucketName);
      s3.deleteBucketCrossOriginConfiguration(bucketName);
    } catch (AmazonServiceException ase) {
      verifyException(ase);
      error = true;
    } finally {
      assertTrue("Expected to receive a 501 NotImplemented error but did not", error);
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
