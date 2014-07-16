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
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.NavigableMap;
import java.util.Random;
import java.util.TreeMap;
import java.util.TreeSet;

import org.apache.commons.lang.StringUtils;
import org.testng.annotations.AfterClass;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import com.amazonaws.AmazonServiceException;
import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.model.Bucket;
import com.amazonaws.services.s3.model.BucketVersioningConfiguration;
import com.amazonaws.services.s3.model.ListVersionsRequest;
import com.amazonaws.services.s3.model.PutObjectResult;
import com.amazonaws.services.s3.model.S3VersionSummary;
import com.amazonaws.services.s3.model.SetBucketVersioningConfigurationRequest;
import com.amazonaws.services.s3.model.VersionListing;
import com.amazonaws.util.BinaryUtils;
import com.amazonaws.util.Md5Utils;

/**
 * <p>This class contains tests for listing object versions in a bucket.</p>
 * 
 * <p>All tests are passing after the commit 2841c3707b6b918bd84b2e849d107d154ad2a2e2</p>
 * 
 * <li>All tests failed against Walrus due to <a href="https://eucalyptus.atlassian.net/browse/EUCA-7855">EUCA-7855</a> unless the owner canonical ID
 * verification is commented out</li>
 * 
 * <li>{@link #deleteMarker()} fails against Walrus due to <a href="https://eucalyptus.atlassian.net/browse/EUCA-7818">EUCA-7818</a></li>
 * 
 * <li>{@link #keyMarker()} fails against Walrus due to <a href="https://eucalyptus.atlassian.net/browse/EUCA-7985">EUCA-7985</a></li>
 * 
 * <li>{@link #keyMarkerVersionIdMarker()} fails against Walrus due to <a href="https://eucalyptus.atlassian.net/browse/EUCA-7985">EUCA-7985</a> and <a
 * href="https://eucalyptus.atlassian.net/browse/EUCA-7986">EUCA-7986</a></li>
 * 
 * <li>{@link #delimiterAndPrefix()} fails against Walrus due to <a href="https://eucalyptus.atlassian.net/browse/EUCA-7991">EUCA-7991</a></li>
 * 
 * <li>{@link #maxKeysSingleKeyMultipleUploads()} fails against Walrus due to <a href="https://eucalyptus.atlassian.net/browse/EUCA-7985">EUCA-7985</a> and <a
 * href="https://eucalyptus.atlassian.net/browse/EUCA-7986">EUCA-7986</a></li>
 * 
 * @author Swathi Gangisetty
 * 
 */
public class S3ListVersionsTests {

	private static String bucketName = null;
	private static List<Runnable> cleanupTasks = null;
	private static Random random = new Random();
	private static File fileToPut = new File("test.dat");
	private static long size = 0;
	private static String md5 = null;
	private static String ownerID = null;
	private static AmazonS3 s3 = null;
	private static String account = null;
	private static String VALID_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
	private static final int DEFAULT_MAX_KEYS = 1000;

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
		ownerID = s3.getS3AccountOwner().getId();
		md5 = BinaryUtils.toHex(Md5Utils.computeMD5Hash(new FileInputStream(fileToPut)));
		size = fileToPut.length();
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
		bucketName = eucaUUID();
		// bucketName = "test-bucket";
		// bucketName = "marker-test";
		cleanupTasks = new ArrayList<Runnable>();
		print("Creating bucket " + bucketName);
		Bucket bucket = s3.createBucket(bucketName);
		cleanupTasks.add(new Runnable() {
			@Override
			public void run() {
				print("Deleting bucket " + bucketName);
				try {
					s3.deleteBucket(bucketName);
				} catch (AmazonServiceException ase) {
					printException(ase);
					assertThat(false, "Failed to delete bucket " + bucketName);
				}
			}
		});

		assertTrue("Invalid reference to bucket", bucket != null);
		assertTrue("Mismatch in bucket names. Expected bucket name to be " + bucketName + ", but got " + bucket.getName(), bucketName.equals(bucket.getName()));

		// Enable versioning on bucket
		enableBucketVersioning(bucketName);
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
	 * <p>Test for verifying ordering of version information for a single key in a bucket</p>
	 * 
	 * <p>This test uploads an object using the same key multiple times. It fetches the version information for the bucket and verifies it for chronological
	 * ordering of versions</p>
	 */
	@Test
	public void oneKey() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - oneKey");

		try {
			final String key = eucaUUID();
			LinkedList<String> versionIdList = new LinkedList<String>();
			int uploads = 3 + random.nextInt(8);// 3-10 uploads
			print("Number of uploads: " + uploads);
			VersionListing versions = null;

			for (int i = 0; i < uploads; i++) {
				// Upload an object
				putObject(bucketName, key, fileToPut, versionIdList);

				// List the object versions and verify them against the put object results
				versions = listVersions(bucketName, null, null, null, null, null, false);
				verifyVersionSummaries(key, versionIdList, versions.getVersionSummaries());
			}

			// List the object versions using a prefix and verify them against the put object results
			versions = listVersions(bucketName, null, null, null, null, null, false);
			verifyVersionSummaries(key, versionIdList, versions.getVersionSummaries());
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run oneKey");
		}
	}

	/**
	 * <p>Test for verifying ordering of version information for multiple keys in a bucket</p>
	 * 
	 * <p>This test uploads objects using the different keys multiple times. It fetches the version information for the bucket and verifies it for lexicographic
	 * ordering of keys and chronological ordering of versions</p>
	 */
	@Test
	public void prefix() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - prefix");

		try {
			int keys = 3 + random.nextInt(3); // 3-5 keys
			int uploads = 2 + random.nextInt(4);// 2-5 uploads
			Map<String, List<String>> keyVersionMap = new TreeMap<String, List<String>>();
			int idCount = 0;
			VersionListing versions = null;

			print("Number of keys: " + keys);
			print("Number of uploads per key: " + uploads);

			for (int i = 0; i < keys; i++) {
				String key = VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length())) + eucaUUID(); // Prefix it with any character in the valid chars
				print("Key name: " + key);
				LinkedList<String> partialVersionIdList = new LinkedList<String>();

				// Upload object multiple times using the key1
				for (int j = 0; j < uploads; j++) {
					putObject(bucketName, key, fileToPut, partialVersionIdList);
				}

				// List the object versions and verify them against the put object results
				versions = listVersions(bucketName, key, null, null, null, null, false);
				verifyVersionSummaries(key, partialVersionIdList, versions.getVersionSummaries());

				// Reverse the version ID list and add it to the map
				Collections.reverse(partialVersionIdList);

				// Put the key name and version ID list in the map. The map should order the keys in lexicographic order
				keyVersionMap.put(key, partialVersionIdList);

				// Increment version elements
				idCount = idCount + partialVersionIdList.size();
			}

			// List versions and verify the results
			versions = listVersions(bucketName, null, null, null, null, null, false);
			assertTrue("Expected version summary list to be of size " + idCount + ", but got a list of size " + versions.getVersionSummaries().size(), versions
					.getVersionSummaries().size() == idCount);
			Iterator<S3VersionSummary> summaryIterator = versions.getVersionSummaries().iterator();

			for (Map.Entry<String, List<String>> mapEntry : keyVersionMap.entrySet()) {
				for (String versionId : mapEntry.getValue()) {
					S3VersionSummary versionSummary = summaryIterator.next();
					assertTrue("Expected versions to be lexicographically and chronologically ordered. Verification failed for key " + mapEntry.getKey()
							+ ". Expected version ID " + versionId + ", but got " + versionSummary.getVersionId(),
							versionSummary.getVersionId().equals(versionId));
					assertTrue("Expected delete marker to be set to false but found it to be true", !versionSummary.isDeleteMarker());
					verifyVersionCommonElements(versionSummary, mapEntry.getKey());
				}
			}
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run prefix");
		}
	}

	/**
	 * <p>Test for verifying delete markers and verifying the ordering of version information for a single key in a bucket</p>
	 * 
	 * <p>This test uploads an object using the same key multiple times, deletes the object without specifying the version and repeats the upload step again.
	 * After each action, the test fetches the version information for the bucket and verifies it for chronological ordering of versions and delete markers.</p>
	 * 
	 * <p>Test failed against Walrus. Walrus does not list the delete marker after the object is deleted without specifying the version.</p>
	 * 
	 * @see <a href="https://eucalyptus.atlassian.net/browse/EUCA-7818">EUCA-7818</a>
	 */
	@Test
	public void deleteMarker() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - deleteMarker");

		try {
			final String key = eucaUUID();
			LinkedList<String> versionIdList = new LinkedList<String>();
			final List<String> deleteMarkers = new ArrayList<String>();
			int uploads = 2 + random.nextInt(4);// 2-5 uploads
			VersionListing versions = null;

			print("Number of uploads: " + uploads);

			// Upload object using the same key
			for (int i = 0; i < uploads; i++) {
				putObject(bucketName, key, fileToPut, versionIdList);
			}
			// List the object versions and verify them against the put object results
			versions = listVersions(bucketName, null, null, null, null, null, false);
			verifyVersionSummaries(key, versionIdList, versions.getVersionSummaries());

			// Delete the object without specifying the version
			print("Deleting object " + key);
			s3.deleteObject(bucketName, key);

			// List versions and verify the results for delete marker
			versions = listVersions(bucketName, null, null, null, null, null, false);
			assertTrue("Expected version summary list to be of size " + (versionIdList.size() + 1) + ", but got a list of size "
					+ versions.getVersionSummaries().size() + ". Delete marker might be missing",
					versions.getVersionSummaries().size() == (versionIdList.size() + 1));

			Iterator<S3VersionSummary> summaryIterator = versions.getVersionSummaries().iterator();
			Iterator<String> versionIdIterator = versionIdList.descendingIterator();

			// The first version summary should be a delete marker and the latest marker
			S3VersionSummary versionSummary = summaryIterator.next();
			assertTrue("Invalid version ID", versionSummary.getVersionId() != null);
			assertTrue("Expected delete marker to be set to true but found it to be false", versionSummary.isDeleteMarker());
			assertTrue("Expected latest marker to be set to true but found it to be false", versionSummary.isLatest());
			assertTrue("Expected version ID of delete-marker to be unique", !versionIdList.contains(versionSummary.getVersionId()));
			verifyDeleteMarkerCommonElements(versionSummary, key);
			deleteMarkers.add(versionSummary.getVersionId());

			// Add a cleanup task for the delete markers
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					for (String versionId : deleteMarkers) {
						print("Deleting delete marker for key " + key + ", with version " + versionId);
						s3.deleteVersion(bucketName, key, versionId);
					}
				}
			});

			// Verify the remaining version summaries against the version ID list
			while (versionIdIterator.hasNext()) {
				versionSummary = summaryIterator.next();
				assertTrue("Expected versions to be chronologically ordered", versionIdIterator.next().equals(versionSummary.getVersionId()));
				assertTrue("Expected delete marker to be set to false but found it to be true", !versionSummary.isDeleteMarker());
				assertTrue("Expected latest marker to be set to false but found it to be true", !versionSummary.isLatest());
				verifyVersionCommonElements(versionSummary, key);
			}

			// Get the object metadata
			boolean error = false;
			try {
				s3.getObjectMetadata(bucketName, key);
			} catch (AmazonServiceException ase) {
				assertTrue("Expected status code to be 404, but got " + ase.getStatusCode(), ase.getStatusCode() == 404);
				error = true;
			} finally {
				assertTrue("Expected to get 404 NOT FOUND error on get object but did not", error);
			}

			// Upload object using the same key
			for (int i = 0; i < uploads; i++) {
				putObject(bucketName, key, fileToPut, versionIdList);
			}

			// List versions and verify it
			versions = listVersions(bucketName, null, null, null, null, null, false);
			assertTrue("Expected version summary list to be of size " + (versionIdList.size() + deleteMarkers.size()) + ", but got a list of size "
					+ versions.getVersionSummaries().size() + ". Delete marker might be missing",
					versions.getVersionSummaries().size() == (versionIdList.size() + deleteMarkers.size()));

			summaryIterator = versions.getVersionSummaries().iterator();
			versionIdIterator = versionIdList.descendingIterator();

			// The first version summary must be marked as the latest
			versionSummary = summaryIterator.next();
			int deleteMarkerCountdown = uploads;
			assertTrue("Expected version to be chronologically ordered", versionIdIterator.next().equals(versionSummary.getVersionId()));
			assertTrue("Expected delete marker to be set to false but found it to be true", !versionSummary.isDeleteMarker());
			assertTrue("Expected latest marker to be set to true but found it to be false", versionSummary.isLatest());

			while (summaryIterator.hasNext()) {
				versionSummary = summaryIterator.next();
				deleteMarkerCountdown--;
				if (deleteMarkerCountdown == 0) {
					assertTrue("Expected version summary element to be a delete marker", deleteMarkers.contains(versionSummary.getVersionId()));
					assertTrue("Expected delete marker to be set to true but found it to be false", versionSummary.isDeleteMarker());
					assertTrue("Expected latest marker to be set to false but found it to be true", !versionSummary.isLatest());
					verifyDeleteMarkerCommonElements(versionSummary, key);
				} else {
					assertTrue("Expected versions to be chronologically ordered", versionIdIterator.next().equals(versionSummary.getVersionId()));
					assertTrue("Expected delete marker to be set to false but found it to be true", !versionSummary.isDeleteMarker());
					assertTrue("Expected latest marker to be set to false but found it to be true", !versionSummary.isLatest());
					verifyVersionCommonElements(versionSummary, key);
				}
			}
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run deleteMarker");
		}
	}

	/**
	 * <p>Test for listing and verifying object versions using key-marker and no version-id-marker.</p>
	 * 
	 * <p>Test failed against Walrus. Results returned by Walrus are inclusive of the key-marker where as S3's results are exclusive</p>
	 * 
	 * @see <a href="https://eucalyptus.atlassian.net/browse/EUCA-7985">EUCA-7985</a>
	 */
	@Test
	public void keyMarker() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - keyMarker");

		try {
			int keys = 3 + random.nextInt(8); // 3-10 keys
			int uploads = 2 + random.nextInt(4); // 2-5 uploads
			TreeMap<String, List<String>> keyVersionMap = new TreeMap<String, List<String>>();
			VersionListing versions = null;

			print("Number of keys: " + keys);
			print("Number of uploads per key: " + uploads);

			for (int i = 0; i < keys; i++) {
				String key = VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length())) + eucaUUID(); // Prefix it with any character in the valid chars
				print("Key name: " + key);
				LinkedList<String> partialVersionIdList = new LinkedList<String>();

				// Upload object multiple times using the key
				for (int j = 0; j < uploads; j++) {
					putObject(bucketName, key, fileToPut, partialVersionIdList);
				}

				// List the object versions and verify them against the put object results
				versions = listVersions(bucketName, key, null, null, null, null, false);
				verifyVersionSummaries(key, partialVersionIdList, versions.getVersionSummaries());

				// Reverse the version ID list and add it to the map
				Collections.reverse(partialVersionIdList);

				// Put the key name and version ID list in the map. The map should order the keys in lexicographic order
				keyVersionMap.put(key, partialVersionIdList);
			}

			// Starting with every key in the ascending order, list the versions using that key as the key marker and verify that the results.
			for (String keyMarker : keyVersionMap.keySet()) {
				// Compute what the sorted versions should look like
				NavigableMap<String, List<String>> tailMap = keyVersionMap.tailMap(keyMarker, false);

				// List the versions using the key marker and verify
				versions = listVersions(bucketName, null, keyMarker, null, null, null, false);
				assertTrue("Expected version summary list to be of size " + (tailMap.size() * uploads) + ", but got a list of size "
						+ versions.getVersionSummaries().size(), versions.getVersionSummaries().size() == (tailMap.size() * uploads));
				Iterator<S3VersionSummary> summaryIterator = versions.getVersionSummaries().iterator();

				for (Map.Entry<String, List<String>> mapEntry : tailMap.entrySet()) {
					for (String versionId : mapEntry.getValue()) {
						S3VersionSummary versionSummary = summaryIterator.next();
						assertTrue("Expected versions to be lexicographically and chronologically ordered. Verification failed for key " + mapEntry.getKey()
								+ ". Expected version ID " + versionId + ", but got " + versionSummary.getVersionId(),
								versionSummary.getVersionId().equals(versionId));
						assertTrue("Expected delete marker to be set to false but found it to be true", !versionSummary.isDeleteMarker());
						verifyVersionCommonElements(versionSummary, mapEntry.getKey());
					}
				}
			}
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run keyMarker");
		}
	}

	/**
	 * <p>Test for listing and verifying object versions using key-marker and version-id-marker.</p>
	 * 
	 * <p>Test failed against Walrus. Results returned by Walrus are inclusive of the version summary that matches the key-marker and version-id-marker pair
	 * where as S3's results are exclusive. Version ID marker is missing in the response</p>
	 * 
	 * @see <a href="https://eucalyptus.atlassian.net/browse/EUCA-7985">EUCA-7985</a>
	 * @see <a href="https://eucalyptus.atlassian.net/browse/EUCA-7986">EUCA-7986</a>
	 */
	@Test
	public void keyMarkerVersionIdMarker() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - keyMarkerVersionIdMarker");

		try {
			int keys = 3 + random.nextInt(3); // 3-5 keys
			int uploads = 3 + random.nextInt(4); // 3-6 uploads
			TreeMap<String, List<String>> keyVersionMap = new TreeMap<String, List<String>>();
			VersionListing versions = null;

			print("Number of keys: " + keys);
			print("Number of uploads per key: " + uploads);

			for (int i = 0; i < keys; i++) {
				String key = VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length())) + eucaUUID(); // Prefix it with any character in the valid chars
				print("Key name: " + key);
				LinkedList<String> partialVersionIdList = new LinkedList<String>();

				// Upload object multiple times using the key
				for (int j = 0; j < uploads; j++) {
					putObject(bucketName, key, fileToPut, partialVersionIdList);
				}

				// Verify the linked list size
				assertTrue(
						"Expected version ID list size to be same as the number of uploads which is " + uploads + ", but got " + partialVersionIdList.size(),
						partialVersionIdList.size() == uploads);

				// List the object versions and verify them against the put object results
				versions = listVersions(bucketName, key, null, null, null, null, false);
				verifyVersionSummaries(key, partialVersionIdList, versions.getVersionSummaries());

				// Reverse the version ID list and add it to the map
				Collections.reverse(partialVersionIdList);

				// Put the key name and version ID list in the map. The map should order the keys in lexicographic order
				keyVersionMap.put(key, partialVersionIdList);
			}

			// Starting with every key in the ascending order, list the versions using that key as the key marker and verify that the results.
			for (Map.Entry<String, List<String>> mapEntry : keyVersionMap.entrySet()) {
				// Compute what the sorted versions should look like from the next key
				NavigableMap<String, List<String>> tailMap = keyVersionMap.tailMap(mapEntry.getKey(), false);

				for (int i = 0; i < uploads; i++) {
					// Compute what the sorted versions should look like this key
					List<String> tailList = mapEntry.getValue().subList(i + 1, uploads);

					// List the versions using the key marker and verify
					versions = listVersions(bucketName, null, mapEntry.getKey(), mapEntry.getValue().get(i), null, null, false);
					assertTrue("Expected version summary list to be of size " + ((tailMap.size() * uploads) + (uploads - i - 1)) + ", but got a list of size "
							+ versions.getVersionSummaries().size(), versions.getVersionSummaries().size() == ((tailMap.size() * uploads) + (uploads - i - 1)));

					Iterator<S3VersionSummary> summaryIterator = versions.getVersionSummaries().iterator();

					for (String versionId : tailList) {
						S3VersionSummary versionSummary = summaryIterator.next();
						assertTrue("Expected versions to be lexicographically and chronologically ordered. Verification failed for key " + mapEntry.getKey()
								+ ". Expected version ID " + versionId + ", but got " + versionSummary.getVersionId(),
								versionSummary.getVersionId().equals(versionId));
						assertTrue("Expected delete marker to be set to false but found it to be true", !versionSummary.isDeleteMarker());
						verifyVersionCommonElements(versionSummary, mapEntry.getKey());
					}

					for (Map.Entry<String, List<String>> tailMapEntry : tailMap.entrySet()) {
						for (String versionId : tailMapEntry.getValue()) {
							S3VersionSummary versionSummary = summaryIterator.next();
							assertTrue(
									"Expected versions to be lexicographically and chronologically ordered. Verification failed for key "
											+ tailMapEntry.getKey() + ". Expected version ID " + versionId + ", but got " + versionSummary.getVersionId(),
									versionSummary.getVersionId().equals(versionId));
							assertTrue("Expected delete marker to be set to false but found it to be true", !versionSummary.isDeleteMarker());
							verifyVersionCommonElements(versionSummary, tailMapEntry.getKey());
						}
					}
				}

			}
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run keyMarkerVersionIdMarker");
		}
	}

	/**
	 * Test for verifying common prefixes using a delimiter
	 */
	@Test
	public void delimiter() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - delimiter");

		try {
			int prefixes = 3 + random.nextInt(3); // 3-5 prefixes
			int keys = 2 + random.nextInt(3); // 2-5 keys
			int uploads = 2 + random.nextInt(3); // 2-4 uploads
			String delimiter = "/"; // Pick a random delimiter afterwards
			TreeMap<String, TreeMap<String, List<String>>> prefixKeyVersionMap = new TreeMap<String, TreeMap<String, List<String>>>();
			VersionListing versions = null;

			print("Number of prefixes: " + prefixes);
			print("Number of keys per prefix: " + keys);
			print("Number of uploads per key: " + uploads);

			for (int i = 0; i < prefixes; i++) {
				String prefix = VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length())) + eucaUUID() + delimiter;
				print("Prefix name: " + prefix);

				TreeMap<String, List<String>> keyVersionMap = new TreeMap<String, List<String>>();

				// Upload object multiple times using the key
				for (int j = 0; j < keys; j++) {
					String key = prefix + VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length())) + eucaUUID(); // Prefix it with any character in
					LinkedList<String> partialVersionIdList = new LinkedList<String>();
					print("Key name: " + key);

					for (int k = 0; k < uploads; k++) {
						putObject(bucketName, key, fileToPut, partialVersionIdList);
					}

					// Verify the linked list size
					assertTrue(
							"Expected version ID list size to be same as the number of uploads which is " + uploads + ", but got "
									+ partialVersionIdList.size(), partialVersionIdList.size() == uploads);

					// List the object versions and verify them against the put object results
					versions = listVersions(bucketName, key, null, null, null, null, false);
					verifyVersionSummaries(key, partialVersionIdList, versions.getVersionSummaries());

					// Reverse the version ID list and add it to the map
					Collections.reverse(partialVersionIdList);

					// Put the key name and version ID list in the map. The map should order the keys in lexicographic order
					keyVersionMap.put(key, partialVersionIdList);
				}

				prefixKeyVersionMap.put(prefix, keyVersionMap);
			}

			versions = listVersions(bucketName, null, null, null, delimiter, null, false);
			assertTrue("Expected to not get any version summaries but got a list of size " + versions.getVersionSummaries().size(), versions
					.getVersionSummaries().size() == 0);
			assertTrue("Expected common prefixes list to be of size " + prefixKeyVersionMap.size() + ", but got a list of size "
					+ versions.getCommonPrefixes().size(), versions.getCommonPrefixes().size() == prefixKeyVersionMap.size());
			for (String prefix : prefixKeyVersionMap.keySet()) {
				assertTrue("Expected common prefix list to contain " + prefix, versions.getCommonPrefixes().contains(prefix));
			}
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run delimiter");
		}
	}

	/**
	 * Test for verifying the common prefixes, delimiter and version information
	 * 
	 * Test fails against Walrus, prefixes in the common prefix list are incorrectly represented. The prefix part is not included, only the portion from prefix
	 * to the first occurrence of the delimiter is returned
	 * 
	 * @see <a href="https://eucalyptus.atlassian.net/browse/EUCA-7991">EUCA-7991</a>
	 */
	@Test
	public void delimiterAndPrefix() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - delimiterAndPrefix");

		try {
			int innerP = 2 + random.nextInt(4); // 2-5 inner prefixes
			int keys = 2 + random.nextInt(3); // 2-4 keys
			int uploads = 2 + random.nextInt(3); // 2-4 uploads
			String delimiter = "/";
			String outerPrefix = VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length())) + eucaUUID() + delimiter;
			VersionListing versions = null;
			TreeSet<String> commonPrefixes = new TreeSet<String>();
			TreeMap<String, List<String>> keyVersionMap = new TreeMap<String, List<String>>();

			print("Number of inner prefixes: " + innerP);
			print("Number of keys: " + keys);
			print("Number of uploads per key: " + uploads);
			print("Outer prefix: " + outerPrefix);

			for (int i = 0; i < innerP; i++) {
				String innerPrefix = VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length())) + eucaUUID() + delimiter;
				print("Inner prefix: " + innerPrefix);
				commonPrefixes.add(outerPrefix + innerPrefix);

				for (int j = 0; j < keys; j++) {
					String key = outerPrefix + innerPrefix + VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length())) + eucaUUID();
					LinkedList<String> partialVersionIdList = new LinkedList<String>();
					print("Key name: " + key);

					for (int k = 0; k < uploads; k++) {
						putObject(bucketName, key, fileToPut, partialVersionIdList);
					}

					// Verify the linked list size
					assertTrue(
							"Expected version ID list size to be same as the number of uploads which is " + uploads + ", but got "
									+ partialVersionIdList.size(), partialVersionIdList.size() == uploads);

					// List the object versions and verify them against the put object results
					versions = listVersions(bucketName, key, null, null, null, null, false);
					verifyVersionSummaries(key, partialVersionIdList, versions.getVersionSummaries());

					// Reverse the version ID list and add it to the map
					Collections.reverse(partialVersionIdList);

					// Put the key name and version ID list in the map. The map should order the keys in lexicographic order
					keyVersionMap.put(key, partialVersionIdList);
				}
			}

			// Upload something of the form outerprefix/key
			String key = outerPrefix + VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length())) + eucaUUID();
			LinkedList<String> partialVersionIdList = new LinkedList<String>();
			print("Key name: " + key);

			for (int k = 0; k < uploads; k++) {
				putObject(bucketName, key, fileToPut, partialVersionIdList);
			}
			versions = listVersions(bucketName, key, null, null, null, null, false);
			verifyVersionSummaries(key, partialVersionIdList, versions.getVersionSummaries());

			// Reverse the version ID list and add it to the map
			Collections.reverse(partialVersionIdList);

			// Put the key name and version ID list in the map. The map should order the keys in lexicographic order
			keyVersionMap.put(key, partialVersionIdList);

			// List versions and verify the results
			versions = listVersions(bucketName, null, null, null, null, null, false);
			assertTrue("Expected version summary list to be of size " + (keyVersionMap.size() * uploads) + ", but got a list of size "
					+ versions.getVersionSummaries().size(), versions.getVersionSummaries().size() == (keyVersionMap.size() * uploads));
			Iterator<S3VersionSummary> summaryIterator = versions.getVersionSummaries().iterator();

			for (Map.Entry<String, List<String>> mapEntry : keyVersionMap.entrySet()) {
				for (String versionId : mapEntry.getValue()) {
					S3VersionSummary versionSummary = summaryIterator.next();
					assertTrue("Expected versions to be lexicographically and chronologically ordered. Verification failed for key " + mapEntry.getKey()
							+ ". Expected version ID " + versionId + ", but got " + versionSummary.getVersionId(),
							versionSummary.getVersionId().equals(versionId));
					assertTrue("Expected delete marker to be set to false but found it to be true", !versionSummary.isDeleteMarker());
					verifyVersionCommonElements(versionSummary, mapEntry.getKey());
				}
			}

			// List the versions with prefix and delimiter and verify again
			versions = listVersions(bucketName, outerPrefix, null, null, delimiter, null, false);
			assertTrue("Expected version summaries list to be of size " + uploads + "but got a list of size " + versions.getVersionSummaries().size(), versions
					.getVersionSummaries().size() == uploads);
			assertTrue("Expected common prefixes list to be of size " + commonPrefixes.size() + ", but got a list of size "
					+ versions.getCommonPrefixes().size(), versions.getCommonPrefixes().size() == commonPrefixes.size());

			Iterator<String> prefixIterator = versions.getCommonPrefixes().iterator();
			for (String prefix : commonPrefixes) {
				String nextCommonPrefix = prefixIterator.next();
				assertTrue("Common prefixes are not ordered lexicographically. Expected " + prefix + ", but got " + nextCommonPrefix,
						prefix.equals(nextCommonPrefix));
			}

			// last key versions should be in the summary list
			summaryIterator = versions.getVersionSummaries().iterator();
			for (String versionId : keyVersionMap.get(key)) {
				S3VersionSummary versionSummary = summaryIterator.next();
				assertTrue("Expected versions to be lexicographically and chronologically ordered. Verification failed for key " + key
						+ ". Expected version ID " + versionId + ", but got " + versionSummary.getVersionId(), versionSummary.getVersionId().equals(versionId));
				assertTrue("Expected delete marker to be set to false but found it to be true", !versionSummary.isDeleteMarker());
				verifyVersionCommonElements(versionSummary, key);
			}
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run delimiterAndPrefix");
		}
	}

	/**
	 * Test for verifying paginated listing of versions
	 * 
	 * <p>Test failed against Walrus. Results returned by Walrus are inclusive of the version summary that matches the key-marker and version-id-marker pair
	 * where as S3's results are exclusive. Version ID marker is missing in the response</p>
	 * 
	 * @see <a href="https://eucalyptus.atlassian.net/browse/EUCA-7985">EUCA-7985</a>
	 * @see <a href="https://eucalyptus.atlassian.net/browse/EUCA-7986">EUCA-7986</a>
	 * 
	 */
	@Test
	public void maxKeysSingleKeyMultipleUploads() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - maxKeysSingleKeyMultipleUploads");

		try {
			int maxKeys = 3 + random.nextInt(3); // Max keys 3-5
			int multiplier = 3 + random.nextInt(4); // Max uploads 9-18
			String key = eucaUUID();
			LinkedList<String> versionIdList = new LinkedList<String>();

			print("Number of uploads: " + (maxKeys * multiplier));
			print("Number of max-keys in list versions request: " + maxKeys);

			for (int i = 0; i < (maxKeys * multiplier); i++) {
				putObject(bucketName, key, fileToPut, versionIdList);
			}
			Iterator<String> versionIdIterator = versionIdList.descendingIterator();

			String nextKeyMarker = null;
			String nextVersionIdMarker = null;
			VersionListing versions = null;

			for (int i = 1; i <= multiplier; i++) {
				if (i != multiplier) {
					versions = listVersions(bucketName, null, nextKeyMarker, nextVersionIdMarker, null, maxKeys, true);
					assertTrue("Invalid next-version-ID-marker, expected it to contain next version ID but got null", versions.getNextVersionIdMarker() != null);
				} else {
					versions = listVersions(bucketName, null, nextKeyMarker, nextVersionIdMarker, null, maxKeys, false);
				}

				assertTrue("Expected version summaries list to be of size " + maxKeys + "but got a list of size " + versions.getVersionSummaries().size(),
						versions.getVersionSummaries().size() == maxKeys);
				Iterator<S3VersionSummary> summaryIterator = versions.getVersionSummaries().iterator();
				S3VersionSummary versionSummary = null;

				// The first version summary must be marked as the latest
				if (i == 1) {
					versionSummary = summaryIterator.next();
					assertTrue("Expected version to be chronologically ordered", versionIdIterator.next().equals(versionSummary.getVersionId()));
					assertTrue("Expected delete marker to be set to false but found it to be true", !versionSummary.isDeleteMarker());
					assertTrue("Expected latest marker to be set to true but found it to be false", versionSummary.isLatest());
					verifyVersionCommonElements(versionSummary, key);
				}

				// Verify the remaining version summaries against the version ID list
				while (summaryIterator.hasNext()) {
					versionSummary = summaryIterator.next();
					assertTrue("Expected versions to be chronologically ordered", versionIdIterator.next().equals(versionSummary.getVersionId()));
					assertTrue("Expected delete marker to be set to false but found it to be true", !versionSummary.isDeleteMarker());
					assertTrue("Expected latest marker to be set to false but found it to be true", !versionSummary.isLatest());
					verifyVersionCommonElements(versionSummary, key);
				}

				if (i != multiplier) {
					nextKeyMarker = versions.getNextKeyMarker();
					nextVersionIdMarker = versions.getNextVersionIdMarker();
					assertTrue("Expected next-key-marker to be " + versionSummary.getKey() + ", but got " + nextKeyMarker,
							versionSummary.getKey().equals(nextKeyMarker));
					assertTrue("Expected nex-version-id-marker to be " + versionSummary.getVersionId() + ", but got " + nextVersionIdMarker, versionSummary
							.getVersionId().equals(nextVersionIdMarker));
				} else {
					assertTrue("Expected next-key-marker to be mull, but got " + versions.getNextKeyMarker(), versions.getNextKeyMarker() == null);
					assertTrue("Expected nex-version-id-marker to be null, but got " + versions.getNextVersionIdMarker(),
							versions.getNextVersionIdMarker() == null);
				}
			}
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run maxKeysSingleKeyMultipleUploads");
		}
	}

	@Test
	public void maxKeysMultipleKeysMultipleUploads() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - maxKeysMultipleKeysMultipleUploads");

		try {
			int maxKeys = 3 + random.nextInt(3); // Max keys 3-5
			int uploads = maxKeys + 1;
			int numKeys = maxKeys * (1 + random.nextInt(3));
			int counter = ((numKeys * uploads) / maxKeys);
			TreeMap<String, List<String>> keyVersionMap = new TreeMap<String, List<String>>();
			String key = new String();

			print("Number of keys: " + numKeys);
			print("Number of uploads per key: " + uploads);
			print("Number of max-keys in list versions request: " + maxKeys);

			for (int i = 0; i < numKeys; i++) {
				key += VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length()));
				LinkedList<String> versionIdList = new LinkedList<String>();

				for (int j = 0; j < uploads; j++) {
					putObject(bucketName, key, fileToPut, versionIdList);
				}

				Collections.reverse(versionIdList);
				keyVersionMap.put(key, versionIdList);
			}

			Iterator<String> keySetIterator = keyVersionMap.keySet().iterator();
			key = keySetIterator.next();
			Iterator<String> versionIdIterator = keyVersionMap.get(key).iterator();
			boolean isFirst = true;

			String nextKeyMarker = null;
			String nextVersionIdMarker = null;
			VersionListing versions = null;

			for (int i = 1; i <= counter; i++) {
				if (i != counter) {
					versions = listVersions(bucketName, null, nextKeyMarker, nextVersionIdMarker, null, maxKeys, true);
					assertTrue("Invalid next-version-ID-marker, expected it to contain next version ID but got null", versions.getNextVersionIdMarker() != null);
				} else {
					versions = listVersions(bucketName, null, nextKeyMarker, nextVersionIdMarker, null, maxKeys, false);
				}

				assertTrue("Expected version summaries list to be of size " + maxKeys + "but got a list of size " + versions.getVersionSummaries().size(),
						versions.getVersionSummaries().size() == maxKeys);
				Iterator<S3VersionSummary> summaryIterator = versions.getVersionSummaries().iterator();
				S3VersionSummary versionSummary = null;

				while (summaryIterator.hasNext()) {
					if (!versionIdIterator.hasNext()) {
						key = keySetIterator.next();
						versionIdIterator = keyVersionMap.get(key).iterator();
						isFirst = true;
					}
					versionSummary = summaryIterator.next();
					if (isFirst) { // The first version summary must be marked as the latest
						assertTrue("Expected version to be chronologically ordered", versionIdIterator.next().equals(versionSummary.getVersionId()));
						assertTrue("Expected delete marker to be set to false but found it to be true", !versionSummary.isDeleteMarker());
						assertTrue("Expected latest marker to be set to true but found it to be false", versionSummary.isLatest());
						verifyVersionCommonElements(versionSummary, key);
						isFirst = false;
					} else { // Verify the remaining version summaries against the version ID list
						assertTrue("Expected versions to be chronologically ordered", versionIdIterator.next().equals(versionSummary.getVersionId()));
						assertTrue("Expected delete marker to be set to false but found it to be true", !versionSummary.isDeleteMarker());
						assertTrue("Expected latest marker to be set to false but found it to be true", !versionSummary.isLatest());
						verifyVersionCommonElements(versionSummary, key);
					}
				}

				if (i != counter) {
					nextKeyMarker = versions.getNextKeyMarker();
					nextVersionIdMarker = versions.getNextVersionIdMarker();
					assertTrue("Expected next-key-marker to be " + versionSummary.getKey() + ", but got " + nextKeyMarker,
							versionSummary.getKey().equals(nextKeyMarker));
					assertTrue("Expected nex-version-id-marker to be " + versionSummary.getVersionId() + ", but got " + nextVersionIdMarker, versionSummary
							.getVersionId().equals(nextVersionIdMarker));
				} else {
					assertTrue("Expected next-key-marker to be mull, but got " + versions.getNextKeyMarker(), versions.getNextKeyMarker() == null);
					assertTrue("Expected nex-version-id-marker to be null, but got " + versions.getNextVersionIdMarker(),
							versions.getNextVersionIdMarker() == null);
				}
			}
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run maxKeysMultipleKeysMultipleUploads");
		}
	}

	@Test
	public void maxKeysMultipleKeysSingleUpload() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - maxKeysMultipleKeysSingleUpload");

		try {
			int maxKeys = 3 + random.nextInt(3); // Max keys 3-5
			int multiplier = 3 + random.nextInt(4); // Max uploads 9-18
			int numKeys = maxKeys * multiplier;
			TreeMap<String, String> keyVersionMap = new TreeMap<String, String>();
			String key = new String();

			print("Number of keys: " + numKeys);
			print("Number of max-keys in list versions request: " + maxKeys);

			for (int i = 0; i < numKeys; i++) {
				key += VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length()));
				keyVersionMap.put(key, putObject(bucketName, key, fileToPut));
			}

			Iterator<String> keySetIterator = keyVersionMap.keySet().iterator();

			String nextKeyMarker = null;
			String nextVersionIdMarker = null;
			VersionListing versions = null;

			for (int i = 1; i <= multiplier; i++) {
				if (i != multiplier) {
					versions = listVersions(bucketName, null, nextKeyMarker, nextVersionIdMarker, null, maxKeys, true);
					assertTrue("Invalid next-version-ID-marker, expected it to contain next version ID but got null", versions.getNextVersionIdMarker() != null);
				} else {
					versions = listVersions(bucketName, null, nextKeyMarker, nextVersionIdMarker, null, maxKeys, false);
				}

				assertTrue("Expected version summaries list to be of size " + maxKeys + "but got a list of size " + versions.getVersionSummaries().size(),
						versions.getVersionSummaries().size() == maxKeys);
				Iterator<S3VersionSummary> summaryIterator = versions.getVersionSummaries().iterator();
				S3VersionSummary versionSummary = null;

				while (summaryIterator.hasNext()) {
					// The first version summary must be marked as the latest
					versionSummary = summaryIterator.next();
					key = keySetIterator.next();
					String versionId = keyVersionMap.get(key);
					assertTrue("Expected version to be " + versionId + ", but got " + versionSummary.getVersionId(),
							versionId.equals(versionSummary.getVersionId()));
					assertTrue("Expected delete marker to be set to false but found it to be true", !versionSummary.isDeleteMarker());
					assertTrue("Expected latest marker to be set to true but found it to be false", versionSummary.isLatest());
					verifyVersionCommonElements(versionSummary, key);
				}

				if (i != multiplier) {
					nextKeyMarker = versions.getNextKeyMarker();
					nextVersionIdMarker = versions.getNextVersionIdMarker();
					assertTrue("Expected next-key-marker to be " + versionSummary.getKey() + ", but got " + nextKeyMarker,
							versionSummary.getKey().equals(nextKeyMarker));
					assertTrue("Expected nex-version-id-marker to be " + versionSummary.getVersionId() + ", but got " + nextVersionIdMarker, versionSummary
							.getVersionId().equals(nextVersionIdMarker));
				} else {
					assertTrue("Expected next-key-marker to be mull, but got " + versions.getNextKeyMarker(), versions.getNextKeyMarker() == null);
					assertTrue("Expected nex-version-id-marker to be null, but got " + versions.getNextVersionIdMarker(),
							versions.getNextVersionIdMarker() == null);
				}
			}
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run maxKeysMultipleKeysSingleUpload");
		} finally {
			for (S3VersionSummary version : listVersions(bucketName, null, null, null, null, null, false).getVersionSummaries()) {
				try {
					print("Deleting object " + version.getKey() + ", version " + version.getVersionId());
					s3.deleteVersion(bucketName, version.getKey(), version.getVersionId());
				} catch (AmazonServiceException ase) {
					printException(ase);
				}
			}
		}
	}

	/**
	 * Test for verifying paginated listing of common prefixes
	 * 
	 * Test fails against Walrus, prefixes in the common prefix list are incorrectly represented. Results returned by Walrus are inclusive of the key that
	 * matches the key-marker where as S3's results are exclusive.
	 * 
	 * @see <a href="https://eucalyptus.atlassian.net/browse/EUCA-8113">EUCA-8112</a>
	 * @see <a href="https://eucalyptus.atlassian.net/browse/EUCA-8112">EUCA-8113</a>
	 */
	@Test
	public void delimiterPrefixAndMaxKeys() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - delimiterPrefixAndMaxKeys");

		try {
			int maxKeys = 3 + random.nextInt(3); // Max keys 3-5
			int multiplier = 3 + random.nextInt(4);
			int prefixes = maxKeys * multiplier; // Max prefixes 9-18
			int keys = 2 + random.nextInt(3); // 2-4 keys
			int uploads = 2 + random.nextInt(3); // 2-4 uploads
			String delimiter = "/"; // Pick a random delimiter afterwards
			TreeSet<String> prefixSet = new TreeSet<String>();
			VersionListing versions = null;

			print("Number of prefixes: " + prefixes);
			print("Number of keys per prefix: " + keys);
			print("Number of uploads per key: " + uploads);
			print("Number of max-keys in list versions request: " + maxKeys);

			for (int i = 0; i < prefixes; i++) {
				String prefix = VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length())) + eucaUUID() + delimiter;
				print("Prefix name: " + prefix);

				// Upload object multiple times using the key
				for (int j = 0; j < keys; j++) {
					String key = prefix + VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length())) + eucaUUID(); // Prefix it with any character in
					LinkedList<String> partialVersionIdList = new LinkedList<String>();
					print("Key name: " + key);

					for (int k = 0; k < uploads; k++) {
						putObject(bucketName, key, fileToPut, partialVersionIdList);
					}

					// Verify the linked list size
					assertTrue(
							"Expected version ID list size to be same as the number of uploads which is " + uploads + ", but got "
									+ partialVersionIdList.size(), partialVersionIdList.size() == uploads);

					// List the object versions and verify them against the put object results
					versions = listVersions(bucketName, key, null, null, null, null, false);
					verifyVersionSummaries(key, partialVersionIdList, versions.getVersionSummaries());
				}

				prefixSet.add(prefix);
			}

			Iterator<String> prefixIterator = prefixSet.iterator();

			String nextKeyMarker = null;
			String nextVersionIdMarker = null;

			for (int i = 1; i <= multiplier; i++) {
				if (i != multiplier) {
					versions = listVersions(bucketName, null, nextKeyMarker, nextVersionIdMarker, delimiter, maxKeys, true);
					assertTrue("Invalid next-version-ID-marker, expected null but got " + versions.getNextVersionIdMarker(),
							versions.getNextVersionIdMarker() == null);
				} else {
					versions = listVersions(bucketName, null, nextKeyMarker, nextVersionIdMarker, delimiter, maxKeys, false);
				}

				assertTrue("Expected to not get any version summaries but got a list of size " + versions.getVersionSummaries().size(), versions
						.getVersionSummaries().size() == 0);
				assertTrue("Expected common prefixes list to be of size " + maxKeys + ", but got a list of size " + versions.getCommonPrefixes().size(),
						versions.getCommonPrefixes().size() == maxKeys);

				Iterator<String> commonPrefixIterator = versions.getCommonPrefixes().iterator();
				String commonPrefix = null;

				while (commonPrefixIterator.hasNext()) {
					String expectedPrefix = prefixIterator.next();
					commonPrefix = commonPrefixIterator.next();
					assertTrue("Expected common prefix " + expectedPrefix + ", but got " + commonPrefix, expectedPrefix.equals(commonPrefix));
				}

				if (i != multiplier) {
					nextKeyMarker = versions.getNextKeyMarker();
					nextVersionIdMarker = versions.getNextVersionIdMarker();
					assertTrue("Expected next-key-marker to be " + commonPrefix + ", but got " + nextKeyMarker, commonPrefix.equals(nextKeyMarker));
					assertTrue("Expected nex-version-id-marker to be null, but got " + nextVersionIdMarker, nextVersionIdMarker == null);
				} else {
					assertTrue("Expected next-key-marker to be mull, but got " + versions.getNextKeyMarker(), versions.getNextKeyMarker() == null);
					assertTrue("Expected nex-version-id-marker to be null, but got " + versions.getNextVersionIdMarker(),
							versions.getNextVersionIdMarker() == null);
				}
			}
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run delimiterPrefixAndMaxKeys");
		}
	}

	@Test
	public void toggleVersioning() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - toggleVersioning");

		try {
			String key = eucaUUID();
			LinkedList<KeyEntry> history = new LinkedList<KeyEntry>();

			history.addFirst(new KeyEntry(putObject(bucketName, key, fileToPut), Element.VERSION_ENTRY));
			history.addFirst(new KeyEntry(deleteObject(bucketName, key), Element.DELETE_MARKER));
			history.addFirst(new KeyEntry(putObject(bucketName, key, fileToPut), Element.VERSION_ENTRY));

			VersionListing versions = listVersions(bucketName, key, null, null, null, null, false);
			compare(history, versions);

			// Suspend versioning
			print("Suspending versioning");
			s3.setBucketVersioningConfiguration(new SetBucketVersioningConfigurationRequest(bucketName, new BucketVersioningConfiguration()
					.withStatus(BucketVersioningConfiguration.SUSPENDED)));
			print("Versioning state: " + s3.getBucketVersioningConfiguration(bucketName).getStatus());

			history.addFirst(new KeyEntry(deleteObject(bucketName, key), Element.DELETE_MARKER));
			versions = listVersions(bucketName, key, null, null, null, null, false);
			compare(history, versions);
			history.remove();

			history.addFirst(new KeyEntry(putObject(bucketName, key, fileToPut), Element.VERSION_ENTRY));
			versions = listVersions(bucketName, key, null, null, null, null, false);
			compare(history, versions);
			history.remove();

			history.addFirst(new KeyEntry(deleteObject(bucketName, key), Element.DELETE_MARKER));
			versions = listVersions(bucketName, key, null, null, null, null, false);
			compare(history, versions);

			// Enable versioning
			print("Enabling versioning");
			s3.setBucketVersioningConfiguration(new SetBucketVersioningConfigurationRequest(bucketName, new BucketVersioningConfiguration()
					.withStatus(BucketVersioningConfiguration.ENABLED)));
			print("Versioning state: " + s3.getBucketVersioningConfiguration(bucketName).getStatus());

			history.addFirst(new KeyEntry(putObject(bucketName, key, fileToPut), Element.VERSION_ENTRY));
			versions = listVersions(bucketName, key, null, null, null, null, false);
			compare(history, versions);

			history.addFirst(new KeyEntry(deleteObject(bucketName, key), Element.DELETE_MARKER));
			versions = listVersions(bucketName, key, null, null, null, null, false);
			compare(history, versions);

			// Suspend versioning
			print("Suspending versioning");
			s3.setBucketVersioningConfiguration(new SetBucketVersioningConfigurationRequest(bucketName, new BucketVersioningConfiguration()
					.withStatus(BucketVersioningConfiguration.SUSPENDED)));
			print("Versioning state: " + s3.getBucketVersioningConfiguration(bucketName).getStatus());

			// Remove all previous null versions from history
			history.remove(new KeyEntry("null", Element.DELETE_MARKER));
			history.remove(new KeyEntry("null", Element.VERSION_ENTRY));

			history.addFirst(new KeyEntry(putObject(bucketName, key, fileToPut), Element.VERSION_ENTRY));
			versions = listVersions(bucketName, key, null, null, null, null, false);
			compare(history, versions);
			history.remove();

			history.addFirst(new KeyEntry(deleteObject(bucketName, key), Element.DELETE_MARKER));
			versions = listVersions(bucketName, key, null, null, null, null, false);
			compare(history, versions);
			history.remove();

			history.addFirst(new KeyEntry(putObject(bucketName, key, fileToPut), Element.VERSION_ENTRY));
			versions = listVersions(bucketName, key, null, null, null, null, false);
			compare(history, versions);

			// Enable versioning
			print("Suspending versioning");
			s3.setBucketVersioningConfiguration(new SetBucketVersioningConfigurationRequest(bucketName, new BucketVersioningConfiguration()
					.withStatus(BucketVersioningConfiguration.ENABLED)));
			print("Versioning state: " + s3.getBucketVersioningConfiguration(bucketName).getStatus());

			history.addFirst(new KeyEntry(deleteObject(bucketName, key), Element.DELETE_MARKER));
			versions = listVersions(bucketName, key, null, null, null, null, false);
			compare(history, versions);

			history.addFirst(new KeyEntry(putObject(bucketName, key, fileToPut), Element.VERSION_ENTRY));
			versions = listVersions(bucketName, key, null, null, null, null, false);
			compare(history, versions);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run toggleVersioning");
		} finally {
			for (S3VersionSummary version : listVersions(bucketName, null, null, null, null, null, false).getVersionSummaries()) {
				try {
					print("Deleting object " + version.getKey() + ", version " + version.getVersionId());
					s3.deleteVersion(bucketName, version.getKey(), version.getVersionId());
				} catch (AmazonServiceException ase) {
					printException(ase);
				}
			}
		}
	}

	@Test
	public void suspendVersioningAndDeleteVersions() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - suspendVersioningAndDeleteVersions");

		try {
			String key = eucaUUID();
			LinkedList<KeyEntry> history = new LinkedList<KeyEntry>();

			history.addFirst(new KeyEntry(putObject(bucketName, key, fileToPut), Element.VERSION_ENTRY));
			history.addFirst(new KeyEntry(deleteObject(bucketName, key), Element.DELETE_MARKER));
			history.addFirst(new KeyEntry(putObject(bucketName, key, fileToPut), Element.VERSION_ENTRY));

			VersionListing versions = listVersions(bucketName, key, null, null, null, null, false);
			compare(history, versions);

			// Suspend versioning
			print("Suspending versioning");
			s3.setBucketVersioningConfiguration(new SetBucketVersioningConfigurationRequest(bucketName, new BucketVersioningConfiguration()
					.withStatus(BucketVersioningConfiguration.SUSPENDED)));
			print("Versioning state: " + s3.getBucketVersioningConfiguration(bucketName).getStatus());

			history.addFirst(new KeyEntry(putObject(bucketName, key, fileToPut), Element.VERSION_ENTRY));
			versions = listVersions(bucketName, key, null, null, null, null, false);
			compare(history, versions);
			history.remove();

			history.addFirst(new KeyEntry(deleteObject(bucketName, key), Element.DELETE_MARKER));
			versions = listVersions(bucketName, key, null, null, null, null, false);
			compare(history, versions);
			history.remove();

			history.addFirst(new KeyEntry(putObject(bucketName, key, fileToPut), Element.VERSION_ENTRY));
			versions = listVersions(bucketName, key, null, null, null, null, false);
			compare(history, versions);

			// AmazonS3 s3clientA = getS3Client("awsrc_mcflurry");
			// print("S3 account for delete: " + s3clientA.getS3AccountOwner().getDisplayName());

			boolean error = false;
			for (S3VersionSummary version : versions.getVersionSummaries()) {
				try {
					print("Deleting object " + version.getKey() + ", version " + version.getVersionId());
					s3.deleteVersion(bucketName, version.getKey(), version.getVersionId());
				} catch (AmazonServiceException ase) {
					error = true;
					printException(ase);
				}
			}
			assertTrue("Error deleting one of the versions", !error);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run suspendVersioningAndDeleteVersions");
		}
	}

	@Test
	public void deleteBucketWithDeleteMarker() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - deleteBucketWithDeleteMarker");

		try {
			String key = eucaUUID();
			LinkedList<KeyEntry> history = new LinkedList<KeyEntry>();

			history.addFirst(new KeyEntry(putObject(bucketName, key, fileToPut), Element.VERSION_ENTRY));
			history.addFirst(new KeyEntry(deleteObject(bucketName, key), Element.DELETE_MARKER));
			history.addFirst(new KeyEntry(putObject(bucketName, key, fileToPut), Element.VERSION_ENTRY));
			history.addFirst(new KeyEntry(deleteObject(bucketName, key), Element.DELETE_MARKER));

			VersionListing versions = listVersions(bucketName, key, null, null, null, null, false);
			compare(history, versions);

			boolean error = false;
			for (S3VersionSummary version : versions.getVersionSummaries()) {
				try {
					if (!version.isDeleteMarker()) {
						print("Deleting version element: key " + version.getKey() + ", version " + version.getVersionId());
						s3.deleteVersion(bucketName, version.getKey(), version.getVersionId());
					}
				} catch (AmazonServiceException ase) {
					error = true;
					printException(ase);
				}
			}
			assertTrue("Error deleting versions", !error);

			error = false;
			try {
				print("Deleting bucket " + bucketName);
				s3.deleteBucket(bucketName);
			} catch (AmazonServiceException ase) {
				error = true;
				assertTrue("Expected HTTP status code to be 409, but got " + ase.getStatusCode(), ase.getStatusCode() == 409);
				assertTrue("Expected error code to be BucketNotEmpty, but got " + ase.getErrorCode(), ase.getErrorCode().equals("BucketNotEmpty"));
			}
			assertTrue("Expected bucket delete to fail", error);
			versions = listVersions(bucketName, null, null, null, null, null, false);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run deleteBucketWithDeleteMarker");
		} finally {
			for (S3VersionSummary version : listVersions(bucketName, null, null, null, null, null, false).getVersionSummaries()) {
				try {
					print("Deleting object " + version.getKey() + ", version " + version.getVersionId());
					s3.deleteVersion(bucketName, version.getKey(), version.getVersionId());
				} catch (AmazonServiceException ase) {
					printException(ase);
				}
			}
		}
	}

	private AmazonS3 getS3Client(String credPath) throws Exception {
		print("Getting cloud information from " + credPath);

		String s3Endpoint = Eutester4j.parseEucarc(credPath, "S3_URL") + "/";

		String secretKey = Eutester4j.parseEucarc(credPath, "EC2_SECRET_KEY").replace("'", "");
		String accessKey = Eutester4j.parseEucarc(credPath, "EC2_ACCESS_KEY").replace("'", "");

		print("Initializing S3 connections");
		return Eutester4j.getS3Client(accessKey, secretKey, s3Endpoint);
	}

	// @Test
	public void invalidMarkers() {
		testInfo(this.getClass().getSimpleName() + " - keyMarkerVersionIdMarker");

		try {
			int keys = 3; // + random.nextInt(8); // 3-10 keys
			int uploads = 3; // + random.nextInt(14); // 2-15 uploads
			TreeMap<String, List<String>> keyVersionMap = new TreeMap<String, List<String>>();
			VersionListing versions = null;

			print("Number of keys: " + keys);
			print("Number of uploads per key: " + uploads);

			String key = null;

			for (int i = 0; i < keys; i++) {
				// key = VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length())) + eucaUUID(); // Prefix it with any character in the valid chars
				key = VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length())) + "";
				print("Key name: " + key);
				LinkedList<String> partialVersionIdList = new LinkedList<String>();

				// Upload object multiple times using the key
				for (int j = 0; j < uploads; j++) {
					putObject(bucketName, key, fileToPut, partialVersionIdList);
				}

				// // List the object versions and verify them against the put object results
				// versions = listVersions(bucketName, key, null, null, null, null, false);
				// verifyVersionSummaries(key, partialVersionIdList, versions.getVersionSummaries());

				// Reverse the version ID list and add it to the map
				Collections.reverse(partialVersionIdList);

				// Put the key name and version ID list in the map. The map should order the keys in lexicographic order
				keyVersionMap.put(key, partialVersionIdList);
			}

			List<String> versionIdList = keyVersionMap.get(key);
			versions = listVersions(bucketName, null, key, versionIdList.get(1), null, null, false);
			s3.deleteVersion(bucketName, key, versionIdList.get(1));
			versions = listVersions(bucketName, null, key, "uS9AJ_SGUh0xgRfsRV0okMOf1rRGloee", null, null, false);

			// versions = listVersions(bucketName, null, null, null, null, null, false);
			// for(S3VersionSummary sum : versions.getVersionSummaries()){
			// s3.deleteVersion(bucketName, sum.getKey(), sum.getVersionId());
			// }
			// s3.deleteBucket(bucketName);

			versions.getPrefix();
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run keyMarkerVersionIdMarker");
		}
	}

	// @Test
	public void cleanupmess() {
		VersionListing versions = listVersions("3fc48edc955b2cf4", null, null, null, null, null, false);
		for (S3VersionSummary version : versions.getVersionSummaries()) {
			print("Deleting object " + version.getKey() + ", version " + version.getVersionId());
			s3.deleteVersion("3fc48edc955b2cf4", version.getKey(), version.getVersionId());
		}
		print("Deleting bucket 3fc48edc955b2cf4");
		s3.deleteBucket("3fc48edc955b2cf4");
	}

	// @Test
	public void delimiterTest() {
		LinkedList<String> versionIdList = new LinkedList<String>();
		putObject(bucketName, "foo/bar/crazy", fileToPut, versionIdList);
		putObject(bucketName, "foo/bar/weird", fileToPut, versionIdList);
		putObject(bucketName, "foo/bar/insane", fileToPut, versionIdList);
		putObject(bucketName, "foo/dan/insane", fileToPut, versionIdList);
		putObject(bucketName, "foo/dan/weird", fileToPut, versionIdList);
		putObject(bucketName, "foo/dan/crazy", fileToPut, versionIdList);
		putObject(bucketName, "foo/crap", fileToPut, versionIdList);

		VersionListing versions = listVersions(bucketName, "foo/", null, null, "/", null, false);
		print("Common prefixes: " + versions.getCommonPrefixes());
	}

	enum Element {
		DELETE_MARKER, VERSION_ENTRY;
	}

	public static class KeyEntry {
		private String versionId;
		private Element element;

		public KeyEntry(String versionId, Element element) {
			this.versionId = versionId;
			this.element = element;
		}

		public String getVersionId() {
			return versionId;
		}

		public void setVersionId(String versionId) {
			this.versionId = versionId;
		}

		public Element getElement() {
			return element;
		}

		public void setElement(Element element) {
			this.element = element;
		}

		@Override
		public int hashCode() {
			final int prime = 31;
			int result = 1;
			result = prime * result + ((element == null) ? 0 : element.hashCode());
			result = prime * result + ((versionId == null) ? 0 : versionId.hashCode());
			return result;
		}

		@Override
		public boolean equals(Object obj) {
			if (this == obj)
				return true;
			if (obj == null)
				return false;
			if (getClass() != obj.getClass())
				return false;
			KeyEntry other = (KeyEntry) obj;
			if (element != other.element)
				return false;
			if (versionId == null) {
				if (other.versionId != null)
					return false;
			} else if (!versionId.equals(other.versionId))
				return false;
			return true;
		}

		@Override
		public String toString() {
			return "KeyEntry [versionId=" + versionId + ", element=" + element + "]";
		}
	}

	private void compare(LinkedList<KeyEntry> history, VersionListing versions) {
		assertTrue("Expected " + history.size() + " elements, but got " + versions.getVersionSummaries().size(), history.size() == versions
				.getVersionSummaries().size());
		Iterator<S3VersionSummary> versionIterator = versions.getVersionSummaries().iterator();
		Iterator<KeyEntry> historyIterator = history.iterator();

		// First one should always be the latest
		S3VersionSummary version = versionIterator.next();
		KeyEntry key = historyIterator.next();
		assertTrue("Expected element to be latest", version.isLatest());
		assertTrue("Mimatch in key type. Expected " + key.getElement() + " but got isDeleteMarker=" + version.isDeleteMarker(),
				key.getElement().equals(Element.DELETE_MARKER) ? version.isDeleteMarker() : !version.isDeleteMarker());

		// Rest of them should not be the latest
		while (versionIterator.hasNext()) {
			version = versionIterator.next();
			key = historyIterator.next();
			assertTrue("Expected element to be not latest", !version.isLatest());
			assertTrue("Mimatch in key type. Expected " + key.getElement() + " but got isDeleteMarker=" + version.isDeleteMarker(),
					key.getElement().equals(Element.DELETE_MARKER) ? version.isDeleteMarker() : !version.isDeleteMarker());
		}
	}

	private void enableBucketVersioning(String bucketName) throws InterruptedException {
		print("Enabling versioning");
		s3.setBucketVersioningConfiguration(new SetBucketVersioningConfigurationRequest(bucketName, new BucketVersioningConfiguration()
				.withStatus(BucketVersioningConfiguration.ENABLED)));

		BucketVersioningConfiguration versioning = null;
		int counter = 0;
		do {
			Thread.sleep(1000);
			versioning = s3.getBucketVersioningConfiguration(bucketName);
			print("Versioning state: " + versioning.getStatus());
			if (versioning.getStatus().equals(BucketVersioningConfiguration.ENABLED)) {
				break;
			}
			counter++;
		} while (counter < 5);
		assertTrue("Invalid result for bucket versioning configuration", versioning != null);
		assertTrue("Expected bucket versioning configuration to be ENABLED, but found it to be " + versioning.getStatus(),
				versioning.getStatus().equals(BucketVersioningConfiguration.ENABLED));
	}

	private void putObject(final String bucketName, final String key, File fileToPut, List<String> versionIdList) {
		print("Putting object " + key + " in bucket " + bucketName);
		final PutObjectResult putResult = s3.putObject(bucketName, key, fileToPut);
		cleanupTasks.add(new Runnable() {
			@Override
			public void run() {
				if (putResult.getVersionId() != null) {
					print("Deleting object " + key + ", version " + putResult.getVersionId());
					s3.deleteVersion(bucketName, key, putResult.getVersionId());
				} else {
					print("Deleting object " + key);
					s3.deleteObject(bucketName, key);
				}
			}
		});
		assertTrue("Invalid put object result", putResult != null);
		assertTrue("Invalid version ID: " + putResult.getVersionId(), StringUtils.isNotBlank(putResult.getVersionId()));
		assertTrue("Expected version ID to be unique", !versionIdList.contains(putResult.getVersionId()));
		versionIdList.add(putResult.getVersionId());
	}

	private String putObject(String bucketName, String key, File fileToPut) {
		print("Putting object " + key + " in bucket " + bucketName);
		PutObjectResult putResult = s3.putObject(bucketName, key, fileToPut);
		assertTrue("Invalid put object result", putResult != null);
		return putResult.getVersionId() != null ? putResult.getVersionId() : new String("null");
	}

	private String deleteObject(String bucketName, String key) {
		print("Deleting object " + key + " in bucket " + bucketName);
		s3.deleteObject(bucketName, key);
		VersionListing versions = listVersions(bucketName, key, null, null, null, null, false);
		S3VersionSummary deleteMarker = versions.getVersionSummaries().get(0);
		assertTrue("Invalid version summary", deleteMarker != null);
		assertTrue("Expected version element to be a delete marker", deleteMarker.isDeleteMarker());
		assertTrue("Expected delete marker to be the latest", deleteMarker.isLatest());
		return deleteMarker.getVersionId();
	}

	private void verifyVersionSummaries(String key, LinkedList<String> versionIdList, List<S3VersionSummary> versionSummaries) {
		assertTrue("Expected version summary list to be of size " + versionIdList.size() + ", but got a list of size " + versionSummaries.size(),
				versionIdList.size() == versionSummaries.size());

		Iterator<String> versionIdIterator = versionIdList.descendingIterator();
		Iterator<S3VersionSummary> summaryIterator = versionSummaries.iterator();

		// The first version summary must be marked as the latest
		S3VersionSummary versionSummary = summaryIterator.next();
		assertTrue("Expected version to be chronologically ordered", versionIdIterator.next().equals(versionSummary.getVersionId()));
		assertTrue("Expected delete marker to be set to false but found it to be true", !versionSummary.isDeleteMarker());
		assertTrue("Expected latest marker to be set to true but found it to be false", versionSummary.isLatest());
		verifyVersionCommonElements(versionSummary, key);

		// Verify the remaining version summaries against the version ID list
		while (summaryIterator.hasNext()) {
			versionSummary = summaryIterator.next();
			assertTrue("Expected versions to be chronologically ordered", versionIdIterator.next().equals(versionSummary.getVersionId()));
			assertTrue("Expected delete marker to be set to false but found it to be true", !versionSummary.isDeleteMarker());
			assertTrue("Expected latest marker to be set to false but found it to be true", !versionSummary.isLatest());
			verifyVersionCommonElements(versionSummary, key);
		}
	}

	private VersionListing listVersions(String bucketName, String prefix, String keyMarker, String versionIdMarker, String delimiter, Integer maxKeys,
			boolean isTruncated) {

		StringBuilder sb = new StringBuilder("List object versions using bucket=" + bucketName);

		ListVersionsRequest request = new ListVersionsRequest();
		request.setBucketName(bucketName);

		if (prefix != null) {
			request.setPrefix(prefix);
			sb.append(", prefix=").append(prefix);
		}
		if (keyMarker != null) {
			request.setKeyMarker(keyMarker);
			sb.append(", key marker=").append(keyMarker);
		}
		if (versionIdMarker != null) {
			request.setVersionIdMarker(versionIdMarker);
			sb.append(", version ID marker=").append(versionIdMarker);
		}
		if (delimiter != null) {
			request.setDelimiter(delimiter);
			sb.append(", delimiter=").append(delimiter);
		}
		if (maxKeys != null) {
			request.setMaxResults(maxKeys);
			sb.append(", max results=").append(maxKeys);
		}

		print(sb.toString());
		VersionListing versionList = s3.listVersions(request);

		assertTrue("Invalid version list", versionList != null);
		assertTrue("Expected version listing bucket name to be " + bucketName + ", but got " + versionList.getBucketName(),
				versionList.getBucketName().equals(bucketName));
		assertTrue("Expected delimiter to be " + delimiter + ", but got " + versionList.getDelimiter(),
				StringUtils.equals(versionList.getDelimiter(), delimiter));
		assertTrue("Expected common prefixes to be empty or populated, but got " + versionList.getCommonPrefixes(), versionList.getCommonPrefixes() != null);
		assertTrue("Expected key-marker to be " + keyMarker + ", but got " + versionList.getKeyMarker(),
				StringUtils.equals(versionList.getKeyMarker(), keyMarker));
		assertTrue("Expected max-keys to be " + (maxKeys != null ? maxKeys : DEFAULT_MAX_KEYS) + ", but got " + versionList.getMaxKeys(),
				versionList.getMaxKeys() == (maxKeys != null ? maxKeys : DEFAULT_MAX_KEYS));
		assertTrue("Expected prefix to be " + prefix + ", but got " + versionList.getPrefix(), StringUtils.equals(versionList.getPrefix(), prefix));
		assertTrue("Expected version-id-marker to be " + versionIdMarker + ", but got " + versionList.getVersionIdMarker(),
				StringUtils.equals(versionList.getVersionIdMarker(), versionIdMarker));
		assertTrue("Invalid version summary list", versionList.getVersionSummaries() != null);
		assertTrue("Expected is truncated to be " + isTruncated + ", but got " + versionList.isTruncated(), versionList.isTruncated() == isTruncated);
		if (versionList.isTruncated()) {
			assertTrue("Invalid next-key-marker, expected it to contain next key but got null", versionList.getNextKeyMarker() != null);
		} else {
			assertTrue("Invalid next-key-marker, expected it to be null but got " + versionList.getNextKeyMarker(), versionList.getNextKeyMarker() == null);
			assertTrue("Invalid next-version-ID-marker, expected it to be null but got " + versionList.getNextVersionIdMarker(),
					versionList.getNextVersionIdMarker() == null);
		}

		return versionList;
	}

	private void verifyVersionCommonElements(S3VersionSummary versionSummary, String key) {
		assertTrue("Expected key to be " + key + ", but got " + versionSummary.getKey(), versionSummary.getKey().equals(key));
		assertTrue("Expected etag to be " + md5 + ", but got " + versionSummary.getETag(), versionSummary.getETag().equals(md5));
		assertTrue("Expected size to be " + size + ", but got " + versionSummary.getSize(), versionSummary.getSize() == size);
		assertTrue("Invalid last modified field", versionSummary.getLastModified() != null);
		assertTrue("Expected owner ID to be " + ownerID + ", but got " + versionSummary.getOwner().getId(), versionSummary.getOwner().getId().equals(ownerID));
	}

	private void verifyDeleteMarkerCommonElements(S3VersionSummary versionSummary, String key) {
		assertTrue("Expected key to be " + key + ", but got " + versionSummary.getKey(), versionSummary.getKey().equals(key));
		assertTrue("Invalid last modified field", versionSummary.getLastModified() != null);
		assertTrue("Expected owner ID to be " + ownerID + ", but got " + versionSummary.getOwner().getId(), versionSummary.getOwner().getId().equals(ownerID));
	}

	private void printException(AmazonServiceException ase) {
		ase.printStackTrace();
		print("Caught Exception: " + ase.getMessage());
		print("HTTP Status Code: " + ase.getStatusCode());
		print("Amazon Error Code: " + ase.getErrorCode());
		print("Request ID: " + ase.getRequestId());
	}
}
