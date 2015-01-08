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
import com.amazonaws.services.s3.model.Bucket;
import com.amazonaws.services.s3.model.CannedAccessControlList;
import com.amazonaws.services.s3.model.CanonicalGrantee;
import com.amazonaws.services.s3.model.CreateBucketRequest;
import com.amazonaws.services.s3.model.Grant;
import com.amazonaws.services.s3.model.GroupGrantee;
import com.amazonaws.services.s3.model.ObjectMetadata;
import com.amazonaws.services.s3.model.Owner;
import com.amazonaws.services.s3.model.Permission;
import com.amazonaws.services.s3.model.PutObjectRequest;
import com.amazonaws.services.s3.model.PutObjectResult;
import com.amazonaws.util.BinaryUtils;
import com.amazonaws.util.Md5Utils;

/**
 * </p>Amazon S3 supports a set of predefined grants, known as canned ACLs. Each canned ACL has a predefined a set of grantees and permissions. This class
 * contains tests for creating buckets with canned ACLs. After a bucket is successfully created, the bucket ACL is fetched and verified against the canned ACL
 * definition.</p>
 * 
 * @see <a href="http://docs.aws.amazon.com/AmazonS3/latest/dev/ACLOverview.html">S3 Access Control Lists</a>
 * @author Swathi Gangisetty
 * 
 */
public class S3ObjectACLAcrossAccountsTests {

	private static String bucketName = null;
	private static String key = null;
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
	private static String md5_orig = null;

	@BeforeClass
	public void init() throws Exception {
		print("*** PRE SUITE SETUP ***");

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

		Owner ownerA = s3ClientA.getS3AccountOwner();
		Owner ownerB = s3ClientB.getS3AccountOwner();
		ownerNameA = ownerA.getDisplayName();
		ownerNameB = ownerB.getDisplayName();
		ownerIdA = ownerA.getId();
		ownerIdB = ownerB.getId();

		md5_orig = BinaryUtils.toHex(Md5Utils.computeMD5Hash(new FileInputStream(fileToPut)));
	}

	@AfterClass
	public void teardown() throws Exception {
		print("*** POST SUITE CLEANUP ***");
		Eutester4j.deleteAccount(accountA);
		Eutester4j.deleteAccount(accountB);
		s3ClientA = null;
		s3ClientB = null;
	}

	@BeforeMethod
	public void setup() throws Exception {
		print("*** PRE TEST SETUP ***");
		print("Initializing bucket name, key name and clean up tasks");
		bucketName = eucaUUID();
		key = eucaUUID();
		cleanupTasks = new ArrayList<Runnable>();
	}

	@AfterMethod
	public void cleanup() throws Exception {
		print("*** POST TEST CLEANUP ***");
		Collections.reverse(cleanupTasks);
		for (final Runnable cleanupTask : cleanupTasks) {
			try {
				cleanupTask.run();
			} catch (Exception e) {
				e.printStackTrace();
			}
		}
	}

	/**
	 * <p>Test for <code>public-read-write</code> canned ACL on bucket and <code>bucket-owner-full-control</code> canned ACL on object</p>
	 * 
	 * <p>S3: Initially, the bucket owner has FULL_CONTROL permission on both the bucket and the object. Object owner has FULL_CONTROL permission on the object.
	 * As the bucket owner, change the canned ACL on the object to <code>private</code>. This reduces the number of grants on the object to 1. Bucket owner
	 * continues to have FULL_CONTROL permission on the object, object owner has no listed permissions. However the object owner seems to have READ_ACP
	 * permission since he/she can get the ACL for the object. Object owner cannot get the object i.e. object owner does not have READ permission on the
	 * object</p>
	 * 
	 * <p>Walrus: Initially, the bucket owner has FULL_CONTROL permission on both the bucket and the object. Though not listed in the object ACL, object owner
	 * has FULL_CONTROL permission on the object. As the bucket owner, change the canned ACL on the object to <code>private</code>. This reduces the number of
	 * grants on the object to 1. Object owner continues to have FULL_CONTROL permission on the object, and is listed in the object ACL. Bucket owner has no
	 * listed permissions in the ACL and does not seem to have READ_ACP, WRITE_ACP or READ permissions</p>
	 * 
	 * @see <a href="https://eucalyptus.atlassian.net/browse/EUCA-7712">EUCA-7712</a>
	 */
	// @Test
	public void bucket_PublicReadWrite_object_BucketOwnerFullControl_1() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - bucket_PublicReadWrite_object_BucketOwnerFullControl_1");

		try {
			/* Create bucket with Canned ACL PublicReadWrite as account A admin */
			createBucket(s3ClientA, ownerNameA, bucketName, CannedAccessControlList.PublicReadWrite, ownerIdA);

			/* Put object with Canned ACL BucketOwnerFullControl as account B admin */
			putObjectWithCannedACL(ownerNameB, s3ClientB, bucketName, key, CannedAccessControlList.BucketOwnerFullControl);

			/* Get object ACL as account B admin */
			print(ownerNameB + ": Getting ACL for object " + key);
			AccessControlList objectACL = s3ClientB.getObjectAcl(bucketName, key);
			assertTrue("Mismatch in number of ACLs associated with the object. Expected 2 but got " + objectACL.getGrants().size(), objectACL.getGrants()
					.size() == 2);
			Iterator<Grant> iterator = objectACL.getGrants().iterator();
			while (iterator.hasNext()) {
				Grant grant = iterator.next();
				assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
				assertTrue("Expected grantee to be object owner " + objectACL.getOwner().getId() + " or bucket owner " + s3ClientA.getS3AccountOwner().getId()
						+ ", but found " + grant.getGrantee().getIdentifier(), grant.getGrantee().getIdentifier().equals(objectACL.getOwner().getId())
						|| grant.getGrantee().getIdentifier().equals(s3ClientA.getS3AccountOwner().getId()));
				assertTrue("Expected object/bucket owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
						.getPermission().equals(Permission.FullControl));
			}

			/* Verify that account A admin has READ, READ_ACP and WRITE_ACP permissions */
			assertTrue("Expected bucket owner " + ownerNameA + " to have READ permission over the object",
					canReadObject(ownerNameA, s3ClientA, bucketName, key));
			assertTrue("Expected bucket owner " + ownerNameA + " to have READ_ACP permission over the object",
					canReadObjectACP(ownerNameA, s3ClientA, bucketName, key));
			assertTrue("Expected bucket owner " + ownerNameA + " to have WRITE_ACP permission over the object",
					canWriteObjectACP(ownerNameA, s3ClientA, bucketName, key));

			/* Verify that account B admin has READ, READ_ACP and WRITE_ACP permissions */
			assertTrue("Expected object owner " + ownerNameB + " to have READ permission over the object",
					canReadObject(ownerNameB, s3ClientB, bucketName, key));
			assertTrue("Expected object owner " + ownerNameB + " to have READ_ACP permission over the object",
					canReadObjectACP(ownerNameB, s3ClientB, bucketName, key));
			assertTrue("Expected object owner " + ownerNameB + " to have WRITE_ACP permission over the object",
					canWriteObjectACP(ownerNameB, s3ClientB, bucketName, key));

			/* Set canned ACL Private for object as account A admin */
			print(ownerNameA + ": Setting canned ACL " + CannedAccessControlList.Private + " for object " + key);
			s3ClientA.setObjectAcl(bucketName, key, CannedAccessControlList.Private);

			/* Verify that account A admin has READ, READ_ACP and WRITE_ACP permissions */
			assertTrue("Expected bucket owner " + ownerNameA + " to have READ permission over the object",
					canReadObject(ownerNameA, s3ClientA, bucketName, key));
			assertTrue("Expected bucket owner " + ownerNameA + " to have READ_ACP permission over the object",
					canReadObjectACP(ownerNameA, s3ClientA, bucketName, key));
			assertTrue("Expected bucket owner " + ownerNameA + " to have WRITE_ACP permission over the object",
					canWriteObjectACP(ownerNameA, s3ClientA, bucketName, key));

			/* Verify that account B admin has READ_ACP permission */
			assertTrue("Expected object owner " + ownerNameB + " to have READ_ACP permission over the object",
					canReadObjectACP(ownerNameB, s3ClientB, bucketName, key));

			/* Verify that account B admin does not have READ or WRITE_ACP permissions */
			assertTrue("Expected object owner " + ownerNameB + " to not have READ permission over the object",
					!canReadObject(ownerNameB, s3ClientB, bucketName, key));
			assertTrue("Expected object owner " + ownerNameB + " to not have WRITE_ACP permission over the object",
					!canWriteObjectACP(ownerNameB, s3ClientB, bucketName, key));
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run bucket_PublicReadWrite_object_BucketOwnerFullControl_1");
		}
	}

	/**
	 * <p>Test for <code>public-read-write</code> canned ACL on bucket and <code>bucket-owner-full-control</code> canned ACL on object</p>
	 * 
	 * <p>S3: Initially, the bucket owner has FULL_CONTROL permission on both the bucket and the object. Object owner has FULL_CONTROL permission on the object.
	 * As the object owner, change the canned ACL on the object to <code>private</code>. This reduces the number of grants on the object to 1. Object owner
	 * continues to have FULL_CONTROL permission on the object, bucket owner has no listed permissions. Bucket owner cannot get the object or the ACL for the
	 * object i.e. bucket owner does not have READ and READ_ACP permissions on the object</p>
	 * 
	 * @see <a href="https://eucalyptus.atlassian.net/browse/EUCA-7712">EUCA-7712</a>
	 */
	@Test
	public void bucket_PublicReadWrite_object_BucketOwnerFullControl_2() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - bucket_PublicReadWrite_object_BucketOwnerFullControl_2");

		try {
			/* Create bucket with Canned ACL PublicReadWrite as account A admin */
			createBucket(s3ClientA, ownerNameA, bucketName, CannedAccessControlList.PublicReadWrite, ownerIdA);

			/* Put object with Canned ACL BucketOwnerFullControl as account B admin */
			putObjectWithCannedACL(ownerNameB, s3ClientB, bucketName, key, CannedAccessControlList.BucketOwnerFullControl);

			/* Get object ACL as account B admin */
			print(ownerNameB + ": Getting ACL for object " + key);
			AccessControlList objectACL = s3ClientB.getObjectAcl(bucketName, key);
			assertTrue("Mismatch in number of ACLs associated with the object. Expected 2 but got " + objectACL.getGrants().size(), objectACL.getGrants()
					.size() == 2);
			Iterator<Grant> iterator = objectACL.getGrants().iterator();
			while (iterator.hasNext()) {
				Grant grant = iterator.next();
				assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
				assertTrue("Expected grantee to be object owner " + objectACL.getOwner().getId() + " or bucket owner " + s3ClientA.getS3AccountOwner().getId()
						+ ", but found " + grant.getGrantee().getIdentifier(), grant.getGrantee().getIdentifier().equals(objectACL.getOwner().getId())
						|| grant.getGrantee().getIdentifier().equals(s3ClientA.getS3AccountOwner().getId()));
				assertTrue("Expected object/bucket owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
						.getPermission().equals(Permission.FullControl));
			}

			/* Verify that account A admin has READ, READ_ACP and WRITE_ACP permissions */
			assertTrue("Expected bucket owner " + ownerNameA + " to have READ permission over the object",
					canReadObject(ownerNameA, s3ClientA, bucketName, key));
			assertTrue("Expected bucket owner " + ownerNameA + " to have READ_ACP permission over the object",
					canReadObjectACP(ownerNameA, s3ClientA, bucketName, key));
			assertTrue("Expected bucket owner " + ownerNameA + " to have WRITE_ACP permission over the object",
					canWriteObjectACP(ownerNameA, s3ClientA, bucketName, key));

			/* Verify that account B admin has READ, READ_ACP and WRITE_ACP permissions */
			assertTrue("Expected object owner " + ownerNameB + " to have READ permission over the object",
					canReadObject(ownerNameB, s3ClientB, bucketName, key));
			assertTrue("Expected object owner " + ownerNameB + " to have READ_ACP permission over the object",
					canReadObjectACP(ownerNameB, s3ClientB, bucketName, key));
			assertTrue("Expected object owner " + ownerNameB + " to have WRITE_ACP permission over the object",
					canWriteObjectACP(ownerNameB, s3ClientB, bucketName, key));

			/* Set canned ACL Private for object as account B admin */
			print(ownerNameB + ": Setting canned ACL " + CannedAccessControlList.Private + " for object " + key);
			s3ClientB.setObjectAcl(bucketName, key, CannedAccessControlList.Private);

			/* Verify that account A admin does not have READ, READ_ACP and WRITE_ACP permissions */
			assertTrue("Expected bucket owner " + ownerNameA + " to not have READ permission over the object",
					!canReadObject(ownerNameA, s3ClientA, bucketName, key));
			assertTrue("Expected bucket owner " + ownerNameA + " to not have READ_ACP permission over the object",
					!canReadObjectACP(ownerNameA, s3ClientA, bucketName, key));
			assertTrue("Expected bucket owner " + ownerNameA + " to not have WRITE_ACP permission over the object",
					!canWriteObjectACP(ownerNameA, s3ClientA, bucketName, key));

			/* Verify that account B admin has READ, READ_ACP and WRITE_ACP permissions */
			assertTrue("Expected object owner " + ownerNameB + " to have READ permission over the object",
					canReadObject(ownerNameB, s3ClientB, bucketName, key));
			assertTrue("Expected object owner " + ownerNameB + " to have READ_ACP permission over the object",
					canReadObjectACP(ownerNameB, s3ClientB, bucketName, key));
			assertTrue("Expected object owner " + ownerNameB + " to have WRITE_ACP permission over the object",
					canWriteObjectACP(ownerNameB, s3ClientB, bucketName, key));
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run bucket_PublicReadWrite_object_BucketOwnerFullControl_2");
		}
	}

	/**
	 * <p>Test for <code>public-read-write</code> canned ACL on bucket and <code>bucket-owner-read</code> canned ACL on object</p>
	 * 
	 * @see <a href="https://eucalyptus.atlassian.net/browse/EUCA-7724">EUCA-7724</a>
	 */
	@Test
	public void bucket_PublicReadWrite_object_BucketOwnerRead() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - bucket_PublicReadWrite_object_BucketOwnerRead");

		try {
			/* Create bucket with Canned ACL PublicReadWrite as account A admin */
			createBucket(s3ClientA, ownerNameA, bucketName, CannedAccessControlList.PublicReadWrite, ownerIdA);

			/* Put object with Canned ACL BucketOwnerRead as account B admin */
			putObjectWithCannedACL(ownerNameB, s3ClientB, bucketName, key, CannedAccessControlList.BucketOwnerRead);

			/* Get object ACL as account B admin */
			print(ownerNameB + ": Getting ACL for object " + key);
			AccessControlList objectACL = s3ClientB.getObjectAcl(bucketName, key);
			assertTrue("Mismatch in number of ACLs associated with the object. Expected 2 but got " + objectACL.getGrants().size(), objectACL.getGrants()
					.size() == 2);
			Iterator<Grant> iterator = objectACL.getGrants().iterator();
			while (iterator.hasNext()) {
				Grant grant = iterator.next();
				assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
				assertTrue("Expected grantee to be object owner " + objectACL.getOwner().getId() + " or bucket owner " + s3ClientA.getS3AccountOwner().getId()
						+ ", but found " + grant.getGrantee().getIdentifier(), grant.getGrantee().getIdentifier().equals(objectACL.getOwner().getId())
						|| grant.getGrantee().getIdentifier().equals(s3ClientA.getS3AccountOwner().getId()));
				if (grant.getGrantee().getIdentifier().equals(objectACL.getOwner().getId())) {
					assertTrue("Expected object owner to have " + Permission.FullControl.toString() + " privileges, but found " + grant.getPermission(), grant
							.getPermission().equals(Permission.FullControl));
				} else {
					assertTrue("Expected bucket owner to have " + Permission.Read.toString() + " privileges, but found " + grant.getPermission(), grant
							.getPermission().equals(Permission.Read));
				}

			}

			/* Verify that account A admin has READ permission */
			assertTrue("Expected bucket owner " + ownerNameA + " to have READ permission over the object",
					canReadObject(ownerNameA, s3ClientA, bucketName, key));

			/* Verify that account A admin does not have READ_ACP and WRITE_ACP permissions */
			assertTrue("Expected bucket owner " + ownerNameA + " to not have READ_ACP permission over the object",
					!canReadObjectACP(ownerNameA, s3ClientA, bucketName, key));
			assertTrue("Expected bucket owner " + ownerNameA + " to not have WRITE_ACP permission over the object",
					!canWriteObjectACP(ownerNameA, s3ClientA, bucketName, key));

			/* Verify that account B admin has READ, READ_ACP and WRITE_ACP permissions */
			assertTrue("Expected object owner " + ownerNameB + " to have READ permission over the object",
					canReadObject(ownerNameB, s3ClientB, bucketName, key));
			assertTrue("Expected object owner " + ownerNameB + " to have READ_ACP permission over the object",
					canReadObjectACP(ownerNameB, s3ClientB, bucketName, key));
			assertTrue("Expected object owner " + ownerNameB + " to have WRITE_ACP permission over the object",
					canWriteObjectACP(ownerNameB, s3ClientB, bucketName, key));
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run bucket_PublicReadWrite_object_BucketOwnerRead");
		}
	}

	/**
	 * <p>Test for <code>public-read-write</code> canned ACL on bucket and <code>authenticated-read</code> canned ACL on object</p>
	 * 
	 * @see <a href="https://eucalyptus.atlassian.net/browse/EUCA-7728">EUCA-7728</a>
	 */
	@Test
	public void bucket_PublicReadWrite_object_AuthenticatedRead() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - bucket_PublicReadWrite_object_AuthenticatedRead");

		try {
			/* Create bucket with Canned ACL PublicReadWrite as account A admin */
			createBucket(s3ClientA, ownerNameA, bucketName, CannedAccessControlList.PublicReadWrite, ownerIdA);

			/* Put object with Canned ACL BucketOwnerFullControl as account B admin */
			putObjectWithCannedACL(ownerNameB, s3ClientB, bucketName, key, CannedAccessControlList.AuthenticatedRead);

			/* Get object ACL as account B admin */
			print(ownerNameB + ": Getting ACL for object " + key);
			AccessControlList objectACL = s3ClientB.getObjectAcl(bucketName, key);
			assertTrue("Mismatch in number of ACLs associated with the object. Expected 2 but got " + objectACL.getGrants().size(), objectACL.getGrants()
					.size() == 2);
			Iterator<Grant> iterator = objectACL.getGrants().iterator();
			while (iterator.hasNext()) {
				Grant grant = iterator.next();
				if (grant.getGrantee() instanceof CanonicalGrantee) {
					assertTrue("Expected grantee to be object owner " + objectACL.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(),
							grant.getGrantee().getIdentifier().equals(objectACL.getOwner().getId()));
					assertTrue("Expected object owner to have " + Permission.FullControl.toString() + " privileges, but found " + grant.getPermission(), grant
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

			/* Verify that account A admin has READ permission */
			assertTrue("Expected bucket owner " + ownerNameA + " to have READ permission over the object",
					canReadObject(ownerNameA, s3ClientA, bucketName, key));

			/* Verify that account A admin does not have READ_ACP and WRITE_ACP permissions */
			assertTrue("Expected bucket owner " + ownerNameA + " to not have READ_ACP permission over the object",
					!canReadObjectACP(ownerNameA, s3ClientA, bucketName, key));
			assertTrue("Expected bucket owner " + ownerNameA + " to not have WRITE_ACP permission over the object",
					!canWriteObjectACP(ownerNameA, s3ClientA, bucketName, key));

			/* Verify that account B admin has READ, READ_ACP and WRITE_ACP permissions */
			assertTrue("Expected object owner " + ownerNameB + " to have READ permission over the object",
					canReadObject(ownerNameB, s3ClientB, bucketName, key));
			assertTrue("Expected object owner " + ownerNameB + " to have READ_ACP permission over the object",
					canReadObjectACP(ownerNameB, s3ClientB, bucketName, key));
			assertTrue("Expected object owner " + ownerNameB + " to have WRITE_ACP permission over the object",
					canWriteObjectACP(ownerNameB, s3ClientB, bucketName, key));
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run bucket_PublicReadWrite_object_AuthenticatedRead");
		}
	}

	/**
	 * <p>Test for <code>public-read-write</code> canned ACL on bucket and <code>public-read</code> canned ACL on object</p>
	 * 
	 * bug only in case of eucalyptus admin account
	 */
	@Test
	public void bucket_PublicReadWrite_object_PublicRead() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - bucket_PublicReadWrite_object_PublicRead");

		try {
			/* Create bucket with Canned ACL PublicReadWrite as account A admin */
			createBucket(s3ClientA, ownerNameA, bucketName, CannedAccessControlList.PublicReadWrite, ownerIdA);

			/* Put object with Canned ACL BucketOwnerFullControl as account B admin */
			putObjectWithCannedACL(ownerNameB, s3ClientB, bucketName, key, CannedAccessControlList.PublicRead);

			/* Get object ACL as account B admin */
			print(ownerNameB + ": Getting ACL for object " + key);
			AccessControlList objectACL = s3ClientB.getObjectAcl(bucketName, key);
			assertTrue("Mismatch in number of ACLs associated with the object. Expected 2 but got " + objectACL.getGrants().size(), objectACL.getGrants()
					.size() == 2);
			Iterator<Grant> iterator = objectACL.getGrants().iterator();
			while (iterator.hasNext()) {
				Grant grant = iterator.next();
				if (grant.getGrantee() instanceof CanonicalGrantee) {
					assertTrue("Expected grantee to be object owner " + objectACL.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(),
							grant.getGrantee().getIdentifier().equals(objectACL.getOwner().getId()));
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

			/* Verify that account A admin has READ permission */
			assertTrue("Expected bucket owner " + ownerNameA + " to have READ permission over the object",
					canReadObject(ownerNameA, s3ClientA, bucketName, key));

			/* Verify that account A admin does not have READ_ACP and WRITE_ACP permissions */
			assertTrue("Expected bucket owner " + ownerNameA + " to not have READ_ACP permission over the object",
					!canReadObjectACP(ownerNameA, s3ClientA, bucketName, key));
			assertTrue("Expected bucket owner " + ownerNameA + " to not have WRITE_ACP permission over the object",
					!canWriteObjectACP(ownerNameA, s3ClientA, bucketName, key));

			/* Verify that account B admin has READ, READ_ACP and WRITE_ACP permissions */
			assertTrue("Expected object owner " + ownerNameB + " to have READ permission over the object",
					canReadObject(ownerNameB, s3ClientB, bucketName, key));
			assertTrue("Expected object owner " + ownerNameB + " to have READ_ACP permission over the object",
					canReadObjectACP(ownerNameB, s3ClientB, bucketName, key));
			assertTrue("Expected object owner " + ownerNameB + " to have WRITE_ACP permission over the object",
					canWriteObjectACP(ownerNameB, s3ClientB, bucketName, key));
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run bucket_PublicReadWrite_object_PublicRead");
		}
	}

	/**
	 * <p>Test for <code>public-read-write</code> canned ACL on bucket and <code>public-read-write</code> canned ACL on object</p>
	 * 
	 * bug only in case of eucalyptus admin account
	 */
	@Test
	public void bucket_PublicReadWrite_object_PublicReadWrite() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - bucket_PublicReadWrite_object_PublicReadWrite");

		try {
			/* Create bucket with Canned ACL PublicReadWrite as account A admin */
			createBucket(s3ClientA, ownerNameA, bucketName, CannedAccessControlList.PublicReadWrite, ownerIdA);

			/* Put object with Canned ACL BucketOwnerFullControl as account B admin */
			putObjectWithCannedACL(ownerNameB, s3ClientB, bucketName, key, CannedAccessControlList.PublicReadWrite);

			/* Get object ACL as account B admin */
			print(ownerNameB + ": Getting ACL for object " + key);
			AccessControlList objectACL = s3ClientB.getObjectAcl(bucketName, key);
			assertTrue("Mismatch in number of ACLs associated with the object. Expected 3 but got " + objectACL.getGrants().size(), objectACL.getGrants()
					.size() == 3);
			Iterator<Grant> iterator = objectACL.getGrants().iterator();
			while (iterator.hasNext()) {
				Grant grant = iterator.next();
				if (grant.getGrantee() instanceof CanonicalGrantee) {
					assertTrue("Expected grantee to be object owner " + objectACL.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(),
							grant.getGrantee().getIdentifier().equals(objectACL.getOwner().getId()));
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

			/* Verify that account A admin has READ permission */
			assertTrue("Expected bucket owner " + ownerNameA + " to have READ permission over the object",
					canReadObject(ownerNameA, s3ClientA, bucketName, key));

			/* Verify that account A admin does not have READ_ACP and WRITE_ACP permissions */
			assertTrue("Expected bucket owner " + ownerNameA + " to not have READ_ACP permission over the object",
					!canReadObjectACP(ownerNameA, s3ClientA, bucketName, key));
			assertTrue("Expected bucket owner " + ownerNameA + " to not have WRITE_ACP permission over the object",
					!canWriteObjectACP(ownerNameA, s3ClientA, bucketName, key));

			/* Verify that account B admin has READ, READ_ACP and WRITE_ACP permissions */
			assertTrue("Expected object owner " + ownerNameB + " to have READ permission over the object",
					canReadObject(ownerNameB, s3ClientB, bucketName, key));
			assertTrue("Expected object owner " + ownerNameB + " to have READ_ACP permission over the object",
					canReadObjectACP(ownerNameB, s3ClientB, bucketName, key));
			assertTrue("Expected object owner " + ownerNameB + " to have WRITE_ACP permission over the object",
					canWriteObjectACP(ownerNameB, s3ClientB, bucketName, key));
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run bucket_PublicReadWrite_object_PublicReadWrite");
		}
	}

	/**
	 * <p>Test for <code>public-read-write</code> canned ACL on bucket and <code>private</code> canned ACL on object</p>
	 * 
	 * bug only in case of eucalyptus admin account
	 */
	@Test
	public void bucket_PublicReadWrite_object_Private() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - bucket_PublicReadWrite_object_PublicReadWrite");

		try {
			/* Create bucket with Canned ACL PublicReadWrite as account A admin */
			createBucket(s3ClientA, ownerNameA, bucketName, CannedAccessControlList.PublicReadWrite, ownerIdA);

			/* Put object with Canned ACL BucketOwnerFullControl as account B admin */
			putObjectWithCannedACL(ownerNameB, s3ClientB, bucketName, key, CannedAccessControlList.Private);

			/* Get object ACL as account B admin */
			print(ownerNameB + ": Getting ACL for object " + key);
			AccessControlList objectACL = s3ClientB.getObjectAcl(bucketName, key);
			assertTrue("Mismatch in number of ACLs associated with the object. Expected 1 but got " + objectACL.getGrants().size(), objectACL.getGrants()
					.size() == 1);
			Iterator<Grant> iterator = objectACL.getGrants().iterator();
			while (iterator.hasNext()) {
				Grant grant = iterator.next();
				assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
				assertTrue("Expected grantee to be object owner " + objectACL.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
						.getGrantee().getIdentifier().equals(objectACL.getOwner().getId()));
				assertTrue("Expected object owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant.getPermission()
						.equals(Permission.FullControl));
			}

			/* Verify that account A admin does not have READ, READ_ACP and WRITE_ACP permissions */
			assertTrue("Expected bucket owner " + ownerNameA + " to not have READ permission over the object",
					!canReadObject(ownerNameA, s3ClientA, bucketName, key));
			assertTrue("Expected bucket owner " + ownerNameA + " to not have READ_ACP permission over the object",
					!canReadObjectACP(ownerNameA, s3ClientA, bucketName, key));
			assertTrue("Expected bucket owner " + ownerNameA + " to not have WRITE_ACP permission over the object",
					!canWriteObjectACP(ownerNameA, s3ClientA, bucketName, key));

			/* Verify that account B admin has READ, READ_ACP and WRITE_ACP permissions */
			assertTrue("Expected object owner " + ownerNameB + " to have READ permission over the object",
					canReadObject(ownerNameB, s3ClientB, bucketName, key));
			assertTrue("Expected object owner " + ownerNameB + " to have READ_ACP permission over the object",
					canReadObjectACP(ownerNameB, s3ClientB, bucketName, key));
			assertTrue("Expected object owner " + ownerNameB + " to have WRITE_ACP permission over the object",
					canWriteObjectACP(ownerNameB, s3ClientB, bucketName, key));
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run bucket_PublicReadWrite_object_PublicReadWrite");
		}
	}

	private void printException(AmazonServiceException ase) {
		ase.printStackTrace();
		print("Caught Exception: " + ase.getMessage());
		print("HTTP Status Code: " + ase.getStatusCode());
		print("Amazon Error Code: " + ase.getErrorCode());
	}

	private void createBucket(final AmazonS3 s3, final String accountName, final String bucketName, CannedAccessControlList cannedACL, String bucketOwnerId) {
		print(accountName + ": Creating bucket " + bucketName + " with canned ACL " + cannedACL);
		Bucket bucket = s3.createBucket(new CreateBucketRequest(bucketName).withCannedAcl(cannedACL));
		cleanupTasks.add(new Runnable() {
			@Override
			public void run() {
				print(accountName + ": Deleting bucket " + bucketName);
				s3.deleteBucket(bucketName);
			}
		});
		assertTrue("Invalid reference to bucket", bucket != null);
		assertTrue("Mismatch in bucket names. Expected bucket name to be " + bucketName + ", but got " + bucket.getName(), bucketName.equals(bucket.getName()));

		S3Utils.verifyBucketACL(s3, accountName, bucketName, cannedACL, bucketOwnerId);
	}

	private void putObjectWithCannedACL(final String accountName, final AmazonS3 s3, final String bucketName, final String key,
			CannedAccessControlList cannedACL) throws Exception {
		print(accountName + ": Putting object " + key + " with canned ACL " + cannedACL + " in bucket " + bucketName);
		PutObjectResult putObj = s3.putObject(new PutObjectRequest(bucketName, key, fileToPut).withCannedAcl(cannedACL));
		cleanupTasks.add(new Runnable() {
			@Override
			public void run() {
				print(accountName + ": Deleting object " + key + " from bucket " + bucketName);
				s3.deleteObject(bucketName, key);
			}
		});
		assertTrue("Invalid put object result", putObj != null);
		assertTrue("Mimatch in md5sums between original object and PUT result. Expected " + md5_orig + ", but got " + putObj.getETag(),
				putObj.getETag() != null && putObj.getETag().equals(md5_orig));
	}

	private boolean canReadObject(String accountName, AmazonS3 s3, String bucketName, String key) {

		boolean canDo = false;
		try {
			print(accountName + ": Getting object metadata for " + key + " from bucket " + bucketName);
			ObjectMetadata metadata = s3.getObjectMetadata(bucketName, key);
			assertTrue("Invalid metadata for object " + key, metadata != null);
			canDo = true;
		} catch (AmazonServiceException ex) {
			assertTrue("Expected status code to be 403, but got " + ex.getStatusCode(), ex.getStatusCode() == 403);
			print(accountName + ": Not authorized to READ on " + key);
		}
		return canDo;
	}

	private boolean canReadObjectACP(String accountName, AmazonS3 s3, String bucketName, String key) {
		boolean canDo = false;
		try {
			print(accountName + ": Getting ACL for object " + key);
			AccessControlList acl = s3.getObjectAcl(bucketName, key);
			assertTrue("Invalid ACL for object " + key, acl != null);
			canDo = true;
		} catch (AmazonServiceException ex) {
			assertTrue("Expected status code to be 403, but got " + ex.getStatusCode(), ex.getStatusCode() == 403);
			print(accountName + ": Not authorized to READ_ACP on " + key);
		}
		return canDo;
	}

	private boolean canWriteObjectACP(String accountName, AmazonS3 s3, String bucketName, String key) {
		boolean canDo = false;
		try {
			print(accountName + ": Setting ACL for object " + key);
			s3.setObjectAcl(bucketName, key, CannedAccessControlList.Private);
			canDo = true;
		} catch (AmazonServiceException ex) {
			assertTrue("Expected status code to be 403, but got " + ex.getStatusCode(), ex.getStatusCode() == 403);
			print(accountName + ": Not authorized to WRITE_ACP on " + key);
		}
		return canDo;
	}
}
