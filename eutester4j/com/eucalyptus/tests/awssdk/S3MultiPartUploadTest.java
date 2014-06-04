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

import java.io.File;
import java.net.URL;
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
import com.amazonaws.services.s3.model.AbortMultipartUploadRequest;
import com.amazonaws.services.s3.model.Bucket;
import com.amazonaws.services.s3.model.CompleteMultipartUploadRequest;
import com.amazonaws.services.s3.model.InitiateMultipartUploadRequest;
import com.amazonaws.services.s3.model.InitiateMultipartUploadResult;
import com.amazonaws.services.s3.model.PartETag;
import com.amazonaws.services.s3.model.UploadPartRequest;
import com.google.common.collect.Lists;

/**
 * These tests are basic Multipart Upload tests. The documentation for the SDK and MPU are available here -
 * http://docs.aws.amazon.com/AmazonS3/latest/dev/UsingMPDotJavaAPI.html
 * 
 * These tests currently leverage the Low-Level Java API only for more fine-grained control and debugging.
 * 
 */
public class S3MultiPartUploadTest {

	String bucketName = null;
	List<Runnable> cleanupTasks = null;
	private static AmazonS3 s3 = null;
	private static String account = null;

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

	private void printException(AmazonServiceException ase) {
		printPlainException(ase);
		print("HTTP Status Code: " + ase.getStatusCode());
		print("Amazon Error Code: " + ase.getErrorCode());
	}

	private void printPlainException(Exception e) {
		e.printStackTrace();
		print("Caught Exception: " + e.getMessage());
	}

	@Test
	public void basicMultiPartUpload() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - basicMultiPartUpload");
		try {
			final String key = eucaUUID();
			URL resPath = this.getClass().getClassLoader().getResource("zerofile");
			File fileToPut = new File(resPath.toURI());
			print("using multi-part-upload to create file with key - " + key + " in bucket - " + bucketName);
			List<PartETag> partETags = Lists.newArrayList();

			InitiateMultipartUploadRequest initReq = new InitiateMultipartUploadRequest(bucketName, key);
			InitiateMultipartUploadResult initResp = s3.initiateMultipartUpload(initReq);
			print("multi-part-upload initiated with upload id - " + initResp.getUploadId());
			long contentLength = fileToPut.length();
			long partSz = 5l * 1024l * 1024l; // 5mb
			try {
				long filePos = 0; // position ptr
				for (int partIdx = 1; filePos < contentLength; partIdx++) {
					partSz = Math.min(partSz, (contentLength - filePos));
					UploadPartRequest upr = new UploadPartRequest().withBucketName(bucketName).withKey(key).withUploadId(initResp.getUploadId())
							.withPartNumber(partIdx).withFileOffset(filePos).withFile(fileToPut).withPartSize(partSz);
					print("sending part number - " + partIdx + " with size - " + partSz + " in bytes");
					partETags.add(s3.uploadPart(upr).getPartETag());
					filePos += partSz;
					print("part number - " + partIdx + " sent successfully, file position is now - " + filePos);
				}
				print("completing multi-part-upload with id - " + initResp.getUploadId());
				CompleteMultipartUploadRequest completeReq = new CompleteMultipartUploadRequest(bucketName, key, initResp.getUploadId(), partETags);
				s3.completeMultipartUpload(completeReq);
				print("multi-part-upload with id - " + initResp.getUploadId() + " completed successfully");
				cleanupTasks.add(new Runnable() {
					@Override
					public void run() {
						print("Deleting object " + key);
						s3.deleteObject(bucketName, key);
					}
				});
			} catch (Exception e) {
				s3.abortMultipartUpload(new AbortMultipartUploadRequest(bucketName, key, initResp.getUploadId()));
				if (e instanceof AmazonServiceException) {
					throw e; // let outter handler handle
				} else {
					printPlainException(e);
					assertThat(false, "Failed to run basicMultiPartUpload");
				}
			}
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run basicMultiPartUpload");
		}
	}

	@Test
	public void multiPartUploadWithBadId() throws Exception {
		testInfo(this.getClass().getSimpleName() + " - multiPartUploadWithBadId");
		boolean tryingBadId = false;
		try {
			final String key = eucaUUID();
			URL resPath = this.getClass().getClassLoader().getResource("zerofile");
			File fileToPut = new File(resPath.toURI());
			print("using multi-part-upload to create file with key - " + key + " in bucket - " + bucketName);
			List<PartETag> partETags = Lists.newArrayList();

			InitiateMultipartUploadRequest initReq = new InitiateMultipartUploadRequest(bucketName, key);
			InitiateMultipartUploadResult initResp = s3.initiateMultipartUpload(initReq);
			print("multi-part-upload initiated with upload id - " + initResp.getUploadId());
			long contentLength = fileToPut.length();
			long partSz = 5l * 1024l * 1024l; // 5mb
			try {
				long filePos = 0; // position ptr
				String badId = eucaUUID();
				for (int partIdx = 1; filePos < contentLength; partIdx++) {
					partSz = Math.min(partSz, (contentLength - filePos));
					UploadPartRequest upr = new UploadPartRequest().withBucketName(bucketName).withKey(key).withUploadId(badId).withPartNumber(partIdx)
							.withFileOffset(filePos).withFile(fileToPut).withPartSize(partSz);
					print("sending part number - " + partIdx + " with size - " + partSz + " in bytes using id - " + badId);
					tryingBadId = true;
					partETags.add(s3.uploadPart(upr).getPartETag());
					filePos += partSz;
					print("part number - " + partIdx + " sent successfully, file position is now - " + filePos);
				}
				print("completing multi-part-upload with id - " + initResp.getUploadId());
				CompleteMultipartUploadRequest completeReq = new CompleteMultipartUploadRequest(bucketName, key, initResp.getUploadId(), partETags);
				s3.completeMultipartUpload(completeReq);
				print("multi-part-upload with id - " + initResp.getUploadId() + " completed successfully");
				cleanupTasks.add(new Runnable() {
					@Override
					public void run() {
						print("Deleting object " + key);
						s3.deleteObject(bucketName, key);
					}
				});
			} catch (Exception e) {
				s3.abortMultipartUpload(new AbortMultipartUploadRequest(bucketName, key, initResp.getUploadId()));
				if (e instanceof AmazonServiceException && tryingBadId) {
					assertThat(true, "expected an exception to be thrown because a bad upload ID was specified");
					print("an exception was received with message - " + e.getMessage());
				} else {
					printPlainException(e);
					assertThat(false, "Failed to run basicMultiPartUpload");
				}
			}
		} catch (AmazonServiceException ase) {
			printException(ase);
			assertThat(false, "Failed to run basicMultiPartUpload");
		}
	}
}
