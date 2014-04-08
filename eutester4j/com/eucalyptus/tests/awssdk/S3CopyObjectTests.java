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
import com.amazonaws.services.s3.model.CopyObjectRequest;
import com.amazonaws.services.s3.model.CopyObjectResult;
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

		md5 = BinaryUtils.toHex(Md5Utils.computeMD5Hash(new FileInputStream(fileToPut)));
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
		cleanupTasks = new ArrayList<Runnable>();
		sourceBucket = eucaUUID();
		sourceKey = eucaUUID();
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

	@Test
	public void oneUserSameBucket() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - oneUserSameBucket");
		try {
			// Create bucket with Canned ACL PublicReadWrite as account A admin
			createBucketWithCannedACL(ownerNameA, s3ClientA, sourceBucket, CannedAccessControlList.PublicReadWrite);

			// Put object with Canned ACL Private in source bucket as account A admin
			putObjectWithCannedACL(ownerNameA, s3ClientA, sourceBucket, sourceKey, CannedAccessControlList.Private);

			// As account A admin

			// Copy object into the same bucket and verify the ACL
			String destKey = eucaUUID();
			copyObject(ownerNameA, s3ClientA, new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey), md5);
			verifyObjectACL(s3ClientA, sourceBucket, destKey, CannedAccessControlList.Private, ownerIdA, ownerNameA, ownerIdA);

			// Copy object into the same bucket with canned ACL AuthenticatedRead and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameA, s3ClientA,
					new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey)
							.withCannedAccessControlList(CannedAccessControlList.AuthenticatedRead), md5);
			verifyObjectACL(s3ClientA, sourceBucket, destKey, CannedAccessControlList.AuthenticatedRead, ownerIdA, ownerNameA, ownerIdA);

			// Copy object into the same bucket with canned ACL BucketOwnerFullControl and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameA, s3ClientA,
					new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey)
							.withCannedAccessControlList(CannedAccessControlList.BucketOwnerFullControl), md5);
			verifyObjectACL(s3ClientA, sourceBucket, destKey, CannedAccessControlList.BucketOwnerFullControl, ownerIdA, ownerNameA, ownerIdA);

			// Copy object into the same bucket with canned ACL BucketOwnerRead and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameA, s3ClientA,
					new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.BucketOwnerRead),
					md5);
			verifyObjectACL(s3ClientA, sourceBucket, destKey, CannedAccessControlList.BucketOwnerRead, ownerIdA, ownerNameA, ownerIdA);

			// Copy object into the same bucket with canned ACL LogDeliveryWrite and verify the ACL
			destKey = eucaUUID();
			copyObject(
					ownerNameA,
					s3ClientA,
					new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.LogDeliveryWrite),
					md5);
			verifyObjectACL(s3ClientA, sourceBucket, destKey, CannedAccessControlList.LogDeliveryWrite, ownerIdA, ownerNameA, ownerIdA);

			// Copy object into the same bucket with canned ACL Private and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameA, s3ClientA,
					new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.Private), md5);
			verifyObjectACL(s3ClientA, sourceBucket, destKey, CannedAccessControlList.Private, ownerIdA, ownerNameA, ownerIdA);

			// Copy object into the same bucket with canned ACL PublicRead and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameA, s3ClientA,
					new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicRead), md5);
			verifyObjectACL(s3ClientA, sourceBucket, destKey, CannedAccessControlList.PublicRead, ownerIdA, ownerNameA, ownerIdA);

			// Copy object into the same bucket with canned ACL PublicReadWrite and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameA, s3ClientA,
					new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicReadWrite),
					md5);
			verifyObjectACL(s3ClientA, sourceBucket, destKey, CannedAccessControlList.PublicReadWrite, ownerIdA, ownerNameA, ownerIdA);
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
			putObjectWithCannedACL(ownerNameA, s3ClientA, sourceBucket, sourceKey, CannedAccessControlList.Private);

			// Create bucket with Canned ACL Private as account A admin
			String destBucket = eucaUUID();
			createBucketWithCannedACL(ownerNameA, s3ClientA, destBucket, CannedAccessControlList.Private);

			// As account A admin

			// Copy object into the different bucket and verify the ACL
			String destKey = eucaUUID();
			copyObject(ownerNameA, s3ClientA, new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey), md5);
			verifyObjectACL(s3ClientA, destBucket, destKey, CannedAccessControlList.Private, ownerIdA, ownerNameA, ownerIdA);

			// Copy object into a different bucket with canned ACL AuthenticatedRead and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameA, s3ClientA,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.AuthenticatedRead),
					md5);
			verifyObjectACL(s3ClientA, destBucket, destKey, CannedAccessControlList.AuthenticatedRead, ownerIdA, ownerNameA, ownerIdA);

			// Copy object into a different bucket with canned ACL BucketOwnerFullControl and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameA, s3ClientA,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey)
							.withCannedAccessControlList(CannedAccessControlList.BucketOwnerFullControl), md5);
			verifyObjectACL(s3ClientA, destBucket, destKey, CannedAccessControlList.BucketOwnerFullControl, ownerIdA, ownerNameA, ownerIdA);

			// Copy object into a different bucket with canned ACL BucketOwnerRead and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameA, s3ClientA,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.BucketOwnerRead),
					md5);
			verifyObjectACL(s3ClientA, destBucket, destKey, CannedAccessControlList.BucketOwnerRead, ownerIdA, ownerNameA, ownerIdA);

			// Copy object into a different bucket with canned ACL LogDeliveryWrite and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameA, s3ClientA,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.LogDeliveryWrite),
					md5);
			verifyObjectACL(s3ClientA, destBucket, destKey, CannedAccessControlList.LogDeliveryWrite, ownerIdA, ownerNameA, ownerIdA);

			// Copy object into a different bucket with canned ACL Private and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameA, s3ClientA,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.Private), md5);
			verifyObjectACL(s3ClientA, destBucket, destKey, CannedAccessControlList.Private, ownerIdA, ownerNameA, ownerIdA);

			// Copy object into a different bucket with canned ACL PublicRead and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameA, s3ClientA,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicRead), md5);
			verifyObjectACL(s3ClientA, destBucket, destKey, CannedAccessControlList.PublicRead, ownerIdA, ownerNameA, ownerIdA);

			// Copy object into a different bucket with canned ACL PublicReadWrite and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameA, s3ClientA,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicReadWrite),
					md5);
			verifyObjectACL(s3ClientA, destBucket, destKey, CannedAccessControlList.PublicReadWrite, ownerIdA, ownerNameA, ownerIdA);
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
			putObjectWithCannedACL(ownerNameA, s3ClientA, sourceBucket, sourceKey, CannedAccessControlList.AuthenticatedRead);

			// As account B admin

			// Copy object into the same bucket and verify the ACL
			String destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB, new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey), md5);
			verifyObjectACL(s3ClientB, sourceBucket, destKey, CannedAccessControlList.Private, ownerIdB, ownerNameB, ownerIdA);

			// Copy object into the same bucket with canned ACL AuthenticatedRead and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey)
							.withCannedAccessControlList(CannedAccessControlList.AuthenticatedRead), md5);
			verifyObjectACL(s3ClientB, sourceBucket, destKey, CannedAccessControlList.AuthenticatedRead, ownerIdB, ownerNameB, ownerIdA);

			// Copy object into the same bucket with canned ACL BucketOwnerFullControl and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey)
							.withCannedAccessControlList(CannedAccessControlList.BucketOwnerFullControl), md5);
			verifyObjectACL(s3ClientB, sourceBucket, destKey, CannedAccessControlList.BucketOwnerFullControl, ownerIdB, ownerNameB, ownerIdA);

			// Copy object into the same bucket with canned ACL BucketOwnerRead and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.BucketOwnerRead),
					md5);
			verifyObjectACL(s3ClientB, sourceBucket, destKey, CannedAccessControlList.BucketOwnerRead, ownerIdB, ownerNameB, ownerIdA);

			// Copy object into the same bucket with canned ACL LogDeliveryWrite and verify the ACL
			destKey = eucaUUID();
			copyObject(
					ownerNameB,
					s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.LogDeliveryWrite),
					md5);
			verifyObjectACL(s3ClientB, sourceBucket, destKey, CannedAccessControlList.LogDeliveryWrite, ownerIdB, ownerNameB, ownerIdA);

			// Copy object into the same bucket with canned ACL Private and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.Private), md5);
			verifyObjectACL(s3ClientB, sourceBucket, destKey, CannedAccessControlList.Private, ownerIdB, ownerNameB, ownerIdA);

			// Copy object into the same bucket with canned ACL PublicRead and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicRead), md5);
			verifyObjectACL(s3ClientB, sourceBucket, destKey, CannedAccessControlList.PublicRead, ownerIdB, ownerNameB, ownerIdA);

			// Copy object into the same bucket with canned ACL PublicReadWrite and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicReadWrite),
					md5);
			verifyObjectACL(s3ClientB, sourceBucket, destKey, CannedAccessControlList.PublicReadWrite, ownerIdB, ownerNameB, ownerIdA);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run multipleUsersSameBucket");
		}
	}

	@Test
	public void multipleUsersDifferentBuckets1() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - multipleUsersDifferentBuckets1");
		try {
			// Create bucket with Canned ACL Private as account A admin
			createBucketWithCannedACL(ownerNameA, s3ClientA, sourceBucket, CannedAccessControlList.Private);

			// Put object with Canned ACL AuthenticatedRead in source bucket as account A admin
			putObjectWithCannedACL(ownerNameA, s3ClientA, sourceBucket, sourceKey, CannedAccessControlList.AuthenticatedRead);

			// Create bucket with Canned ACL Private as account B admin
			String destBucket = eucaUUID();
			createBucketWithCannedACL(ownerNameB, s3ClientB, destBucket, CannedAccessControlList.Private);

			// As account B admin

			// Copy object into the same bucket and verify the ACL
			String destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB, new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey), md5);
			verifyObjectACL(s3ClientB, destBucket, destKey, CannedAccessControlList.Private, ownerIdB, ownerNameB, ownerIdB);

			// Copy object into the same bucket with canned ACL AuthenticatedRead and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.AuthenticatedRead),
					md5);
			verifyObjectACL(s3ClientB, destBucket, destKey, CannedAccessControlList.AuthenticatedRead, ownerIdB, ownerNameB, ownerIdB);

			// Copy object into the same bucket with canned ACL BucketOwnerFullControl and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey)
							.withCannedAccessControlList(CannedAccessControlList.BucketOwnerFullControl), md5);
			verifyObjectACL(s3ClientB, destBucket, destKey, CannedAccessControlList.BucketOwnerFullControl, ownerIdB, ownerNameB, ownerIdB);

			// Copy object into the same bucket with canned ACL BucketOwnerRead and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.BucketOwnerRead),
					md5);
			verifyObjectACL(s3ClientB, destBucket, destKey, CannedAccessControlList.BucketOwnerRead, ownerIdB, ownerNameB, ownerIdB);

			// Copy object into the same bucket with canned ACL LogDeliveryWrite and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.LogDeliveryWrite),
					md5);
			verifyObjectACL(s3ClientB, destBucket, destKey, CannedAccessControlList.LogDeliveryWrite, ownerIdB, ownerNameB, ownerIdB);

			// Copy object into the same bucket with canned ACL Private and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.Private), md5);
			verifyObjectACL(s3ClientB, destBucket, destKey, CannedAccessControlList.Private, ownerIdB, ownerNameB, ownerIdB);

			// Copy object into the same bucket with canned ACL PublicRead and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicRead), md5);
			verifyObjectACL(s3ClientB, destBucket, destKey, CannedAccessControlList.PublicRead, ownerIdB, ownerNameB, ownerIdB);

			// Copy object into the same bucket with canned ACL PublicReadWrite and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicReadWrite),
					md5);
			verifyObjectACL(s3ClientB, destBucket, destKey, CannedAccessControlList.PublicReadWrite, ownerIdB, ownerNameB, ownerIdB);
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
			putObjectWithCannedACL(ownerNameA, s3ClientA, sourceBucket, sourceKey, CannedAccessControlList.AuthenticatedRead);

			// Create bucket with Canned ACL PublicReadWrite as account A admin
			String destBucket = eucaUUID();
			createBucketWithCannedACL(ownerNameA, s3ClientA, destBucket, CannedAccessControlList.PublicReadWrite);

			// As account B admin

			// Copy object into the same bucket and verify the ACL
			String destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB, new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey), md5);
			verifyObjectACL(s3ClientB, destBucket, destKey, CannedAccessControlList.Private, ownerIdB, ownerNameB, ownerIdA);

			// Copy object into the same bucket with canned ACL AuthenticatedRead and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.AuthenticatedRead),
					md5);
			verifyObjectACL(s3ClientB, destBucket, destKey, CannedAccessControlList.AuthenticatedRead, ownerIdB, ownerNameB, ownerIdA);

			// Copy object into the same bucket with canned ACL BucketOwnerFullControl and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey)
							.withCannedAccessControlList(CannedAccessControlList.BucketOwnerFullControl), md5);
			verifyObjectACL(s3ClientB, destBucket, destKey, CannedAccessControlList.BucketOwnerFullControl, ownerIdB, ownerNameB, ownerIdA);

			// Copy object into the same bucket with canned ACL BucketOwnerRead and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.BucketOwnerRead),
					md5);
			verifyObjectACL(s3ClientB, destBucket, destKey, CannedAccessControlList.BucketOwnerRead, ownerIdB, ownerNameB, ownerIdA);

			// Copy object into the same bucket with canned ACL LogDeliveryWrite and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.LogDeliveryWrite),
					md5);
			verifyObjectACL(s3ClientB, destBucket, destKey, CannedAccessControlList.LogDeliveryWrite, ownerIdB, ownerNameB, ownerIdA);

			// Copy object into the same bucket with canned ACL Private and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.Private), md5);
			verifyObjectACL(s3ClientB, destBucket, destKey, CannedAccessControlList.Private, ownerIdB, ownerNameB, ownerIdA);

			// Copy object into the same bucket with canned ACL PublicRead and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicRead), md5);
			verifyObjectACL(s3ClientB, destBucket, destKey, CannedAccessControlList.PublicRead, ownerIdB, ownerNameB, ownerIdA);

			// Copy object into the same bucket with canned ACL PublicReadWrite and verify the ACL
			destKey = eucaUUID();
			copyObject(ownerNameB, s3ClientB,
					new CopyObjectRequest(sourceBucket, sourceKey, destBucket, destKey).withCannedAccessControlList(CannedAccessControlList.PublicReadWrite),
					md5);
			verifyObjectACL(s3ClientB, destBucket, destKey, CannedAccessControlList.PublicReadWrite, ownerIdB, ownerNameB, ownerIdA);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run multipleUsersDifferentBuckets2");
		}
	}

	@Test
	public void etagConstraint() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - etagConstraint");
		try {
			// Create bucket with Canned ACL Private as account A admin
			createBucketWithCannedACL(ownerNameA, s3ClientA, sourceBucket, CannedAccessControlList.Private);

			// Put object with Canned ACL Private in source bucket as account A admin
			PutObjectResult putResult = putObjectWithCannedACL(ownerNameA, s3ClientA, sourceBucket, sourceKey, CannedAccessControlList.Private);

			// Copy object with matching etag
			String destKey = eucaUUID();
			copyObject(ownerNameA, s3ClientA, new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withMatchingETagConstraint(eucaUUID())
					.withMatchingETagConstraint(putResult.getETag()), md5);
			verifyObjectACL(s3ClientA, sourceBucket, destKey, CannedAccessControlList.Private, ownerIdA, ownerNameA, ownerIdA);

			// Try to copy object with matching etag constraint but supply with non-matching etag
			destKey = eucaUUID();
			CopyObjectRequest copyRequest = new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withMatchingETagConstraint(eucaUUID())
					.withMatchingETagConstraint(eucaUUID());
			printCopyObjectRequest(ownerNameA, copyRequest);
			CopyObjectResult copyResult = s3ClientA.copyObject(copyRequest);
			assertTrue("Expected an invalid copy object result", copyResult == null);

			// Copy object with non-matching etag constraint
			destKey = eucaUUID();
			copyObject(ownerNameA, s3ClientA, new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withNonmatchingETagConstraint(eucaUUID())
					.withNonmatchingETagConstraint(eucaUUID()), md5);
			verifyObjectACL(s3ClientA, sourceBucket, destKey, CannedAccessControlList.Private, ownerIdA, ownerNameA, ownerIdA);

			// Try to copy object with non-matching etag constraint but supply with matching etag
			destKey = eucaUUID();
			copyRequest = new CopyObjectRequest(sourceBucket, sourceKey, sourceBucket, destKey).withNonmatchingETagConstraint(eucaUUID())
					.withNonmatchingETagConstraint(putResult.getETag());
			printCopyObjectRequest(ownerNameA, copyRequest);
			copyResult = s3ClientA.copyObject(copyRequest);
			assertTrue("Expected an invalid copy object result", copyResult == null);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run etagConstraint");
		}
	}

	// Modified since test

	private void printException(AmazonServiceException ase) {
		ase.printStackTrace();
		print("Caught Exception: " + ase.getMessage());
		print("HTTP Status Code: " + ase.getStatusCode());
		print("Amazon Error Code: " + ase.getErrorCode());
	}

	private void createBucketWithCannedACL(final String accountName, final AmazonS3 s3, final String bucketName, CannedAccessControlList cannedACL) {
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
	}

	private PutObjectResult putObjectWithCannedACL(final String accountName, final AmazonS3 s3, final String bucket, final String key,
			CannedAccessControlList cannedACL) throws Exception {
		print(accountName + ": Putting object " + key + " with canned ACL " + cannedACL + " in bucket " + bucket);
		PutObjectResult putResult = s3.putObject(new PutObjectRequest(bucket, key, fileToPut).withCannedAcl(cannedACL));
		cleanupTasks.add(new Runnable() {
			@Override
			public void run() {
				print(accountName + ": Deleting object " + key + " from bucket " + bucket);
				s3.deleteObject(bucket, key);
			}
		});
		assertTrue("Invalid put object result", putResult != null);
		assertTrue("Mimatch in md5sums between original object and PUT result. Expected " + md5 + ", but got " + putResult.getETag(),
				putResult.getETag() != null && putResult.getETag().equals(md5));

		return putResult;
	}

	private CopyObjectResult copyObject(final String accountName, final AmazonS3 s3, final CopyObjectRequest copyRequest, String sourceMd5) throws Exception {
		// Copy object into the same bucket
		printCopyObjectRequest(accountName, copyRequest);
		CopyObjectResult copyResult = s3.copyObject(copyRequest);
		cleanupTasks.add(new Runnable() {
			@Override
			public void run() {
				print(accountName + ": Deleting object " + copyRequest.getDestinationKey() + " from bucket " + copyRequest.getDestinationBucketName());
				s3.deleteObject(copyRequest.getDestinationBucketName(), copyRequest.getDestinationKey());
			}
		});
		assertTrue("Invalid copy object result", copyResult != null);
		assertTrue("Mimatch in md5sums between original object and copy result. Expected " + sourceMd5 + ", but got " + copyResult.getETag(),
				copyResult.getETag() != null && copyResult.getETag().equals(sourceMd5));

		return copyResult;
	}

	private void printCopyObjectRequest(String accountName, CopyObjectRequest copyRequest) {
		StringBuilder sb = new StringBuilder(accountName + ": Copying object with source key=" + copyRequest.getSourceKey() + ", source bucket="
				+ copyRequest.getSourceBucketName() + ", destination key=" + copyRequest.getDestinationKey() + ", destination bucket="
				+ copyRequest.getDestinationBucketName());

		if (copyRequest.getCannedAccessControlList() != null) {
			sb.append(", canned ACL=").append(copyRequest.getCannedAccessControlList());
		}
		if (copyRequest.getMatchingETagConstraints() != null && !copyRequest.getMatchingETagConstraints().isEmpty()) {
			sb.append(", matching etag constraint=").append(copyRequest.getMatchingETagConstraints());
		}
		if (copyRequest.getModifiedSinceConstraint() != null) {
			sb.append(", modified constraint=").append(copyRequest.getModifiedSinceConstraint());
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

	private void verifyObjectACL(AmazonS3 s3Client, String bucket, String key, CannedAccessControlList cannedACL, String objectOwnerId, String objectOwnerName,
			String bucketOwnerId) throws Exception {
		print(objectOwnerName + ": Getting ACL for object " + key + " in bucket " + bucket);
		AccessControlList acl = s3Client.getObjectAcl(bucket, key);
		assertTrue("Expected owner of the ACL to be " + objectOwnerId + ", but found " + acl.getOwner().getId(), objectOwnerId.equals(acl.getOwner().getId()));
		Iterator<Grant> iterator = acl.getGrants().iterator();

		switch (cannedACL) {
			case AuthenticatedRead:
				assertTrue("Mismatch in number of ACLs associated with the object. Expected 2 but got " + acl.getGrants().size(), acl.getGrants().size() == 2);
				while (iterator.hasNext()) {
					Grant grant = iterator.next();
					if (grant.getGrantee() instanceof CanonicalGrantee) {
						assertTrue("Expected grantee to be object owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
								.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
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
					assertTrue("Mismatch in number of ACLs associated with the object. Expected 1 but got " + acl.getGrants().size(),
							acl.getGrants().size() == 1);
					while (iterator.hasNext()) {
						Grant grant = iterator.next();
						assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
						assertTrue("Expected grantee to be object owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
								.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
						assertTrue("Expected object owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
								.getPermission().equals(Permission.FullControl));
					}
				} else {
					assertTrue("Mismatch in number of ACLs associated with the object. Expected 2 but got " + acl.getGrants().size(),
							acl.getGrants().size() == 2);
					while (iterator.hasNext()) {
						Grant grant = iterator.next();
						assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
						assertTrue("Expected grantee to be object owner " + acl.getOwner().getId() + " or bucket owner " + bucketOwnerId + ", but found "
								+ grant.getGrantee().getIdentifier(), (grant.getGrantee().getIdentifier().equals(acl.getOwner().getId()) || grant.getGrantee()
								.getIdentifier().equals(bucketOwnerId)));
						assertTrue("Expected object and bucket owners to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(),
								grant.getPermission().equals(Permission.FullControl));
					}
				}
				break;

			case BucketOwnerRead:
				if (objectOwnerId.equals(bucketOwnerId)) {
					assertTrue("Mismatch in number of ACLs associated with the object. Expected 1 but got " + acl.getGrants().size(),
							acl.getGrants().size() == 1);
					while (iterator.hasNext()) {
						Grant grant = iterator.next();
						assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
						assertTrue("Expected grantee to be object owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
								.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
						assertTrue("Expected object owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
								.getPermission().equals(Permission.FullControl));
					}
				} else {
					assertTrue("Mismatch in number of ACLs associated with the object. Expected 2 but got " + acl.getGrants().size(),
							acl.getGrants().size() == 2);
					while (iterator.hasNext()) {
						Grant grant = iterator.next();
						assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
						assertTrue("Expected grantee to be object owner " + acl.getOwner().getId() + " or bucket owner " + bucketOwnerId + ", but found "
								+ grant.getGrantee().getIdentifier(), (grant.getGrantee().getIdentifier().equals(acl.getOwner().getId()) || grant.getGrantee()
								.getIdentifier().equals(bucketOwnerId)));
						if (grant.getGrantee().getIdentifier().equals(bucketOwnerId)) {
							assertTrue("Expected bucket owner to have " + Permission.Read + " privilege, but found " + grant.getPermission(), grant
									.getPermission().equals(Permission.Read));
						} else {
							assertTrue("Expected object owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
									.getPermission().equals(Permission.FullControl));
						}
					}
				}
				break;

			case LogDeliveryWrite:
				assertTrue("Mismatch in number of ACLs associated with the object. Expected 3 but got " + acl.getGrants().size(), acl.getGrants().size() == 3);
				while (iterator.hasNext()) {
					Grant grant = iterator.next();
					if (grant.getGrantee() instanceof CanonicalGrantee) {
						assertTrue("Expected grantee to be object owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
								.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
						assertTrue("Expected object owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
								.getPermission().equals(Permission.FullControl));
					} else {
						assertTrue("Grantee of type GroupGrantee not found", grant.getGrantee() instanceof GroupGrantee);
						assertTrue("Expected grantee to be " + GroupGrantee.LogDelivery + ", but found " + ((GroupGrantee) grant.getGrantee()),
								((GroupGrantee) grant.getGrantee()).equals(GroupGrantee.LogDelivery));
						assertTrue(
								"Expected " + GroupGrantee.LogDelivery + " to have " + Permission.Write.toString() + " or "
										+ grant.getPermission().equals(Permission.ReadAcp) + " privileges, but found " + grant.getPermission(), grant
										.getPermission().equals(Permission.Write) || grant.getPermission().equals(Permission.ReadAcp));
					}
				}
				break;

			case Private:
				assertTrue("Mismatch in number of ACLs associated with the object. Expected 1 but got " + acl.getGrants().size(), acl.getGrants().size() == 1);
				while (iterator.hasNext()) {
					Grant grant = iterator.next();
					assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
					assertTrue("Expected grantee to be object owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
							.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
					assertTrue("Expected object owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
							.getPermission().equals(Permission.FullControl));
				}
				break;

			case PublicRead:
				assertTrue("Mismatch in number of ACLs associated with the object. Expected 2 but got " + acl.getGrants().size(), acl.getGrants().size() == 2);
				while (iterator.hasNext()) {
					Grant grant = iterator.next();
					if (grant.getGrantee() instanceof CanonicalGrantee) {
						assertTrue("Expected grantee to be object owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
								.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
						assertTrue("Expected object owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
								.getPermission().equals(Permission.FullControl));
					} else {
						assertTrue("Grantee of type GroupGrantee not found", grant.getGrantee() instanceof GroupGrantee);
						assertTrue("Expected grantee to be " + GroupGrantee.AllUsers + ", but found " + ((GroupGrantee) grant.getGrantee()),
								((GroupGrantee) grant.getGrantee()).equals(GroupGrantee.AllUsers));
						assertTrue(
								"Expected " + GroupGrantee.AllUsers + " to have " + Permission.Read.toString() + " privilege, but found "
										+ grant.getPermission(), grant.getPermission().equals(Permission.Read));
					}
				}
				break;

			case PublicReadWrite:
				assertTrue("Mismatch in number of ACLs associated with the object. Expected 3 but got " + acl.getGrants().size(), acl.getGrants().size() == 3);
				while (iterator.hasNext()) {
					Grant grant = iterator.next();
					if (grant.getGrantee() instanceof CanonicalGrantee) {
						assertTrue("Expected grantee to be object owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
								.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
						assertTrue("Expected object owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
								.getPermission().equals(Permission.FullControl));
					} else {
						assertTrue("Grantee of type GroupGrantee not found", grant.getGrantee() instanceof GroupGrantee);
						assertTrue("Expected grantee to be " + GroupGrantee.AllUsers + ", but found " + ((GroupGrantee) grant.getGrantee()),
								((GroupGrantee) grant.getGrantee()).equals(GroupGrantee.AllUsers));
						assertTrue("Expected " + GroupGrantee.AllUsers + " to have " + Permission.Read.toString() + " or " + Permission.Write.toString()
								+ " privileges, but found " + grant.getPermission(), grant.getPermission().equals(Permission.Read)
								|| grant.getPermission().equals(Permission.Write));
					}
				}
				break;

			default:
				assertThat(false, "Unknown canned ACL");
				break;
		}
	}

	private void checkMetadata(AmazonS3 s3, String sourceMd5) {
		CopyObjectRequest copyRequest = null;
		// Check the metadata
		ObjectMetadata metadata = s3.getObjectMetadata(copyRequest.getDestinationBucketName(), copyRequest.getDestinationKey());
		assertTrue("Mimatch in md5sums between original object and get object on the copy. Expected " + md5 + ", but got " + metadata.getETag(),
				metadata.getETag() != null && metadata.getETag().equals(sourceMd5));
	}
}
