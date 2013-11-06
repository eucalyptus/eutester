package com.eucalyptus.tests.awssdk;

import static com.eucalyptus.tests.awssdk.Eutester4j.assertThat;
import static com.eucalyptus.tests.awssdk.Eutester4j.eucaUUID;
import static com.eucalyptus.tests.awssdk.Eutester4j.initS3Client;
import static com.eucalyptus.tests.awssdk.Eutester4j.print;
import static com.eucalyptus.tests.awssdk.Eutester4j.s3;
import static com.eucalyptus.tests.awssdk.Eutester4j.testInfo;
import static org.testng.AssertJUnit.assertTrue;

import java.io.File;
import java.io.FileInputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Map.Entry;
import java.util.NavigableSet;
import java.util.Random;
import java.util.Set;
import java.util.TreeMap;
import java.util.TreeSet;

import org.apache.commons.lang3.StringUtils;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import com.amazonaws.AmazonServiceException;
import com.amazonaws.services.s3.model.Bucket;
import com.amazonaws.services.s3.model.BucketVersioningConfiguration;
import com.amazonaws.services.s3.model.ListObjectsRequest;
import com.amazonaws.services.s3.model.ObjectListing;
import com.amazonaws.services.s3.model.PutObjectResult;
import com.amazonaws.services.s3.model.S3ObjectSummary;
import com.amazonaws.services.s3.model.S3VersionSummary;
import com.amazonaws.services.s3.model.SetBucketVersioningConfigurationRequest;
import com.amazonaws.util.BinaryUtils;
import com.amazonaws.util.Md5Utils;

/**
 * <p>This class contains tests for listing objects in a bucket.</p>
 * 
 * <li>All tests fail against Walrus due to <a href="https://eucalyptus.atlassian.net/browse/EUCA-7855">EUCA-7855</a> unless the owner canonical ID verification
 * is commented out</li>
 * 
 * <li>{@link #marker()} fails against Walrus due to <a href="https://eucalyptus.atlassian.net/browse/EUCA-7985">EUCA-7985</a></li>
 * 
 * <li>{@link #delimiter_2()} fails against Walrus due to <a href="https://eucalyptus.atlassian.net/browse/EUCA-7991">EUCA-7991</a></li>
 * 
 * <li>{@link #maxKeys()} fails against Walrus due to <a href="https://eucalyptus.atlassian.net/browse/EUCA-7985">EUCA-7985</a> and <a
 * href="https://eucalyptus.atlassian.net/browse/EUCA-7986">EUCA-7986</a></li>
 * 
 * @author Swathi Gangisetty
 * 
 */
public class S3ListObjectsTests {

	private static String bucketName = null;
	private static List<Runnable> cleanupTasks = null;
	private static Random random = new Random();
	private static File fileToPut = new File("test.dat");
	private static long size = 0;
	private static String md5 = null;
	private static String ownerID = null;
	private static String VALID_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
	private static int DEFAULT_MAX_KEYS = 1000;

	@BeforeClass
	public void init() throws Exception {
		print("*** PRE SUITE SETUP ***");
		initS3Client();
		ownerID = s3.getS3AccountOwner().getId();
		md5 = BinaryUtils.toHex(Md5Utils.computeMD5Hash(new FileInputStream(fileToPut)));
		size = fileToPut.length();
	}

	@BeforeMethod
	public void setup() throws Exception {
		print("*** PRE TEST SETUP ***");
		bucketName = eucaUUID();
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
	 * <p>Test for verifying ordering of list objects result</p>
	 * 
	 * <p>This test uploads multiple objects each with a different key. It lists the objects in the bucket and verifies the list for lexicographic ordering of
	 * key names</p>
	 */
	@Test
	public void multipleKeys() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - multipleKeys");

		try {
			int keys = 5 + random.nextInt(11);// 5-15 uploads
			TreeSet<String> keySet = new TreeSet<String>();
			ObjectListing objects = null;

			print("Number of keys: " + keys);

			for (int i = 0; i < keys; i++) {
				// Upload an object using the key
				putObject(bucketName, eucaUUID(), fileToPut, keySet);

				// List objects and verify that they are ordered lexicographically
				objects = listObjects(bucketName, null, null, null, null, false);
				verifyObjectSummaries(keySet, objects.getObjectSummaries());
			}

			// List objects and verify that they are ordered lexicographically
			objects = listObjects(bucketName, null, null, null, null, false);
			verifyObjectSummaries(keySet, objects.getObjectSummaries());
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run multipleKeys");
		}
	}

	/**
	 * <p>Test for verifying ordering of list objects using a prefix</p>
	 * 
	 * <p>This test uploads multiple objects each with a different key and a prefix that is shared by a few keys. It lists the objects in the bucket and
	 * verifies the list for lexicographic ordering of key names</p>
	 */
	@Test
	public void prefix() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - prefix");

		try {
			int prefixes = 3 + random.nextInt(8); // 3-10 prefixes
			int keys = 2 + random.nextInt(14);// 2-15 keys perfix
			Map<String, TreeSet<String>> prefixKeyMap = new TreeMap<String, TreeSet<String>>();
			ObjectListing objects = null;

			print("Number of prefixes: " + prefixes);
			print("Number of keys per prefix: " + keys);

			for (int i = 0; i < prefixes; i++) {
				String prefix = VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length())) + eucaUUID(); // Prefix it with any character in the valid chars
				print("Prefix name: " + prefix);
				TreeSet<String> keySet = new TreeSet<String>();

				// Upload objects with different keys that start with the same prefix
				for (int j = 0; j < keys; j++) {
					putObject(bucketName, prefix + eucaUUID(), fileToPut, keySet);
				}

				// List objects and verify that they are ordered lexicographically
				objects = listObjects(bucketName, prefix, null, null, null, false);
				verifyObjectSummaries(keySet, objects.getObjectSummaries());

				// Put the prefix and keys in the map
				prefixKeyMap.put(prefix, keySet);
			}

			// List objects and verify the results
			objects = listObjects(bucketName, null, null, null, null, false);
			assertTrue("Expected version summary list to be of size " + (prefixes * keys) + ", but got a list of size " + objects.getObjectSummaries().size(),
					objects.getObjectSummaries().size() == (prefixes * keys));
			Iterator<S3ObjectSummary> summaryIterator = objects.getObjectSummaries().iterator();

			for (Entry<String, TreeSet<String>> mapEntry : prefixKeyMap.entrySet()) {
				for (String key : mapEntry.getValue()) {
					S3ObjectSummary objectSummary = summaryIterator.next();
					assertTrue("Expected keys to be ordered lexicographically", objectSummary.getKey().equals(key));
					verifyObjectCommonElements(objectSummary);
				}
			}
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run prefix");
		}
	}

	/**
	 * <p>Test for verifying ordering of list objects using a marker</p>
	 * 
	 * <p>Test failed against Walrus. Results returned by Walrus are inclusive of the marker where as S3's results are exclusive</p>
	 * 
	 * @see <a href="https://eucalyptus.atlassian.net/browse/EUCA-7985">EUCA-7985</a>
	 */
	@Test
	public void marker() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - keyMarker");

		try {
			int keys = 3;// + random.nextInt(8); // 3-10 keys
			TreeSet<String> keySet = new TreeSet<String>();
			ObjectListing objects = null;

			print("Number of keys: " + keys);

			for (int i = 0; i < keys; i++) {
				String key = VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length())) + eucaUUID(); // Prefix it with any character in the valid chars

				// Upload an object using the key
				putObject(bucketName, key, fileToPut, keySet);
			}

			// List the objects and verify that they are ordered lexicographically
			objects = listObjects(bucketName, null, null, null, null, false);
			verifyObjectSummaries(keySet, objects.getObjectSummaries());

			// Starting with every key in the ascending order, list the objects using that key as the key marker and verify that the results.
			for (String marker : keySet) {
				// Compute what the sorted versions should look like
				NavigableSet<String> tailSet = keySet.tailSet(marker, false);

				// List the objects and verify that they are ordered lexicographically
				objects = listObjects(bucketName, null, marker, null, null, false);
				verifyObjectSummaries(tailSet, objects.getObjectSummaries());
			}
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run keyMarker");
		}
	}

	/**
	 * Test for verifying common prefixes using a delimiter
	 */
	@Test
	public void delimiter_1() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - delimiter_1");

		try {
			int prefixes = 3 + random.nextInt(3); // 3-5 prefixes
			int keys = 3 + random.nextInt(3); // 3-5 keys
			String delimiter = "/"; // Pick a random delimiter afterwards
			Map<String, TreeSet<String>> prefixKeyMap = new TreeMap<String, TreeSet<String>>();
			ObjectListing objects = null;

			print("Number of prefixes: " + prefixes);
			print("Number of keys: " + keys);

			for (int i = 0; i < prefixes; i++) {
				String prefix = VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length())) + eucaUUID() + delimiter; // Prefix it with a char
				print("Prefix name: " + prefix);
				TreeSet<String> keySet = new TreeSet<String>();

				// Upload objects with different keys that start with the same prefix
				for (int j = 0; j < keys; j++) {
					putObject(bucketName, prefix + eucaUUID(), fileToPut, keySet);
				}

				// List objects and verify that they are ordered lexicographically
				objects = listObjects(bucketName, prefix, null, null, null, false);
				verifyObjectSummaries(keySet, objects.getObjectSummaries());

				// Put the prefix and keys in the map
				prefixKeyMap.put(prefix, keySet);
			}

			objects = listObjects(bucketName, null, null, delimiter, null, false);
			assertTrue("Expected to not get any version summaries but got a list of size " + objects.getObjectSummaries().size(), objects.getObjectSummaries()
					.size() == 0);
			assertTrue("Expected common prefixes list to be of size " + prefixKeyMap.size() + ", but got a list of size " + objects.getCommonPrefixes().size(),
					objects.getCommonPrefixes().size() == prefixKeyMap.size());
			for (String prefix : prefixKeyMap.keySet()) {
				assertTrue("Expected common prefix list to contain " + prefix, objects.getCommonPrefixes().contains(prefix));
			}
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run delimiter_1");
		}
	}

	/**
	 * Test for verifying the common prefixes and delimiter
	 * 
	 * Test fails against Walrus, prefixes in the common prefix list are incorrectly represented. The prefix part is not included, only the portion from prefix
	 * to the first occurrence of the delimiter is returned
	 * 
	 * @see <a href="https://eucalyptus.atlassian.net/browse/EUCA-7991">EUCA-7991</a>
	 */
	@Test
	public void delimiter_2() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - delimiter_2");

		try {
			int innerP = 2;// + random.nextInt(4); // 2-5 inner prefixes
			int keys = 3;// + random.nextInt(3); // 3-5 keys
			String delimiter = "/";
			String outerPrefix = VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length())) + eucaUUID() + delimiter;
			Map<String, TreeSet<String>> prefixKeyMap = new TreeMap<String, TreeSet<String>>();
			ObjectListing objects = null;

			print("Number of inner prefixes: " + innerP);
			print("Number of keys: " + keys);
			print("Outer prefix: " + outerPrefix);

			for (int i = 0; i < innerP; i++) {
				String innerPrefix = outerPrefix + VALID_CHARS.charAt(random.nextInt(VALID_CHARS.length())) + eucaUUID() + delimiter;
				print("Inner prefix: " + innerPrefix);
				TreeSet<String> keySet = new TreeSet<String>();

				// Upload objects with different keys that start with the same prefix
				for (int j = 0; j < keys; j++) {
					putObject(bucketName, innerPrefix + eucaUUID(), fileToPut, keySet);
				}

				// List objects and verify that they are ordered lexicographically
				objects = listObjects(bucketName, innerPrefix, null, null, null, false);
				verifyObjectSummaries(keySet, objects.getObjectSummaries());

				// Put the prefix and keys in the map
				prefixKeyMap.put(innerPrefix, keySet);
			}

			// Upload something of the form outerprefix/key
			TreeSet<String> keySet = new TreeSet<String>();
			for (int i = 0; i < keys; i++) {
				putObject(bucketName, outerPrefix + eucaUUID(), fileToPut, keySet);
			}
			prefixKeyMap.put(outerPrefix, keySet);

			// List objects and verify the results
			objects = listObjects(bucketName, null, null, null, null, false);
			assertTrue("Expected version summary list to be of size " + (prefixKeyMap.size() * keys) + ", but got a list of size "
					+ objects.getObjectSummaries().size(), objects.getObjectSummaries().size() == (prefixKeyMap.size() * keys));
			Iterator<S3ObjectSummary> summaryIterator = objects.getObjectSummaries().iterator();

			for (Entry<String, TreeSet<String>> mapEntry : prefixKeyMap.entrySet()) {
				for (String key : mapEntry.getValue()) {
					S3ObjectSummary objectSummary = summaryIterator.next();
					assertTrue("Expected keys to be ordered lexicographically", objectSummary.getKey().equals(key));
					verifyObjectCommonElements(objectSummary);
				}
			}

			// List objects with prefix and delimiter and verify again
			objects = listObjects(bucketName, outerPrefix, null, delimiter, null, false);
			assertTrue("Expected version summaries list to be of size " + keys + "but got a list of size " + objects.getObjectSummaries().size(), objects
					.getObjectSummaries().size() == keys);
			assertTrue("Expected common prefixes list to be of size " + innerP + ", but got a list of size " + objects.getCommonPrefixes().size(), objects
					.getCommonPrefixes().size() == innerP);

			for (String prefix : prefixKeyMap.keySet()) {
				if (!prefix.equals(outerPrefix)) {
					assertTrue("Expected common prefix list to contain " + prefix, objects.getCommonPrefixes().contains(prefix));
				}
			}

			// keys with only the oute rprefix should be in the summary list
			summaryIterator = objects.getObjectSummaries().iterator();
			for (String key : prefixKeyMap.get(outerPrefix)) {
				S3ObjectSummary objectSummary = summaryIterator.next();
				assertTrue("Expected keys to be ordered lexicographically", objectSummary.getKey().equals(key));
				verifyObjectCommonElements(objectSummary);
			}
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run delimiter_2");
		}
	}

	/**
	 * Test for listing and verifying the order of versions using max-keys, next-key-marker and next-version-id-marker
	 * 
	 * <p>Test failed against Walrus. Results returned by Walrus are inclusive of the version summary that matches the key-marker and version-id-marker pair
	 * where as S3's results are exclusive. Version ID marker is missing in the response</p>
	 * 
	 * @see <a href="https://eucalyptus.atlassian.net/browse/EUCA-7985">EUCA-7985</a>
	 * @see <a href="https://eucalyptus.atlassian.net/browse/EUCA-7986">EUCA-7986</a>
	 * 
	 */
	@Test
	public void maxKeys() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - maxKeys");

		try {
			int maxKeys = 3 + random.nextInt(4); // Max keys 3-6
			int multiplier = 3 + random.nextInt(4); // Max uploads 9 - 36
			TreeSet<String> keySet = new TreeSet<String>();
			ObjectListing objects = null;

			print("Max keys: " + maxKeys);
			print("Number of keys: " + (maxKeys * multiplier));

			for (int i = 0; i < (maxKeys * multiplier); i++) {
				// Upload an object using the key
				putObject(bucketName, eucaUUID(), fileToPut, keySet);
			}

			// List objects and verify that they are ordered lexicographically
			objects = listObjects(bucketName, null, null, null, null, false);
			verifyObjectSummaries(keySet, objects.getObjectSummaries());

			Iterator<String> keyIterator = keySet.iterator();
			String nextMarker = null;

			for (int i = 1; i <= multiplier; i++) {
				if (i != multiplier) {
					objects = listObjects(bucketName, null, nextMarker, null, maxKeys, true);
				} else {
					objects = listObjects(bucketName, null, nextMarker, null, maxKeys, false);
				}

				assertTrue("Expected version summaries list to be of size " + maxKeys + "but got a list of size " + objects.getObjectSummaries().size(),
						objects.getObjectSummaries().size() == maxKeys);
				Iterator<S3ObjectSummary> summaryIterator = objects.getObjectSummaries().iterator();
				S3ObjectSummary objectSummary = null;

				// Verify the object list
				while (summaryIterator.hasNext()) {
					objectSummary = summaryIterator.next();
					assertTrue("Expected keys to be ordered lexicographically", objectSummary.getKey().equals(keyIterator.next()));
					verifyObjectCommonElements(objectSummary);
				}

				if (i != multiplier) {
					nextMarker = objects.getNextMarker();
					assertTrue("Expected next-marker to be " + objectSummary.getKey() + ", but got " + nextMarker, objectSummary.getKey().equals(nextMarker));
				} else {
					assertTrue("Expected next-marker to be null, but got " + objects.getNextMarker(), objects.getNextMarker() == null);
				}
			}
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run maxKeys");
		}
	}

	private void enableBucketVersioning(String bucketName) throws InterruptedException {
		print("Setting bucket versioning configuration to ENABLED");
		s3.setBucketVersioningConfiguration(new SetBucketVersioningConfigurationRequest(bucketName, new BucketVersioningConfiguration()
				.withStatus(BucketVersioningConfiguration.ENABLED)));

		print("Fetching bucket versioning configuration after setting it to ENABLED");
		BucketVersioningConfiguration versioning = null;
		int counter = 0;
		do {
			Thread.sleep(1000);
			versioning = s3.getBucketVersioningConfiguration(bucketName);
			if (versioning.getStatus().equals(BucketVersioningConfiguration.ENABLED)) {
				break;
			}
			counter++;
		} while (counter < 5);
		assertTrue("Invalid result for bucket versioning configuration", versioning != null);
		assertTrue("Expected bucket versioning configuration to be ENABLED, but found it to be " + versioning.getStatus(),
				versioning.getStatus().equals(BucketVersioningConfiguration.ENABLED));
	}

	private void putObject(final String bucketName, final String key, File fileToPut, Set<String> keySet) {
		print("Putting object " + key + " in bucket " + bucketName);
		final PutObjectResult putResult = s3.putObject(bucketName, key, fileToPut);
		cleanupTasks.add(new Runnable() {
			@Override
			public void run() {
				print("Deleting object " + key);
				s3.deleteObject(bucketName, key);
			}
		});
		assertTrue("Invalid put object result", putResult != null);
		assertTrue("Expected version ID to be null, but got " + putResult.getVersionId(), putResult.getVersionId() == null);
		assertTrue("Mimatch in md5sums between object and PUT result. Expected " + md5 + ", but got " + putResult.getETag(), putResult.getETag() != null
				&& putResult.getETag().equals(md5));
		keySet.add(key);
	}

	private ObjectListing listObjects(String bucketName, String prefix, String marker, String delimiter, Integer maxKeys, boolean isTruncated) {

		StringBuilder sb = new StringBuilder("List objects using bucket=" + bucketName);

		ListObjectsRequest request = new ListObjectsRequest();
		request.setBucketName(bucketName);

		if (prefix != null) {
			request.setPrefix(prefix);
			sb.append(", prefix=").append(prefix);
		}
		if (marker != null) {
			request.setMarker(marker);
			sb.append(", key marker=").append(marker);
		}
		if (delimiter != null) {
			request.setDelimiter(delimiter);
			sb.append(", delimiter=").append(delimiter);
		}
		if (maxKeys != null) {
			request.setMaxKeys(maxKeys);
			sb.append(", max results=").append(maxKeys);
		}

		print(sb.toString());
		ObjectListing objectList = s3.listObjects(request);

		assertTrue("Invalid object list", objectList != null);
		assertTrue("Expected object listing bucket name to be " + bucketName + ", but got " + objectList.getBucketName(),
				objectList.getBucketName().equals(bucketName));
		assertTrue("Expected delimiter to be " + delimiter + ", but got " + objectList.getDelimiter(), StringUtils.equals(objectList.getDelimiter(), delimiter));
		assertTrue("Expected common prefixes to be empty or populated, but got " + objectList.getCommonPrefixes(), objectList.getCommonPrefixes() != null);
		assertTrue("Expected marker to be " + marker + ", but got " + objectList.getMarker(), StringUtils.equals(objectList.getMarker(), marker));
		assertTrue("Expected max-keys to be " + (maxKeys != null ? maxKeys : DEFAULT_MAX_KEYS) + ", but got " + objectList.getMaxKeys(),
				objectList.getMaxKeys() == (maxKeys != null ? maxKeys : DEFAULT_MAX_KEYS));
		assertTrue("Expected prefix to be " + prefix + ", but got " + objectList.getPrefix(), StringUtils.equals(objectList.getPrefix(), prefix));
		assertTrue("Invalid object summary list", objectList.getObjectSummaries() != null);
		assertTrue("Expected is truncated to be " + isTruncated + ", but got " + objectList.isTruncated(), objectList.isTruncated() == isTruncated);
		if (objectList.isTruncated()) {
			assertTrue("Invalid next-marker, expected it to contain next key but got null", objectList.getNextMarker() != null);
		} else {
			assertTrue("Invalid next-marker, expected it to be null but got " + objectList.getNextMarker(), objectList.getNextMarker() == null);
		}

		return objectList;
	}

	private void verifyObjectSummaries(Set<String> keySet, List<S3ObjectSummary> objectSummaries) {
		assertTrue("Expected object summary list to be of size " + keySet.size() + ", but got a list of size " + objectSummaries.size(),
				keySet.size() == objectSummaries.size());

		Iterator<String> keyIterator = keySet.iterator();
		Iterator<S3ObjectSummary> summaryIterator = objectSummaries.iterator();
		S3ObjectSummary objectSummary = null;

		// Verify the object summaries against the key set
		while (summaryIterator.hasNext()) {
			objectSummary = summaryIterator.next();
			assertTrue("Expected keys to be ordered lexicographically", objectSummary.getKey().equals(keyIterator.next()));
			verifyObjectCommonElements(objectSummary);
		}
	}

	private void verifyObjectCommonElements(S3ObjectSummary objectSummary) {
		assertTrue("Expected bucket name to be " + bucketName + ", but got " + objectSummary.getBucketName(), objectSummary.getBucketName().equals(bucketName));
		assertTrue("Expected etag to be " + md5 + ", but got " + objectSummary.getETag(), objectSummary.getETag().equals(md5));
		assertTrue("Invalid last modified field", objectSummary.getLastModified() != null);
		// assertTrue("Expected owner ID to be " + ownerID + ", but got " + objectSummary.getOwner().getId(), objectSummary.getOwner().getId().equals(ownerID));
		assertTrue("Expected size to be " + size + ", but got " + objectSummary.getSize(), objectSummary.getSize() == size);
	}

	private void printException(AmazonServiceException ase) {
		ase.printStackTrace();
		print("Caught Exception: " + ase.getMessage());
		print("HTTP Status Code: " + ase.getStatusCode());
		print("Amazon Error Code: " + ase.getErrorCode());
		print("Request ID: " + ase.getRequestId());
	}
}
