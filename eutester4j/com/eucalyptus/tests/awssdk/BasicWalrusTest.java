package com.eucalyptus.tests.awssdk;

import com.amazonaws.AmazonServiceException;
import com.amazonaws.services.s3.model.*;
import org.testng.annotations.Test;

import java.io.File;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;


public class BasicWalrusTest {

    String bucketName;

    @Test
    public void WalrusTestNG() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();

        File fileToPut = new File("/Users/tony/Documents/Eutester/eutester4j/3wolfmoon-download.jpg");
        File fileToGet = new File("3wolfmoon-download.jpg");
        bucketName = new String("mybucket-new");

        /* A welcome message does not hurt your eyes */
        print("===========================================");
        print("Welcome to the AWS Java SDK!");
        print("===========================================");

        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            /* Create bucket */
            try {
                s3.createBucket(bucketName);
                cleanupTasks.add(new Runnable() {
                    @Override
                    public void run() {
                        print("Deleting Bucket: " + bucketName);
                        s3.deleteBucket(bucketName);
                    }
                });
            } catch (AmazonServiceException ase) {
                print("Error creating bucket: " + bucketName);
                ase.printStackTrace();
                print("Caught Exception: " + ase.getMessage());
                print("Reponse Status Code: " + ase.getStatusCode());
                print("Error Code: " + ase.getErrorCode());
                print("Request ID: " + ase.getRequestId());
                assertThat(false,"Failed to create bucket");
            }

		    /* Upload a file to the bucket */
            try {
                s3.putObject(bucketName, "3wolfmoon.jpg", fileToPut);
                cleanupTasks.add(new Runnable() {
                    @Override
                    public void run() {
                        print("Deleting top level object");
                        s3.deleteObject(bucketName, "3wolfmoon.jpg");
                    }
                });
            } catch (AmazonServiceException ase) {
                print("Error uploading file to the bucket: " + bucketName);
                ase.printStackTrace();
                print("Caught Exception: " + ase.getMessage());
                print("Reponse Status Code: " + ase.getStatusCode());
                print("Error Code: " + ase.getErrorCode());
                print("Request ID: " + ase.getRequestId());
                assertThat(false,"Failed to upload file to bucket");
            }

            /* Upload a file using delimiters in the key */
            try {
                s3.putObject(bucketName, "abc/def/3wolfmoon.jpg", fileToPut);
                cleanupTasks.add(new Runnable() {
                    @Override
                    public void run() {
                        print("Deleting nested object");
                        s3.deleteObject(bucketName, "abc/def/3wolfmoon.jpg");
                    }
                });
            } catch (AmazonServiceException ase) {
                print("Error uploading a file using key with delimiters\n");
                ase.printStackTrace();
                print("Caught Exception: " + ase.getMessage());
                print("Reponse Status Code: " + ase.getStatusCode());
                print("Error Code: " + ase.getErrorCode());
                print("Request ID: " + ase.getRequestId());
                assertThat(false,"Failed to put file using key with delimiters");
            }

            /* Download a file from the bucket to local filesystem */
            try {
                s3.getObject(new GetObjectRequest(bucketName, "3wolfmoon.jpg"), fileToGet);
            } catch (AmazonServiceException ase) {
                print("Error download file from the bucket\n");
                ase.printStackTrace();
                print("Caught Exception: " + ase.getMessage());
                print("Reponse Status Code: " + ase.getStatusCode());
                print("Error Code: " + ase.getErrorCode());
                print("Request ID: " + ase.getRequestId());
                assertThat(false,"Failed to download bucket");
            }

		    /* Listing keys */
            ObjectListing objectListing;

            ListObjectsRequest listObjectsRequest = new ListObjectsRequest();
            listObjectsRequest.withBucketName(bucketName);
            listObjectsRequest.withPrefix("abc/");

            do {
                objectListing = s3.listObjects(listObjectsRequest);
                for (S3ObjectSummary objectSummary :
                        objectListing.getObjectSummaries()) {
                    print("Listing abc folder: " + objectSummary.getKey() + "  " +
                            "(size = " + objectSummary.getSize() +
                            ")");
                }
                listObjectsRequest.setMarker(objectListing.getNextMarker());
            } while (objectListing.isTruncated());

		    /* List all buckets in the cloud */
            try {
                List<Bucket> buckets = s3.listBuckets();
                print("List of all buckets in your cloud:");
                for (Bucket bucket : buckets) {
                    print(bucket.getName());
                }
            } catch (AmazonServiceException ase) {
                ase.printStackTrace();
                print("Error Message:    " + ase.getMessage());
                print("HTTP Status Code: " + ase.getStatusCode());
                print("AWS Error Code:   " + ase.getErrorCode());
                print("Error Type:       " + ase.getErrorType());
                print("Request ID:       " + ase.getRequestId());
                assertThat(false,"Failed to list buckets");
            }
        } finally {
            Collections.reverse(cleanupTasks);
            for (final Runnable cleanupTask : cleanupTasks)
                try {
                    cleanupTask.run();
                } catch (Exception e) {
                    e.printStackTrace();
                }
        }
    }
}
