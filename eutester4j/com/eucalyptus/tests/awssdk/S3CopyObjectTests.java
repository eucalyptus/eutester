package com.eucalyptus.tests.awssdk;

import static com.eucalyptus.tests.awssdk.Eutester4j.assertThat;
import static com.eucalyptus.tests.awssdk.Eutester4j.eucaUUID;
import static com.eucalyptus.tests.awssdk.Eutester4j.initS3ClientWithNewAccount;
import static com.eucalyptus.tests.awssdk.Eutester4j.print;
import static com.eucalyptus.tests.awssdk.Eutester4j.testInfo;
import static org.testng.AssertJUnit.assertTrue;

import java.io.File;
import java.io.FileInputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.testng.annotations.AfterClass;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import com.amazonaws.AmazonServiceException;
import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.model.AccessControlList;
import com.amazonaws.services.s3.model.Bucket;
import com.amazonaws.services.s3.model.BucketVersioningConfiguration;
import com.amazonaws.services.s3.model.CannedAccessControlList;
import com.amazonaws.services.s3.model.CanonicalGrantee;
import com.amazonaws.services.s3.model.CopyObjectRequest;
import com.amazonaws.services.s3.model.CopyObjectResult;
import com.amazonaws.services.s3.model.Grant;
import com.amazonaws.services.s3.model.GroupGrantee;
import com.amazonaws.services.s3.model.ObjectMetadata;
import com.amazonaws.services.s3.model.Owner;
import com.amazonaws.services.s3.model.Permission;
import com.amazonaws.services.s3.model.PutObjectRequest;
import com.amazonaws.services.s3.model.PutObjectResult;
import com.amazonaws.services.s3.model.SetBucketVersioningConfigurationRequest;
import com.amazonaws.util.BinaryUtils;
import com.amazonaws.util.Md5Utils;

public class S3CopyObjectTests {
  private static String sourceBucket = null;
  private static String sourceKey = null;
  private static List<Runnable> cleanupTasks = null;
  private static final File fileToPut = new File("test.dat");
  private static AmazonS3 s3ClientA = null;
  private static AmazonS3 s3ClientB = null;
  private static String accountA = null;
  private static String accountB = null;
  private static String ownerNameA = null;
  private static String ownerNameB = null;
  private static String ownerIdA = null;
  private static String ownerIdB = null;
  private static String md5 = null;

  @BeforeClass
  public void init() throws Exception {
    print("### PRE SUITE SETUP - " + this.getClass().getSimpleName());

    try {
      accountA = this.getClass().getSimpleName().toLowerCase() + "a";
      accountB = this.getClass().getSimpleName().toLowerCase() + "b";
      s3ClientA = initS3ClientWithNewAccount(accountA, "admin");
      s3ClientB = initS3ClientWithNewAccount(accountB, "admin");
    } catch (Exception e) {
      try {
        teardown();
      } catch (Exception ie) {
      }
      throw e;
    }

    // s3ClientB = getS3Client("awsrc_euca");
    // s3ClientA = getS3Client("awsrc_personal");

    Owner ownerA = s3ClientA.getS3AccountOwner();
    Owner ownerB = s3ClientB.getS3AccountOwner();
    ownerNameA = ownerA.getDisplayName();
    ownerNameB = ownerB.getDisplayName();
    ownerIdA = ownerA.getId();
    ownerIdB = ownerB.getId();

    md5 = BinaryUtils.toHex(Md5Utils.computeMD5Hash(new FileInputStream(fileToPut)));
  }

  public AmazonS3 getS3Client(String credPath) throws Exception {
    print("Getting cloud information from " + credPath);

    String s3Endpoint = Eutester4j.parseEucarc(credPath, "S3_URL");

    String secretKey = Eutester4j.parseEucarc(credPath, "EC2_SECRET_KEY").replace("'", "");
    String accessKey = Eutester4j.parseEucarc(credPath, "EC2_ACCESS_KEY").replace("'", "");

    print("Initializing S3 connections");
    return Eutester4j.getS3Client(accessKey, secretKey, s3Endpoint);
  }

  @AfterClass
  public void teardown() throws Exception {
    print("### POST SUITE CLEANUP - " + this.getClass().getSimpleName());
    Eutester4j.deleteAccount(accountA);
    Eutester4j.deleteAccount(accountB);
    s3ClientA = null;
    s3ClientB = null;
  }

  @BeforeMethod
  public void setup() throws Exception {
    print("Initializing bucket name, key name and clean up tasks");
    cleanupTasks = new ArrayList<Runnable>();
    sourceBucket = eucaUUID();
    sourceKey = eucaUUID();
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

  @Test
  public void oneUserSameBucket() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - oneUserSameBucket");
    try {
      // Create bucket with Canned ACL PublicReadWrite as account A admin
      createBucketWithCannedACL(ownerNameA, s3ClientA, sourceBucket, CannedAccessControlList.PublicReadWrite);

      // Put object with Canned ACL Private in source bucket as account A admin
      putObject(ownerNameA, s3ClientA, new PutObjectRequest(sourceBucket, sourceKey, fileToPut).withCannedAcl(CannedAccessControlList.Private), md5);

      // As account A admin

      // Copy object into the same bucket and verify the ACL
      String destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA, new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey), md5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, sourceBucket, destKey, CannedAccessControlList.Private, ownerIdA, ownerIdA);

      // Copy object into the same bucket with canned ACL AuthenticatedRead and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey)
              .withCannedAccessControlList(CannedAccessControlList.AuthenticatedRead), md5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, sourceBucket, destKey, CannedAccessControlList.AuthenticatedRead, ownerIdA, ownerIdA);

      // Copy object into the same bucket with canned ACL BucketOwnerFullControl and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey)
              .withCannedAccessControlList(CannedAccessControlList.BucketOwnerFullControl), md5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, sourceBucket, destKey, CannedAccessControlList.BucketOwnerFullControl, ownerIdA, ownerIdA);

      // Copy object into the same bucket with canned ACL BucketOwnerRead and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.BucketOwnerRead),
          md5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, sourceBucket, destKey, CannedAccessControlList.BucketOwnerRead, ownerIdA, ownerIdA);

      // Copy object into the same bucket with canned ACL LogDeliveryWrite and verify the ACL
      destKey = eucaUUID();
      copyObject(
          ownerNameA,
          s3ClientA,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.LogDeliveryWrite),
          md5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, sourceBucket, destKey, CannedAccessControlList.LogDeliveryWrite, ownerIdA, ownerIdA);

      // Copy object into the same bucket with canned ACL Private and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.Private), md5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, sourceBucket, destKey, CannedAccessControlList.Private, ownerIdA, ownerIdA);

      // Copy object into the same bucket with canned ACL PublicRead and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicRead), md5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, sourceBucket, destKey, CannedAccessControlList.PublicRead, ownerIdA, ownerIdA);

      // Copy object into the same bucket with canned ACL PublicReadWrite and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicReadWrite),
          md5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, sourceBucket, destKey, CannedAccessControlList.PublicReadWrite, ownerIdA, ownerIdA);
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run oneUserSameBucket");
    }
  }

  @Test
  public void oneUserDifferentBuckets() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - oneUserDifferentBuckets");
    try {
      // Create bucket with Canned ACL PublicReadWrite as account A admin
      createBucketWithCannedACL(ownerNameA, s3ClientA, sourceBucket, CannedAccessControlList.PublicReadWrite);

      // Put object with Canned ACL Private in source bucket as account A admin
      putObject(ownerNameA, s3ClientA, new PutObjectRequest(sourceBucket, sourceKey, fileToPut).withCannedAcl(CannedAccessControlList.Private), md5);

      // Create bucket with Canned ACL Private as account A admin
      String destBucket = eucaUUID();
      createBucketWithCannedACL(ownerNameA, s3ClientA, destBucket, CannedAccessControlList.Private);

      // As account A admin

      // Copy object into the different bucket and verify the ACL
      String destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA, new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey), md5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, destBucket, destKey, CannedAccessControlList.Private, ownerIdA, ownerIdA);

      // Copy object into a different bucket with canned ACL AuthenticatedRead and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.AuthenticatedRead),
          md5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, destBucket, destKey, CannedAccessControlList.AuthenticatedRead, ownerIdA, ownerIdA);

      // Copy object into a different bucket with canned ACL BucketOwnerFullControl and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey)
              .withCannedAccessControlList(CannedAccessControlList.BucketOwnerFullControl), md5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, destBucket, destKey, CannedAccessControlList.BucketOwnerFullControl, ownerIdA, ownerIdA);

      // Copy object into a different bucket with canned ACL BucketOwnerRead and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.BucketOwnerRead),
          md5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, destBucket, destKey, CannedAccessControlList.BucketOwnerRead, ownerIdA, ownerIdA);

      // Copy object into a different bucket with canned ACL LogDeliveryWrite and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.LogDeliveryWrite),
          md5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, destBucket, destKey, CannedAccessControlList.LogDeliveryWrite, ownerIdA, ownerIdA);

      // Copy object into a different bucket with canned ACL Private and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.Private), md5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, destBucket, destKey, CannedAccessControlList.Private, ownerIdA, ownerIdA);

      // Copy object into a different bucket with canned ACL PublicRead and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicRead), md5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, destBucket, destKey, CannedAccessControlList.PublicRead, ownerIdA, ownerIdA);

      // Copy object into a different bucket with canned ACL PublicReadWrite and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicReadWrite),
          md5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, destBucket, destKey, CannedAccessControlList.PublicReadWrite, ownerIdA, ownerIdA);
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run oneUserDifferentBuckets");
    }
  }

  @Test
  public void multipleUsersSameBucket() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - multipleUsersSameBucket");
    try {
      // Create bucket with Canned ACL PublicReadWrite as account A admin
      createBucketWithCannedACL(ownerNameA, s3ClientA, sourceBucket, CannedAccessControlList.PublicReadWrite);

      // Put object with Canned ACL AuthenticatedRead in source bucket as account A admin
      putObject(ownerNameA, s3ClientA,
          new PutObjectRequest(sourceBucket, sourceKey, fileToPut).withCannedAcl(CannedAccessControlList.AuthenticatedRead), md5);

      // As account B admin

      // Copy object into the same bucket and verify the ACL
      String destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB, new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey), md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, sourceBucket, destKey, CannedAccessControlList.Private, ownerIdB, ownerIdA);

      // Copy object into the same bucket with canned ACL AuthenticatedRead and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey)
              .withCannedAccessControlList(CannedAccessControlList.AuthenticatedRead), md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, sourceBucket, destKey, CannedAccessControlList.AuthenticatedRead, ownerIdB, ownerIdA);

      // Copy object into the same bucket with canned ACL BucketOwnerFullControl and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey)
              .withCannedAccessControlList(CannedAccessControlList.BucketOwnerFullControl), md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, sourceBucket, destKey, CannedAccessControlList.BucketOwnerFullControl, ownerIdB, ownerIdA);

      // Copy object into the same bucket with canned ACL BucketOwnerRead and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.BucketOwnerRead),
          md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, sourceBucket, destKey, CannedAccessControlList.BucketOwnerRead, ownerIdB, ownerIdA);

      // Copy object into the same bucket with canned ACL LogDeliveryWrite and verify the ACL
      destKey = eucaUUID();
      copyObject(
          ownerNameB,
          s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.LogDeliveryWrite),
          md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, sourceBucket, destKey, CannedAccessControlList.LogDeliveryWrite, ownerIdB, ownerIdA);

      // Copy object into the same bucket with canned ACL Private and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.Private), md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, sourceBucket, destKey, CannedAccessControlList.Private, ownerIdB, ownerIdA);

      // Copy object into the same bucket with canned ACL PublicRead and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicRead), md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, sourceBucket, destKey, CannedAccessControlList.PublicRead, ownerIdB, ownerIdA);

      // Copy object into the same bucket with canned ACL PublicReadWrite and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicReadWrite),
          md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, sourceBucket, destKey, CannedAccessControlList.PublicReadWrite, ownerIdB, ownerIdA);
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run multipleUsersSameBucket");
    }
  }

  @Test
  public void nonCannedACLInHeader() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - nonCannedACLInHeader");
    try {
      // Construct acl equivalent to canned acl PublicReadWrite
      AccessControlList acl = new AccessControlList();
      acl.getGrants().add(new Grant(GroupGrantee.AllUsers, Permission.Read));
      acl.getGrants().add(new Grant(GroupGrantee.AllUsers, Permission.Write));

      // Create bucket with acl equivalent of Canned ACL PublicReadWrite as account A admin
      createBucketWithACL(ownerNameA, s3ClientA, sourceBucket, acl);

      // Construct acl equivalent to canned acl authenticated-read
      acl = new AccessControlList();
      acl.getGrants().add(new Grant(GroupGrantee.AuthenticatedUsers, Permission.Read));

      // Put object with acl equivalent of Canned ACL AuthenticatedRead in source bucket as account A admin
      putObject(ownerNameA, s3ClientA, new PutObjectRequest(sourceBucket, sourceKey, fileToPut).withAccessControlList(acl), md5);

      // As account B admin
      Grant ownerGrant = new Grant(new CanonicalGrantee(ownerIdB), Permission.FullControl);

      // Copy object into the same bucket with acl equivalent of canned ACL AuthenticatedRead and verify the ACL
      acl = new AccessControlList();
      acl.getGrants().add(new Grant(GroupGrantee.AuthenticatedUsers, Permission.Read));
      String destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB, new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withAccessControlList(acl), md5);
      acl.getGrants().add(ownerGrant);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, sourceBucket, destKey, acl, ownerIdB);

      // Copy object into the same bucket with acl equivalent of canned ACL BucketOwnerFullControl and verify the ACL
      acl = new AccessControlList();
      acl.getGrants().add(new Grant(new CanonicalGrantee(ownerIdA), Permission.FullControl));
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB, new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withAccessControlList(acl), md5);
      acl.getGrants().add(ownerGrant);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, sourceBucket, destKey, acl, ownerIdB);

      // Copy object into the same bucket with acl equivalent of canned ACL BucketOwnerRead and verify the ACL
      acl = new AccessControlList();
      acl.getGrants().add(new Grant(new CanonicalGrantee(ownerIdA), Permission.Read));
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB, new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withAccessControlList(acl), md5);
      acl.getGrants().add(ownerGrant);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, sourceBucket, destKey, acl, ownerIdB);

      // Copy object into the same bucket with acl equivalent of canned ACL LogDeliveryWrite and verify the ACL
      acl = new AccessControlList();
      acl.getGrants().add(new Grant(GroupGrantee.LogDelivery, Permission.Write));
      acl.getGrants().add(new Grant(GroupGrantee.LogDelivery, Permission.ReadAcp));
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB, new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withAccessControlList(acl), md5);
      acl.getGrants().add(ownerGrant);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, sourceBucket, destKey, acl, ownerIdB);

      // Copy object into the same bucket with acl equivalent of canned ACL Private and verify the ACL
      acl = new AccessControlList();
      acl.getGrants().add(ownerGrant);
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.Private), md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, sourceBucket, destKey, acl, ownerIdB);

      // Copy object into the same bucket with acl equivalent of canned ACL PublicRead and verify the ACL
      acl = new AccessControlList();
      acl.getGrants().add(new Grant(GroupGrantee.AllUsers, Permission.Read));
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB, new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withAccessControlList(acl), md5);
      acl.getGrants().add(ownerGrant);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, sourceBucket, destKey, acl, ownerIdB);

      // Copy object into the same bucket with acl equivalent of canned ACL PublicReadWrite and verify the ACL
      acl = new AccessControlList();
      acl.getGrants().add(new Grant(GroupGrantee.AllUsers, Permission.Read));
      acl.getGrants().add(new Grant(GroupGrantee.AllUsers, Permission.Write));
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB, new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withAccessControlList(acl), md5);
      acl.getGrants().add(ownerGrant);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, sourceBucket, destKey, acl, ownerIdB);
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run nonCannedACLInHeader");
    }
  }

  @Test
  public void multipleUsersDifferentBuckets1() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - multipleUsersDifferentBuckets1");
    try {
      // Create bucket with Canned ACL Private as account A admin
      createBucketWithCannedACL(ownerNameA, s3ClientA, sourceBucket, CannedAccessControlList.Private);

      // Put object with Canned ACL AuthenticatedRead in source bucket as account A admin
      putObject(ownerNameA, s3ClientA,
          new PutObjectRequest(sourceBucket, sourceKey, fileToPut).withCannedAcl(CannedAccessControlList.AuthenticatedRead), md5);

      // Create bucket with Canned ACL Private as account B admin
      String destBucket = eucaUUID();
      createBucketWithCannedACL(ownerNameB, s3ClientB, destBucket, CannedAccessControlList.Private);

      // As account B admin

      // Copy object into the same bucket and verify the ACL
      String destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB, new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey), md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, destBucket, destKey, CannedAccessControlList.Private, ownerIdB, ownerIdB);

      // Copy object into the same bucket with canned ACL AuthenticatedRead and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.AuthenticatedRead),
          md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, destBucket, destKey, CannedAccessControlList.AuthenticatedRead, ownerIdB, ownerIdB);

      // Copy object into the same bucket with canned ACL BucketOwnerFullControl and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey)
              .withCannedAccessControlList(CannedAccessControlList.BucketOwnerFullControl), md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, destBucket, destKey, CannedAccessControlList.BucketOwnerFullControl, ownerIdB, ownerIdB);

      // Copy object into the same bucket with canned ACL BucketOwnerRead and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.BucketOwnerRead),
          md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, destBucket, destKey, CannedAccessControlList.BucketOwnerRead, ownerIdB, ownerIdB);

      // Copy object into the same bucket with canned ACL LogDeliveryWrite and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.LogDeliveryWrite),
          md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, destBucket, destKey, CannedAccessControlList.LogDeliveryWrite, ownerIdB, ownerIdB);

      // Copy object into the same bucket with canned ACL Private and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.Private), md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, destBucket, destKey, CannedAccessControlList.Private, ownerIdB, ownerIdB);

      // Copy object into the same bucket with canned ACL PublicRead and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicRead), md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, destBucket, destKey, CannedAccessControlList.PublicRead, ownerIdB, ownerIdB);

      // Copy object into the same bucket with canned ACL PublicReadWrite and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicReadWrite),
          md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, destBucket, destKey, CannedAccessControlList.PublicReadWrite, ownerIdB, ownerIdB);
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run multipleUsersDifferentBuckets1");
    }
  }

  @Test
  public void multipleUsersDifferentBuckets2() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - multipleUsersDifferentBuckets2");
    try {
      // Create bucket with Canned ACL Private as account A admin
      createBucketWithCannedACL(ownerNameA, s3ClientA, sourceBucket, CannedAccessControlList.Private);

      // Put object with Canned ACL AuthenticatedRead in source bucket as account A admin
      putObject(ownerNameA, s3ClientA,
          new PutObjectRequest(sourceBucket, sourceKey, fileToPut).withCannedAcl(CannedAccessControlList.AuthenticatedRead), md5);

      // Create bucket with Canned ACL PublicReadWrite as account A admin
      String destBucket = eucaUUID();
      createBucketWithCannedACL(ownerNameA, s3ClientA, destBucket, CannedAccessControlList.PublicReadWrite);

      // As account B admin

      // Copy object into the same bucket and verify the ACL
      String destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB, new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey), md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, destBucket, destKey, CannedAccessControlList.Private, ownerIdB, ownerIdA);

      // Copy object into the same bucket with canned ACL AuthenticatedRead and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.AuthenticatedRead),
          md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, destBucket, destKey, CannedAccessControlList.AuthenticatedRead, ownerIdB, ownerIdA);

      // Copy object into the same bucket with canned ACL BucketOwnerFullControl and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey)
              .withCannedAccessControlList(CannedAccessControlList.BucketOwnerFullControl), md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, destBucket, destKey, CannedAccessControlList.BucketOwnerFullControl, ownerIdB, ownerIdA);

      // Copy object into the same bucket with canned ACL BucketOwnerRead and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.BucketOwnerRead),
          md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, destBucket, destKey, CannedAccessControlList.BucketOwnerRead, ownerIdB, ownerIdA);

      // Copy object into the same bucket with canned ACL LogDeliveryWrite and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.LogDeliveryWrite),
          md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, destBucket, destKey, CannedAccessControlList.LogDeliveryWrite, ownerIdB, ownerIdA);

      // Copy object into the same bucket with canned ACL Private and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.Private), md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, destBucket, destKey, CannedAccessControlList.Private, ownerIdB, ownerIdA);

      // Copy object into the same bucket with canned ACL PublicRead and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicRead), md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, destBucket, destKey, CannedAccessControlList.PublicRead, ownerIdB, ownerIdA);

      // Copy object into the same bucket with canned ACL PublicReadWrite and verify the ACL
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicReadWrite),
          md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, destBucket, destKey, CannedAccessControlList.PublicReadWrite, ownerIdB, ownerIdA);
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run multipleUsersDifferentBuckets2");
    }
  }

  @Test
  public void accessDeniedCheck() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - accessDeniedCheck");
    try {
      // Create bucket with Canned ACL Private as account A admin
      createBucketWithCannedACL(ownerNameA, s3ClientA, sourceBucket, CannedAccessControlList.Private);

      // Put object with Canned ACL PublicRead in source bucket as account A admin
      putObject(ownerNameA, s3ClientA, new PutObjectRequest(sourceBucket, sourceKey, fileToPut).withCannedAcl(CannedAccessControlList.PublicRead),
          md5);

      // Create bucket with Canned ACL LogDeliveryWrite as account A admin
      String destBucket = eucaUUID();
      createBucketWithCannedACL(ownerNameA, s3ClientA, destBucket, CannedAccessControlList.LogDeliveryWrite);

      // As account B admin copy object into the same bucket and verify the error
      boolean error = false;
      try {
        String destKey = eucaUUID();
        copyObject(ownerNameB, s3ClientB, new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey), md5);
      } catch (AmazonServiceException ase) {
        error = true;
        printException(ase);
        assertTrue("Expected 403 error but got " + ase.getStatusCode(), ase.getStatusCode() == 403);
        assertTrue("Expected S3 error AccessDenied but got " + ase.getErrorCode(), ase.getErrorCode().equals("AccessDenied"));
      } finally {
        assertTrue("Expected 403 AccessDenied error", error);
      }
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run accessDeniedCheck");
    }
  }

  @Test
  public void etagConstraint() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - etagConstraint");
    try {
      // Create bucket with Canned ACL Private as account A admin
      createBucketWithCannedACL(ownerNameA, s3ClientA, sourceBucket, CannedAccessControlList.Private);

      // Put object with Canned ACL Private in source bucket as account A admin
      PutObjectResult putResult =
          putObject(ownerNameA, s3ClientA, new PutObjectRequest(sourceBucket, sourceKey, fileToPut).withCannedAcl(CannedAccessControlList.Private),
              md5);

      // Copy object with matching etag
      String destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withMatchingETagConstraint(putResult.getETag()), md5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, sourceBucket, destKey, CannedAccessControlList.Private, ownerIdA, ownerIdA);

      // Try to copy object with matching etag constraint but supply with non-matching etag
      destKey = eucaUUID();
      CopyObjectRequest copyRequest = new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withMatchingETagConstraint(eucaUUID());
      printCopyObjectRequest(ownerNameA, copyRequest);
      CopyObjectResult copyResult = s3ClientA.copyObject(copyRequest);
      assertTrue("Expected an invalid copy object result", copyResult == null);

      // Copy object with non-matching etag constraint
      destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withNonmatchingETagConstraint(eucaUUID()), md5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, sourceBucket, destKey, CannedAccessControlList.Private, ownerIdA, ownerIdA);

      // Try to copy object with non-matching etag constraint but supply with matching etag
      destKey = eucaUUID();
      copyRequest = new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withNonmatchingETagConstraint(putResult.getETag());
      printCopyObjectRequest(ownerNameA, copyRequest);
      copyResult = s3ClientA.copyObject(copyRequest);
      assertTrue("Expected an invalid copy object result", copyResult == null);
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run etagConstraint");
    }
  }

  @Test
  public void lastModifiedConstraint() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - lastModifiedConstraint");
    try {
      // Get a timestamp before the put
      Date beforePut = new Date(new Date().getTime() - 10000000);

      // Create bucket with Canned ACL Private as account B admin
      createBucketWithCannedACL(ownerNameB, s3ClientB, sourceBucket, CannedAccessControlList.Private);

      // Put object with Canned ACL Private in source bucket as account B admin
      putObject(ownerNameB, s3ClientB, new PutObjectRequest(sourceBucket, sourceKey, fileToPut).withCannedAcl(CannedAccessControlList.Private), md5);

      // Get a timestamp after the put
      Date afterPut = new Date(new Date().getTime() + 10000000);

      // Copy object with modified since date set to before the source object was created
      String destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB, new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withModifiedSinceConstraint(beforePut),
          md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, sourceBucket, destKey, CannedAccessControlList.Private, ownerIdB, ownerIdB);

      // Try to copy object with modified since constraint but supply with timestamp after the source object was created
      destKey = eucaUUID();
      CopyObjectRequest copyRequest = new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withModifiedSinceConstraint(afterPut);
      printCopyObjectRequest(ownerNameB, copyRequest);
      CopyObjectResult copyResult = s3ClientB.copyObject(copyRequest);
      assertTrue("Expected an invalid copy object result", copyResult == null);

      // Copy object with unmodified since date set to after the source object was created
      destKey = eucaUUID();
      copyObject(ownerNameB, s3ClientB,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withUnmodifiedSinceConstraint(afterPut), md5);
      S3Utils.verifyObjectACL(s3ClientB, ownerNameB, sourceBucket, destKey, CannedAccessControlList.Private, ownerIdB, ownerIdB);

      // Try to copy object with unmodified since constraint but supply with timestamp before the source object was created
      destKey = eucaUUID();
      copyRequest = new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withUnmodifiedSinceConstraint(beforePut);
      printCopyObjectRequest(ownerNameB, copyRequest);
      copyResult = s3ClientB.copyObject(copyRequest);
      assertTrue("Expected an invalid copy object result", copyResult == null);
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run lastModifiedConstraint");
    }
  }

  @Test
  public void metadataDirective() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - metadataDirective");
    try {
      // Create bucket with Canned ACL Private as account A admin
      createBucketWithCannedACL(ownerNameA, s3ClientA, sourceBucket, CannedAccessControlList.Private);

      // Put object with Canned ACL Private and some metadata in source bucket as account A admin
      ObjectMetadata om = new ObjectMetadata();
      Map<String, String> userMetadataMap = new HashMap<String, String>();
      userMetadataMap.put("somerandomkey", "somerandomvalue");
      userMetadataMap.put("hello", "world");
      om.setUserMetadata(userMetadataMap);
      putObject(ownerNameA, s3ClientA, new PutObjectRequest(sourceBucket, sourceKey, fileToPut).withCannedAcl(CannedAccessControlList.Private)
          .withMetadata(om), md5);

      // Copy both object and metadata - default behavior
      String destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA, new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey), md5);
      verifyUserMetadata(ownerNameA, s3ClientA, sourceBucket, destKey, userMetadataMap);

      // Copy object and replace metadata
      om = new ObjectMetadata();
      userMetadataMap = new HashMap<String, String>();
      userMetadataMap.put("foo", "bar");
      userMetadataMap.put("more", "stuff");
      om.setUserMetadata(userMetadataMap);
      destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA, new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withNewObjectMetadata(om), md5);
      verifyUserMetadata(ownerNameA, s3ClientA, sourceBucket, destKey, userMetadataMap);
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run metadataDirective");
    }
  }

  @Test
  public void metadataDirective_SameObject() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - metadataDirective_SameObject");
    try {
      // Create bucket with Canned ACL Private as account B admin
      createBucketWithCannedACL(ownerNameB, s3ClientB, sourceBucket, CannedAccessControlList.Private);

      // Put object with Canned ACL Private and some metadata in source bucket as account B admin
      ObjectMetadata om = new ObjectMetadata();
      Map<String, String> userMetadataMap = new HashMap<String, String>();
      userMetadataMap.put("somerandomkey", "somerandomvalue");
      userMetadataMap.put("hello", "world");
      om.setUserMetadata(userMetadataMap);
      putObject(ownerNameB, s3ClientB, new PutObjectRequest(sourceBucket, sourceKey, fileToPut).withCannedAcl(CannedAccessControlList.Private)
          .withMetadata(om), md5);

      // Copy object on to itself and replace metadata
      om = new ObjectMetadata();
      userMetadataMap = new HashMap<String, String>();
      userMetadataMap.put("foo", "bar");
      userMetadataMap.put("more", "stuff");
      om.setUserMetadata(userMetadataMap);
      copyObject(ownerNameB, s3ClientB, new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, sourceKey).withNewObjectMetadata(om), md5);
      verifyUserMetadata(ownerNameB, s3ClientB, sourceBucket, sourceKey, userMetadataMap);

      // Copy object on to itself without replacing metadata, should throw an error
      boolean error = false;
      try {
        copyObject(ownerNameB, s3ClientB, new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, sourceKey), md5);
      } catch (AmazonServiceException ase) {
        error = true;
        printException(ase);
        assertTrue("Expected 400 error but got " + ase.getStatusCode(), ase.getStatusCode() == 400);
        assertTrue("Expected S3 error InvalidRequest but got " + ase.getErrorCode(), ase.getErrorCode().equals("InvalidRequest"));
      } finally {
        assertTrue("Expected 400 InvalidRequest error", error);
      }
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run metadataDirective_SameObject");
    }
  }

  @Test
  public void versionedBuckets() throws Exception {
    try {
      testInfo(this.getClass().getSimpleName() + " - versionedBuckets");
      File anotherFile = new File("3wolfmoon-download.jpg");
      String newMd5 = BinaryUtils.toHex(Md5Utils.computeMD5Hash(new FileInputStream(anotherFile)));

      // Create bucket with Canned ACL PublicReadWrite as account A admin and enable versioning
      createBucketWithCannedACL(ownerNameA, s3ClientA, sourceBucket, CannedAccessControlList.Private);
      print(ownerNameA + ": Enabling versioning for bucket " + sourceBucket);
      s3ClientA.setBucketVersioningConfiguration(new SetBucketVersioningConfigurationRequest(sourceBucket, new BucketVersioningConfiguration()
          .withStatus(BucketVersioningConfiguration.ENABLED)));

      // Put modified object with Canned ACL Private and some metadata in source bucket as account B admin
      PutObjectResult putResult1 =
          putObject(ownerNameA, s3ClientA, new PutObjectRequest(sourceBucket, sourceKey, anotherFile).withCannedAcl(CannedAccessControlList.Private),
              newMd5);

      // Put object with Canned ACL Private and some metadata in source bucket as account B admin
      PutObjectResult putResult2 =
          putObject(ownerNameA, s3ClientA, new PutObjectRequest(sourceBucket, sourceKey, fileToPut).withCannedAcl(CannedAccessControlList.Private),
              md5);

      // Copy object from first version
      String destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withSourceVersionId(putResult1.getVersionId())
              .withCannedAccessControlList(CannedAccessControlList.LogDeliveryWrite), newMd5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, sourceBucket, destKey, CannedAccessControlList.LogDeliveryWrite, ownerIdA, ownerIdA);

      // Copy object from second version
      destKey = eucaUUID();
      copyObject(ownerNameA, s3ClientA,
          new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withSourceVersionId(putResult2.getVersionId())
              .withCannedAccessControlList(CannedAccessControlList.PublicRead), md5);
      S3Utils.verifyObjectACL(s3ClientA, ownerNameA, sourceBucket, destKey, CannedAccessControlList.PublicRead, ownerIdA, ownerIdA);

    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run versionedBuckets");
    }
  }

  private void printException(AmazonServiceException ase) {
    ase.printStackTrace();
    print("Caught Exception: " + ase.getMessage());
    print("HTTP Status Code: " + ase.getStatusCode());
    print("Amazon Error Code: " + ase.getErrorCode());
  }

  private void createBucketWithCannedACL(final String accountName, final AmazonS3 s3, final String bucketName, CannedAccessControlList cannedACL)
      throws Exception {
    Bucket bucket = S3Utils.createBucketWithCannedACL(s3, accountName, bucketName, cannedACL, S3Utils.BUCKET_CREATION_RETRIES);
    cleanupTasks.add(new Runnable() {
      @Override
      public void run() {
        print(accountName + ": Deleting bucket " + bucketName);
        s3.deleteBucket(bucketName);
      }
    });
    assertTrue("Invalid reference to bucket", bucket != null);
    assertTrue("Mismatch in bucket names. Expected bucket name to be " + bucketName + ", but got " + bucket.getName(),
        bucketName.equals(bucket.getName()));
  }

  private void createBucketWithACL(final String accountName, final AmazonS3 s3, final String bucketName, AccessControlList acl) throws Exception {
    Bucket bucket = S3Utils.createBucketWithACL(s3, accountName, bucketName, acl, S3Utils.BUCKET_CREATION_RETRIES);
    cleanupTasks.add(new Runnable() {
      @Override
      public void run() {
        print(accountName + ": Deleting bucket " + bucketName);
        s3.deleteBucket(bucketName);
      }
    });
    assertTrue("Invalid reference to bucket", bucket != null);
    assertTrue("Mismatch in bucket names. Expected bucket name to be " + bucketName + ", but got " + bucket.getName(),
        bucketName.equals(bucket.getName()));
  }

  private PutObjectResult putObject(final String accountName, final AmazonS3 s3, final PutObjectRequest putRequest, String sourceMd5) {
    printPutObjectRequest(accountName, putRequest);
    final PutObjectResult putResult = s3.putObject(putRequest);
    cleanupTasks.add(new Runnable() {
      @Override
      public void run() {
        if (putResult.getVersionId() == null) {
          print(accountName + ": Deleting object " + putRequest.getKey() + " from bucket " + putRequest.getBucketName());
          s3.deleteObject(putRequest.getBucketName(), putRequest.getKey());
        } else {
          print(accountName + ": Deleting object " + putRequest.getKey() + ", version " + putResult.getVersionId() + " from bucket "
              + putRequest.getBucketName());
          s3.deleteVersion(putRequest.getBucketName(), putRequest.getKey(), putResult.getVersionId());
        }
      }
    });
    assertTrue("Invalid put object result", putResult != null);
    assertTrue("Mimatch in md5sums between original object and PUT result. Expected " + sourceMd5 + ", but got " + putResult.getETag(),
        putResult.getETag() != null && putResult.getETag().equals(sourceMd5));
    return putResult;
  }

  private void printPutObjectRequest(String accountName, PutObjectRequest putRequest) {
    StringBuilder sb = new StringBuilder(accountName + ": Putting object with key=" + putRequest.getKey() + ", bucket=" + putRequest.getBucketName());

    if (putRequest.getCannedAcl() != null) {
      sb.append(", canned ACL=").append(putRequest.getCannedAcl());
    }
    if (putRequest.getMetadata() != null) {
      if (putRequest.getMetadata().getUserMetadata() != null) {
        sb.append(", user metadata=").append(putRequest.getMetadata().getUserMetadata());
      }
    }
    print(sb.toString());
  }

  private CopyObjectResult copyObject(final String accountName, final AmazonS3 s3, final CopyObjectRequest copyRequest, String sourceMd5)
      throws Exception {
    printCopyObjectRequest(accountName, copyRequest);
    final CopyObjectResult copyResult = s3.copyObject(copyRequest);
    cleanupTasks.add(new Runnable() {
      @Override
      public void run() {
        if (copyResult.getVersionId() == null) {
          print(accountName + ": Deleting object " + copyRequest.getDestinationKey() + " from bucket " + copyRequest.getDestinationBucketName());
          s3.deleteObject(copyRequest.getDestinationBucketName(), copyRequest.getDestinationKey());
        } else {
          print(accountName + ": Deleting object " + copyRequest.getDestinationKey() + ", version " + copyResult.getVersionId() + " from bucket "
              + copyRequest.getDestinationBucketName());
          s3.deleteVersion(copyRequest.getDestinationBucketName(), copyRequest.getDestinationKey(), copyResult.getVersionId());
        }
      }
    });
    assertTrue("Invalid copy object result", copyResult != null);
    assertTrue("Mimatch in md5sums between original object and copy result. Expected " + sourceMd5 + ", but got " + copyResult.getETag(),
        copyResult.getETag() != null && copyResult.getETag().equals(sourceMd5));

    return copyResult;
  }

  private void printCopyObjectRequest(String accountName, CopyObjectRequest copyRequest) {
    StringBuilder sb =
        new StringBuilder(accountName + ": Copying object with source key=" + copyRequest.getSourceKey() + ", source bucket="
            + copyRequest.getSourceBucketName() + ", destination key=" + copyRequest.getDestinationKey() + ", destination bucket="
            + copyRequest.getDestinationBucketName());

    if (copyRequest.getCannedAccessControlList() != null) {
      sb.append(", canned ACL=").append(copyRequest.getCannedAccessControlList());
    }
    if (copyRequest.getMatchingETagConstraints() != null && !copyRequest.getMatchingETagConstraints().isEmpty()) {
      sb.append(", matching etag constraint=").append(copyRequest.getMatchingETagConstraints());
    }
    if (copyRequest.getModifiedSinceConstraint() != null) {
      sb.append(", modified since constraint=").append(copyRequest.getModifiedSinceConstraint());
    }
    if (copyRequest.getNonmatchingETagConstraints() != null && !copyRequest.getNonmatchingETagConstraints().isEmpty()) {
      sb.append(", non matching etag constraint=").append(copyRequest.getNonmatchingETagConstraints());
    }
    if (copyRequest.getSourceVersionId() != null) {
      sb.append(", version ID=").append(copyRequest.getSourceVersionId());
    }
    if (copyRequest.getUnmodifiedSinceConstraint() != null) {
      sb.append(", unmodified since constraint=").append(copyRequest.getUnmodifiedSinceConstraint());
    }

    print(sb.toString());
  }

  private void verifyUserMetadata(String ownerName, AmazonS3 s3, String bucket, String key, Map<String, String> metadataMap) {
    print(ownerName + ": Getting metadata for object key=" + key + ", bucket=" + bucket);
    ObjectMetadata metadata = s3.getObjectMetadata(bucket, key);
    assertTrue("Invalid object metadata", metadata != null);
    if (metadataMap != null && !metadataMap.isEmpty()) {
      assertTrue("No user metadata found", metadata.getUserMetadata() != null || !metadata.getUserMetadata().isEmpty());
      assertTrue("Expected to find " + metadataMap.size() + " element(s) in the metadata but found " + metadata.getUserMetadata().size(),
          metadataMap.size() == metadata.getUserMetadata().size());
      for (Map.Entry<String, String> entry : metadataMap.entrySet()) {
        assertTrue("Metadata key " + entry.getKey() + " not found in response", metadata.getUserMetadata().containsKey(entry.getKey()));
        assertTrue(
            "Expected metadata value for key " + entry.getKey() + " to be " + entry.getValue() + " but got "
                + metadata.getUserMetadata().get(entry.getKey()), metadata.getUserMetadata().get(entry.getKey()).equals(entry.getValue()));
      }
    }
  }
}
