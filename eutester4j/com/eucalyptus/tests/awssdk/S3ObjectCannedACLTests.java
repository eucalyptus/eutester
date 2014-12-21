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
import org.testng.annotations.BeforeClass;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import com.amazonaws.AmazonServiceException;
import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.model.AccessControlList;
import com.amazonaws.services.s3.model.Bucket;
import com.amazonaws.services.s3.model.CannedAccessControlList;
import com.amazonaws.services.s3.model.CanonicalGrantee;
import com.amazonaws.services.s3.model.Grant;
import com.amazonaws.services.s3.model.GroupGrantee;
import com.amazonaws.services.s3.model.Owner;
import com.amazonaws.services.s3.model.Permission;
import com.amazonaws.services.s3.model.PutObjectRequest;
import com.amazonaws.services.s3.model.PutObjectResult;
import com.amazonaws.util.BinaryUtils;
import com.amazonaws.util.Md5Utils;

/**
 * <p>Amazon S3 supports a set of predefined grants, known as canned ACLs. Each canned ACL has a predefined a set of grantees and permissions. This class
 * contains tests for creating buckets with canned ACLs. After a bucket is successfully created, the bucket ACL is fetched and verified against the canned ACL
 * definition.</p>
 * 
 * <p>As of 9/19/2013 all tests passed against S3. All tests fail against Walrus due to <a
 * href="https://eucalyptus.atlassian.net/browse/EUCA-7747">EUCA-7747</a> </p>
 * 
 * <p>{@link #putObject_CannedACL_BucketOwnerRead()}, {@link #setObject_CannedACL_BucketOwnerRead()} and {@link #setObject_CannedACLs()} fail against Walrus due
 * to <a href="https://eucalyptus.atlassian.net/browse/EUCA-7625">EUCA-7625</a></p>
 * 
 * @see <a href="http://docs.aws.amazon.com/AmazonS3/latest/dev/ACLOverview.html">S3 Access Control Lists</a>
 * @author Swathi Gangisetty
 * 
 */
public class S3ObjectCannedACLTests {

	private static String bucketName = null;
	private static String key = null;
	private static List<Runnable> cleanupTasks = null;
	private static File fileToPut = new File("test.dat");
	private static String md5_orig = null;
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
		bucketName = eucaUUID();
		cleanupTasks = new ArrayList<Runnable>();
		print("Creating bucket " + bucketName);
		Bucket bucket = s3.createBucket(bucketName);
		cleanupTasks.add(new Runnable() {
			@Override
			public void run() {
				print("Deleting bucket " + bucketName);
				s3.deleteBucket(bucketName);
			}
		});

		assertTrue("Invalid reference to bucket", bucket != null);
		assertTrue("Mismatch in bucket names. Expected bucket name to be " + bucketName + ", but got " + bucket.getName(), bucketName.equals(bucket.getName()));

		owner = s3.getS3AccountOwner();
		ownerName = owner.getDisplayName();
		ownerId = owner.getId();

		md5_orig = BinaryUtils.toHex(Md5Utils.computeMD5Hash(new FileInputStream(fileToPut)));
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
		print("Initializing key name");
		key = eucaUUID();
	}

	@AfterClass
	public void cleanup() throws Exception {
		print("*** POST SUITE CLEANUP ***");
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
	public void putObject_CannedACL_AuthenticatedRead() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - putObject_CannedACL_AuthenticatedRead");

		/* Put object with Canned ACL AuthenticatedRead */
		try {
			putObjectWithCannedACL(bucketName, key, CannedAccessControlList.AuthenticatedRead);
			verifyObjectACL(key, CannedAccessControlList.AuthenticatedRead);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run putObject_CannedACL_AuthenticatedRead");
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
	public void setObject_CannedACL_AuthenticatedRead() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - setObject_CannedACL_AuthenticatedRead");

		/* Put object and set Canned ACL AuthenticatedRead */
		try {
			putObject(key);
			print("Setting canned ACL " + CannedAccessControlList.AuthenticatedRead + " for object " + key);
			s3.setObjectAcl(bucketName, key, CannedAccessControlList.AuthenticatedRead);
			verifyObjectACL(key, CannedAccessControlList.AuthenticatedRead);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run setObject_CannedACL_AuthenticatedRead");
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
	public void putObject_CannedACL_BucketOwnerFullControl() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - putObject_CannedACL_BucketOwnerFullControl");

		/* Put object with Canned ACL BucketOwnerFullControl */
		try {
			putObjectWithCannedACL(bucketName, key, CannedAccessControlList.BucketOwnerFullControl);
			verifyObjectACL(key, CannedAccessControlList.BucketOwnerFullControl);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run putObject_CannedACL_BucketOwnerFullControl");
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
	public void setObject_CannedACL_BucketOwnerFullControl() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - setObject_CannedACL_BucketOwnerFullControl");

		/* Put object and set Canned ACL BucketOwnerFullControl */
		try {
			putObject(key);
			print("Setting canned ACL " + CannedAccessControlList.BucketOwnerFullControl + " for object " + key);
			s3.setObjectAcl(bucketName, key, CannedAccessControlList.BucketOwnerFullControl);
			verifyObjectACL(key, CannedAccessControlList.BucketOwnerFullControl);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run setObject_CannedACL_BucketOwnerFullControl");
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
	public void putObject_CannedACL_BucketOwnerRead() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - putObject_CannedACL_BucketOwnerRead");

		/* Put object with Canned ACL BucketOwnerRead */
		try {
			putObjectWithCannedACL(bucketName, key, CannedAccessControlList.BucketOwnerRead);
			verifyObjectACL(key, CannedAccessControlList.BucketOwnerRead);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run putObject_CannedACL_BucketOwnerRead");
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
	public void setObject_CannedACL_BucketOwnerRead() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - setObject_CannedACL_BucketOwnerRead");

		/* Put object and set Canned ACL BucketOwnerRead */
		try {
			putObject(key);
			print("Setting canned ACL " + CannedAccessControlList.BucketOwnerRead + " for object " + key);
			s3.setObjectAcl(bucketName, key, CannedAccessControlList.BucketOwnerRead);
			verifyObjectACL(key, CannedAccessControlList.BucketOwnerRead);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run setObject_CannedACL_BucketOwnerRead");
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
	public void putObject_CannedACL_LogDeliveryWrite() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - putObject_CannedACL_LogDeliveryWrite");

		/* Put object with Canned ACL LogDeliveryWrite */
		try {
			putObjectWithCannedACL(bucketName, key, CannedAccessControlList.LogDeliveryWrite);
			verifyObjectACL(key, CannedAccessControlList.LogDeliveryWrite);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run putObject_CannedACL_LogDeliveryWrite");
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
	public void setObject_CannedACL_LogDeliveryWrite() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - setObject_CannedACL_LogDeliveryWrite");

		/* Put object and set Canned ACL LogDeliveryWrite */
		try {
			putObject(key);
			print("Setting canned ACL " + CannedAccessControlList.LogDeliveryWrite + " for object " + key);
			s3.setObjectAcl(bucketName, key, CannedAccessControlList.LogDeliveryWrite);
			verifyObjectACL(key, CannedAccessControlList.LogDeliveryWrite);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run setObject_CannedACL_LogDeliveryWrite");
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
	public void putObject_CannedACL_Private() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - putObject_CannedACL_Private");

		/* Put object with Canned ACL Private */
		try {
			putObjectWithCannedACL(bucketName, key, CannedAccessControlList.Private);
			verifyObjectACL(key, CannedAccessControlList.Private);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run putObject_CannedACL_Private");
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
	public void setObject_CannedACL_Private() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - setObject_CannedACL_Private");

		/* Put object and set Canned ACL Private */
		try {
			putObject(key);
			print("Setting canned ACL " + CannedAccessControlList.Private + " for object " + key);
			s3.setObjectAcl(bucketName, key, CannedAccessControlList.Private);
			verifyObjectACL(key, CannedAccessControlList.Private);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run setObject_CannedACL_Private");
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
	public void putObject_CannedACL_PublicRead() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - putObject_CannedACL_PublicRead");

		/* Put object with Canned ACL PublicRead */
		try {
			putObjectWithCannedACL(bucketName, key, CannedAccessControlList.PublicRead);
			verifyObjectACL(key, CannedAccessControlList.PublicRead);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run putObject_CannedACL_PublicRead");
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
	public void setObject_CannedACL_PublicRead() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - setObject_CannedACL_PublicRead");

		/* Put object and set Canned ACL PublicRead */
		try {
			putObject(key);
			print("Setting canned ACL " + CannedAccessControlList.PublicRead + " for object " + key);
			s3.setObjectAcl(bucketName, key, CannedAccessControlList.PublicRead);
			verifyObjectACL(key, CannedAccessControlList.PublicRead);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run setObject_CannedACL_PublicRead");
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
	public void putObject_CannedACL_PublicReadWrite() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - putObject_CannedACL_PublicReadWrite");

		/* Put object with Canned ACL PublicReadWrite */
		try {
			putObjectWithCannedACL(bucketName, key, CannedAccessControlList.PublicReadWrite);
			verifyObjectACL(key, CannedAccessControlList.PublicReadWrite);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run putObject_CannedACL_PublicReadWrite");
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
	public void setObject_CannedACL_PublicReadWrite() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - setObject_CannedACL_PublicReadWrite");

		/* Put object and set Canned ACL PublicReadWrite */
		try {
			putObject(key);
			print("Setting canned ACL " + CannedAccessControlList.PublicReadWrite + " for object " + key);
			s3.setObjectAcl(bucketName, key, CannedAccessControlList.PublicReadWrite);
			verifyObjectACL(key, CannedAccessControlList.PublicReadWrite);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run setObject_CannedACL_PublicReadWrite");
		}
	}

	/**
	 * <p>Test for cycling through all canned ACLs, setting them one by one for the same object and verifying that the appropriate permissions are set.</p>
	 * 
	 * <p>Test failed against Walrus. Bucket ACL contained no grants after setting canned ACL BucketOwnerRead. Jira ticket for the issue - <a
	 * href="https://eucalyptus.atlassian.net/browse/EUCA-7625">EUCA-7625</a></p>
	 */
	@Test
	public void setObject_CannedACLs() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - setObject_CannedACLs");

		try {
			putObject(key);

			/* Put object and set Canned ACL AuthenticatedRead */
			print("Setting canned ACL " + CannedAccessControlList.AuthenticatedRead + " for object " + key);
			s3.setObjectAcl(bucketName, key, CannedAccessControlList.AuthenticatedRead);
			verifyObjectACL(key, CannedAccessControlList.AuthenticatedRead);

			/* Put object and set Canned ACL BucketOwnerFullControl */
			print("Setting canned ACL " + CannedAccessControlList.BucketOwnerFullControl + " for object " + key);
			s3.setObjectAcl(bucketName, key, CannedAccessControlList.BucketOwnerFullControl);
			verifyObjectACL(key, CannedAccessControlList.BucketOwnerFullControl);

			/* Put object and set Canned ACL BucketOwnerRead */
			print("Setting canned ACL " + CannedAccessControlList.BucketOwnerRead + " for object " + key);
			s3.setObjectAcl(bucketName, key, CannedAccessControlList.BucketOwnerRead);
			verifyObjectACL(key, CannedAccessControlList.BucketOwnerRead);

			/* Put object and set Canned ACL LogDeliveryWrite */
			print("Setting canned ACL " + CannedAccessControlList.LogDeliveryWrite + " for object " + key);
			s3.setObjectAcl(bucketName, key, CannedAccessControlList.LogDeliveryWrite);
			verifyObjectACL(key, CannedAccessControlList.LogDeliveryWrite);

			/* Put object and set Canned ACL Private */
			print("Setting canned ACL " + CannedAccessControlList.Private + " for object " + key);
			s3.setObjectAcl(bucketName, key, CannedAccessControlList.Private);
			verifyObjectACL(key, CannedAccessControlList.Private);

			/* Put object and set Canned ACL PublicRead */
			print("Setting canned ACL " + CannedAccessControlList.PublicRead + " for object " + key);
			s3.setObjectAcl(bucketName, key, CannedAccessControlList.PublicRead);
			verifyObjectACL(key, CannedAccessControlList.PublicRead);

			/* Put object and set Canned ACL PublicReadWrite */
			print("Setting canned ACL " + CannedAccessControlList.PublicReadWrite + " for object " + key);
			s3.setObjectAcl(bucketName, key, CannedAccessControlList.PublicReadWrite);
			verifyObjectACL(key, CannedAccessControlList.PublicReadWrite);
		} catch (AmazonServiceException ase) {
			ase.printStackTrace();
			print("Caught Exception: " + ase.getMessage());
			print("Reponse Status Code: " + ase.getStatusCode());
			print("Error Code: " + ase.getErrorCode());
			print("Request ID: " + ase.getRequestId());
			assertThat(false, "Failed to run setObject_CannedACLs");
		}
	}

	@Test
	public void setObject_nonCannedACL() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - setObject_nonCannedACL");
		try {
			putObject(key);

			Grant ownerGrant = new Grant(new CanonicalGrantee(ownerId), Permission.FullControl);

			AccessControlList acl = new AccessControlList();
			acl.setOwner(owner);
			acl.getGrants().add(new Grant(GroupGrantee.AuthenticatedUsers, Permission.FullControl));
			print("Setting ACL for " + key + " to " + acl);
			s3.setObjectAcl(bucketName, key, acl);
			acl.getGrants().add(ownerGrant);
			verifyObjectACL(key, acl);

			acl = new AccessControlList();
			acl.setOwner(owner);
			acl.getGrants().add(new Grant(GroupGrantee.AllUsers, Permission.WriteAcp));
			print("Setting ACL for " + key + " to " + acl);
			s3.setObjectAcl(bucketName, key, acl);
			acl.getGrants().add(ownerGrant);
			verifyObjectACL(key, acl);

			acl = new AccessControlList();
			acl.setOwner(owner);
			acl.getGrants().add(new Grant(GroupGrantee.LogDelivery, Permission.ReadAcp));
			print("Setting ACL for " + key + " to " + acl);
			s3.setObjectAcl(bucketName, key, acl);
			acl.getGrants().add(ownerGrant);
			verifyObjectACL(key, acl);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run setObject_nonCannedACL");
		}
	}

	@Test
	public void putObject_nonCannedACL() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - putObject_nonCannedACL");
		try {
			Grant ownerGrant = new Grant(new CanonicalGrantee(ownerId), Permission.FullControl);
			
			AccessControlList acl = new AccessControlList();
			acl.getGrants().add(new Grant(GroupGrantee.AuthenticatedUsers, Permission.Write));
			putObjectWithCannedACL(bucketName, key, acl);
			acl.getGrants().add(ownerGrant);
			verifyObjectACL(key, acl);
			
			acl = new AccessControlList();
			acl.getGrants().add(new Grant(GroupGrantee.LogDelivery, Permission.FullControl));
			acl.getGrants().add(new Grant(GroupGrantee.AllUsers, Permission.ReadAcp));
			putObjectWithCannedACL(bucketName, key, acl);
			acl.getGrants().add(ownerGrant);
			verifyObjectACL(key, acl);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run putObject_nonCannedACL");
		}
	}

	private void printException(AmazonServiceException ase) {
		ase.printStackTrace();
		print("Caught Exception: " + ase.getMessage());
		print("HTTP Status Code: " + ase.getStatusCode());
		print("Amazon Error Code: " + ase.getErrorCode());
	}

	private void putObject(final String key) throws Exception {
		print("Putting object " + key + " in bucket " + bucketName);
		PutObjectResult putObj = s3.putObject(bucketName, key, fileToPut);
		cleanupTasks.add(new Runnable() {
			@Override
			public void run() {
				print("Deleting object " + key + " from bucket " + bucketName);
				s3.deleteObject(bucketName, key);
			}
		});
		assertTrue("Invalid put object result", putObj != null);
		assertTrue("Mimatch in md5sums between original object and PUT result. Expected " + md5_orig + ", but got " + putObj.getETag(),
				putObj.getETag() != null && putObj.getETag().equals(md5_orig));

		verifyObjectACL(key, CannedAccessControlList.Private);
	}

	private void putObjectWithCannedACL(final String bucketName, final String key, CannedAccessControlList cannedACL) throws Exception {
		print("Putting object " + key + " with canned ACL " + cannedACL + " in bucket " + bucketName);
		PutObjectResult putObj = s3.putObject(new PutObjectRequest(bucketName, key, fileToPut).withCannedAcl(cannedACL));
		cleanupTasks.add(new Runnable() {
			@Override
			public void run() {
				print("Deleting object " + key + " from bucket " + bucketName);
				s3.deleteObject(bucketName, key);
			}
		});
		assertTrue("Invalid put object result", putObj != null);
		assertTrue("Mimatch in md5sums between original object and PUT result. Expected " + md5_orig + ", but got " + putObj.getETag(),
				putObj.getETag() != null && putObj.getETag().equals(md5_orig));
	}

	private void putObjectWithCannedACL(final String bucketName, final String key, AccessControlList acl) throws Exception {
		print("Putting object " + key + " with canned ACL " + acl + " in bucket " + bucketName);
		PutObjectResult putObj = s3.putObject(new PutObjectRequest(bucketName, key, fileToPut).withAccessControlList(acl));
		cleanupTasks.add(new Runnable() {
			@Override
			public void run() {
				print("Deleting object " + key + " from bucket " + bucketName);
				s3.deleteObject(bucketName, key);
			}
		});
		assertTrue("Invalid put object result", putObj != null);
		assertTrue("Mimatch in md5sums between original object and PUT result. Expected " + md5_orig + ", but got " + putObj.getETag(),
				putObj.getETag() != null && putObj.getETag().equals(md5_orig));
	}

	private void verifyObjectACL(String key, CannedAccessControlList cannedACL) {
		print("Getting ACL for object " + key);
		AccessControlList acl = s3.getObjectAcl(bucketName, key);
		assertTrue("Expected owner of the ACL to be " + ownerId + ", but found " + acl.getOwner().getId(), acl.getOwner().getId().equals(ownerId));
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
			assertTrue("Mismatch in number of ACLs associated with the object. Expected 1 but got " + acl.getGrants().size(), acl.getGrants().size() == 1);
			while (iterator.hasNext()) {
				Grant grant = iterator.next();
				assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
				assertTrue("Expected grantee to be object owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
						.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
				assertTrue("Expected object owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant.getPermission()
						.equals(Permission.FullControl));
			}
			break;

		case BucketOwnerRead:
			assertTrue("Mismatch in number of ACLs associated with the object. Expected 1 but got " + acl.getGrants().size(), acl.getGrants().size() == 1);
			while (iterator.hasNext()) {
				Grant grant = iterator.next();
				assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
				assertTrue("Expected grantee to be object owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
						.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
				assertTrue("Expected object owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant.getPermission()
						.equals(Permission.FullControl));
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
				assertTrue("Expected object owner to have " + Permission.FullControl + " privilege, but found " + grant.getPermission(), grant.getPermission()
						.equals(Permission.FullControl));
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
							"Expected " + GroupGrantee.AllUsers + " to have " + Permission.Read.toString() + " privilege, but found " + grant.getPermission(),
							grant.getPermission().equals(Permission.Read));
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

	private void verifyObjectACL(String key, AccessControlList inputAcl) throws Exception {
		print("Getting ACL for object " + key);
		AccessControlList acl = s3.getObjectAcl(bucketName, key);
		assertTrue("Expected owner of the ACL to be " + ownerId + ", but found " + acl.getOwner().getId(), acl.getOwner().getId().equals(ownerId));
		assertTrue("Mismatch in number of ACLs associated with the object. Expected " + inputAcl.getGrants().size() + " but got " + acl.getGrants().size(), acl
				.getGrants().size() == inputAcl.getGrants().size());

		for (Grant grant : inputAcl.getGrants()) {
			assertTrue("Mismatch between grants, result set does not contain " + grant, acl.getGrants().contains(grant));
		}
	}
}
