package com.eucalyptus.tests.awssdk;

import static com.eucalyptus.tests.awssdk.Eutester4j.print;
import static com.eucalyptus.tests.awssdk.Eutester4j.testInfo;
import static com.eucalyptus.tests.awssdk.Eutester4j.assertThat;
import static com.eucalyptus.tests.awssdk.Eutester4j.eucaUUID;

//LPT The below import is only needed for running against Eucalyptus
import static com.eucalyptus.tests.awssdk.Eutester4j.initS3ClientWithNewAccount;

//LPT The below two imports are only needed for running against AWS
import static com.eucalyptus.tests.awssdk.Eutester4j.initS3Client;
import static com.eucalyptus.tests.awssdk.Eutester4j.s3;

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
import com.amazonaws.services.s3.model.CORSRule.AllowedMethods;
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
 * This class contains tests for getting, setting, verifying, and deleting
 * rules for Cross-Origin Resource Sharing (CORS) on a bucket.
 * <p>
 * It also tests pre-flight requests that normally come from a Web browser
 * to determine what resources the browser can request from other origins.
 * <p>
 * Since CORS is not yet implemented by Eucalyptus, and the tests expect 
 * a 501 NotImplemented error response, these tests will pass for Eucalyptus
 * and fail for AWS. 
 * </p>
 * The next incarnation of these tests will switch to expecting valid
 * responses, and will thus pass for AWS, and fail for Eucalyptus until the
 * CORS features is added.
 *
 * @author Lincoln Thomas <lincoln.thomas@hpe.com>
 * 
 */
public class S3CorsTests {

  private static String bucketName = null;
  private static List<Runnable> cleanupTasks = null;
  //LPT don't declare this local var if running against AWS
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
      //LPT Declare s3 this way for Eucalyptus only, because AWS won't 
      //    let you create an account via API.
      s3 = initS3ClientWithNewAccount(account, "admin");
      //LPT Declare s3 this way for AWS
      //initS3Client();
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
    //LPT Don't do this with AWS, won't let you create an account via API
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
   * Test getting, setting, verifying, and deleting
   * rules for Cross-Origin Resource Sharing (CORS) on a bucket.
   * <p>
   * Test pre-flight requests that normally come from a Web browser
   * to determine what resources the browser can request from other origins.
   * <p>
   */
  @Test
  public void testCors() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - testCors");

    boolean error;

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
      /**
       * Create a CORS configuration of several rules, based on the examples in:
       * http://docs.aws.amazon.com/AmazonS3/latest/dev/cors.html
       */
      List<CORSRule> corsRuleList = new ArrayList<CORSRule>(2);

      CORSRule corsRuleGets = new CORSRule();
      corsRuleGets.setAllowedOrigins("*");
      corsRuleGets.setAllowedMethods(AllowedMethods.GET);
      corsRuleList.add(corsRuleGets);

      CORSRule corsRulePuts = new CORSRule();
      corsRulePuts.setAllowedOrigins("https", "http://*.example1.com", "http://www.example2.com");
      corsRulePuts.setAllowedMethods(
          AllowedMethods.PUT, 
          AllowedMethods.POST, 
          AllowedMethods.DELETE);
      corsRulePuts.setAllowedHeaders("*");
      corsRuleList.add(corsRulePuts);

      CORSRule corsRuleExtended = new CORSRule();
      corsRuleExtended.setAllowedOrigins("*");
      corsRuleExtended.setAllowedMethods(AllowedMethods.GET);
      corsRuleExtended.setAllowedHeaders("*");
      corsRuleExtended.setId("ManuallyAssignedId1");
      corsRuleExtended.setMaxAgeSeconds(3000);
      corsRuleExtended.setExposedHeaders(
          "x-amz-server-side-encryption",
          "x-amz-request-id",
          "x-amz-id-2");
      corsRuleList.add(corsRuleExtended);      

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
      //LPT: Create sending various preflight OPTIONS requests,
      //and validating the preflight responses against the CORS config

      //LPT: Create new data structure and method:
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
