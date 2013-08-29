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

import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.model.ObjectListing;
import com.amazonaws.services.s3.model.S3ObjectSummary;

import java.util.Collections;
import java.util.List;
import java.util.UUID;

import static com.eucalyptus.tests.awssdk.Eutester4j.assertThat;
import static com.eucalyptus.tests.awssdk.Eutester4j.print;

/*
 *
 */
public class WalrusTestSupport {

    protected static final String DEFAULT_BUCKET_PREFIX = "euca-test-";

    protected void cleanBucket(String bucket, AmazonS3 s3) {
        ObjectListing objListing = s3.listObjects(bucket);
        List<S3ObjectSummary> summaries = objListing.getObjectSummaries();
        for (S3ObjectSummary summary : summaries) {
            s3.deleteObject(bucket, summary.getKey());
        }
        s3.deleteBucket(bucket);
    }

    protected String generateBucketName() {
        return generateBucketName(DEFAULT_BUCKET_PREFIX);
    }

    protected String generateBucketName(final String prefix) {
        StringBuilder buf = new StringBuilder();
        buf.append(prefix);
        buf.append(UUID.randomUUID().toString());
        return buf.toString();
    }

    protected static void assertTrue(String message, boolean condition) {
        assertThat(condition, message);
    }

    protected static class CleanupTask implements Runnable {
        private String taskName;
        private boolean asThread;

        public CleanupTask(String taskName) {
            this(taskName, false);
        }

        public CleanupTask(String taskName, boolean asThread) {
            this.taskName = taskName;
            this.asThread = asThread;
        }

        @Override
        public void run() {
            // no-op by default
        }

        public String getTaskName() {
            return taskName;
        }

        public void setTaskName(String taskName) {
            this.taskName = taskName;
        }

        public boolean isAsThread() {
            return asThread;
        }

        public void setAsThread(boolean asThread) {
            this.asThread = asThread;
        }
    }

    protected void cleanup(List<CleanupTask> tasks) {
        print("cleaning up");
        if (tasks != null && tasks.size() > 0) {
            Collections.reverse(tasks);
            for (CleanupTask task : tasks) {
                print("executing clean up task - " + task.getTaskName() +
                        ", running as thread: " + (task.isAsThread() ? "yes" : "no" ));
                try {
                    if (task.isAsThread()) {
                        new Thread(task).start();
                    }
                    else {
                        task.run();
                    }
                }
                catch (Exception ex) {
                    print("error executing cleanup task named " + task.getTaskName());
                    print("exception message: " + ex.getMessage());
                }
            }
        }
    }

}
