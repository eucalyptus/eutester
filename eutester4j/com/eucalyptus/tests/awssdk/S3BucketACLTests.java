package com.eucalyptus.tests.awssdk;

import static com.eucalyptus.tests.awssdk.Eutester4j.assertThat;
import static com.eucalyptus.tests.awssdk.Eutester4j.eucaUUID;
import static com.eucalyptus.tests.awssdk.Eutester4j.initS3ClientWithNewAccount;
import static com.eucalyptus.tests.awssdk.Eutester4j.print;
import static com.eucalyptus.tests.awssdk.Eutester4j.testInfo;
import static org.testng.AssertJUnit.assertTrue;

import java.util.ArrayList;
import java.util.Collections;
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
import com.amazonaws.services.s3.model.Owner;
import com.amazonaws.services.s3.model.Permission;

/**
 * <p>Amazon S3 supports a set of predefined grants, known as canned ACLs. Each canned ACL has a predefined a set of grantees and permissions. This class
 * contains tests for creating buckets with canned ACLs. After a bucket is successfully created, the bucket ACL is fetched and verified against the canned ACL
 * definition.</p>
 * 
 * <p>As of 9/19/2013 all tests passed against S3. All tests fail against Walrus due to <a
 * href="https://eucalyptus.atlassian.net/browse/EUCA-7747">EUCA-7747</a> </p>
 * 
 * <p>{@link #createBucket_CannedACL_BucketOwnerRead()}, {@link #setBucket_CannedACL_BucketOwnerRead()} and {@link #setBucket_CannedACLs()} fail against Walrus
 * due to <a href="https://eucalyptus.atlassian.net/browse/EUCA-7625">EUCA-7625</a></p>
 * 
 * @see <a href="http://docs.aws.amazon.com/AmazonS3/latest/dev/ACLOverview.html">S3 Access Control Lists</a>
 * @author Swathi Gangisetty
 * 
 */
public class S3BucketACLTests {

	private static String bucketName = null;
	private static List<Runnable> cleanupTasks = null;
	private static AmazonS3 s3 = null;
	private static String account = null;
	private static Owner owner = null;
	private static String ownerName = null;
	private static String ownerId = null;

	@BeforeClass
	public void init() throws Exception {
		print("*** PRE SUITE SETUP ***");
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
		print("*** POST SUITE CLEANUP ***");
		Eutester4j.deleteAccount(account);
		s3 = null;
	}

	@BeforeMethod
	public void setup() throws Exception {
		print("*** PRE TEST SETUP ***");
		print("Initializing bucket name and clean up tasks");
		bucketName = eucaUUID();
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
	 * </p>Test for <code>authenticated-read</code> canned ACL</p>
	 * 
	 * </p>Canned ACL applies to bucket and object</p>
	 * 
	 * </p>Owner gets FULL_CONTROL. The AuthenticatedUsers group gets READ access.</p>
	 */
	@Test
	public void createBucket_CannedACL_AuthenticatedRead() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - createBucket_CannedACL_AuthenticatedRead");

		/* Create bucket with Canned ACL AuthenticatedRead */
		try {
			createBucketWithCannedACL(bucketName, CannedAccessControlList.AuthenticatedRead);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.AuthenticatedRead, ownerId);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run createBucket_CannedACL_AuthenticatedRead");
		}
	}

	/**
	 * </p>Test for <code>authenticated-read</code> canned ACL</p>
	 * 
	 * </p>Canned ACL applies to bucket and object</p>
	 * 
	 * </p>Owner gets FULL_CONTROL. The AuthenticatedUsers group gets READ access.</p>
	 */
	@Test
	public void setBucket_CannedACL_AuthenticatedRead() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - setBucket_CannedACL_AuthenticatedRead");

		/* Create bucket and set Canned ACL AuthenticatedRead */
		try {
			createBucket(bucketName);
			print("Setting canned ACL " + CannedAccessControlList.AuthenticatedRead + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.AuthenticatedRead);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.AuthenticatedRead, ownerId);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run setBucket_CannedACL_AuthenticatedRead");
		}
	}

	/**
	 * <p>Test for <code>bucket-owner-full-control</code> canned ACL</p>
	 * 
	 * <p>Canned ACL applies to object</p>
	 * 
	 * <p>Both the object owner and the bucket owner get FULL_CONTROL over the object. If you specify this canned ACL when creating a bucket, Amazon S3 ignores
	 * it.</p>
	 */
	@Test
	public void createBucket_CannedACL_BucketOwnerFullControl() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - createBucket_CannedACL_BucketOwnerFullControl");

		/* Create bucket with Canned ACL BucketOwnerFullControl */
		try {
			createBucketWithCannedACL(bucketName, CannedAccessControlList.BucketOwnerFullControl);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.BucketOwnerFullControl, ownerId);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run createBucket_CannedACL_BucketOwnerFullControl");
		}
	}

	/**
	 * <p>Test for <code>bucket-owner-full-control</code> canned ACL</p>
	 * 
	 * <p>Canned ACL applies to object</p>
	 * 
	 * <p>Both the object owner and the bucket owner get FULL_CONTROL over the object. If you specify this canned ACL when creating a bucket, Amazon S3 ignores
	 * it.</p>
	 */
	@Test
	public void setBucket_CannedACL_BucketOwnerFullControl() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - setBucket_CannedACL_BucketOwnerFullControl");

		/* Create bucket and set Canned ACL BucketOwnerFullControl */
		try {
			createBucket(bucketName);
			print("Setting canned ACL " + CannedAccessControlList.BucketOwnerFullControl + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.BucketOwnerFullControl);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.BucketOwnerFullControl, ownerId);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run setBucket_CannedACL_BucketOwnerFullControl");
		}
	}

	/**
	 * <p>Test for <code>bucket-owner-read</code> canned ACL</p>
	 * 
	 * <p>Canned ACL applies to object</p>
	 * 
	 * <p>Object owner gets FULL_CONTROL. Bucket owner gets READ access. If you specify this canned ACL when creating a bucket, Amazon S3 ignores it. </p>
	 * 
	 * <p>Test failed against Walrus. ACL contained no grants. Jira ticket for the issue - <a
	 * href="https://eucalyptus.atlassian.net/browse/EUCA-7625">EUCA-7625</a></p>
	 */
	@Test
	public void createBucket_CannedACL_BucketOwnerRead() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - createBucket_CannedACL_BucketOwnerRead");

		/* Create bucket with Canned ACL BucketOwnerRead */
		try {
			createBucketWithCannedACL(bucketName, CannedAccessControlList.BucketOwnerRead);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.BucketOwnerRead, ownerId);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run createBucket_CannedACL_BucketOwnerRead");
		}
	}

	/**
	 * <p>Test for <code>bucket-owner-read</code> canned ACL</p>
	 * 
	 * <p>Canned ACL applies to object</p>
	 * 
	 * <p>Object owner gets FULL_CONTROL. Bucket owner gets READ access. If you specify this canned ACL when creating a bucket, Amazon S3 ignores it. </p>
	 * 
	 * <p>Test failed against Walrus. ACL contained no grants. Jira ticket for the issue - <a
	 * href="https://eucalyptus.atlassian.net/browse/EUCA-7625">EUCA-7625</a></p>
	 */
	@Test
	public void setBucket_CannedACL_BucketOwnerRead() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - setBucket_CannedACL_BucketOwnerRead");

		/* Create bucket and set Canned ACL BucketOwnerRead */
		try {
			createBucket(bucketName);
			print("Setting canned ACL " + CannedAccessControlList.BucketOwnerRead + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.BucketOwnerRead);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.BucketOwnerRead, ownerId);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run setBucket_CannedACL_BucketOwnerRead()");
		}
	}

	/**
	 * <p>Test for <code>log-delivery-write</code> canned ACL</p>
	 * 
	 * <p>Canned ACL applies to bucket</p>
	 * 
	 * <p>The LogDelivery group gets WRITE and READ_ACP permissions on the bucket.</p>
	 */
	@Test
	public void createBucket_CannedACL_LogDeliveryWrite() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - createBucket_CannedACL_LogDeliveryWrite");

		/* Create bucket with Canned ACL LogDeliveryWrite */
		try {
			createBucketWithCannedACL(bucketName, CannedAccessControlList.LogDeliveryWrite);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.LogDeliveryWrite, ownerId);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run createBucket_CannedACL_LogDeliveryWrite");
		}
	}

	/**
	 * <p>Test for <code>log-delivery-write</code> canned ACL</p>
	 * 
	 * <p>Canned ACL applies to bucket</p>
	 * 
	 * <p>The LogDelivery group gets WRITE and READ_ACP permissions on the bucket.</p>
	 */
	@Test
	public void setBucket_CannedACL_LogDeliveryWrite() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - setBucket_CannedACL_LogDeliveryWrite");

		/* Create bucket and set Canned ACL LogDeliveryWrite */
		try {
			createBucket(bucketName);
			print("Setting canned ACL " + CannedAccessControlList.LogDeliveryWrite + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.LogDeliveryWrite);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.LogDeliveryWrite, ownerId);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run setBucket_CannedACL_LogDeliveryWrite()");
		}
	}

	/**
	 * <p>Test for <code>private</code> canned ACL</p>
	 * 
	 * <p>Canned ACL applies to bucket and object</p>
	 * 
	 * <p>Owner gets FULL_CONTROL. No one else has access rights (default).</p>
	 */
	@Test
	public void createBucket_CannedACL_Private() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - createBucket_CannedACL_Private");

		/* Create bucket with Canned ACL Private */
		try {
			createBucketWithCannedACL(bucketName, CannedAccessControlList.Private);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.Private, ownerId);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run createBucket_CannedACL_Private");
		}
	}

	/**
	 * <p>Test for <code>private</code> canned ACL</p>
	 * 
	 * <p>Canned ACL applies to bucket and object</p>
	 * 
	 * <p>Owner gets FULL_CONTROL. No one else has access rights (default).</p>
	 */
	@Test
	public void setBucket_CannedACL_Private() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - setBucket_CannedACL_Private");

		/* Create bucket and set Canned ACL Private */
		try {
			createBucket(bucketName);
			print("Setting canned ACL " + CannedAccessControlList.Private + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.Private);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.Private, ownerId);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run setBucket_CannedACL_Private");
		}
	}

	/**
	 * <p>Test for <code>public-read</code> canned ACL</p>
	 * 
	 * <p>Canned ACL applies to bucket and object</p>
	 * 
	 * <p>Owner gets FULL_CONTROL. The AllUsers group gets READ access.</p>
	 */
	@Test
	public void createBucket_CannedACL_PublicRead() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - createBucket_CannedACL_PublicRead");

		/* Create bucket with Canned ACL PublicRead */
		try {
			createBucketWithCannedACL(bucketName, CannedAccessControlList.PublicRead);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.PublicRead, ownerId);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run createBucket_CannedACL_PublicRead");
		}
	}

	/**
	 * <p>Test for <code>public-read</code> canned ACL</p>
	 * 
	 * <p>Canned ACL applies to bucket and object</p>
	 * 
	 * <p>Owner gets FULL_CONTROL. The AllUsers group gets READ access.</p>
	 */
	@Test
	public void setBucket_CannedACL_PublicRead() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - setBucket_CannedACL_PublicRead");

		/* Create bucket and set Canned ACL PublicRead */
		try {
			createBucket(bucketName);
			print("Setting canned ACL " + CannedAccessControlList.PublicRead + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.PublicRead);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.PublicRead, ownerId);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run setBucket_CannedACL_PublicRead");
		}
	}

	/**
	 * <p>Test for <code>public-read-write</code> canned ACL</p>
	 * 
	 * <p>Canned ACL applies to bucket and object</p>
	 * 
	 * <p>Owner gets FULL_CONTROL. The AllUsers group gets READ and WRITE access.</p>
	 */
	@Test
	public void createBucket_CannedACL_PublicReadWrite() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - createBucket_CannedACL_PublicReadWrite");

		/* Create bucket with Canned ACL PublicReadWrite */
		try {
			createBucketWithCannedACL(bucketName, CannedAccessControlList.PublicReadWrite);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.PublicReadWrite, ownerId);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run createBucket_CannedACL_PublicReadWrite");
		}
	}

	/**
	 * <p>Test for <code>public-read-write</code> canned ACL</p>
	 * 
	 * <p>Canned ACL applies to bucket and object</p>
	 * 
	 * <p>Owner gets FULL_CONTROL. The AllUsers group gets READ and WRITE access.</p>
	 */
	@Test
	public void setBucket_CannedACL_PublicReadWrite() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - setBucket_CannedACL_PublicReadWrite");

		/* Create bucket and set Canned ACL PublicReadWrite */
		try {
			createBucket(bucketName);
			print("Setting canned ACL " + CannedAccessControlList.PublicReadWrite + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.PublicReadWrite);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.PublicReadWrite, ownerId);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run setBucket_CannedACL_PublicReadWrite");
		}
	}

	/**
	 * <p>Test for cycling through all canned ACLs, setting them one by one for the same bucket and verifying that the appropriate permissions are set.</p>
	 * 
	 * <p>Test failed against Walrus. Bucket ACL contained no grants after setting canned ACL BucketOwnerRead. Jira ticket for the issue - <a
	 * href="https://eucalyptus.atlassian.net/browse/EUCA-7625">EUCA-7625</a></p>
	 */
	@Test
	public void setBucket_CannedACLs() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - setBucket_CannedACLs");

		try {
			createBucket(bucketName);

			/* Set Canned ACL AuthenticatedRead */
			print("Setting canned ACL " + CannedAccessControlList.AuthenticatedRead + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.AuthenticatedRead);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.AuthenticatedRead, ownerId);

			/* Set Canned ACL BucketOwnerFullControl */
			print("Setting canned ACL " + CannedAccessControlList.BucketOwnerFullControl + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.BucketOwnerFullControl);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.BucketOwnerFullControl, ownerId);

			/* Set Canned ACL BucketOwnerRead */
			print("Setting canned ACL " + CannedAccessControlList.BucketOwnerRead + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.BucketOwnerRead);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.BucketOwnerRead, ownerId);

			/* Set Canned ACL LogDeliveryWrite */
			print("Setting canned ACL " + CannedAccessControlList.LogDeliveryWrite + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.LogDeliveryWrite);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.LogDeliveryWrite, ownerId);

			/* Set Canned ACL Private */
			print("Setting canned ACL " + CannedAccessControlList.Private + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.Private);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.Private, ownerId);

			/* Set Canned ACL PublicRead */
			print("Setting canned ACL " + CannedAccessControlList.PublicRead + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.PublicRead);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.PublicRead, ownerId);

			/* Set Canned ACL PublicReadWrite */
			print("Setting canned ACL " + CannedAccessControlList.PublicReadWrite + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.PublicReadWrite);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.PublicReadWrite, ownerId);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run setBucket_CannedACLs");
		}
	}

	@Test
	public void createBucket_ACL_Headers() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - createBucket_ACL_Headers");
		try {
			AccessControlList acl = new AccessControlList();
			acl.getGrants().add(new Grant(GroupGrantee.AuthenticatedUsers, Permission.ReadAcp));
			acl.getGrants().add(new Grant(GroupGrantee.AllUsers, Permission.FullControl));
			acl.getGrants().add(new Grant(new CanonicalGrantee(ownerId), Permission.FullControl));
			createBucketWithACL(bucketName, acl);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, acl, ownerId);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run createBucket_ACL_Headers");
		}
	}

	@Test
	public void setBucket_ACL_XMLBody() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - setBucket_ACL_XMLBody");
		try {
			createBucket(bucketName);

			AccessControlList acl = new AccessControlList();
			acl.setOwner(owner);
			acl.getGrants().add(new Grant(GroupGrantee.LogDelivery, Permission.FullControl));
			acl.getGrants().add(new Grant(GroupGrantee.AllUsers, Permission.WriteAcp));
			acl.getGrants().add(new Grant(new CanonicalGrantee(ownerId), Permission.FullControl));
			print("Setting ACL " + acl + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, acl);
			S3Utils.verifyBucketACL(s3, ownerName, bucketName, acl, ownerId);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run setBucket_ACL_XMLBody");
		}
	}

	private void printException(AmazonServiceException ase) {
		ase.printStackTrace();
		print("Caught Exception: " + ase.getMessage());
		print("HTTP Status Code: " + ase.getStatusCode());
		print("Amazon Error Code: " + ase.getErrorCode());
	}

	private Bucket createBucket(final String bucketName) {
		print("Creating bucket " + bucketName);
		Bucket bucket = s3.createBucket(bucketName);
		cleanupTasks.add(new Runnable() {
			@Override
			public void run() {
				print("Deleting bucket " + bucketName);
				s3.deleteBucket(bucketName);
			}
		});

		S3Utils.verifyBucketACL(s3, ownerName, bucketName, CannedAccessControlList.Private, ownerId);
		return bucket;
	}

	private void createBucketWithCannedACL(final String bucketName, CannedAccessControlList cannedACL) {
		print("Creating bucket " + bucketName + " with canned ACL " + cannedACL);
		Bucket bucket = s3.createBucket(new CreateBucketRequest(bucketName).withCannedAcl(cannedACL));
		cleanupTasks.add(new Runnable() {
			@Override
			public void run() {
				print("Deleting bucket " + bucketName);
				s3.deleteBucket(bucketName);
			}
		});

		assertTrue("Invalid reference to bucket", bucket != null);
		assertTrue("Mismatch in bucket names. Expected bucket name to be " + bucketName + ", but got " + bucket.getName(), bucket.getName().equals(bucketName));
	}

	private void createBucketWithACL(final String bucketName, AccessControlList acl) {
		print("Creating bucket " + bucketName + " with ACL " + acl);
		Bucket bucket = s3.createBucket(new CreateBucketRequest(bucketName).withAccessControlList(acl));
		cleanupTasks.add(new Runnable() {
			@Override
			public void run() {
				print("Deleting bucket " + bucketName);
				s3.deleteBucket(bucketName);
			}
		});

		assertTrue("Invalid reference to bucket", bucket != null);
		assertTrue("Mismatch in bucket names. Expected bucket name to be " + bucketName + ", but got " + bucket.getName(), bucket.getName().equals(bucketName));
	}
}
