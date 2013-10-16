package com.eucalyptus.tests.awssdk;

import static com.eucalyptus.tests.awssdk.Eutester4j.assertThat;
import static com.eucalyptus.tests.awssdk.Eutester4j.eucaUUID;
import static com.eucalyptus.tests.awssdk.Eutester4j.initS3Client;
import static com.eucalyptus.tests.awssdk.Eutester4j.print;
import static com.eucalyptus.tests.awssdk.Eutester4j.s3;
import static com.eucalyptus.tests.awssdk.Eutester4j.testInfo;
import static org.testng.AssertJUnit.assertTrue;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import org.apache.commons.codec.digest.DigestUtils;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import com.amazonaws.AmazonServiceException;
import com.amazonaws.services.s3.model.Bucket;
import com.amazonaws.services.s3.model.GetObjectRequest;
import com.amazonaws.services.s3.model.ObjectMetadata;
import com.amazonaws.services.s3.model.PutObjectRequest;
import com.amazonaws.services.s3.model.PutObjectResult;
import com.amazonaws.services.s3.model.S3Object;
import com.amazonaws.util.BinaryUtils;
import com.amazonaws.util.Md5Utils;

/**
 * <p>This class contains tests for basic operations on S3 objects.</p>
 * 
 * @author Swathi Gangisetty
 * 
 */
public class S3ObjectTests {

	String bucketName = null;
	List<Runnable> cleanupTasks = null;

	@BeforeClass
	public void init() throws Exception {
		print("*** PRE SUITE SETUP ***");
		initS3Client();
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
				s3.deleteBucket(bucketName);
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

	@Test
	public void objectBasics() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - objectBasics");
		try {
			final String key = eucaUUID();
			File fileToPut = new File("3wolfmoon-download.jpg");
			String md5_orig = BinaryUtils.toHex(Md5Utils.computeMD5Hash(new FileInputStream(fileToPut)));

			print("Putting object " + key + " in bucket " + bucketName);
			PutObjectResult putObj = s3.putObject(new PutObjectRequest(bucketName, key, fileToPut));
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting object " + key);
					s3.deleteObject(bucketName, key);
				}
			});
			assertTrue("Invalid put object result", putObj != null);
			assertTrue("Mimatch in md5sums between original object and PUT result. Expected " + md5_orig + ", but got " + putObj.getETag(),
					putObj.getETag() != null && putObj.getETag().equals(md5_orig));
			assertTrue("Invalid version id. Expected to be null but got " + putObj.getVersionId(), putObj.getVersionId() == null);

			final String fileName1 = key + '_' + eucaUUID();
			ObjectMetadata metadata = s3.getObject(new GetObjectRequest(bucketName, key), new File(fileName1));
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting file " + fileName1);
					new File(fileName1).delete();
				}
			});
			String md5_get = BinaryUtils.toHex(Md5Utils.computeMD5Hash(new FileInputStream(fileName1)));
			assertTrue("Invalid metadata result", metadata != null);
			assertTrue("Mismatch in content lengths. Expected " + fileToPut.length() + ", but got" + metadata.getContentLength(),
					fileToPut.length() == metadata.getContentLength());
			assertTrue("Mismatch in md5sums between original and downloaded objects. Expected " + md5_orig + ", but got " + md5_get, md5_orig.equals(md5_get));
			assertTrue("Mismatch in md5sums between original and GET object metadata. Expected " + md5_orig + ", but got " + metadata.getETag(),
					metadata.getETag() != null && metadata.getETag().equals(md5_orig));
			assertTrue("Invalid last modified date", metadata.getLastModified() != null);
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run objectBasics");
		}
	}

	@Test
	public void getObjectWithRange() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - getObjectWithRange");
		try {
			final String key = eucaUUID();
			File fileToPut = new File("test.dat");
			String md5 = BinaryUtils.toHex(Md5Utils.computeMD5Hash(new FileInputStream(fileToPut)));

			long length = fileToPut.length();
			print("Size of object: " + length);

			print("Putting object " + key + " in bucket " + bucketName);
			PutObjectResult putObj = s3.putObject(new PutObjectRequest(bucketName, key, fileToPut));
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					int counter = 0;
					do {
						print("Deleting object " + key + " from bucket " + bucketName);
						counter++;
						try {
							s3.deleteObject(bucketName, key);
							break;
						} catch (AmazonServiceException ase) {
							// TODO File a bug
							print("Error deleting object " + key + " from bucket " + bucketName);
							ase.printStackTrace();
							if (counter < 5) {
								try {
									Thread.sleep(2000);
								} catch (InterruptedException e) {
									e.printStackTrace();
								}
							}
						}
					} while (counter < 5);
				}
			});
			assertTrue("Invalid put object result", putObj != null);
			assertTrue("md5sums dont match, expected " + md5 + " but got " + putObj.getETag(), putObj.getETag().equals(md5));

			GetObjectRequest request = new GetObjectRequest(bucketName, key);

			print("Getting object with range 0-" + (length + 1));
			request.setRange(0, length + 1);
			S3Object object = s3.getObject(request);
			assertTrue("Invalid get object result", object != null);
			assertTrue("Mismatch in object length. Expected " + length + " , but got " + object.getObjectMetadata().getContentLength(), object
					.getObjectMetadata().getContentLength() == length);
			flushDataSilently(object.getObjectContent());

			print("Getting object with range 0-" + length);
			request.setRange(0, length);
			final String fileName1 = key + '_' + eucaUUID();
			ObjectMetadata metadata = s3.getObject(request, new File(fileName1));
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting file " + fileName1);
					new File(fileName1).delete();
				}
			});
			assertTrue("Invalid metadata result", metadata != null);
			assertTrue("Mismatch in object length. Expected " + length + " , but got " + metadata.getContentLength(), metadata.getContentLength() == length);
			assertTrue("Mismatch in file length. Expected " + length + ", but got " + new File(fileName1).length(), new File(fileName1).length() == length);

			print("Getting object with range 0-" + (length - 1));
			request.setRange(0, length - 1);
			object = s3.getObject(request);
			assertTrue("Invalid get object result", object != null);
			assertTrue("Mismatch in object length. Expected " + length + " , but got " + object.getObjectMetadata().getContentLength(), object
					.getObjectMetadata().getContentLength() == length);
			flushDataSilently(object.getObjectContent());

			print("Getting object with range 0-" + (length - 2));
			request.setRange(0, length - 2);
			object = s3.getObject(request);
			assertTrue("Invalid get object result", object != null);
			assertTrue("Mismatch in object length. Expected " + (length - 1) + " , but got " + object.getObjectMetadata().getContentLength(), object
					.getObjectMetadata().getContentLength() == (length - 1));
			flushDataSilently(object.getObjectContent());

			print("Getting object with range 4-" + (length - 2));
			request.setRange(4, length - 2);
			final String fileName2 = key + '_' + eucaUUID();
			metadata = s3.getObject(request, new File(fileName2));
			cleanupTasks.add(new Runnable() {
				@Override
				public void run() {
					print("Deleting file " + fileName2);
					new File(fileName2).delete();
				}
			});
			assertTrue("Invalid metadata result", metadata != null);
			assertTrue("Mismatch in object length. Expected " + (length - 5) + " , but got " + metadata.getContentLength(),
					metadata.getContentLength() == (length - 5));
			assertTrue("Mismatch in file length. Expected " + (length - 5) + ", but got " + new File(fileName2).length(),
					new File(fileName2).length() == (length - 5));
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run getObjectWithRange");
		}
	}

	private void flushDataSilently(InputStream input) throws IOException {
		BufferedReader reader = new BufferedReader(new InputStreamReader(input));
		print("Flushing object input stream silently");
		while (true) {
			String line = reader.readLine();
			if (line == null)
				break;
		}
		input.close();
	}

	private void printException(AmazonServiceException ase) {
		ase.printStackTrace();
		print("Caught Exception: " + ase.getMessage());
		print("HTTP Status Code: " + ase.getStatusCode());
		print("Amazon Error Code: " + ase.getErrorCode());
	}
}
