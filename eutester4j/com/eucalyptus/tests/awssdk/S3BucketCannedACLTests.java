package com.eucalyptus.tests.awssdk;

import static com.eucalyptus.tests.awssdk.Eutester4j.assertThat;
import static com.eucalyptus.tests.awssdk.Eutester4j.eucaUUID;
import static com.eucalyptus.tests.awssdk.Eutester4j.initS3Client;
import static com.eucalyptus.tests.awssdk.Eutester4j.print;
import static com.eucalyptus.tests.awssdk.Eutester4j.s3;
import static com.eucalyptus.tests.awssdk.Eutester4j.testInfo;
import static org.testng.AssertJUnit.assertTrue;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;

import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import com.amazonaws.AmazonServiceException;
import com.amazonaws.services.s3.model.AccessControlList;
import com.amazonaws.services.s3.model.Bucket;
import com.amazonaws.services.s3.model.CannedAccessControlList;
import com.amazonaws.services.s3.model.CanonicalGrantee;
import com.amazonaws.services.s3.model.CreateBucketRequest;
import com.amazonaws.services.s3.model.Grant;
import com.amazonaws.services.s3.model.GroupGrantee;
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
public class S3BucketCannedACLTests {

	private static String bucketName = null;
	private static List<Runnable> cleanupTasks = null;

	@BeforeClass
	public void init() throws Exception {
		print("*** PRE SUITE SETUP ***");
		initS3Client();
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
			verifyBucketACL(bucketName, CannedAccessControlList.AuthenticatedRead);
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
			verifyBucketACL(bucketName, CannedAccessControlList.AuthenticatedRead);
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
			verifyBucketACL(bucketName, CannedAccessControlList.BucketOwnerFullControl);
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
			verifyBucketACL(bucketName, CannedAccessControlList.BucketOwnerFullControl);
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
			verifyBucketACL(bucketName, CannedAccessControlList.BucketOwnerRead);
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
			verifyBucketACL(bucketName, CannedAccessControlList.BucketOwnerRead);
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
			verifyBucketACL(bucketName, CannedAccessControlList.LogDeliveryWrite);
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
			verifyBucketACL(bucketName, CannedAccessControlList.LogDeliveryWrite);
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
			verifyBucketACL(bucketName, CannedAccessControlList.Private);
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
			verifyBucketACL(bucketName, CannedAccessControlList.Private);
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
			verifyBucketACL(bucketName, CannedAccessControlList.PublicRead);
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
			verifyBucketACL(bucketName, CannedAccessControlList.PublicRead);
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
			verifyBucketACL(bucketName, CannedAccessControlList.PublicReadWrite);
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
			verifyBucketACL(bucketName, CannedAccessControlList.PublicReadWrite);
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
			final String bucketName = eucaUUID();
			createBucket(bucketName);

			/* Set Canned ACL AuthenticatedRead */
			print("Setting canned ACL " + CannedAccessControlList.AuthenticatedRead + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.AuthenticatedRead);
			verifyBucketACL(bucketName, CannedAccessControlList.AuthenticatedRead);

			/* Set Canned ACL BucketOwnerFullControl */
			print("Setting canned ACL " + CannedAccessControlList.BucketOwnerFullControl + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.BucketOwnerFullControl);
			verifyBucketACL(bucketName, CannedAccessControlList.BucketOwnerFullControl);

			/* Set Canned ACL BucketOwnerRead */
			print("Setting canned ACL " + CannedAccessControlList.BucketOwnerRead + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.BucketOwnerRead);
			verifyBucketACL(bucketName, CannedAccessControlList.BucketOwnerRead);

			/* Set Canned ACL LogDeliveryWrite */
			print("Setting canned ACL " + CannedAccessControlList.LogDeliveryWrite + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.LogDeliveryWrite);
			verifyBucketACL(bucketName, CannedAccessControlList.LogDeliveryWrite);

			/* Set Canned ACL Private */
			print("Setting canned ACL " + CannedAccessControlList.Private + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.Private);
			verifyBucketACL(bucketName, CannedAccessControlList.Private);

			/* Set Canned ACL PublicRead */
			print("Setting canned ACL " + CannedAccessControlList.PublicRead + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.PublicRead);
			verifyBucketACL(bucketName, CannedAccessControlList.PublicRead);

			/* Set Canned ACL PublicReadWrite */
			print("Setting canned ACL " + CannedAccessControlList.PublicReadWrite + " for bucket " + bucketName);
			s3.setBucketAcl(bucketName, CannedAccessControlList.PublicReadWrite);
			verifyBucketACL(bucketName, CannedAccessControlList.PublicReadWrite);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run setBucket_CannedACLs");
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

		verifyBucketACL(bucketName, CannedAccessControlList.Private);
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

	private void verifyBucketACL(String bucketName, CannedAccessControlList cannedACL) {
		print("Getting ACL for bucket " + bucketName);
		AccessControlList acl = s3.getBucketAcl(bucketName);
		assertTrue("Expected owner of the ACL to be " + s3.getS3AccountOwner().getId() + ", but found " + acl.getOwner().getId(), s3.getS3AccountOwner()
				.getId().equals(acl.getOwner().getId()));
		Iterator<Grant> iterator = acl.getGrants().iterator();

		switch (cannedACL) {
			case AuthenticatedRead:
				assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 2 but got " + acl.getGrants().size(), acl.getGrants().size() == 2);
				while (iterator.hasNext()) {
					Grant grant = iterator.next();
					if (grant.getGrantee() instanceof CanonicalGrantee) {
						assertTrue("Expected grantee to be bucket owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
								.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
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
				assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 1 but got " + acl.getGrants().size(), acl.getGrants().size() == 1);
				while (iterator.hasNext()) {
					Grant grant = iterator.next();
					assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
					assertTrue("Expected grantee to be bucket owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
							.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
					assertTrue("Expected bucket owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
							.getPermission().equals(Permission.FullControl));
				}
				break;

			case BucketOwnerRead:
				assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 1 but got " + acl.getGrants().size(), acl.getGrants().size() == 1);
				while (iterator.hasNext()) {
					Grant grant = iterator.next();
					assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
					assertTrue("Expected grantee to be bucket owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
							.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
					assertTrue("Expected bucket owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
							.getPermission().equals(Permission.FullControl));
				}
				break;

			case LogDeliveryWrite:
				assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 3 but got " + acl.getGrants().size(), acl.getGrants().size() == 3);
				while (iterator.hasNext()) {
					Grant grant = iterator.next();
					if (grant.getGrantee() instanceof CanonicalGrantee) {
						assertTrue("Expected grantee to be bucket owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
								.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
						assertTrue("Expected bucket owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
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
				assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 1 but got " + acl.getGrants().size(), acl.getGrants().size() == 1);
				while (iterator.hasNext()) {
					Grant grant = iterator.next();
					assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
					assertTrue("Expected grantee to be bucket owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
							.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
					assertTrue("Expected bucket owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
							.getPermission().equals(Permission.FullControl));
				}
				break;

			case PublicRead:
				assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 2 but got " + acl.getGrants().size(), acl.getGrants().size() == 2);
				while (iterator.hasNext()) {
					Grant grant = iterator.next();
					if (grant.getGrantee() instanceof CanonicalGrantee) {
						assertTrue("Expected grantee to be bucket owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
								.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
						assertTrue("Expected bucket owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
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
				assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 3 but got " + acl.getGrants().size(), acl.getGrants().size() == 3);
				while (iterator.hasNext()) {
					Grant grant = iterator.next();
					if (grant.getGrantee() instanceof CanonicalGrantee) {
						assertTrue("Expected grantee to be bucket owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
								.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
						assertTrue("Expected bucket owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant
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
}
