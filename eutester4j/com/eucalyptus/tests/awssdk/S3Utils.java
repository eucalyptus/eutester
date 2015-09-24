package com.eucalyptus.tests.awssdk;

import static com.eucalyptus.tests.awssdk.Eutester4j.assertThat;
import static com.eucalyptus.tests.awssdk.Eutester4j.print;
import static org.testng.AssertJUnit.assertTrue;

import java.util.Iterator;

import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.model.AccessControlList;
import com.amazonaws.services.s3.model.Bucket;
import com.amazonaws.services.s3.model.CannedAccessControlList;
import com.amazonaws.services.s3.model.CanonicalGrantee;
import com.amazonaws.services.s3.model.CreateBucketRequest;
import com.amazonaws.services.s3.model.Grant;
import com.amazonaws.services.s3.model.GroupGrantee;
import com.amazonaws.services.s3.model.Permission;

public class S3Utils {

  public static final int BUCKET_CREATION_RETRIES = 10;
  public static final int BUCKET_CREATION_SLEEP = 1000;

  /**
   * Perform GET object acl and verify with input cannedACL
   * 
   * @param s3Client
   * @param s3AccountOwner
   * @param bucket
   * @param key
   * @param cannedACL
   * @param objectOwnerId
   * @param bucketOwnerId
   * @throws Exception
   */
  public static void verifyObjectACL(AmazonS3 s3Client, String s3AccountOwner, String bucket, String key, CannedAccessControlList cannedACL,
      String objectOwnerId, String bucketOwnerId) throws Exception {
    print(s3AccountOwner + ": Getting ACL for object " + key + " in bucket " + bucket);
    AccessControlList aclResult = s3Client.getObjectAcl(bucket, key);
    assertTrue("Expected owner of the ACL to be " + objectOwnerId + ", but found " + aclResult.getOwner().getId(),
        objectOwnerId.equals(aclResult.getOwner().getId()));
    Iterator<Grant> iterator = aclResult.getGrants().iterator();

    switch (cannedACL) {
      case AuthenticatedRead:
        assertTrue("Mismatch in number of ACLs associated with the object. Expected 2 but got " + aclResult.getGrants().size(), aclResult.getGrants()
            .size() == 2);
        while (iterator.hasNext()) {
          Grant grant = iterator.next();
          if (grant.getGrantee() instanceof CanonicalGrantee) {
            assertTrue("Expected grantee to be object owner " + aclResult.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(),
                grant.getGrantee().getIdentifier().equals(aclResult.getOwner().getId()));
            assertTrue("Expected object owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
                .getPermission().equals(Permission.FullControl));
          } else {
            assertTrue("Grantee of type GroupGrantee not found", grant.getGrantee() instanceof GroupGrantee);
            assertTrue("Expected grantee to be " + GroupGrantee.AuthenticatedUsers + ", but found " + ((GroupGrantee) grant.getGrantee()),
                ((GroupGrantee) grant.getGrantee()).equals(GroupGrantee.AuthenticatedUsers));
            assertTrue(
                "Expected " + GroupGrantee.AuthenticatedUsers + " to have " + Permission.Read.toString() + " privilege, but found "
                    + grant.getPermission(), grant.getPermission().equals(Permission.Read));
          }
        }
        break;

      case BucketOwnerFullControl:
        if (objectOwnerId.equals(bucketOwnerId)) {
          assertTrue("Mismatch in number of ACLs associated with the object. Expected 1 but got " + aclResult.getGrants().size(), aclResult
              .getGrants().size() == 1);
          while (iterator.hasNext()) {
            Grant grant = iterator.next();
            assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
            assertTrue("Expected grantee to be object owner " + aclResult.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(),
                grant.getGrantee().getIdentifier().equals(aclResult.getOwner().getId()));
            assertTrue("Expected object owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
                .getPermission().equals(Permission.FullControl));
          }
        } else {
          assertTrue("Mismatch in number of ACLs associated with the object. Expected 2 but got " + aclResult.getGrants().size(), aclResult
              .getGrants().size() == 2);
          while (iterator.hasNext()) {
            Grant grant = iterator.next();
            assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
            assertTrue("Expected grantee to be object owner " + aclResult.getOwner().getId() + " or bucket owner " + bucketOwnerId + ", but found "
                + grant.getGrantee().getIdentifier(), (grant.getGrantee().getIdentifier().equals(aclResult.getOwner().getId()) || grant.getGrantee()
                .getIdentifier().equals(bucketOwnerId)));
            assertTrue("Expected object and bucket owners to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(),
                grant.getPermission().equals(Permission.FullControl));
          }
        }
        break;

      case BucketOwnerRead:
        if (objectOwnerId.equals(bucketOwnerId)) {
          assertTrue("Mismatch in number of ACLs associated with the object. Expected 1 but got " + aclResult.getGrants().size(), aclResult
              .getGrants().size() == 1);
          while (iterator.hasNext()) {
            Grant grant = iterator.next();
            assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
            assertTrue("Expected grantee to be object owner " + aclResult.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(),
                grant.getGrantee().getIdentifier().equals(aclResult.getOwner().getId()));
            assertTrue("Expected object owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
                .getPermission().equals(Permission.FullControl));
          }
        } else {
          assertTrue("Mismatch in number of ACLs associated with the object. Expected 2 but got " + aclResult.getGrants().size(), aclResult
              .getGrants().size() == 2);
          while (iterator.hasNext()) {
            Grant grant = iterator.next();
            assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
            assertTrue("Expected grantee to be object owner " + aclResult.getOwner().getId() + " or bucket owner " + bucketOwnerId + ", but found "
                + grant.getGrantee().getIdentifier(), (grant.getGrantee().getIdentifier().equals(aclResult.getOwner().getId()) || grant.getGrantee()
                .getIdentifier().equals(bucketOwnerId)));
            if (grant.getGrantee().getIdentifier().equals(bucketOwnerId)) {
              assertTrue("Expected bucket owner to have " + Permission.Read + " privilege, but found " + grant.getPermission(), grant.getPermission()
                  .equals(Permission.Read));
            } else {
              assertTrue("Expected object owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
                  .getPermission().equals(Permission.FullControl));
            }
          }
        }
        break;

      case LogDeliveryWrite:
        assertTrue("Mismatch in number of ACLs associated with the object. Expected 3 but got " + aclResult.getGrants().size(), aclResult.getGrants()
            .size() == 3);
        while (iterator.hasNext()) {
          Grant grant = iterator.next();
          if (grant.getGrantee() instanceof CanonicalGrantee) {
            assertTrue("Expected grantee to be object owner " + aclResult.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(),
                grant.getGrantee().getIdentifier().equals(aclResult.getOwner().getId()));
            assertTrue("Expected object owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
                .getPermission().equals(Permission.FullControl));
          } else {
            assertTrue("Grantee of type GroupGrantee not found", grant.getGrantee() instanceof GroupGrantee);
            assertTrue("Expected grantee to be " + GroupGrantee.LogDelivery + ", but found " + ((GroupGrantee) grant.getGrantee()),
                ((GroupGrantee) grant.getGrantee()).equals(GroupGrantee.LogDelivery));
            assertTrue(
                "Expected " + GroupGrantee.LogDelivery + " to have " + Permission.Write.toString() + " or "
                    + grant.getPermission().equals(Permission.ReadAcp) + " privileges, but found " + grant.getPermission(), grant.getPermission()
                    .equals(Permission.Write) || grant.getPermission().equals(Permission.ReadAcp));
          }
        }
        break;

      case Private:
        assertTrue("Mismatch in number of ACLs associated with the object. Expected 1 but got " + aclResult.getGrants().size(), aclResult.getGrants()
            .size() == 1);
        while (iterator.hasNext()) {
          Grant grant = iterator.next();
          assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
          assertTrue("Expected grantee to be object owner " + aclResult.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(),
              grant.getGrantee().getIdentifier().equals(aclResult.getOwner().getId()));
          assertTrue("Expected object owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
              .getPermission().equals(Permission.FullControl));
        }
        break;

      case PublicRead:
        assertTrue("Mismatch in number of ACLs associated with the object. Expected 2 but got " + aclResult.getGrants().size(), aclResult.getGrants()
            .size() == 2);
        while (iterator.hasNext()) {
          Grant grant = iterator.next();
          if (grant.getGrantee() instanceof CanonicalGrantee) {
            assertTrue("Expected grantee to be object owner " + aclResult.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(),
                grant.getGrantee().getIdentifier().equals(aclResult.getOwner().getId()));
            assertTrue("Expected object owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
                .getPermission().equals(Permission.FullControl));
          } else {
            assertTrue("Grantee of type GroupGrantee not found", grant.getGrantee() instanceof GroupGrantee);
            assertTrue("Expected grantee to be " + GroupGrantee.AllUsers + ", but found " + ((GroupGrantee) grant.getGrantee()),
                ((GroupGrantee) grant.getGrantee()).equals(GroupGrantee.AllUsers));
            assertTrue(
                "Expected " + GroupGrantee.AllUsers + " to have " + Permission.Read.toString() + " privilege, but found " + grant.getPermission(),
                grant.getPermission().equals(Permission.Read));
          }
        }
        break;

      case PublicReadWrite:
        assertTrue("Mismatch in number of ACLs associated with the object. Expected 3 but got " + aclResult.getGrants().size(), aclResult.getGrants()
            .size() == 3);
        while (iterator.hasNext()) {
          Grant grant = iterator.next();
          if (grant.getGrantee() instanceof CanonicalGrantee) {
            assertTrue("Expected grantee to be object owner " + aclResult.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(),
                grant.getGrantee().getIdentifier().equals(aclResult.getOwner().getId()));
            assertTrue("Expected object owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
                .getPermission().equals(Permission.FullControl));
          } else {
            assertTrue("Grantee of type GroupGrantee not found", grant.getGrantee() instanceof GroupGrantee);
            assertTrue("Expected grantee to be " + GroupGrantee.AllUsers + ", but found " + ((GroupGrantee) grant.getGrantee()),
                ((GroupGrantee) grant.getGrantee()).equals(GroupGrantee.AllUsers));
            assertTrue("Expected " + GroupGrantee.AllUsers + " to have " + Permission.Read.toString() + " or " + Permission.Write.toString()
                + " privileges, but found " + grant.getPermission(),
                grant.getPermission().equals(Permission.Read) || grant.getPermission().equals(Permission.Write));
          }
        }
        break;

      default:
        assertThat(false, "Unknown canned ACL");
        break;
    }
  }

  /**
   * Perform GET object acl and verify with input acl
   * 
   * @param s3Client
   * @param s3AccountOwner
   * @param bucket
   * @param key
   * @param acl
   * @param objectOwnerId
   * @param bucketOwnerId
   * @throws Exception
   */
  public static void verifyObjectACL(AmazonS3 s3Client, String s3AccountOwner, String bucket, String key, AccessControlList acl, String objectOwnerId)
      throws Exception {
    print(s3AccountOwner + ": Getting ACL for object " + key + " in bucket " + bucket);
    AccessControlList aclResult = s3Client.getObjectAcl(bucket, key);
    assertTrue("Expected owner of the ACL to be " + objectOwnerId + ", but found " + aclResult.getOwner().getId(),
        objectOwnerId.equals(aclResult.getOwner().getId()));
    assertTrue("Mismatch in number of ACLs associated with the object. Expected " + acl.getGrants().size() + " but got "
        + aclResult.getGrants().size(), aclResult.getGrants().size() == acl.getGrants().size());

    for (Grant grant : acl.getGrants()) {
      assertTrue("Mismatch between grants, result set does not contain " + grant, aclResult.getGrants().contains(grant));
    }
  }

  /**
   * Perform GET bucket acl and verify with input cannedACL
   * 
   * @param s3Client
   * @param s3AccountOwner
   * @param bucket
   * @param cannedACL
   * @param bucketOwnerId
   */
  public static void verifyBucketACL(AmazonS3 s3Client, String s3AccountOwner, String bucket, CannedAccessControlList cannedACL, String bucketOwnerId) {
    print(s3AccountOwner + ": Getting ACL for bucket " + bucket);
    AccessControlList aclResult = s3Client.getBucketAcl(bucket);
    assertTrue("Expected owner of the ACL to be " + bucketOwnerId + ", but found " + aclResult.getOwner().getId(), aclResult.getOwner().getId()
        .equals(bucketOwnerId));
    Iterator<Grant> iterator = aclResult.getGrants().iterator();

    switch (cannedACL) {
      case AuthenticatedRead:
        assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 2 but got " + aclResult.getGrants().size(), aclResult.getGrants()
            .size() == 2);
        while (iterator.hasNext()) {
          Grant grant = iterator.next();
          if (grant.getGrantee() instanceof CanonicalGrantee) {
            assertTrue("Expected grantee to be bucket owner " + aclResult.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(),
                grant.getGrantee().getIdentifier().equals(aclResult.getOwner().getId()));
            assertTrue("Expected bucket owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
                .getPermission().equals(Permission.FullControl));
          } else {
            assertTrue("Grantee of type GroupGrantee not found", grant.getGrantee() instanceof GroupGrantee);
            assertTrue("Expected grantee to be " + GroupGrantee.AuthenticatedUsers + ", but found " + ((GroupGrantee) grant.getGrantee()),
                ((GroupGrantee) grant.getGrantee()).equals(GroupGrantee.AuthenticatedUsers));
            assertTrue(
                "Expected " + GroupGrantee.AuthenticatedUsers + " to have " + Permission.Read.toString() + " privilege, but found "
                    + grant.getPermission(), grant.getPermission().equals(Permission.Read));
          }
        }
        break;

      case BucketOwnerFullControl:
        assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 1 but got " + aclResult.getGrants().size(), aclResult.getGrants()
            .size() == 1);
        while (iterator.hasNext()) {
          Grant grant = iterator.next();
          assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
          assertTrue("Expected grantee to be bucket owner " + aclResult.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(),
              grant.getGrantee().getIdentifier().equals(aclResult.getOwner().getId()));
          assertTrue("Expected bucket owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
              .getPermission().equals(Permission.FullControl));
        }
        break;

      case BucketOwnerRead:
        assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 1 but got " + aclResult.getGrants().size(), aclResult.getGrants()
            .size() == 1);
        while (iterator.hasNext()) {
          Grant grant = iterator.next();
          assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
          assertTrue("Expected grantee to be bucket owner " + aclResult.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(),
              grant.getGrantee().getIdentifier().equals(aclResult.getOwner().getId()));
          assertTrue("Expected bucket owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
              .getPermission().equals(Permission.FullControl));
        }
        break;

      case LogDeliveryWrite:
        assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 3 but got " + aclResult.getGrants().size(), aclResult.getGrants()
            .size() == 3);
        while (iterator.hasNext()) {
          Grant grant = iterator.next();
          if (grant.getGrantee() instanceof CanonicalGrantee) {
            assertTrue("Expected grantee to be bucket owner " + aclResult.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(),
                grant.getGrantee().getIdentifier().equals(aclResult.getOwner().getId()));
            assertTrue("Expected bucket owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
                .getPermission().equals(Permission.FullControl));
          } else {
            assertTrue("Grantee of type GroupGrantee not found", grant.getGrantee() instanceof GroupGrantee);
            assertTrue("Expected grantee to be " + GroupGrantee.LogDelivery + ", but found " + ((GroupGrantee) grant.getGrantee()),
                ((GroupGrantee) grant.getGrantee()).equals(GroupGrantee.LogDelivery));
            assertTrue(
                "Expected " + GroupGrantee.LogDelivery + " to have " + Permission.Write.toString() + " or "
                    + grant.getPermission().equals(Permission.ReadAcp) + " privileges, but found " + grant.getPermission(), grant.getPermission()
                    .equals(Permission.Write) || grant.getPermission().equals(Permission.ReadAcp));
          }
        }
        break;

      case Private:
        assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 1 but got " + aclResult.getGrants().size(), aclResult.getGrants()
            .size() == 1);
        while (iterator.hasNext()) {
          Grant grant = iterator.next();
          assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
          assertTrue("Expected grantee to be bucket owner " + aclResult.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(),
              grant.getGrantee().getIdentifier().equals(aclResult.getOwner().getId()));
          assertTrue("Expected bucket owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
              .getPermission().equals(Permission.FullControl));
        }
        break;

      case PublicRead:
        assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 2 but got " + aclResult.getGrants().size(), aclResult.getGrants()
            .size() == 2);
        while (iterator.hasNext()) {
          Grant grant = iterator.next();
          if (grant.getGrantee() instanceof CanonicalGrantee) {
            assertTrue("Expected grantee to be bucket owner " + aclResult.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(),
                grant.getGrantee().getIdentifier().equals(aclResult.getOwner().getId()));
            assertTrue("Expected bucket owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
                .getPermission().equals(Permission.FullControl));
          } else {
            assertTrue("Grantee of type GroupGrantee not found", grant.getGrantee() instanceof GroupGrantee);
            assertTrue("Expected grantee to be " + GroupGrantee.AllUsers + ", but found " + ((GroupGrantee) grant.getGrantee()),
                ((GroupGrantee) grant.getGrantee()).equals(GroupGrantee.AllUsers));
            assertTrue(
                "Expected " + GroupGrantee.AllUsers + " to have " + Permission.Read.toString() + " privilege, but found " + grant.getPermission(),
                grant.getPermission().equals(Permission.Read));
          }
        }
        break;

      case PublicReadWrite:
        assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 3 but got " + aclResult.getGrants().size(), aclResult.getGrants()
            .size() == 3);
        while (iterator.hasNext()) {
          Grant grant = iterator.next();
          if (grant.getGrantee() instanceof CanonicalGrantee) {
            assertTrue("Expected grantee to be bucket owner " + aclResult.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(),
                grant.getGrantee().getIdentifier().equals(aclResult.getOwner().getId()));
            assertTrue("Expected bucket owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
                .getPermission().equals(Permission.FullControl));
          } else {
            assertTrue("Grantee of type GroupGrantee not found", grant.getGrantee() instanceof GroupGrantee);
            assertTrue("Expected grantee to be " + GroupGrantee.AllUsers + ", but found " + ((GroupGrantee) grant.getGrantee()),
                ((GroupGrantee) grant.getGrantee()).equals(GroupGrantee.AllUsers));
            assertTrue("Expected " + GroupGrantee.AllUsers + " to have " + Permission.Read.toString() + " or " + Permission.Write.toString()
                + " privileges, but found " + grant.getPermission(),
                grant.getPermission().equals(Permission.Read) || grant.getPermission().equals(Permission.Write));
          }
        }
        break;

      default:
        assertThat(false, "Unknown canned ACL");
        break;

    }
  }

  /**
   * Perform GET bucket acl and verify with input acl
   * 
   * @param s3Client
   * @param s3AccountOwner
   * @param bucket
   * @param acl
   * @param bucketOwnerId
   */
  public static void verifyBucketACL(AmazonS3 s3Client, String s3AccountOwner, String bucket, AccessControlList acl, String bucketOwnerId) {
    print(s3AccountOwner + ": Getting ACL for bucket " + bucket);
    AccessControlList aclResult = s3Client.getBucketAcl(bucket);
    assertTrue("Expected owner of the ACL to be " + bucketOwnerId + ", but found " + aclResult.getOwner().getId(), aclResult.getOwner().getId()
        .equals(bucketOwnerId));
    assertTrue("Mismatch in number of ACLs associated with the object. Expected " + acl.getGrants().size() + " but got "
        + aclResult.getGrants().size(), aclResult.getGrants().size() == acl.getGrants().size());

    for (Grant grant : acl.getGrants()) {
      assertTrue("Mismatch between grants, result set does not contain " + grant, aclResult.getGrants().contains(grant));
    }
  }

  public static Bucket createBucket(AmazonS3 s3Client, String s3AccountOwner, String bucket, int retries) throws Exception {
    print(s3AccountOwner + ": Creating bucket " + bucket);
    return createBucket(s3Client, s3AccountOwner, new CreateBucketRequest(bucket), retries);
  }

  public static Bucket createBucketWithCannedACL(AmazonS3 s3Client, String s3AccountOwner, String bucket, CannedAccessControlList cannedACL,
      int retries) throws Exception {
    print(s3AccountOwner + ": Creating bucket " + bucket + " with canned ACL " + cannedACL);
    return createBucket(s3Client, s3AccountOwner, new CreateBucketRequest(bucket).withCannedAcl(cannedACL), retries);
  }

  public static Bucket createBucketWithACL(AmazonS3 s3Client, String s3AccountOwner, String bucket, AccessControlList acl, int retries)
      throws Exception {
    print(s3AccountOwner + ": Creating bucket " + bucket + " with ACL " + acl);
    return createBucket(s3Client, s3AccountOwner, new CreateBucketRequest(bucket).withAccessControlList(acl), retries);
  }

  private static Bucket createBucket(AmazonS3 s3Client, String s3AccountOwner, CreateBucketRequest request, int retries) throws Exception {
    int attempts = 0;
    do {
      attempts++;
      try {
        if (attempts != 1) // print only on retries
          print(s3AccountOwner + ": Bucket creation attempt " + attempts);
        return s3Client.createBucket(request);
      } catch (Throwable t) {
        print("Error trying to create bucket: " + t.getStackTrace());
        if (attempts <= retries) {
          print("Retry creating bucket " + request.getBucketName() + " after " + BUCKET_CREATION_SLEEP + " millisecond sleep");
          try {
            Thread.sleep(BUCKET_CREATION_SLEEP);
          } catch (InterruptedException e) {

          }
        } else {
          print("Giving up on creating bucket " + request.getBucketName());
          throw t;
        }
      }
    } while (attempts <= retries);

    throw new Exception("Cannot create bucket " + request.getBucketName());
  }
}
