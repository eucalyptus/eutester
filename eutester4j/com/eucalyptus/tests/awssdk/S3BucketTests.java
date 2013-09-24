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
import com.amazonaws.services.s3.model.AmazonS3Exception;
import com.amazonaws.services.s3.model.Bucket;
import com.amazonaws.services.s3.model.BucketLoggingConfiguration;
import com.amazonaws.services.s3.model.BucketVersioningConfiguration;
import com.amazonaws.services.s3.model.CannedAccessControlList;
import com.amazonaws.services.s3.model.CanonicalGrantee;
import com.amazonaws.services.s3.model.Grant;
import com.amazonaws.services.s3.model.GroupGrantee;
import com.amazonaws.services.s3.model.Permission;
import com.amazonaws.services.s3.model.SetBucketLoggingConfigurationRequest;
import com.amazonaws.services.s3.model.SetBucketVersioningConfigurationRequest;

/**
 * <p>
 * This class contains tests for basic operations on S3 buckets.
 * </p>
 * 
 * </p> As of 9/24/2013 all tests passed against S3. {@link #versioningConfiguration()} fails against Walrus. Jira ticket for the issue - <a
 * href="https://eucalyptus.atlassian.net/browse/EUCA-7635">EUCA-7635</a> </p>
 * 
 * @author Swathi Gangisetty
 * 
 */
public class S3BucketTests {

	@BeforeClass
	public void init() throws Exception {
		initS3Client();
	}

	/**
	 * Tests for the following S3 APIs
	 * 
	 * <li>createBucket</li> <li>deleteBucket</li> <li>listBuckets</li> <li>doesBucketExist</li> <li>getBucketLocation</li> <li>getBucketLoggingConfiguration</li>
	 * <li>getBucketVersioningConfiguration</li>
	 */
	@Test
	public void bucketBasics() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - bucketBasics");

		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			try {
				final String bucketName = eucaUUID();
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
				assertTrue("Mismatch in bucket names. Expected bucket name to be " + bucketName + ", but got " + bucket.getName(),
						bucketName.equals(bucket.getName()));

				print("Listing all buckets");
				List<Bucket> bucketList = s3.listBuckets();
				assertTrue("Invalid or empty bucket list", bucketList != null && !bucketList.isEmpty());
				boolean found = false;
				for (Bucket buck : bucketList) {
					if (buck.getName().equals(bucketName)) {
						found = true;
						break;
					}
				}
				assertTrue("Expected newly created bucket to be listed in the buckets but did not", found);

				print("Checking if the bucket " + bucketName + " exists");
				assertTrue("Expected to find " + bucketName + ", but the bucket was not found", s3.doesBucketExist(bucketName));

				print("Fetching bucket location for " + bucketName);
				String location = s3.getBucketLocation(bucketName);
				assertTrue("Invalid result for bucket location, expected a string", location != null && !location.isEmpty());

				print("Fetching bucket logging configuration for " + bucketName);
				BucketLoggingConfiguration loggingConfig = s3.getBucketLoggingConfiguration(bucketName);
				assertTrue("Invalid result for bucket logging configuration", loggingConfig != null);
				assertTrue("Expected bucket logging to be disabled, but got enabled", !loggingConfig.isLoggingEnabled());
				assertTrue("Expected destination bucket to be null, but got " + loggingConfig.getDestinationBucketName(),
						loggingConfig.getDestinationBucketName() == null);
				assertTrue("Expected log file prefix to be null, but got " + loggingConfig.getLogFilePrefix(), loggingConfig.getLogFilePrefix() == null);

				print("Fetching bucket versioning configuration for " + bucketName);
				BucketVersioningConfiguration versioning = s3.getBucketVersioningConfiguration(bucketName);
				assertTrue("Invalid result for bucket versioning configuration", versioning != null);
				assertTrue("Expected bucket versioning configuration to be OFF, but found it to be " + versioning.getStatus(),
						versioning.getStatus().equals(BucketVersioningConfiguration.OFF));

				// NPE against Walrus
				// print("Fetching bucket policy for " + bucketName);
				// BucketPolicy bucketPolicy = s3.getBucketPolicy(bucketName);
				// assertTrue("Invalid result for bucket policy", bucketPolicy != null);
				// assertTrue("Expected empty or null policy text, but got back " + bucketPolicy.getPolicyText(), bucketPolicy.getPolicyText() == null);
			} catch (AmazonServiceException ase) {
				ase.printStackTrace();
				print("Caught Exception: " + ase.getMessage());
				print("Reponse Status Code: " + ase.getStatusCode());
				print("Error Code: " + ase.getErrorCode());
				print("Request ID: " + ase.getRequestId());
				assertThat(false, "Failed to execute basic bucket tests");
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
	 * Test for changing logging configuration of a bucket and verifying it.
	 */
	@Test
	public void loggingConfiguration() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - loggingConfiguration");

		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			try {
				final String bucketName = eucaUUID();
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
				assertTrue("Mismatch in bucket names. Expected bucket name to be " + bucketName + ", but got " + bucket.getName(),
						bucketName.equals(bucket.getName()));

				print("Fetching bucket logging configuration for " + bucketName);
				BucketLoggingConfiguration loggingConfig = s3.getBucketLoggingConfiguration(bucketName);
				assertTrue("Invalid result for bucket logging configuration", loggingConfig != null);
				assertTrue("Expected bucket logging to be disabled, but got enabled", !loggingConfig.isLoggingEnabled());

				boolean error = false;
				try {
					print("Setting bucket logging configuration before assigning log-delivery group WRITE and READ_ACP permissions for " + bucketName);
					s3.setBucketLoggingConfiguration(new SetBucketLoggingConfigurationRequest(bucketName,
							new BucketLoggingConfiguration(bucketName, bucketName)));
				} catch (AmazonS3Exception ex) {
					assertTrue("Expected error code to be 400, but got " + ex.getStatusCode(), ex.getStatusCode() == 400);
					error = true;
				} finally {
					assertTrue(
							"Expected AmazonS3Exception for enabling bucket logging configuration before assigning log-delivery group appropriate permissions",
							error);
				}

				print("Setting canned ACL log-delivery-write for " + bucketName);
				s3.setBucketAcl(bucketName, CannedAccessControlList.LogDeliveryWrite);

				print("Getting ACL for bucket " + bucketName);
				AccessControlList acl = s3.getBucketAcl(bucketName);
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

				print("Setting bucket logging configuration after assigning log-delivery group WRITE and READ_ACP permissions for " + bucketName);
				s3.setBucketLoggingConfiguration(new SetBucketLoggingConfigurationRequest(bucketName, new BucketLoggingConfiguration(bucketName, bucketName)));

				print("Fetching bucket logging configuration for " + bucketName);
				loggingConfig = s3.getBucketLoggingConfiguration(bucketName);
				assertTrue("Invalid result for bucket logging configuration", loggingConfig != null);
				assertTrue("Expected bucket logging to be enabled, but got disabled", loggingConfig.isLoggingEnabled());
				assertTrue("Expected destination bucket to be " + bucketName + ", but got " + loggingConfig.getDestinationBucketName(), loggingConfig
						.getDestinationBucketName().equals(bucketName));
				assertTrue("Expected log file prefix to be " + bucketName + ", but got " + loggingConfig.getLogFilePrefix(), loggingConfig.getLogFilePrefix()
						.equals(bucketName));

			} catch (AmazonServiceException ase) {
				ase.printStackTrace();
				print("Caught Exception: " + ase.getMessage());
				print("Reponse Status Code: " + ase.getStatusCode());
				print("Error Code: " + ase.getErrorCode());
				print("Request ID: " + ase.getRequestId());
				assertThat(false, "Failed to execute bucket logging configuration test");
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
	 * Test for changing versioning configuration of a bucket and verifying it.
	 * 
	 * <p>
	 * Test failed against Walrus. Versioning configuration cannot be turned OFF once its ENABLED/SUSPENDED on a bucket. While S3 throws an exception for such a
	 * request, Walrus does not. The versioning configuration remains unchanged but no error is received
	 * </p>
	 */
	@Test
	public void versioningConfiguration() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - versioningConfiguration");

		final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
		try {
			try {
				final String bucketName = eucaUUID();
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
				assertTrue("Mismatch in bucket names. Expected bucket name to be " + bucketName + ", but got " + bucket.getName(),
						bucketName.equals(bucket.getName()));

				print("Fetching bucket versioning configuration for the newly created bucket " + bucketName);
				BucketVersioningConfiguration versioning = s3.getBucketVersioningConfiguration(bucketName);
				assertTrue("Invalid result for bucket versioning configuration", versioning != null);
				assertTrue("Expected bucket versioning configuration to be OFF, but found it to be " + versioning.getStatus(),
						versioning.getStatus().equals(BucketVersioningConfiguration.OFF));

				print("Setting bucket versioning configuration to ENABLED");
				s3.setBucketVersioningConfiguration(new SetBucketVersioningConfigurationRequest(bucketName, new BucketVersioningConfiguration()
						.withStatus(BucketVersioningConfiguration.ENABLED)));

				print("Fetching bucket versioning configuration after setting it to ENABLED");
				versioning = s3.getBucketVersioningConfiguration(bucketName);
				assertTrue("Invalid result for bucket versioning configuration", versioning != null);
				assertTrue("Expected bucket versioning configuration to be ENABLED, but found it to be " + versioning.getStatus(), versioning.getStatus()
						.equals(BucketVersioningConfiguration.ENABLED));

				print("Setting bucket versioning configuration to SUSPENDED");
				s3.setBucketVersioningConfiguration(new SetBucketVersioningConfigurationRequest(bucketName, new BucketVersioningConfiguration()
						.withStatus(BucketVersioningConfiguration.SUSPENDED)));

				print("Fetching bucket versioning configuration after setting it to SUSPENDED");
				versioning = s3.getBucketVersioningConfiguration(bucketName);
				assertTrue("Invalid result for bucket versioning configuration", versioning != null);
				assertTrue("Expected bucket versioning configuration to be SUSPENDED, but found it to be " + versioning.getStatus(), versioning.getStatus()
						.equals(BucketVersioningConfiguration.SUSPENDED));

				boolean error = false;
				try {
					s3.setBucketVersioningConfiguration(new SetBucketVersioningConfigurationRequest(bucketName, new BucketVersioningConfiguration()
							.withStatus(BucketVersioningConfiguration.OFF)));
				} catch (AmazonS3Exception ex) {
					assertTrue("Expected error code to be 400, but got " + ex.getStatusCode(), ex.getStatusCode() == 400);
					error = true;
				} finally {
					assertTrue("Expected AmazonS3Exception for setting bucking versioning configuration to OFF", error);
				}

			} catch (AmazonServiceException ase) {
				ase.printStackTrace();
				print("Caught Exception: " + ase.getMessage());
				print("Reponse Status Code: " + ase.getStatusCode());
				print("Error Code: " + ase.getErrorCode());
				print("Request ID: " + ase.getRequestId());
				assertThat(false, "Failed to execute bucket versioning configuration test");
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
