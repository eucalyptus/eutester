package com.eucalyptus.tests.awssdk;

import static com.eucalyptus.tests.awssdk.Eutester4j.assertThat;
import static com.eucalyptus.tests.awssdk.Eutester4j.initS3ClientWithNewAccount;
import static com.eucalyptus.tests.awssdk.Eutester4j.print;
import static com.eucalyptus.tests.awssdk.Eutester4j.testInfo;
import static org.testng.AssertJUnit.assertTrue;

import java.io.File;
import java.io.FileInputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Random;
import java.util.UUID;

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
import com.amazonaws.services.s3.model.DeleteObjectsRequest;
import com.amazonaws.services.s3.model.DeleteObjectsRequest.KeyVersion;
import com.amazonaws.services.s3.model.DeleteObjectsResult;
import com.amazonaws.services.s3.model.DeleteObjectsResult.DeletedObject;
import com.amazonaws.services.s3.model.ListVersionsRequest;
import com.amazonaws.services.s3.model.MultiObjectDeleteException;
import com.amazonaws.services.s3.model.MultiObjectDeleteException.DeleteError;
import com.amazonaws.services.s3.model.Owner;
import com.amazonaws.services.s3.model.Permission;
import com.amazonaws.services.s3.model.PutObjectRequest;
import com.amazonaws.services.s3.model.PutObjectResult;
import com.amazonaws.services.s3.model.S3VersionSummary;
import com.amazonaws.services.s3.model.SetBucketVersioningConfigurationRequest;
import com.amazonaws.services.s3.model.VersionListing;
import com.amazonaws.util.BinaryUtils;
import com.amazonaws.util.Md5Utils;

/**
 * 
 * @author Swathi Gangisetty
 * 
 */
public class S3ObjectMultiDeleteTests {

  private static String bucketName = null;
  private static List<Runnable> cleanupTasks = null;
  private static final File fileToPut = new File("test.dat");
  private static AmazonS3 s3ClientA = null;
  private static AmazonS3 s3ClientB = null;
  private static String accountA = null;
  private static String accountB = null;
  private static Owner ownerA = null;
  private static Owner ownerB = null;
  private static String ownerNameA = null;
  private static String ownerNameB = null;
  private static String ownerIdA = null;
  private static String ownerIdB = null;
  private static String md5_orig = null;
  private static Random random = new Random();

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

    ownerA = s3ClientA.getS3AccountOwner();
    ownerB = s3ClientB.getS3AccountOwner();
    ownerNameA = ownerA.getDisplayName();
    ownerNameB = ownerB.getDisplayName();
    ownerIdA = ownerA.getId();
    ownerIdB = ownerB.getId();

    md5_orig = BinaryUtils.toHex(Md5Utils.computeMD5Hash(new FileInputStream(fileToPut)));
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
    print("Initializing bucket name and clean up tasks");
    bucketName = UUID.randomUUID().toString().replaceAll("-", "");;
    cleanupTasks = new ArrayList<Runnable>();
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
  public void singleAccountVerbose() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - singleAccountVerbose");

    try {
      int maxKeys = 2 + random.nextInt(3); // Max keys 2-4

      /* Create bucket with Canned ACL Private */
      createBucket(s3ClientA, ownerNameA, bucketName, CannedAccessControlList.Private, ownerIdA);

      List<KeyVersion> keyVerList = new ArrayList<KeyVersion>();
      List<DeletedObject> expectedDelObjList = new ArrayList<DeletedObject>();

      /* Put objects */
      for (int i = 1; i <= maxKeys; i++) {
        String key = UUID.randomUUID().toString().replaceAll("-", "");
        putObject(s3ClientA, ownerNameA, bucketName, key);
        keyVerList.add(new KeyVersion(key));
        DeletedObject delObj = new DeletedObject();
        delObj.setKey(key);
        expectedDelObjList.add(delObj);
      }

      /* Multi delete objects verbosely */
      DeleteObjectsResult deleteObjectsResult = deleteObjects(s3ClientA, ownerNameA, bucketName, false, keyVerList);

      /* Verify deleted objects result set */
      verifyDeletedObjectsResults(deleteObjectsResult, expectedDelObjList);

      /* Verify bucket is empty */
      verifyBucketIsEmpty(s3ClientA, ownerNameA, bucketName);
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run singleAccountVerbose");
    }
  }

  @Test
  public void singleAccountQuiet() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - singleAccountQuiet");

    try {
      int maxKeys = 2 + random.nextInt(3); // Max keys 2-4

      /* Create bucket with Canned ACL Private */
      createBucket(s3ClientB, ownerNameB, bucketName, CannedAccessControlList.Private, ownerIdB);

      List<KeyVersion> keyVerList = new ArrayList<KeyVersion>();
      List<DeletedObject> expectedDelObjList = new ArrayList<DeletedObject>();

      /* Put objects */
      for (int i = 1; i <= maxKeys; i++) {
        String key = UUID.randomUUID().toString().replaceAll("-", "");
        putObject(s3ClientB, ownerNameB, bucketName, key);
        keyVerList.add(new KeyVersion(key));
      }

      /* Multi delete objects quietly */
      DeleteObjectsResult deleteObjectsResult = deleteObjects(s3ClientB, ownerNameB, bucketName, true, keyVerList);

      /* Verify deleted objects result set */
      verifyDeletedObjectsResults(deleteObjectsResult, expectedDelObjList);

      /* Verify bucket is empty */
      verifyBucketIsEmpty(s3ClientB, ownerNameB, bucketName);
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run singleAccountQuiet");
    }
  }

  @Test
  public void multipleAccountsVerbose() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - multipleAccountsVerbose");

    try {
      int maxKeys = 2 + random.nextInt(3); // Max keys 2-4

      /* Create bucket as account A admin and give FULL_CONTROL to account B */
      AccessControlList acl = new AccessControlList();
      acl.grantPermission(new CanonicalGrantee(ownerIdA), Permission.FullControl);
      acl.grantPermission(new CanonicalGrantee(ownerIdB), Permission.FullControl);
      createBucket(s3ClientA, ownerNameA, bucketName, acl, ownerIdA);

      List<KeyVersion> keyVerList = new ArrayList<KeyVersion>();
      List<DeletedObject> expectedDelObjList = new ArrayList<DeletedObject>();

      /* Put objects as account A */
      for (int i = 1; i <= maxKeys; i++) {
        String key = UUID.randomUUID().toString().replaceAll("-", "");
        putObject(s3ClientA, ownerNameA, bucketName, key);
        keyVerList.add(new KeyVersion(key));
        DeletedObject delObj = new DeletedObject();
        delObj.setKey(key);
        expectedDelObjList.add(delObj);
      }

      /* Put objects as account B */
      for (int i = 1; i <= maxKeys; i++) {
        String key = UUID.randomUUID().toString().replaceAll("-", "");
        putObject(s3ClientB, ownerNameB, bucketName, key);
        keyVerList.add(new KeyVersion(key));
        DeletedObject delObj = new DeletedObject();
        delObj.setKey(key);
        expectedDelObjList.add(delObj);
      }

      /* Multi delete objects verbosely as account B */
      DeleteObjectsResult deleteObjectsResult = deleteObjects(s3ClientB, ownerNameB, bucketName, false, keyVerList);

      /* Verify deleted objects result set */
      verifyDeletedObjectsResults(deleteObjectsResult, expectedDelObjList);

      /* Verify bucket is empty */
      verifyBucketIsEmpty(s3ClientB, ownerNameB, bucketName);
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run multipleAccountsVerbose");
    }
  }

  @Test
  public void multipleAccountsQuiet() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - multipleAccountsQuiet");

    try {
      int maxKeys = 2 + random.nextInt(3); // Max keys 2-4

      /* Create bucket as account B admin and give FULL_CONTROL to account A */
      AccessControlList acl = new AccessControlList();
      acl.grantPermission(new CanonicalGrantee(ownerIdB), Permission.FullControl);
      acl.grantPermission(new CanonicalGrantee(ownerIdA), Permission.FullControl);
      createBucket(s3ClientB, ownerNameB, bucketName, acl, ownerIdB);

      List<KeyVersion> keyVerList = new ArrayList<KeyVersion>();
      List<DeletedObject> expectedDelObjList = new ArrayList<DeletedObject>();

      /* Put objects as account A */
      for (int i = 1; i <= maxKeys; i++) {
        String key = UUID.randomUUID().toString().replaceAll("-", "");
        putObject(s3ClientA, ownerNameA, bucketName, key);
        keyVerList.add(new KeyVersion(key));
      }

      /* Multi delete objects quietly as account B */
      DeleteObjectsResult deleteObjectsResult = deleteObjects(s3ClientB, ownerNameB, bucketName, true, keyVerList);

      /* Verify deleted objects result set */
      verifyDeletedObjectsResults(deleteObjectsResult, expectedDelObjList);

      keyVerList = new ArrayList<KeyVersion>();
      expectedDelObjList = new ArrayList<DeletedObject>();

      /* Put objects as account B */
      for (int i = 1; i <= maxKeys; i++) {
        String key = UUID.randomUUID().toString().replaceAll("-", "");
        putObject(s3ClientB, ownerNameB, bucketName, key);
        keyVerList.add(new KeyVersion(key));
      }

      /* Multi delete objects quietly as account A */
      deleteObjectsResult = deleteObjects(s3ClientA, ownerNameA, bucketName, true, keyVerList);

      /* Verify deleted objects result set */
      verifyDeletedObjectsResults(deleteObjectsResult, expectedDelObjList);

      /* Verify bucket is empty */
      verifyBucketIsEmpty(s3ClientA, ownerNameA, bucketName);
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run multipleAccountsQuiet");
    }
  }

  @Test
  public void singleAccountVersionedVerbose() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - singleAccountVersionedVerbose");

    try {
      int maxVersions = 2 + random.nextInt(3); // Max versions 2-4

      /* Create bucket with Canned ACL Private */
      createBucket(s3ClientA, ownerNameA, bucketName, CannedAccessControlList.Private, ownerIdA);

      /* Enable versioning on bucket */
      enableBucketVersioning(s3ClientA, ownerNameA, bucketName);

      List<KeyVersion> keyVerList = new ArrayList<KeyVersion>();
      List<DeletedObject> expectedDelObjList = new ArrayList<DeletedObject>();
      String key = UUID.randomUUID().toString().replaceAll("-", "");

      /* Put objects multiple times */
      for (int i = 1; i <= maxVersions; i++) {
        PutObjectResult putResult = putObject(s3ClientA, ownerNameA, bucketName, key);
        keyVerList.add(new KeyVersion(key, putResult.getVersionId()));
        DeletedObject delObj = new DeletedObject();
        delObj.setKey(key);
        delObj.setVersionId(putResult.getVersionId());
        expectedDelObjList.add(delObj);
      }

      /* Multi delete object without version ID */
      List<DeletedObject> expectedDelObjListForOne = new ArrayList<DeletedObject>();
      DeletedObject deleteMarker = new DeletedObject();
      deleteMarker.setKey(key);
      deleteMarker.setDeleteMarker(true);
      expectedDelObjListForOne.add(deleteMarker);
      DeleteObjectsResult deleteObjectsResultForOne = deleteObjects(s3ClientA, ownerNameA, bucketName, false, key);

      /* Verify deleted objects result set */
      verifyDeletedObjectsResults(deleteObjectsResultForOne, expectedDelObjListForOne);

      /* Add the delete marker to the key version listing and expected deleted objects listing */
      keyVerList.add(new KeyVersion(key, deleteObjectsResultForOne.getDeletedObjects().get(0).getDeleteMarkerVersionId()));
      deleteMarker.setVersionId(deleteObjectsResultForOne.getDeletedObjects().get(0).getDeleteMarkerVersionId());
      expectedDelObjList.add(deleteMarker);

      /* Multi delete objects verbosely */
      DeleteObjectsResult deleteObjectsResult = deleteObjects(s3ClientA, ownerNameA, bucketName, false, keyVerList);

      /* Verify deleted objects result set */
      verifyDeletedObjectsResults(deleteObjectsResult, expectedDelObjList);

      /* Verify bucket is empty */
      verifyBucketIsEmpty(s3ClientA, ownerNameA, bucketName);
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run singleAccountVersionedVerbose");
    }
  }

  @Test
  public void multipleAccountsNegativeQuiet() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - multipleAccountsNegativeQuiet");

    try {
      int maxKeys = 2 + random.nextInt(3); // Max keys 2-4

      /* Create bucket with Canned ACL Private */
      createBucket(s3ClientB, ownerNameB, bucketName, CannedAccessControlList.Private, ownerIdB);

      List<KeyVersion> keyVerList = new ArrayList<KeyVersion>();
      List<DeleteError> expectedDelErrorList = new ArrayList<DeleteError>();

      /* Put objects */
      for (int i = 1; i <= maxKeys; i++) {
        String key = UUID.randomUUID().toString().replaceAll("-", "");
        putObject(s3ClientB, ownerNameB, bucketName, key);
        keyVerList.add(new KeyVersion(key));
        DeleteError delErr = new DeleteError();
        delErr.setKey(key);
        delErr.setCode("AccessDenied");
        expectedDelErrorList.add(delErr);
      }

      boolean caughtException = false;
      try {
        /* Multi delete objects quietly as account A */
        deleteObjects(s3ClientA, ownerNameA, bucketName, true, keyVerList);
      } catch (MultiObjectDeleteException e) {
        caughtException = true;

        /* Verify deleted objects result set */
        verifyDeleteErrors(e, expectedDelErrorList);
      } finally {
        assertTrue("Expected multi delete errors but did not catch an exception", caughtException);
      }

      /* Verify bucket is not empty */
      verifyBucketIsNotEmpty(s3ClientB, ownerNameB, bucketName);
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run multipleAccountsNegativeQuiet");
    }
  }

  @Test
  public void multipleAccountsVersionedNegative() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - multipleAccountsVersionedNegative");

    try {
      int maxVersions = 2 + random.nextInt(3); // Max versions 2-4

      /* Create bucket as account A admin and give FULL_CONTROL to account B */
      AccessControlList acl = new AccessControlList();
      acl.grantPermission(new CanonicalGrantee(ownerIdA), Permission.FullControl);
      acl.grantPermission(new CanonicalGrantee(ownerIdB), Permission.FullControl);
      createBucket(s3ClientA, ownerNameA, bucketName, acl, ownerIdA);

      /* Enable versioning on bucket */
      enableBucketVersioning(s3ClientA, ownerNameA, bucketName);

      List<KeyVersion> keyVerList = new ArrayList<KeyVersion>();
      List<DeletedObject> expectedDelObjList = new ArrayList<DeletedObject>();
      List<DeleteError> expectedDelErrorList = new ArrayList<DeleteError>();
      String key = UUID.randomUUID().toString().replaceAll("-", "");

      /* Put objects multiple times */
      for (int i = 1; i <= maxVersions; i++) {
        PutObjectResult putResult = putObject(s3ClientA, ownerNameA, bucketName, key);
        keyVerList.add(new KeyVersion(key, putResult.getVersionId()));
        DeleteError delErr = new DeleteError();
        delErr.setKey(key);
        delErr.setVersionId(putResult.getVersionId());
        delErr.setCode("AccessDenied");
        expectedDelErrorList.add(delErr);
      }

      boolean caughtException = false;
      List<KeyVersion> keyVerListForNonBucketOwner = new ArrayList<KeyVersion>(keyVerList);
      keyVerListForNonBucketOwner.add(new KeyVersion(key));
      List<DeletedObject> expectedDelObjListForNonBucketOwner = new ArrayList<DeletedObject>();
      DeletedObject deleteMarker = new DeletedObject();
      deleteMarker.setKey(key);
      deleteMarker.setDeleteMarker(true);
      expectedDelObjListForNonBucketOwner.add(deleteMarker);
      try {
        /* Multi delete versions and object without version ID as account B verbosely */
        deleteObjects(s3ClientB, ownerNameB, bucketName, false, keyVerListForNonBucketOwner);
      } catch (MultiObjectDeleteException e) {
        caughtException = true;

        /* Verify deleted objects result set */
        verifyDeleteErrors(e, expectedDelErrorList);

        /* Verify deleted objects result set */
        verifyDeletedObjectsResults(e, expectedDelObjListForNonBucketOwner);

        /* Add the delete marker to the key version listing and expected deleted objects listing */
        keyVerList.add(new KeyVersion(key, e.getDeletedObjects().get(0).getDeleteMarkerVersionId()));
      } finally {
        assertTrue("Expected multi delete errors but did not catch an exception", caughtException);
      }

      /* Multi delete objects quietly */
      DeleteObjectsResult deleteObjectsResult = deleteObjects(s3ClientA, ownerNameA, bucketName, true, keyVerList);

      /* Verify deleted objects result set */
      verifyDeletedObjectsResults(deleteObjectsResult, expectedDelObjList);

      /* Verify bucket is empty */
      verifyBucketIsEmpty(s3ClientA, ownerNameA, bucketName);
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run multipleAccountsVersionedNegative");
    }
  }

  private void printException(AmazonServiceException ase) {
    ase.printStackTrace();
    print("Caught Exception: " + ase.getMessage());
    print("HTTP Status Code: " + ase.getStatusCode());
    print("Amazon Error Code: " + ase.getErrorCode());
  }

  private void createBucket(final AmazonS3 s3, final String accountName, final String bucketName, CannedAccessControlList cannedACL,
      String bucketOwnerId) throws Exception {
    Bucket bucket = S3Utils.createBucketWithCannedACL(s3, accountName, bucketName, cannedACL, S3Utils.BUCKET_CREATION_RETRIES);
    cleanupTasks.add(new Runnable() {
      @Override
      public void run() {
        print(accountName + ": Cleanup up versions/objects in bucket " + bucketName);
        for (S3VersionSummary version : getVersionListing(s3, accountName, bucketName).getVersionSummaries()) {
          try {
            print(accountName + ": Deleting object " + version.getKey() + ", version " + version.getVersionId());
            s3.deleteVersion(bucketName, version.getKey(), version.getVersionId());
          } catch (AmazonServiceException ase) {
            printException(ase);
          }
        }
        print(accountName + ": Deleting bucket " + bucketName);
        s3.deleteBucket(bucketName);
      }
    });
    assertTrue("Invalid reference to bucket", bucket != null);
    assertTrue("Mismatch in bucket names. Expected bucket name to be " + bucketName + ", but got " + bucket.getName(),
        bucketName.equals(bucket.getName()));

    S3Utils.verifyBucketACL(s3, accountName, bucketName, cannedACL, bucketOwnerId);
  }

  private void createBucket(final AmazonS3 s3, final String accountName, final String bucketName, AccessControlList acl, String bucketOwnerId)
      throws Exception {
    Bucket bucket = S3Utils.createBucketWithACL(s3, accountName, bucketName, acl, S3Utils.BUCKET_CREATION_RETRIES);
    cleanupTasks.add(new Runnable() {
      @Override
      public void run() {
        print(accountName + ": Cleanup up versions/objects in bucket " + bucketName);
        for (S3VersionSummary version : getVersionListing(s3, accountName, bucketName).getVersionSummaries()) {
          try {
            print(accountName + ": Deleting object " + version.getKey() + ", version " + version.getVersionId());
            s3.deleteVersion(bucketName, version.getKey(), version.getVersionId());
          } catch (AmazonServiceException ase) {
            printException(ase);
          }
        }
        print(accountName + ": Deleting bucket " + bucketName);
        s3.deleteBucket(bucketName);
      }
    });
    assertTrue("Invalid reference to bucket", bucket != null);
    assertTrue("Mismatch in bucket names. Expected bucket name to be " + bucketName + ", but got " + bucket.getName(),
        bucketName.equals(bucket.getName()));

    S3Utils.verifyBucketACL(s3, accountName, bucketName, acl, bucketOwnerId);
  }

  private PutObjectResult putObject(final AmazonS3 s3, final String accountName, final String bucketName, final String key) throws Exception {
    print(accountName + ": Putting object " + key + " in bucket " + bucketName);
    PutObjectResult putObj = s3.putObject(new PutObjectRequest(bucketName, key, fileToPut));
    assertTrue("Invalid put object result", putObj != null);
    assertTrue("Mimatch in md5sums between original object and PUT result. Expected " + md5_orig + ", but got " + putObj.getETag(),
        putObj.getETag() != null && putObj.getETag().equals(md5_orig));
    return putObj;
  }

  private DeleteObjectsResult deleteObjects(final AmazonS3 s3, final String accountName, final String bucketName, boolean quiet,
      List<KeyVersion> keyVerList) {
    print(accountName + ": Multi-delete objects in bucket " + bucketName + ", quiet=" + quiet);
    return s3.deleteObjects(new DeleteObjectsRequest(bucketName).withKeys(keyVerList).withQuiet(quiet));
  }

  private DeleteObjectsResult deleteObjects(final AmazonS3 s3, final String accountName, final String bucketName, boolean quiet, String... keys) {
    print(accountName + ": Multi-delete objects in bucket " + bucketName + ", quiet=" + quiet);
    return s3.deleteObjects(new DeleteObjectsRequest(bucketName).withKeys(keys).withQuiet(quiet));
  }

  private void verifyDeletedObjectsResults(DeleteObjectsResult deleteObjectsResult, List<DeletedObject> expectedList) {
    assertTrue("Invalid delete objects result", deleteObjectsResult != null);

    if (expectedList != null && !expectedList.isEmpty()) {
      assertTrue("Expected deleted objects but found invalid or empty results", deleteObjectsResult.getDeletedObjects() != null
          && !deleteObjectsResult.getDeletedObjects().isEmpty());
      assertTrue("Expected " + expectedList.size() + " deleted objects but found " + deleteObjectsResult.getDeletedObjects().size(),
          deleteObjectsResult.getDeletedObjects().size() == expectedList.size());

      for (int i = 0; i < expectedList.size(); i++) {
        DeletedObject delObj = deleteObjectsResult.getDeletedObjects().get(i);
        DeletedObject expected = expectedList.get(i);

        assertTrue("Expected deleted object key to be " + expected.getKey() + " but got " + delObj.getKey(), delObj.getKey()
            .equals(expected.getKey()));
        if (expected.getVersionId() != null) {
          assertTrue("Expected deleted object version ID to be " + expected.getVersionId() + " but got " + delObj.getVersionId(), delObj
              .getVersionId().equals(expected.getVersionId()));
        }
        if (expected.isDeleteMarker()) {
          assertTrue("Expected deleted object to be a delete marker", delObj.isDeleteMarker());
          assertTrue("Invalid delete marker version ID", delObj.getDeleteMarkerVersionId() != null);
        }
      }
    } else {
      assertTrue("Expected deleted objects to be empty but found some results", deleteObjectsResult.getDeletedObjects() == null
          || deleteObjectsResult.getDeletedObjects().isEmpty());
    }
  }

  private void verifyDeletedObjectsResults(MultiObjectDeleteException deleteException, List<DeletedObject> expectedList) {
    assertTrue("Invalid delete objects result", deleteException != null);

    if (expectedList != null && !expectedList.isEmpty()) {
      assertTrue("Expected deleted objects but found invalid or empty results", deleteException.getDeletedObjects() != null
          && !deleteException.getDeletedObjects().isEmpty());
      assertTrue("Expected " + expectedList.size() + " deleted objects but found " + deleteException.getDeletedObjects().size(), deleteException
          .getDeletedObjects().size() == expectedList.size());

      for (int i = 0; i < expectedList.size(); i++) {
        DeletedObject delObj = deleteException.getDeletedObjects().get(i);
        DeletedObject expected = expectedList.get(i);

        assertTrue("Expected deleted object key to be " + expected.getKey() + " but got " + delObj.getKey(), delObj.getKey()
            .equals(expected.getKey()));
        if (expected.getVersionId() != null) {
          assertTrue("Expected deleted object version ID to be " + expected.getVersionId() + " but got " + delObj.getVersionId(), delObj
              .getVersionId().equals(expected.getVersionId()));
        }
        if (expected.isDeleteMarker()) {
          assertTrue("Expected deleted object to be a delete marker", delObj.isDeleteMarker());
          assertTrue("Invalid delete marker version ID", delObj.getDeleteMarkerVersionId() != null);
        }
      }
    } else {
      assertTrue("Expected deleted objects to be empty but found some results", deleteException.getDeletedObjects() == null
          || deleteException.getDeletedObjects().isEmpty());
    }
  }

  private void verifyDeleteErrors(MultiObjectDeleteException deleteException, List<DeleteError> expectedList) {
    assertTrue("Invalid multi delete exception", deleteException != null);

    if (expectedList != null && !expectedList.isEmpty()) {
      assertTrue("Expected delete errors but found invalid or empty results", deleteException.getErrors() != null
          && !deleteException.getErrors().isEmpty());
      assertTrue("Expected " + expectedList.size() + " delete errors but found " + deleteException.getErrors().size(), deleteException.getErrors()
          .size() == expectedList.size());

      for (int i = 0; i < expectedList.size(); i++) {
        DeleteError delErr = deleteException.getErrors().get(i);
        DeleteError expected = expectedList.get(i);

        assertTrue("Expected delete error key to be " + expected.getKey() + " but got " + delErr.getKey(), delErr.getKey().equals(expected.getKey()));
        if (expected.getVersionId() != null) {
          assertTrue("Expected delete error version ID to be " + expected.getVersionId() + " but got " + delErr.getVersionId(), delErr.getVersionId()
              .equals(expected.getVersionId()));
        }
        if (expected.getCode() != null) {
          assertTrue("Expected delete error code to be " + expected.getCode() + " but got " + delErr.getCode(),
              delErr.getCode().equals(expected.getCode()));
        }
      }
    } else {
      assertTrue("Expected deleted objects to be empty but found some results", deleteException.getErrors() == null
          || deleteException.getErrors().isEmpty());
    }
  }

  private void verifyBucketIsEmpty(final AmazonS3 s3, final String accountName, final String bucketName) {
    print(accountName + ": Verify bucket " + bucketName + " is empty");
    VersionListing versionList = getVersionListing(s3, accountName, bucketName);
    assertTrue("Invalid version list", versionList != null);
    assertTrue("Expected bucket to be empty but found some versions/objects", versionList.getVersionSummaries() == null
        || versionList.getVersionSummaries().isEmpty());
  }

  private void verifyBucketIsNotEmpty(final AmazonS3 s3, final String accountName, final String bucketName) {
    print(accountName + ": Verify bucket " + bucketName + " is not empty");
    VersionListing versionList = getVersionListing(s3, accountName, bucketName);
    assertTrue("Invalid version list", versionList != null);
    assertTrue("Expected bucket to contain objects/versions but found it empty", versionList.getVersionSummaries() != null
        && !versionList.getVersionSummaries().isEmpty());
  }

  private VersionListing getVersionListing(final AmazonS3 s3, final String accountName, final String bucketName) {
    print(accountName + ": Listing object versions in bucket " + bucketName);
    return s3.listVersions(new ListVersionsRequest().withBucketName(bucketName));
  }

  private void enableBucketVersioning(final AmazonS3 s3, final String accountName, String bucketName) throws InterruptedException {
    print(accountName + ": Enabling versioning for bucket " + bucketName);
    s3.setBucketVersioningConfiguration(new SetBucketVersioningConfigurationRequest(bucketName, new BucketVersioningConfiguration()
        .withStatus(BucketVersioningConfiguration.ENABLED)));

    BucketVersioningConfiguration versioning = null;
    int counter = 0;
    do {
      Thread.sleep(1000);
      versioning = s3.getBucketVersioningConfiguration(bucketName);
      print(accountName + ": Versioning state: " + versioning.getStatus());
      if (versioning.getStatus().equals(BucketVersioningConfiguration.ENABLED)) {
        break;
      }
      counter++;
    } while (counter < 5);
    assertTrue("Invalid result for bucket versioning configuration", versioning != null);
    assertTrue("Expected bucket versioning configuration to be ENABLED, but found it to be " + versioning.getStatus(),
        versioning.getStatus().equals(BucketVersioningConfiguration.ENABLED));
  }
}
