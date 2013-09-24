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

import org.testng.annotations.BeforeClass;
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
 * </p>Amazon S3 supports a set of predefined grants, known as canned ACLs. Each canned ACL has a predefined a set of grantees and permissions. This class
 * contains tests for creating buckets with canned ACLs. After a bucket is successfully created, the bucket ACL is fetched and verified against the canned ACL
 * definition.</p>
 * 
 * </p>As of 9/19/2013 all tests passed against S3. {@link #createBucket_CannedACL_BucketOwnerRead()} fails against Walrus. Jira ticket for the issue - <a
 * href="https://eucalyptus.atlassian.net/browse/EUCA-7625">EUCA-7625</a></p>
 * 
 * @see <a href="http://docs.aws.amazon.com/AmazonS3/latest/dev/ACLOverview.html">S3 Access Control Lists</a>
 * @author Swathi Gangisetty
 * 
 */
public class S3BucketCannedACLTests {

	@BeforeClass
	public void init() throws Exception {
		initS3Client();
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

		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			/* Create bucket with Canned ACL AuthenticatedRead */
			try {
				final CreateBucketRequest request = new CreateBucketRequest(eucaUUID()).withCannedAcl(CannedAccessControlList.AuthenticatedRead);
				print("Creating bucket " + request.getBucketName() + " with canned ACL " + request.getCannedAcl());
				Bucket bucket = s3.createBucket(request);
				cleanupTasks.add(new Runnable() {
					@Override
					public void run() {
						print("Deleting bucket " + request.getBucketName());
						s3.deleteBucket(request.getBucketName());
					}
				});

				assertTrue("Invalid reference to bucket", bucket != null);
				assertTrue("Mismatch in bucket names. Expected bucket name to be " + request.getBucketName() + ", but got " + bucket.getName(), request
						.getBucketName().equals(bucket.getName()));

				print("Getting ACL for bucket " + request.getBucketName());
				AccessControlList acl = s3.getBucketAcl(request.getBucketName());
				assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 2 but got " + acl.getGrants().size(), acl.getGrants().size() == 2);

				Iterator<Grant> iterator = acl.getGrants().iterator();
				while (iterator.hasNext()) {
					Grant grant = iterator.next();
					if (grant.getGrantee() instanceof CanonicalGrantee) {
						assertTrue("Expected grantee to be bucket owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
								.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
						assertTrue("Grantee should have full control", grant.getPermission().equals(Permission.FullControl));
					} else {
						assertTrue("Grantee of type GroupGrantee not found", grant.getGrantee() instanceof GroupGrantee);
						assertTrue("Expected grantee to be AutheticatedUsers but found " + ((GroupGrantee) grant.getGrantee()),
								((GroupGrantee) grant.getGrantee()).equals(GroupGrantee.AuthenticatedUsers));
						assertTrue("Grantee does not have " + Permission.Read.toString() + " privileges", grant.getPermission().equals(Permission.Read));
					}
				}
			} catch (AmazonServiceException ase) {
				ase.printStackTrace();
				print("Caught Exception: " + ase.getMessage());
				print("Reponse Status Code: " + ase.getStatusCode());
				print("Error Code: " + ase.getErrorCode());
				print("Request ID: " + ase.getRequestId());
				assertThat(false, "Failed to create bucket");
			}
		} finally {
			Collections.reverse(cleanupTasks);
			for (final Runnable cleanupTask : cleanupTasks) {
				try {
					cleanupTask.run();
				} catch (Exception e) {
					e.printStackTrace();
				}
			}
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

		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			/* Create bucket with Canned ACL BucketOwnerFullControl */
			try {
				final CreateBucketRequest request = new CreateBucketRequest(eucaUUID()).withCannedAcl(CannedAccessControlList.BucketOwnerFullControl);
				print("Creating bucket " + request.getBucketName() + " with canned ACL " + request.getCannedAcl());
				Bucket bucket = s3.createBucket(request);
				cleanupTasks.add(new Runnable() {
					@Override
					public void run() {
						print("Deleting bucket " + request.getBucketName());
						s3.deleteBucket(request.getBucketName());
					}
				});

				assertTrue("Invalid reference to bucket", bucket != null);
				assertTrue("Mismatch in bucket names. Expected bucket name to be " + request.getBucketName() + ", but got " + bucket.getName(), request
						.getBucketName().equals(bucket.getName()));

				print("Getting ACL for bucket " + request.getBucketName());
				AccessControlList acl = s3.getBucketAcl(request.getBucketName());
				assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 1 but got " + acl.getGrants().size(), acl.getGrants().size() == 1);

				Iterator<Grant> iterator = acl.getGrants().iterator();
				while (iterator.hasNext()) {
					Grant grant = iterator.next();
					assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
					assertTrue("Expected grantee to be bucket owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
							.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
					assertTrue("Grantee does not have " + Permission.FullControl.toString() + " privileges",
							grant.getPermission().equals(Permission.FullControl));
				}
			} catch (AmazonServiceException ase) {
				ase.printStackTrace();
				print("Caught Exception: " + ase.getMessage());
				print("Reponse Status Code: " + ase.getStatusCode());
				print("Error Code: " + ase.getErrorCode());
				print("Request ID: " + ase.getRequestId());
				assertThat(false, "Failed to create bucket");
			}
		} finally {
			Collections.reverse(cleanupTasks);
			for (final Runnable cleanupTask : cleanupTasks) {
				try {
					cleanupTask.run();
				} catch (Exception e) {
					e.printStackTrace();
				}
			}
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

		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			/* Create bucket with Canned ACL BucketOwnerRead */
			try {
				final CreateBucketRequest request = new CreateBucketRequest(eucaUUID()).withCannedAcl(CannedAccessControlList.BucketOwnerRead);
				print("Creating bucket " + request.getBucketName() + " with canned ACL " + request.getCannedAcl());
				Bucket bucket = s3.createBucket(request);
				cleanupTasks.add(new Runnable() {
					@Override
					public void run() {
						print("Deleting bucket " + request.getBucketName());
						s3.deleteBucket(request.getBucketName());
					}
				});

				assertTrue("Invalid reference to bucket", bucket != null);
				assertTrue("Mismatch in bucket names. Expected bucket name to be " + request.getBucketName() + ", but got " + bucket.getName(), request
						.getBucketName().equals(bucket.getName()));

				print("Getting ACL for bucket " + request.getBucketName());
				AccessControlList acl = s3.getBucketAcl(request.getBucketName());
				assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 1 but got " + acl.getGrants().size(), acl.getGrants().size() == 1);

				Iterator<Grant> iterator = acl.getGrants().iterator();
				while (iterator.hasNext()) {
					Grant grant = iterator.next();
					assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
					assertTrue("Expected grantee to be bucket owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
							.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
					assertTrue("Grantee does not have " + Permission.FullControl.toString() + " privileges",
							grant.getPermission().equals(Permission.FullControl));
				}
			} catch (AmazonServiceException ase) {
				ase.printStackTrace();
				print("Caught Exception: " + ase.getMessage());
				print("Reponse Status Code: " + ase.getStatusCode());
				print("Error Code: " + ase.getErrorCode());
				print("Request ID: " + ase.getRequestId());
				assertThat(false, "Failed to create bucket");
			}
		} finally {
			Collections.reverse(cleanupTasks);
			for (final Runnable cleanupTask : cleanupTasks) {
				try {
					cleanupTask.run();
				} catch (Exception e) {
					e.printStackTrace();
				}
			}
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

		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			/* Create bucket with Canned ACL LogDeliveryWrite */
			try {
				final CreateBucketRequest request = new CreateBucketRequest(eucaUUID()).withCannedAcl(CannedAccessControlList.LogDeliveryWrite);
				print("Creating bucket " + request.getBucketName() + " with canned ACL " + request.getCannedAcl());
				Bucket bucket = s3.createBucket(request);
				cleanupTasks.add(new Runnable() {
					@Override
					public void run() {
						print("Deleting bucket " + request.getBucketName());
						s3.deleteBucket(request.getBucketName());
					}
				});

				assertTrue("Invalid reference to bucket", bucket != null);
				assertTrue("Mismatch in bucket names. Expected bucket name to be " + request.getBucketName() + ", but got " + bucket.getName(), request
						.getBucketName().equals(bucket.getName()));

				print("Getting ACL for bucket " + request.getBucketName());
				AccessControlList acl = s3.getBucketAcl(request.getBucketName());
				assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 3 but got " + acl.getGrants().size(), acl.getGrants().size() == 3);

				Iterator<Grant> iterator = acl.getGrants().iterator();
				while (iterator.hasNext()) {
					Grant grant = iterator.next();
					if (grant.getGrantee() instanceof CanonicalGrantee) {
						assertTrue("Expected grantee to be bucket owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
								.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
						assertTrue("Grantee should have full control", grant.getPermission().equals(Permission.FullControl));
					} else {
						assertTrue("Grantee of type GroupGrantee not found", grant.getGrantee() instanceof GroupGrantee);
						assertTrue("Expected grantee to be LogDelivery but found " + ((GroupGrantee) grant.getGrantee()),
								((GroupGrantee) grant.getGrantee()).equals(GroupGrantee.LogDelivery));
						assertTrue("Grantee does not have " + Permission.Write.toString() + " and/or " + grant.getPermission().equals(Permission.ReadAcp)
								+ " privileges", grant.getPermission().equals(Permission.Write) || grant.getPermission().equals(Permission.ReadAcp));
					}
				}
			} catch (AmazonServiceException ase) {
				ase.printStackTrace();
				print("Caught Exception: " + ase.getMessage());
				print("Reponse Status Code: " + ase.getStatusCode());
				print("Error Code: " + ase.getErrorCode());
				print("Request ID: " + ase.getRequestId());
				assertThat(false, "Failed to create bucket");
			}
		} finally {
			Collections.reverse(cleanupTasks);
			for (final Runnable cleanupTask : cleanupTasks) {
				try {
					cleanupTask.run();
				} catch (Exception e) {
					e.printStackTrace();
				}
			}
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

		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			/* Create bucket with Canned ACL Private */
			try {
				final CreateBucketRequest request = new CreateBucketRequest(eucaUUID()).withCannedAcl(CannedAccessControlList.Private);
				print("Creating bucket " + request.getBucketName() + " with canned ACL " + request.getCannedAcl());
				Bucket bucket = s3.createBucket(request);
				cleanupTasks.add(new Runnable() {
					@Override
					public void run() {
						print("Deleting bucket " + request.getBucketName());
						s3.deleteBucket(request.getBucketName());
					}
				});

				assertTrue("Invalid reference to bucket", bucket != null);
				assertTrue("Mismatch in bucket names. Expected bucket name to be " + request.getBucketName() + ", but got " + bucket.getName(), request
						.getBucketName().equals(bucket.getName()));

				print("Getting ACL for bucket " + request.getBucketName());
				AccessControlList acl = s3.getBucketAcl(request.getBucketName());
				assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 1 but got " + acl.getGrants().size(), acl.getGrants().size() == 1);

				Iterator<Grant> iterator = acl.getGrants().iterator();
				while (iterator.hasNext()) {
					Grant grant = iterator.next();
					assertTrue("Grantee is not of type CanonicalGrantee", grant.getGrantee() instanceof CanonicalGrantee);
					assertTrue("Expected grantee to be bucket owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
							.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
					assertTrue("Grantee does not have " + Permission.FullControl.toString() + " privileges",
							grant.getPermission().equals(Permission.FullControl));
				}
			} catch (AmazonServiceException ase) {
				ase.printStackTrace();
				print("Caught Exception: " + ase.getMessage());
				print("Reponse Status Code: " + ase.getStatusCode());
				print("Error Code: " + ase.getErrorCode());
				print("Request ID: " + ase.getRequestId());
				assertThat(false, "Failed to create bucket");
			}
		} finally {
			Collections.reverse(cleanupTasks);
			for (final Runnable cleanupTask : cleanupTasks) {
				try {
					cleanupTask.run();
				} catch (Exception e) {
					e.printStackTrace();
				}
			}
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

		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			/* Create bucket with Canned ACL PublicRead */
			try {
				final CreateBucketRequest request = new CreateBucketRequest(eucaUUID()).withCannedAcl(CannedAccessControlList.PublicRead);
				print("Creating bucket " + request.getBucketName() + " with canned ACL " + request.getCannedAcl());
				Bucket bucket = s3.createBucket(request);
				cleanupTasks.add(new Runnable() {
					@Override
					public void run() {
						print("Deleting bucket " + request.getBucketName());
						s3.deleteBucket(request.getBucketName());
					}
				});

				assertTrue("Invalid reference to bucket", bucket != null);
				assertTrue("Mismatch in bucket names. Expected bucket name to be " + request.getBucketName() + ", but got " + bucket.getName(), request
						.getBucketName().equals(bucket.getName()));

				print("Getting ACL for bucket " + request.getBucketName());
				AccessControlList acl = s3.getBucketAcl(request.getBucketName());
				assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 2 but got " + acl.getGrants().size(), acl.getGrants().size() == 2);

				Iterator<Grant> iterator = acl.getGrants().iterator();
				while (iterator.hasNext()) {
					Grant grant = iterator.next();
					if (grant.getGrantee() instanceof CanonicalGrantee) {
						assertTrue("Expected grantee to be bucket owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
								.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
						assertTrue("Grantee should have full control", grant.getPermission().equals(Permission.FullControl));
					} else {
						assertTrue("Grantee of type GroupGrantee not found", grant.getGrantee() instanceof GroupGrantee);
						assertTrue("Expected grantee to be AutheticatedUsers but found " + ((GroupGrantee) grant.getGrantee()),
								((GroupGrantee) grant.getGrantee()).equals(GroupGrantee.AllUsers));
						assertTrue("Grantee does not have " + Permission.Read.toString() + " privileges", grant.getPermission().equals(Permission.Read));
					}
				}
			} catch (AmazonServiceException ase) {
				ase.printStackTrace();
				print("Caught Exception: " + ase.getMessage());
				print("Reponse Status Code: " + ase.getStatusCode());
				print("Error Code: " + ase.getErrorCode());
				print("Request ID: " + ase.getRequestId());
				assertThat(false, "Failed to create bucket");
			}
		} finally {
			Collections.reverse(cleanupTasks);
			for (final Runnable cleanupTask : cleanupTasks) {
				try {
					cleanupTask.run();
				} catch (Exception e) {
					e.printStackTrace();
				}
			}
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

		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			/* Create bucket with Canned ACL PublicReadWrite */
			try {
				final CreateBucketRequest request = new CreateBucketRequest(eucaUUID()).withCannedAcl(CannedAccessControlList.PublicReadWrite);
				print("Creating bucket " + request.getBucketName() + " with canned ACL " + request.getCannedAcl());
				Bucket bucket = s3.createBucket(request);
				cleanupTasks.add(new Runnable() {
					@Override
					public void run() {
						print("Deleting bucket " + request.getBucketName());
						s3.deleteBucket(request.getBucketName());
					}
				});

				assertTrue("Invalid reference to bucket", bucket != null);
				assertTrue("Mismatch in bucket names. Expected bucket name to be " + request.getBucketName() + ", but got " + bucket.getName(), request
						.getBucketName().equals(bucket.getName()));

				print("Getting ACL for bucket " + request.getBucketName());
				AccessControlList acl = s3.getBucketAcl(request.getBucketName());
				assertTrue("Mismatch in number of ACLs associated with the bucket. Expected 2 but got " + acl.getGrants().size(), acl.getGrants().size() == 3);

				Iterator<Grant> iterator = acl.getGrants().iterator();
				while (iterator.hasNext()) {
					Grant grant = iterator.next();
					if (grant.getGrantee() instanceof CanonicalGrantee) {
						assertTrue("Expected grantee to be bucket owner " + acl.getOwner().getId() + ", but found " + grant.getGrantee().getIdentifier(), grant
								.getGrantee().getIdentifier().equals(acl.getOwner().getId()));
						assertTrue("Grantee should have full control", grant.getPermission().equals(Permission.FullControl));
					} else {
						assertTrue("Grantee of type GroupGrantee not found", grant.getGrantee() instanceof GroupGrantee);
						assertTrue("Expected grantee to be AutheticatedUsers but found " + ((GroupGrantee) grant.getGrantee()),
								((GroupGrantee) grant.getGrantee()).equals(GroupGrantee.AllUsers));
						assertTrue("Grantee does not have " + Permission.Read.toString() + " and/or " + Permission.Write.toString() + " privileges", grant
								.getPermission().equals(Permission.Read) || grant.getPermission().equals(Permission.Write));
					}
				}
			} catch (AmazonServiceException ase) {
				ase.printStackTrace();
				print("Caught Exception: " + ase.getMessage());
				print("Reponse Status Code: " + ase.getStatusCode());
				print("Error Code: " + ase.getErrorCode());
				print("Request ID: " + ase.getRequestId());
				assertThat(false, "Failed to create bucket");
			}
		} finally {
			Collections.reverse(cleanupTasks);
			for (final Runnable cleanupTask : cleanupTasks) {
				try {
					cleanupTask.run();
				} catch (Exception e) {
					e.printStackTrace();
				}
			}
		}
	}
}
