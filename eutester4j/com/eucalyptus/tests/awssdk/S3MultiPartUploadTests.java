/*************************************************************************
 * Copyright 2009-2013 Eucalyptus Systems, Inc.
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see http://www.gnu.org/licenses/.
 *
 * Please contact Eucalyptus Systems, Inc., 6755 Hollister Ave., Goleta
 * CA 93117, USA or visit http://www.eucalyptus.com/licenses/ if you need
 * additional information or have any questions.
 *
 * This file may incorporate work covered under the following copyright
 * and permission notice:
 *
 *   Software License Agreement (BSD License)
 *
 *   Copyright (c) 2008, Regents of the University of California
 *   All rights reserved.
 *
 *   Redistribution and use of this software in source and binary forms,
 *   with or without modification, are permitted provided that the
 *   following conditions are met:
 *
 *     Redistributions of source code must retain the above copyright
 *     notice, this list of conditions and the following disclaimer.
 *
 *     Redistributions in binary form must reproduce the above copyright
 *     notice, this list of conditions and the following disclaimer
 *     in the documentation and/or other materials provided with the
 *     distribution.
 *
 *   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 *   "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 *   LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
 *   FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
 *   COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
 *   INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
 *   BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
 *   LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 *   CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 *   LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
 *   ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 *   POSSIBILITY OF SUCH DAMAGE. USERS OF THIS SOFTWARE ACKNOWLEDGE
 *   THE POSSIBLE PRESENCE OF OTHER OPEN SOURCE LICENSED MATERIAL,
 *   COPYRIGHTED MATERIAL OR PATENTED MATERIAL IN THIS SOFTWARE,
 *   AND IF ANY SUCH MATERIAL IS DISCOVERED THE PARTY DISCOVERING
 *   IT MAY INFORM DR. RICH WOLSKI AT THE UNIVERSITY OF CALIFORNIA,
 *   SANTA BARBARA WHO WILL THEN ASCERTAIN THE MOST APPROPRIATE REMEDY,
 *   WHICH IN THE REGENTS' DISCRETION MAY INCLUDE, WITHOUT LIMITATION,
 *   REPLACEMENT OF THE CODE SO IDENTIFIED, LICENSING OF THE CODE SO
 *   IDENTIFIED, OR WITHDRAWAL OF THE CODE CAPABILITY TO THE EXTENT
 *   NEEDED TO COMPLY WITH ANY SUCH LICENSES OR RIGHTS.
 ************************************************************************/

package com.eucalyptus.tests.awssdk;

import static com.eucalyptus.tests.awssdk.Eutester4j.assertThat;
import static com.eucalyptus.tests.awssdk.Eutester4j.eucaUUID;
import static com.eucalyptus.tests.awssdk.Eutester4j.initS3ClientWithNewAccount;
import static com.eucalyptus.tests.awssdk.Eutester4j.print;
import static com.eucalyptus.tests.awssdk.Eutester4j.testInfo;
import static org.testng.AssertJUnit.assertTrue;

import java.io.BufferedInputStream;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

import org.testng.annotations.AfterClass;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import com.amazonaws.AmazonServiceException;
import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.model.AbortMultipartUploadRequest;
import com.amazonaws.services.s3.model.AccessControlList;
import com.amazonaws.services.s3.model.Bucket;
import com.amazonaws.services.s3.model.CannedAccessControlList;
import com.amazonaws.services.s3.model.CanonicalGrantee;
import com.amazonaws.services.s3.model.CompleteMultipartUploadRequest;
import com.amazonaws.services.s3.model.CompleteMultipartUploadResult;
import com.amazonaws.services.s3.model.CopyObjectResult;
import com.amazonaws.services.s3.model.GetObjectRequest;
import com.amazonaws.services.s3.model.Grant;
import com.amazonaws.services.s3.model.GroupGrantee;
import com.amazonaws.services.s3.model.InitiateMultipartUploadRequest;
import com.amazonaws.services.s3.model.InitiateMultipartUploadResult;
import com.amazonaws.services.s3.model.ObjectMetadata;
import com.amazonaws.services.s3.model.Owner;
import com.amazonaws.services.s3.model.PartETag;
import com.amazonaws.services.s3.model.Permission;
import com.amazonaws.services.s3.model.S3Object;
import com.amazonaws.services.s3.model.UploadPartRequest;
import com.amazonaws.services.s3.model.UploadPartResult;
import com.amazonaws.util.BinaryUtils;
import com.amazonaws.util.Md5Utils;
import com.google.common.collect.Lists;

/**
 * These tests are basic Multipart Upload tests. The documentation for the SDK and MPU are available here -
 * http://docs.aws.amazon.com/AmazonS3/latest/dev/UsingMPDotJavaAPI.html
 * 
 * These tests currently leverage the Low-Level Java API only for more fine-grained control and debugging.
 * 
 */
public class S3MultiPartUploadTests {

  String bucketName = null;
  List<Runnable> cleanupTasks = null;
  private static AmazonS3 s3 = null;
  private static String account = null;
  private static String ownerName = null;
  private static String ownerId = null;
  byte[] randomBytes;

  @BeforeClass
  public void init() throws Exception {
    print("### PRE SUITE SETUP - " + this.getClass().getSimpleName());
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

    // s3 = getS3Client("awsrc_euca");

    Owner owner = s3.getS3AccountOwner();
    ownerName = owner.getDisplayName();
    ownerId = owner.getId();

    // Generate a 6M random byte stream
    print("Generating a 6MB random byte array");
    randomBytes = new byte[6 * 1024 * 1024];
    new Random().nextBytes(randomBytes);
  }

  public AmazonS3 getS3Client(String credPath) throws Exception {
    print("Getting cloud information from " + credPath);

    String s3Endpoint = Eutester4j.parseEucarc(credPath, "S3_URL");

    String secretKey = Eutester4j.parseEucarc(credPath, "EC2_SECRET_KEY").replace("'", "");
    String accessKey = Eutester4j.parseEucarc(credPath, "EC2_ACCESS_KEY").replace("'", "");

    print("Initializing S3 connections");
    return Eutester4j.getS3Client(accessKey, secretKey, s3Endpoint);
  }

  @AfterClass
  public void teardown() throws Exception {
    print("### POST SUITE CLEANUP - " + this.getClass().getSimpleName());
    Eutester4j.deleteAccount(account);
    s3 = null;
  }

  @BeforeMethod
  public void setup() throws Exception {
    bucketName = eucaUUID();
    cleanupTasks = new ArrayList<Runnable>();
    Bucket bucket = S3Utils.createBucket(s3, account, bucketName, S3Utils.BUCKET_CREATION_RETRIES);
    cleanupTasks.add(new Runnable() {
      @Override
      public void run() {
        print(account + ": Deleting bucket " + bucketName);
        s3.deleteBucket(bucketName);
      }
    });

    assertTrue("Invalid reference to bucket", bucket != null);
    assertTrue("Mismatch in bucket names. Expected bucket name to be " + bucketName + ", but got " + bucket.getName(),
        bucketName.equals(bucket.getName()));
  }

  @AfterMethod
  public void cleanup() throws Exception {
    Collections.reverse(cleanupTasks);
    for (final Runnable cleanupTask : cleanupTasks) {
      try {
        cleanupTask.run();
      } catch (Exception e) {
        print("Unable to run clean up task: " + e);
      }
    }
  }

  private void printException(AmazonServiceException ase) {
    print("Caught Exception: " + ase.getMessage());
    ase.printStackTrace();
  }

  @Test
  public void basicMultiPartUpload() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - basicMultiPartUpload");
    final File fileToPut = new File(eucaUUID());
    FileOutputStream fos = new FileOutputStream(fileToPut);

    try {
      final String key = eucaUUID();
      List<PartETag> partETags = Lists.newArrayList();
      long partSize = randomBytes.length;
      int numberOfParts = 2 + new Random().nextInt(14); // 2-15 parts

      // Inititate mpu
      print(account + ": Initiating multipart upload for object " + key + " in bucket " + bucketName);
      final InitiateMultipartUploadResult initiateMpuResult = s3.initiateMultipartUpload(new InitiateMultipartUploadRequest(bucketName, key));

      // Upload a few parts
      for (int partNumber = 1; partNumber <= numberOfParts; partNumber++) {
        print(account + ": Uploading part of size " + partSize + " bytes for object " + key + ", upload ID " + initiateMpuResult.getUploadId()
            + ", part number " + partNumber);
        partETags.add(s3.uploadPart(
            new UploadPartRequest().withBucketName(bucketName).withKey(key).withUploadId(initiateMpuResult.getUploadId()).withPartNumber(partNumber)
                .withInputStream(new ByteArrayInputStream(randomBytes)).withPartSize(partSize)).getPartETag());

        // Write the bytes to a byte array output stream
        fos.write(randomBytes);
      }

      fos.close();
      cleanupTasks.add(new Runnable() {
        @Override
        public void run() {
          try {
            print(account + ": Deleting file " + fileToPut.toPath());
            Files.deleteIfExists(fileToPut.toPath());
          } catch (IOException e) {
            print("Unable to delete file " + fileToPut.toPath() + " due to " + e);
          }
        }
      });

      // Complete mpu
      print(account + ": Completing multipart upload for object " + key + ", upload ID " + initiateMpuResult.getUploadId());
      s3.completeMultipartUpload(new CompleteMultipartUploadRequest(bucketName, key, initiateMpuResult.getUploadId(), partETags));
      cleanupTasks.add(new Runnable() {
        @Override
        public void run() {
          print(account + ": Deleting object " + key + " from bucket " + bucketName);
          s3.deleteObject(bucketName, key);
        }
      });

      // Compute md5 of uploaded object
      String mpuMd5 = BinaryUtils.toHex(Md5Utils.computeMD5Hash(new FileInputStream(fileToPut)));

      // Get the final object to compute the md5
      print(account + ": Downloading object " + key);
      S3Object s3Obj = s3.getObject(new GetObjectRequest(bucketName, key));
      String getMd5 = BinaryUtils.toHex(Md5Utils.computeMD5Hash(s3Obj.getObjectContent()));

      assertTrue("Expected objectsize to be " + (partSize * numberOfParts) + " bytes but got a file of size "
          + s3Obj.getObjectMetadata().getContentLength() + " bytes", s3Obj.getObjectMetadata().getContentLength() == (partSize * numberOfParts));
      assertTrue("Expected md5sum to be " + mpuMd5 + " but got " + getMd5, mpuMd5.equals(getMd5));
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run basicMultiPartUpload");
    } finally {
      if (fos != null) {
        fos.close();
      }
    }
  }

  @Test
  public void multiPartUploadWithBadId() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - multiPartUploadWithBadId");
    try {
      final String key = eucaUUID();
      long partSize = randomBytes.length;
      print("using multi-part-upload to create file with key - " + key + " in bucket - " + bucketName);
      List<PartETag> partETags = Lists.newArrayList();

      InitiateMultipartUploadRequest initReq = new InitiateMultipartUploadRequest(bucketName, key);
      InitiateMultipartUploadResult initResp = s3.initiateMultipartUpload(initReq);
      print(account + ": multi-part-upload initiated with upload id - " + initResp.getUploadId());
      try {
        String badId = eucaUUID();
        UploadPartRequest upr =
            new UploadPartRequest().withBucketName(bucketName).withKey(key).withUploadId(badId).withPartNumber(1)
                .withInputStream(new ByteArrayInputStream(randomBytes)).withPartSize(partSize);
        print(account + ": sending part number - " + 1 + " with size - " + partSize + " in bytes using id - " + badId);
        partETags.add(s3.uploadPart(upr).getPartETag());
        print(account + ": part number - " + 1 + " sent successfully");
        print(account + ": completing multi-part-upload with id - " + initResp.getUploadId());
        CompleteMultipartUploadRequest completeReq = new CompleteMultipartUploadRequest(bucketName, key, initResp.getUploadId(), partETags);
        s3.completeMultipartUpload(completeReq);
        print(account + ": multi-part-upload with id - " + initResp.getUploadId() + " completed successfully");
        cleanupTasks.add(new Runnable() {
          @Override
          public void run() {
            print(account + ": Deleting object " + key);
            s3.deleteObject(bucketName, key);
          }
        });
      } catch (Exception e) {
        s3.abortMultipartUpload(new AbortMultipartUploadRequest(bucketName, key, initResp.getUploadId()));
        if (e instanceof AmazonServiceException) {
          assertThat(true, "expected an exception to be thrown because a bad upload ID was specified");
          print("an exception was received with message - " + e.getMessage());
        } else {
          e.printStackTrace();
          assertThat(false, "Failed to run basicMultiPartUpload");
        }
      }
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run basicMultiPartUpload");
    }
  }

  @Test
  public void lessThanMinimumPartSize() {
    testInfo(this.getClass().getSimpleName() + " - lessThanMinimumPartSize");
    try {
      File smallFile = new File("test.dat");
      final String key = eucaUUID();
      List<PartETag> partETags = Lists.newArrayList();

      // Inititate mpu
      print(account + ": Initiating multipart upload for object " + key + " in bucket " + bucketName);
      final InitiateMultipartUploadResult initiateMpuResult = s3.initiateMultipartUpload(new InitiateMultipartUploadRequest(bucketName, key));
      cleanupTasks.add(new Runnable() {
        @Override
        public void run() {
          print(account + ": Aborting multipart upload for object " + key + ", upload ID " + initiateMpuResult.getUploadId() + " in bucket "
              + bucketName);
          s3.abortMultipartUpload(new AbortMultipartUploadRequest(bucketName, key, initiateMpuResult.getUploadId()));
        }
      });

      // Upload parts smaller than 5 MB
      print(account + ": Uploading file of size " + smallFile.length() + " bytes for object " + key + ", upload ID "
          + initiateMpuResult.getUploadId() + ", part number 1");
      UploadPartResult uploadPartResult =
          s3.uploadPart(new UploadPartRequest().withBucketName(bucketName).withKey(key).withUploadId(initiateMpuResult.getUploadId())
              .withPartNumber(1).withFile(smallFile));
      partETags.add(uploadPartResult.getPartETag());

      print(account + ": Uploading file of size " + smallFile.length() + " bytes for object " + key + ", upload ID "
          + initiateMpuResult.getUploadId() + ", part number 2");
      uploadPartResult =
          s3.uploadPart(new UploadPartRequest().withBucketName(bucketName).withKey(key).withUploadId(initiateMpuResult.getUploadId())
              .withPartNumber(2).withFile(smallFile));
      partETags.add(uploadPartResult.getPartETag());

      boolean error = false;
      try {
        // Try completing the upload
        print(account + ": Completing multipart upload for object " + key + ", upload ID " + initiateMpuResult.getUploadId());
        s3.completeMultipartUpload(new CompleteMultipartUploadRequest(bucketName, key, initiateMpuResult.getUploadId(), partETags));
      } catch (AmazonServiceException ase) {
        error = true;
        printException(ase);
        assertTrue("Expected a 400 status code but got " + ase.getStatusCode(), ase.getStatusCode() == 400);
        assertTrue("Expected EntityTooSmall error code but got " + ase.getErrorCode(), ase.getErrorCode().equals("EntityTooSmall"));
      } finally {
        assertTrue("Expected multipart upload to fail with 400 EntityTooSmall error because of part size", error);
      }
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run lessThanMinimumPartSize");
    }
  }

  @Test
  public void noParts() {
    testInfo(this.getClass().getSimpleName() + " - noParts");
    try {
      final String key = eucaUUID();

      // Inititate mpu
      print(account + ": Initiating multipart upload for object " + key + " in bucket " + bucketName);
      final InitiateMultipartUploadResult initiateMpuResult = s3.initiateMultipartUpload(new InitiateMultipartUploadRequest(bucketName, key));
      cleanupTasks.add(new Runnable() {
        @Override
        public void run() {
          print(account + ": Aborting multipart upload for object " + key + ", upload ID " + initiateMpuResult.getUploadId() + " in bucket "
              + bucketName);
          s3.abortMultipartUpload(new AbortMultipartUploadRequest(bucketName, key, initiateMpuResult.getUploadId()));
        }
      });

      // Complete mpu
      boolean error = false;
      try {
        print(account + ": Completing multipart upload for object " + key + ", upload ID " + initiateMpuResult.getUploadId());
        s3.completeMultipartUpload(new CompleteMultipartUploadRequest(bucketName, key, initiateMpuResult.getUploadId(), new ArrayList<PartETag>()));
      } catch (AmazonServiceException ase) {
        error = true;
        printException(ase);
        assertTrue("Expected a 400 status code but got " + ase.getStatusCode(), ase.getStatusCode() == 400);
        assertTrue("Expected InvalidRequest error code but got " + ase.getErrorCode(), ase.getErrorCode().equals("InvalidRequest"));
      } finally {
        assertTrue("Expected multipart upload to fail with 400 InvalidRequest error", error);
      }
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run noParts");
    }
  }

  // This test might never pass as the s3 sdk sorts parts before sending the request
  @Test(enabled = false)
  public void invalidPartOrder() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - invalidPartOrder");
    try {
      final String key = eucaUUID();
      List<PartETag> partETags = Lists.newArrayList();
      long partSize = randomBytes.length;

      // Inititate mpu
      print(account + ": Initiating multipart upload for object " + key + " in bucket " + bucketName);
      final InitiateMultipartUploadResult initiateMpuResult = s3.initiateMultipartUpload(new InitiateMultipartUploadRequest(bucketName, key));
      cleanupTasks.add(new Runnable() {
        @Override
        public void run() {
          print(account + ": Aborting multipart upload for object " + key + ", upload ID " + initiateMpuResult.getUploadId() + " in bucket "
              + bucketName);
          s3.abortMultipartUpload(new AbortMultipartUploadRequest(bucketName, key, initiateMpuResult.getUploadId()));
        }
      });

      // Upload a few parts
      for (int partNumber = 1; partNumber <= 4; partNumber++) {
        print(account + ": Uploading part of size " + partSize + " bytes for object " + key + ", upload ID " + initiateMpuResult.getUploadId()
            + ", part number " + partNumber);
        partETags.add(s3.uploadPart(
            new UploadPartRequest().withBucketName(bucketName).withKey(key).withUploadId(initiateMpuResult.getUploadId()).withPartNumber(partNumber)
                .withInputStream(new ByteArrayInputStream(randomBytes)).withPartSize(partSize)).getPartETag());
      }

      // Reverse the list of etags
      Collections.reverse(partETags);

      boolean error = false;
      try {
        // Try completing the upload with reversed list of etags
        print(account + ": Completing multipart upload for object " + key + ", upload ID " + initiateMpuResult.getUploadId());
        s3.completeMultipartUpload(new CompleteMultipartUploadRequest(bucketName, key, initiateMpuResult.getUploadId(), partETags));
      } catch (AmazonServiceException ase) {
        error = true;
        printException(ase);
        assertTrue("Expected a 400 status code but got " + ase.getStatusCode(), ase.getStatusCode() == 400);
        assertTrue("Expected InvalidPartOrder error code but got " + ase.getErrorCode(), ase.getErrorCode().equals("InvalidPartOrder"));
      } finally {
        assertTrue("Expected multipart upload to fail with 400 InvalidPartOrder error because of incorrect part ordering", error);
      }
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run invalidPartOrder");
    }
  }

  @Test
  public void invalidPartNumber() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - invalidPartNumber");
    try {
      File smallFile = new File("test.dat");
      final String key = eucaUUID();

      // Inititate mpu
      print(account + ": Initiating multipart upload for object " + key + " in bucket " + bucketName);
      final InitiateMultipartUploadResult initiateMpuResult = s3.initiateMultipartUpload(new InitiateMultipartUploadRequest(bucketName, key));
      cleanupTasks.add(new Runnable() {
        @Override
        public void run() {
          print(account + ": Aborting multipart upload for object " + key + ", upload ID " + initiateMpuResult.getUploadId() + " in bucket "
              + bucketName);
          s3.abortMultipartUpload(new AbortMultipartUploadRequest(bucketName, key, initiateMpuResult.getUploadId()));
        }
      });

      // Try uploading part with part number 0
      boolean error = false;
      try {
        print(account + ": Uploading file of size " + smallFile.length() + " bytes for object " + key + ", upload ID "
            + initiateMpuResult.getUploadId() + ", part number 0");
        s3.uploadPart(new UploadPartRequest().withBucketName(bucketName).withKey(key).withUploadId(initiateMpuResult.getUploadId()).withPartNumber(0)
            .withFile(smallFile));
      } catch (AmazonServiceException ase) {
        error = true;
        printException(ase);
        assertTrue("Expected a 400 status code but got " + ase.getStatusCode(), ase.getStatusCode() == 400);
        assertTrue("Expected InvalidArgument error code but got " + ase.getErrorCode(), ase.getErrorCode().equals("InvalidArgument"));
      } finally {
        assertTrue("Expected multipart upload to fail with 400 InvalidArgument error", error);
      }

      // Try uploading part with part number 0
      error = false;
      try {
        print(account + ": Uploading file of size " + smallFile.length() + " bytes for object " + key + ", upload ID "
            + initiateMpuResult.getUploadId() + ", part number 10001");
        s3.uploadPart(new UploadPartRequest().withBucketName(bucketName).withKey(key).withUploadId(initiateMpuResult.getUploadId())
            .withPartNumber(10001).withFile(smallFile));
      } catch (AmazonServiceException ase) {
        error = true;
        printException(ase);
        assertTrue("Expected a 400 status code but got " + ase.getStatusCode(), ase.getStatusCode() == 400);
        assertTrue("Expected InvalidArgument error code but got " + ase.getErrorCode(), ase.getErrorCode().equals("InvalidArgument"));
      } finally {
        assertTrue("Expected multipart upload to fail with 400 InvalidArgument error", error);
      }

      // Try completing upload with one of the part numbers set to 0
      List<PartETag> partETags = Lists.newArrayList();
      partETags.add(new PartETag(0, "blah"));
      error = false;
      try {
        print(account + ": Completing multipart upload for object " + key + ", upload ID " + initiateMpuResult.getUploadId());
        s3.completeMultipartUpload(new CompleteMultipartUploadRequest(bucketName, key, initiateMpuResult.getUploadId(), partETags));
      } catch (AmazonServiceException ase) {
        error = true;
        printException(ase);
        assertTrue("Expected a 400 status code but got " + ase.getStatusCode(), ase.getStatusCode() == 400);
        assertTrue("Expected InvalidArgument error code but got " + ase.getErrorCode(), ase.getErrorCode().equals("InvalidArgument"));
      } finally {
        assertTrue("Expected multipart upload to fail with 400 InvalidArgument error", error);
      }

      // Try completing upload with one of the part numbers set to 10001
      partETags = Lists.newArrayList();
      partETags.add(new PartETag(10001, "blah"));
      error = false;
      try {
        print(account + ": Completing multipart upload for object " + key + ", upload ID " + initiateMpuResult.getUploadId());
        s3.completeMultipartUpload(new CompleteMultipartUploadRequest(bucketName, key, initiateMpuResult.getUploadId(), partETags));
      } catch (AmazonServiceException ase) {
        error = true;
        printException(ase);
        assertTrue("Expected a 400 status code but got " + ase.getStatusCode(), ase.getStatusCode() == 400);
        assertTrue("Expected InvalidArgument error code but got " + ase.getErrorCode(), ase.getErrorCode().equals("InvalidArgument"));
      } finally {
        assertTrue("Expected multipart upload to fail with 400 InvalidArgument error", error);
      }
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run invalidPartNumber");
    }
  }

  @Test
  public void mixKeysAndUploadIds() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - mixKeysAndUploadIds");
    try {
      File smallFile = new File("test.dat");
      final String key1 = eucaUUID();
      final String key2 = eucaUUID();

      // Inititate mpu
      print(account + ": Initiating multipart upload for object " + key1 + " in bucket " + bucketName);
      final InitiateMultipartUploadResult initiateMpuResult1 = s3.initiateMultipartUpload(new InitiateMultipartUploadRequest(bucketName, key1));
      cleanupTasks.add(new Runnable() {
        @Override
        public void run() {
          print(account + ": Aborting multipart upload for object " + key1 + ", upload ID " + initiateMpuResult1.getUploadId() + " in bucket "
              + bucketName);
          s3.abortMultipartUpload(new AbortMultipartUploadRequest(bucketName, key1, initiateMpuResult1.getUploadId()));
        }
      });

      print(account + ": Initiating multipart upload for object " + key2 + " in bucket " + bucketName);
      final InitiateMultipartUploadResult initiateMpuResult2 = s3.initiateMultipartUpload(new InitiateMultipartUploadRequest(bucketName, key2));
      cleanupTasks.add(new Runnable() {
        @Override
        public void run() {
          print(account + ": Aborting multipart upload for object " + key2 + ", upload ID " + initiateMpuResult2.getUploadId() + " in bucket "
              + bucketName);
          s3.abortMultipartUpload(new AbortMultipartUploadRequest(bucketName, key2, initiateMpuResult2.getUploadId()));
        }
      });

      // Try to upload a part with incorrect key-uploadID combination
      boolean error = false;
      try {
        print(account + ": Uploading part for object " + key1 + ", upload ID " + initiateMpuResult2.getUploadId() + ", part number 1");
        s3.uploadPart(new UploadPartRequest().withBucketName(bucketName).withKey(key1).withUploadId(initiateMpuResult2.getUploadId())
            .withPartNumber(1).withFile(smallFile));
      } catch (AmazonServiceException ase) {
        error = true;
        printException(ase);
        assertTrue("Expected a 404 status code but got " + ase.getStatusCode(), ase.getStatusCode() == 404);
        assertTrue("Expected NoSuchUpload error code but got " + ase.getErrorCode(), ase.getErrorCode().equals("NoSuchUpload"));
      } finally {
        assertTrue("Expected multipart upload to fail with 404 NoSuchUpload error", error);
      }

      // Try to abort upload with incorrect key-uploadID combination
      error = false;
      try {
        print(account + ": Aborting multipart upload for object " + key2 + ", upload ID " + initiateMpuResult1.getUploadId() + " in bucket "
            + bucketName);
        s3.abortMultipartUpload(new AbortMultipartUploadRequest(bucketName, key2, initiateMpuResult1.getUploadId()));
      } catch (AmazonServiceException ase) {
        error = true;
        printException(ase);
        assertTrue("Expected a 404 status code but got " + ase.getStatusCode(), ase.getStatusCode() == 404);
        assertTrue("Expected NoSuchUpload error code but got " + ase.getErrorCode(), ase.getErrorCode().equals("NoSuchUpload"));
      } finally {
        assertTrue("Expected multipart upload to fail with 404 NoSuchUpload error", error);
      }

      // Try to complete upload with incorrect key-uploadID combination
      error = false;
      try {
        print(account + ": Completing multipart upload for object " + key1 + ", upload ID " + initiateMpuResult1.getUploadId());
        s3.completeMultipartUpload(new CompleteMultipartUploadRequest(bucketName, key1, initiateMpuResult2.getUploadId(), new ArrayList<PartETag>()));
      } catch (AmazonServiceException ase) {
        error = true;
        printException(ase);
        assertTrue("Expected a 404 status code but got " + ase.getStatusCode(), ase.getStatusCode() == 404);
        assertTrue("Expected NoSuchUpload error code but got " + ase.getErrorCode(), ase.getErrorCode().equals("NoSuchUpload"));
      } finally {
        assertTrue("Expected multipart upload to fail with 404 NoSuchUpload error", error);
      }
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run mixKeysAndUploadIds");
    }
  }

  @Test
  public void getWithRange() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - getWithRange");
    try {
      final String key = eucaUUID();
      List<PartETag> partETags = Lists.newArrayList();
      long partSize = randomBytes.length;

      // Inititate mpu
      print(account + ": Initiating multipart upload for object " + key + " in bucket " + bucketName);
      final InitiateMultipartUploadResult initiateMpuResult = s3.initiateMultipartUpload(new InitiateMultipartUploadRequest(bucketName, key));

      // Upload a few parts
      for (int partNumber = 1; partNumber <= 4; partNumber++) {
        print(account + ": Uploading part of size " + partSize + " bytes for object " + key + ", upload ID " + initiateMpuResult.getUploadId()
            + ", part number " + partNumber);
        partETags.add(s3.uploadPart(
            new UploadPartRequest().withBucketName(bucketName).withKey(key).withUploadId(initiateMpuResult.getUploadId()).withPartNumber(partNumber)
                .withInputStream(new ByteArrayInputStream(randomBytes)).withPartSize(partSize)).getPartETag());
      }

      // Complete mpu
      print(account + ": Completing multipart upload for object " + key + ", upload ID " + initiateMpuResult.getUploadId());
      s3.completeMultipartUpload(new CompleteMultipartUploadRequest(bucketName, key, initiateMpuResult.getUploadId(), partETags));
      cleanupTasks.add(new Runnable() {
        @Override
        public void run() {
          print(account + ": Deleting object " + key + " from bucket " + bucketName);
          s3.deleteObject(bucketName, key);
        }
      });

      // Get the final object to verify
      final File fileToVerify = new File(eucaUUID());
      print(account + ": Downloading object " + key + " to file " + fileToVerify.getName());
      s3.getObject(new GetObjectRequest(bucketName, key), fileToVerify);
      cleanupTasks.add(new Runnable() {
        @Override
        public void run() {
          try {
            print(account + ": Deleting file " + fileToVerify.getName());
            fileToVerify.delete();
          } catch (Exception e) {
          }
        }
      });
      assertTrue("Expected objectsize to be " + (partSize * 4) + " bytes but got a file of size " + fileToVerify.length() + " bytes",
          fileToVerify.length() == (partSize * 4));

      // Verify get for first 100 bytes
      verifyGetWithRange(account, s3, bucketName, key, fileToVerify, 0, 100);

      // Verify get for first 100 bytes of second part
      verifyGetWithRange(account, s3, bucketName, key, fileToVerify, (int) partSize, 100);

      // Verify get for first 100 bytes of third part
      verifyGetWithRange(account, s3, bucketName, key, fileToVerify, (int) (partSize * 2), 100);

      // Verify get for first 100 bytes of third part
      verifyGetWithRange(account, s3, bucketName, key, fileToVerify, (int) (partSize * 3), 100);

      // Verify get for 100 bytes between first and second part
      verifyGetWithRange(account, s3, bucketName, key, fileToVerify, (int) (partSize - 58), 100);

      // Verify get for 100 bytes between second and third part
      verifyGetWithRange(account, s3, bucketName, key, fileToVerify, (int) ((2 * partSize) - 47), 100);

      // Verify get for last 100 bytes of first part
      verifyGetWithRange(account, s3, bucketName, key, fileToVerify, (int) (partSize - 100), 100);

      // Verify get for last 100 bytes of second part
      verifyGetWithRange(account, s3, bucketName, key, fileToVerify, (int) ((2 * partSize) - 100), 100);

      // Verify get for partSize bytes starting from the last 100 bytes of first part
      verifyGetWithRange(account, s3, bucketName, key, fileToVerify, (int) (partSize - 100), (int) partSize);

      // Verify get for two times the partSize bytes starting from the last 100 bytes of first part
      verifyGetWithRange(account, s3, bucketName, key, fileToVerify, (int) (partSize - 100), (int) (2 * partSize));

    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run getWithRange");
    }
  }

  private void verifyGetWithRange(String ownerName, AmazonS3 s3, String bucket, String key, File fileToVerify, int offset, int length)
      throws IOException, NoSuchAlgorithmException {
    BufferedInputStream bis = new BufferedInputStream(new FileInputStream(fileToVerify));
    S3Object s3Object = null;
    ByteArrayOutputStream baos = new ByteArrayOutputStream();
    try {
      byte[] sourceBuffer = new byte[length];
      bis.skip(offset);
      bis.read(sourceBuffer, 0, length);
      String sourceMd5 = BinaryUtils.toHex(Md5Utils.computeMD5Hash(sourceBuffer));

      print(ownerName + ": Getting object " + key + " with range " + offset + "-" + (offset + length - 1));
      s3Object = s3.getObject(new GetObjectRequest(bucket, key).withRange(offset, offset + length - 1));
      ObjectMetadata objectMetadata = s3Object.getObjectMetadata();

      assertTrue("Expected " + length + " bytes but got " + objectMetadata.getContentLength() + " bytes", objectMetadata.getContentLength() == length);

      byte[] readBuffer = new byte[1024 * 10];
      int bytesRead;
      while ((bytesRead = s3Object.getObjectContent().read(readBuffer)) > -1) {
        baos.write(readBuffer, 0, bytesRead);
      }
      byte[] getBuffer = baos.toByteArray();
      String getMd5 = BinaryUtils.toHex(Md5Utils.computeMD5Hash(getBuffer));

      assertTrue("Expected md5 to be " + sourceMd5 + " but got " + getMd5, sourceMd5.equals(getMd5));
      assertTrue("Mismatch in source and fetched data", Arrays.equals(sourceBuffer, getBuffer));
    } finally {
      bis.close();
      try {
        s3Object.getObjectContent().close();
      } catch (Exception e) {
      }
      baos.close();
      baos = null;
    }
  }

  @Test
  public void cannedACL() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - cannedACL");
    try {
      final String key = eucaUUID();
      List<PartETag> partETags = Lists.newArrayList();
      long partSize = randomBytes.length;

      // Inititate mpu with canned ACL
      print(account + ": Initiating multipart upload for object " + key + " in bucket " + bucketName);
      final InitiateMultipartUploadResult initiateMpuResult =
          s3.initiateMultipartUpload(new InitiateMultipartUploadRequest(bucketName, key).withCannedACL(CannedAccessControlList.AuthenticatedRead));

      // Upload a few parts
      for (int partNumber = 1; partNumber <= 2; partNumber++) {
        print(account + ": Uploading part of size " + partSize + " bytes for object " + key + ", upload ID " + initiateMpuResult.getUploadId()
            + ", part number " + partNumber);
        partETags.add(s3.uploadPart(
            new UploadPartRequest().withBucketName(bucketName).withKey(key).withUploadId(initiateMpuResult.getUploadId()).withPartNumber(partNumber)
                .withInputStream(new ByteArrayInputStream(randomBytes)).withPartSize(partSize)).getPartETag());
      }

      // Complete mpu
      print(account + ": Completing multipart upload for object " + key + ", upload ID " + initiateMpuResult.getUploadId());
      s3.completeMultipartUpload(new CompleteMultipartUploadRequest(bucketName, key, initiateMpuResult.getUploadId(), partETags));
      cleanupTasks.add(new Runnable() {
        @Override
        public void run() {
          print(account + ": Deleting object " + key + " from bucket " + bucketName);
          s3.deleteObject(bucketName, key);
        }
      });

      S3Utils.verifyObjectACL(s3, ownerName, bucketName, key, CannedAccessControlList.AuthenticatedRead, ownerId, ownerId);
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run cannedACL");
    }
  }

  @Test
  public void headerACL() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - headerACL");
    try {
      final String key = eucaUUID();
      List<PartETag> partETags = Lists.newArrayList();
      long partSize = randomBytes.length;

      Grant ownerGrant = new Grant(new CanonicalGrantee(ownerId), Permission.FullControl);
      AccessControlList acl = new AccessControlList();
      acl.getGrants().add(new Grant(GroupGrantee.LogDelivery, Permission.WriteAcp));

      // Inititate mpu with canned ACL
      print(account + ": Initiating multipart upload for object " + key + " in bucket " + bucketName);
      final InitiateMultipartUploadResult initiateMpuResult =
          s3.initiateMultipartUpload(new InitiateMultipartUploadRequest(bucketName, key).withAccessControlList(acl));

      // Upload a few parts
      for (int partNumber = 1; partNumber <= 2; partNumber++) {
        print(account + ": Uploading part of size " + partSize + " bytes for object " + key + ", upload ID " + initiateMpuResult.getUploadId()
            + ", part number " + partNumber);
        partETags.add(s3.uploadPart(
            new UploadPartRequest().withBucketName(bucketName).withKey(key).withUploadId(initiateMpuResult.getUploadId()).withPartNumber(partNumber)
                .withInputStream(new ByteArrayInputStream(randomBytes)).withPartSize(partSize)).getPartETag());
      }

      // Complete mpu
      print(account + ": Completing multipart upload for object " + key + ", upload ID " + initiateMpuResult.getUploadId());
      s3.completeMultipartUpload(new CompleteMultipartUploadRequest(bucketName, key, initiateMpuResult.getUploadId(), partETags));
      cleanupTasks.add(new Runnable() {
        @Override
        public void run() {
          print(account + ": Deleting object " + key + " from bucket " + bucketName);
          s3.deleteObject(bucketName, key);
        }
      });

      acl.getGrants().add(ownerGrant);
      S3Utils.verifyObjectACL(s3, ownerName, bucketName, key, acl, ownerId);
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run headerACL");
    }
  }

  @Test
  public void getMetadata() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - getMetadata");
    try {
      final String key = eucaUUID();
      List<PartETag> partETags = Lists.newArrayList();
      long partSize = randomBytes.length;

      ObjectMetadata objectMetadata = new ObjectMetadata();
      Map<String, String> userMetadataMap = new HashMap<String, String>();
      userMetadataMap.put("somerandomkey", "somerandomvalue");
      userMetadataMap.put("hello", "world");
      objectMetadata.setUserMetadata(userMetadataMap);

      // Inititate mpu with metadata
      print(account + ": Initiating multipart upload for object " + key + " in bucket " + bucketName);
      final InitiateMultipartUploadResult initiateMpuResult =
          s3.initiateMultipartUpload(new InitiateMultipartUploadRequest(bucketName, key).withObjectMetadata(objectMetadata));

      // Upload a few parts
      for (int partNumber = 1; partNumber <= 2; partNumber++) {
        print(account + ": Uploading part of size " + partSize + " bytes for object " + key + ", upload ID " + initiateMpuResult.getUploadId()
            + ", part number " + partNumber);
        partETags.add(s3.uploadPart(
            new UploadPartRequest().withBucketName(bucketName).withKey(key).withUploadId(initiateMpuResult.getUploadId()).withPartNumber(partNumber)
                .withInputStream(new ByteArrayInputStream(randomBytes)).withPartSize(partSize)).getPartETag());
      }

      // Complete mpu
      print(account + ": Completing multipart upload for object " + key + ", upload ID " + initiateMpuResult.getUploadId());
      s3.completeMultipartUpload(new CompleteMultipartUploadRequest(bucketName, key, initiateMpuResult.getUploadId(), partETags));
      cleanupTasks.add(new Runnable() {
        @Override
        public void run() {
          print(account + ": Deleting object " + key + " from bucket " + bucketName);
          s3.deleteObject(bucketName, key);
        }
      });

      // Get the metadata of the completed object and verify
      verifyUserMetadata(account, s3, bucketName, key, userMetadataMap);
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run getMetadata");
    }
  }

  private void verifyUserMetadata(String ownerName, AmazonS3 s3, String bucket, String key, Map<String, String> metadataMap) {
    print(ownerName + ": Getting metadata for object key=" + key + ", bucket=" + bucket);
    ObjectMetadata metadata = s3.getObjectMetadata(bucket, key);
    assertTrue("Invalid object metadata", metadata != null);
    assertTrue("Invalid content length. Expected non-zero length but got 0", metadata.getContentLength() != 0);
    assertTrue("Invalid ETag value", metadata.getETag() != null);
    assertTrue("Invalid last modified date", metadata.getLastModified() != null);
    if (metadataMap != null && !metadataMap.isEmpty()) {
      assertTrue("No user metadata found", metadata.getUserMetadata() != null || !metadata.getUserMetadata().isEmpty());
      assertTrue("Expected to find " + metadataMap.size() + " element(s) in the metadata but found " + metadata.getUserMetadata().size(),
          metadataMap.size() == metadata.getUserMetadata().size());
      for (Map.Entry<String, String> entry : metadataMap.entrySet()) {
        assertTrue("Metadata key " + entry.getKey() + " not found in response", metadata.getUserMetadata().containsKey(entry.getKey()));
        assertTrue(
            "Expected metadata value for key " + entry.getKey() + " to be " + entry.getValue() + " but got "
                + metadata.getUserMetadata().get(entry.getKey()), metadata.getUserMetadata().get(entry.getKey()).equals(entry.getValue()));
      }
    }
  }

  @Test
  public void copyObject() throws Exception {
    testInfo(this.getClass().getSimpleName() + " - copyObject");
    try {
      final String key = eucaUUID();
      final String copyKey = eucaUUID();
      List<PartETag> partETags = Lists.newArrayList();
      long partSize = randomBytes.length;

      // Inititate mpu
      print(account + ": Initiating multipart upload for object " + key + " in bucket " + bucketName);
      final InitiateMultipartUploadResult initiateMpuResult = s3.initiateMultipartUpload(new InitiateMultipartUploadRequest(bucketName, key));

      // Upload a few parts
      for (int partNumber = 1; partNumber <= 2; partNumber++) {
        print(account + ": Uploading part of size " + partSize + " bytes for object " + key + ", upload ID " + initiateMpuResult.getUploadId()
            + ", part number " + partNumber);
        partETags.add(s3.uploadPart(
            new UploadPartRequest().withBucketName(bucketName).withKey(key).withUploadId(initiateMpuResult.getUploadId()).withPartNumber(partNumber)
                .withInputStream(new ByteArrayInputStream(randomBytes)).withPartSize(partSize)).getPartETag());
      }

      // Complete mpu
      print(account + ": Completing multipart upload for object " + key + ", upload ID " + initiateMpuResult.getUploadId());
      CompleteMultipartUploadResult completeMpuResult =
          s3.completeMultipartUpload(new CompleteMultipartUploadRequest(bucketName, key, initiateMpuResult.getUploadId(), partETags));
      cleanupTasks.add(new Runnable() {
        @Override
        public void run() {
          print(account + ": Deleting object " + key + " from bucket " + bucketName);
          s3.deleteObject(bucketName, key);
        }
      });

      // Copy object
      print(account + ": Copying object " + copyKey + " from " + key);
      CopyObjectResult copyResult = s3.copyObject(bucketName, key, bucketName, copyKey);
      cleanupTasks.add(new Runnable() {
        @Override
        public void run() {
          print(account + ": Deleting object " + copyKey + " from bucket " + bucketName);
          s3.deleteObject(bucketName, copyKey);
        }
      });

      assertTrue("Expected copied object etag to be " + completeMpuResult.getETag() + " but got " + copyResult.getETag(), completeMpuResult.getETag()
          .equals(copyResult.getETag()));

      // Get the objects to verify
      final File originalFile = new File(eucaUUID());
      print(account + ": Downloading original object " + key + " to file " + originalFile.getName());
      ObjectMetadata om = s3.getObject(new GetObjectRequest(bucketName, key), originalFile);
      cleanupTasks.add(new Runnable() {
        @Override
        public void run() {
          try {
            print(account + ": Deleting file " + originalFile.getName());
            originalFile.delete();
          } catch (Exception e) {
          }
        }
      });
      assertTrue("Expected original objectsize to be " + (partSize * 2) + " bytes but got a file of size " + originalFile.length() + " bytes",
          originalFile.length() == (partSize * 2));

      final File copiedFile = new File(eucaUUID());
      print(account + ": Downloading copied object " + key + " to file " + copiedFile.getName());
      ObjectMetadata copyOm = s3.getObject(new GetObjectRequest(bucketName, copyKey), copiedFile);
      cleanupTasks.add(new Runnable() {
        @Override
        public void run() {
          try {
            print(account + ": Deleting file " + copiedFile.getName());
            copiedFile.delete();
          } catch (Exception e) {
          }
        }
      });
      assertTrue("Expected original objectsize to be " + (partSize * 2) + " bytes but got a file of size " + copiedFile.length() + " bytes",
          copiedFile.length() == (partSize * 2));

      assertTrue("Expected content lengths to match", om.getContentLength() == copyOm.getContentLength());
      assertTrue(
          "Expected content md5s to match",
          BinaryUtils.toHex(Md5Utils.computeMD5Hash(new FileInputStream(originalFile))).equals(
              BinaryUtils.toHex(Md5Utils.computeMD5Hash(new FileInputStream(copiedFile)))));
    } catch (AmazonServiceException ase) {
      printException(ase);
      assertThat(false, "Failed to run copyObject");
    }
  }
}
