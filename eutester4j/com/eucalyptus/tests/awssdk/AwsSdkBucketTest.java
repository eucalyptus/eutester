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

import com.amazonaws.AmazonServiceException;
import com.amazonaws.services.s3.model.AmazonS3Exception;
import com.amazonaws.services.s3.model.Bucket;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;
import static org.testng.AssertJUnit.assertTrue;


public class AwsSdkBucketTest {

    /**
     * create a bucket and then delete it
     *
     * @throws Exception
     */
    @Test
    public void basicBucketOperationsTest() throws Exception {
        getCloudInfo();

        final String bucketName = eucaUUID();

        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            /* Create bucket */
            try {
                Bucket bucket = s3.createBucket(bucketName);
                cleanupTasks.add(new Runnable() {
                    @Override
                    public void run() {
                        print("Deleting Bucket: " + bucketName);
                        s3.deleteBucket(bucketName);
                    }
                });
                assertTrue("bucket should have been created",
                        bucket != null
                );

                assertTrue("bucket name should have been named " + bucketName,
                        bucketName.equals(bucket.getName())
                );

            } catch (AmazonServiceException ase) {
                print("Error creating bucket: " + bucketName);
                ase.printStackTrace();
                print("Caught Exception: " + ase.getMessage());
                print("Reponse Status Code: " + ase.getStatusCode());
                print("Error Code: " + ase.getErrorCode());
                print("Request ID: " + ase.getRequestId());
                assertThat(false, "Failed to create bucket");
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

    /**
     * try to create a bucket that already exists with the same
     * AmazonS3Client instance. Against S3, the behavior is to
     * accept the call without errors.
     *
     * @throws Exception
     */
    @Test
    public void duplicateBucketNameSameClientInstanceTest() throws Exception {
        getCloudInfo();

        final String bucketName = eucaUUID();

        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {

            try {
                cleanupTasks.add(new Runnable() {
                    @Override
                    public void run() {
                        print("Deleting Bucket: " + bucketName);
                        s3.deleteBucket(bucketName);
                    }
                });

                Bucket created = s3.createBucket(bucketName);
                assertTrue("first bucket should have worked",
                        created != null
                );

                Bucket duplicate = s3.createBucket(bucketName);
                assertTrue("second bucket should also have worked",
                        duplicate != null
                );

            } catch (AmazonServiceException ase) {
                print("Error creating bucket: " + bucketName);
                ase.printStackTrace();
                print("Caught Exception: " + ase.getMessage());
                print("Reponse Status Code: " + ase.getStatusCode());
                print("Error Code: " + ase.getErrorCode());
                print("Request ID: " + ase.getRequestId());
                assertThat(false, "Failed to create bucket");
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

    @Test(expectedExceptions = AmazonS3Exception.class)
    public void existingBucketNameTest() throws Exception {
        getCloudInfo();

        final String bucketName = eucaUUID();

        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting Bucket: " + bucketName);
                    s3.deleteBucket(bucketName);
                }
            });

            s3.createBucket(bucketName);
            s3.createBucket(bucketName);

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

    /**
     * according to the AWS SDK docs, the following constraints apply to bucket names -
     * - Bucket names should not contain underscores
     * - Bucket names should be between 3 and 63 characters long
     * - Bucket names should not end with a dash
     * - Bucket names cannot contain adjacent periods
     * - Bucket names cannot contain dashes next to periods (e.g., "my-.bucket.com" and "my.-bucket" are invalid)
     * - Bucket names cannot contain uppercase characters
     * - Bucket names cannot be IP addresses
     *
     * @throws Exception
     */
    @Test(expectedExceptions = {AmazonS3Exception.class, IllegalArgumentException.class})
    public void badNamesTest() throws Exception {
        getCloudInfo();
        String testBucketName = eucaUUID() + "-";

        String withUnderscores = testBucketName.replace("-", "_");
        s3.createBucket(withUnderscores);

        String tooLong = new String(testBucketName);
        while (tooLong.length() < 63) {
            tooLong = tooLong + "-" + tooLong;
        }
        s3.createBucket(tooLong);

        String endsWithDash = testBucketName + "-";
        s3.createBucket(endsWithDash);

        String adjacentPeriods = testBucketName.replace("-", "..");
        s3.createBucket(adjacentPeriods);

        String periodNextToDash = testBucketName.replaceFirst("-", "-.");
        s3.createBucket(periodNextToDash);

        String dashNextToPeriod = testBucketName.replaceFirst("-", ".-");
        s3.createBucket(dashNextToPeriod);

        String upperCased = testBucketName.toUpperCase();
        s3.createBucket(upperCased);

        s3.createBucket("10.0.0.1");
    }


}
