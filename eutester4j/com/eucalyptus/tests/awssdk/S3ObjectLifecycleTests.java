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
import com.amazonaws.ClientConfiguration;
import com.amazonaws.auth.AWSCredentials;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.AmazonS3Client;
import com.amazonaws.services.s3.S3ClientOptions;
import com.amazonaws.services.s3.model.Bucket;
import com.amazonaws.services.s3.model.BucketLifecycleConfiguration;
import com.google.common.collect.Lists;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import static com.eucalyptus.tests.awssdk.Eutester4j.ACCESS_KEY;
import static com.eucalyptus.tests.awssdk.Eutester4j.S3_ENDPOINT;
import static com.eucalyptus.tests.awssdk.Eutester4j.SECRET_KEY;
import static com.eucalyptus.tests.awssdk.Eutester4j.assertThat;
import static com.eucalyptus.tests.awssdk.Eutester4j.eucaUUID;
import static com.eucalyptus.tests.awssdk.Eutester4j.initS3Client;
import static com.eucalyptus.tests.awssdk.Eutester4j.print;
import static com.eucalyptus.tests.awssdk.Eutester4j.s3;
import static com.eucalyptus.tests.awssdk.Eutester4j.testInfo;
import static org.testng.AssertJUnit.assertTrue;
import static org.testng.AssertJUnit.fail;

/**
 * <p>This class contains tests for object lifecycle configuration on S3 buckets.</p>
 *
 * @author Wes Wannemacher (wes.wannemacher@eucalyptus.com)
 *
 */
public class S3ObjectLifecycleTests {

    private static String bucketName = null;
    private static List<Runnable> cleanupTasks = null;

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
    public void lifecycleBasics() throws Exception {
        testInfo(this.getClass().getSimpleName() + " - lifecycleBasics");
        try {

            print("retrieving initial lifecycle configuration");
            BucketLifecycleConfiguration initial = s3.getBucketLifecycleConfiguration(bucketName);
            assertTrue("did not expect any data in initial lifecycle configuration",
                    initial == null || initial.getRules() == null || initial.getRules().size() == 0);

            print("creating a lifecycle configuration with only one rule: id => basicTest, prefix => foo");
            BucketLifecycleConfiguration lifecycle = new BucketLifecycleConfiguration();
            BucketLifecycleConfiguration.Rule lifecycleRule = new BucketLifecycleConfiguration.Rule()
                    .withId("basicTest")
                    .withPrefix("foo")
                    .withExpirationInDays(2)
                    .withStatus(BucketLifecycleConfiguration.ENABLED.toString());
            List<BucketLifecycleConfiguration.Rule> rules = Lists.newArrayList();
            rules.add(lifecycleRule);
            lifecycle.setRules(rules);

            print("setting lifecycle configuration on bucket " + bucketName);
            s3.setBucketLifecycleConfiguration(bucketName, lifecycle);

            print("attempting to retrieve lifecycle configuration for bucket " + bucketName);
            BucketLifecycleConfiguration retrieved = s3.getBucketLifecycleConfiguration(bucketName);

            print("comparing retrieved lifecycle configuration to what was sent");
            assertTrue("expected the same number of rules",
                    retrieved.getRules().size() == lifecycle.getRules().size());

            print("deleting lifecycle configuration");
            s3.deleteBucketLifecycleConfiguration(bucketName);
        }
        catch (AmazonServiceException ase) {
            printException(ase);
            assertThat(false, "Failed to run bucketBasics");
        }
    }

    @Test
    public void largeLifecycle() throws Exception {
        final int numRules = 1000; // at 934, request gets chunked

        testInfo(this.getClass().getSimpleName() + " - largeLifecycle");
        try {
            print("creating a lifecycle configuration with " + numRules + " rules");

            List<BucketLifecycleConfiguration.Rule> rules = Lists.newArrayList();
            for (int idx = 1; idx <= numRules; idx++) {
                BucketLifecycleConfiguration.Rule lifecycleRule = new BucketLifecycleConfiguration.Rule()
                        .withId("" + idx)
                        .withPrefix("" + idx)
                        .withExpirationInDays(idx)
                        .withStatus(BucketLifecycleConfiguration.ENABLED.toString());
                rules.add(lifecycleRule);
            }

            BucketLifecycleConfiguration lifecycle = new BucketLifecycleConfiguration();
            lifecycle.setRules(rules);

            print("setting lifecycle configuration on bucket " + bucketName);
            s3.setBucketLifecycleConfiguration(bucketName, lifecycle);

            print("attempting to retrieve lifecycle configuration for bucket " + bucketName);
            BucketLifecycleConfiguration retrieved = s3.getBucketLifecycleConfiguration(bucketName);

            print("comparing retrieved lifecycle configuration to what was sent");
            assertTrue("expected the same number of rules",
                    retrieved.getRules().size() == lifecycle.getRules().size());

            // the following is weird only because we started with 1 up above... an expiration of 0 (zero) days
            // doesn't make much sense, so we have to accomodate with a 1-based index
            boolean matches[] = new boolean[numRules + 1];
            matches[0] = true;
            for (int idx = 1; idx < matches.length; idx++) {
                matches[idx] = false;
            }
            for (BucketLifecycleConfiguration.Rule retrievedRule : retrieved.getRules()) {
                Integer ruleId = Integer.parseInt( retrievedRule.getId() );
                Integer prefix = Integer.parseInt( retrievedRule.getPrefix() );
                if ( retrievedRule.getStatus().equals(BucketLifecycleConfiguration.ENABLED.toString())
                        && retrievedRule.getExpirationInDays() == ruleId.intValue()
                        && ruleId.intValue() == prefix.intValue()) { // looks valid so far

                    if ( matches[ruleId.intValue()] ) { // shouldn't be already true?!
                        fail("found a duplicate rule in retrieved rules, rule id is " + ruleId.intValue());
                    }
                    else {
                        matches[ruleId.intValue()] = true;
                    }
                }
                else {
                    fail("found rule with id - " + retrievedRule.getId() +
                            ", prefix - " + retrievedRule.getPrefix() +
                            ", status - " + retrievedRule.getStatus() +
                            ", and expiration days - " + retrievedRule.getExpirationInDays());
                }
            }

            for (int idx = 0; idx < matches.length; idx++) {
                assertTrue("did not find an enabled rule with expiration days, prefix and id - " + idx,
                        matches[idx]);
            }

            print("deleting lifecycle configuration");
            s3.deleteBucketLifecycleConfiguration(bucketName);
        }
        catch (AmazonServiceException ase) {
            printException(ase);
            assertThat(false, "Failed to run largeLifecycle");
        }
    }

    @Test
    public void tooLargeLifecycle() throws Exception {
        final int numRules = 1001;

        testInfo(this.getClass().getSimpleName() + " - largeLifecycle");
        try {
            print("creating a lifecycle configuration with " + numRules + " rules");

            List<BucketLifecycleConfiguration.Rule> rules = Lists.newArrayList();
            for (int idx = 1; idx <= numRules; idx++) {
                BucketLifecycleConfiguration.Rule lifecycleRule = new BucketLifecycleConfiguration.Rule()
                        .withId("" + idx)
                        .withPrefix("" + idx)
                        .withExpirationInDays(idx)
                        .withStatus(BucketLifecycleConfiguration.ENABLED.toString());
                rules.add(lifecycleRule);
            }

            BucketLifecycleConfiguration lifecycle = new BucketLifecycleConfiguration();
            lifecycle.setRules(rules);

            boolean exceptionCaught = false;
            print("setting lifecycle configuration on bucket " + bucketName);
            try {
                s3.setBucketLifecycleConfiguration(bucketName, lifecycle);
            }
            catch (Exception ex) {
                exceptionCaught = true;
            }
            assertTrue("expected an exception to be thrown because the lifecycle was too large", exceptionCaught);

            print("attempting to retrieve lifecycle configuration for bucket " + bucketName);
            BucketLifecycleConfiguration retrieved = s3.getBucketLifecycleConfiguration(bucketName);

            print("checking that lifecycle is still empty");
            assertTrue("expected empty lifecycle",
                    retrieved == null || retrieved.getRules() == null || retrieved.getRules().size() == 0);

            print("deleting lifecycle configuration");
            s3.deleteBucketLifecycleConfiguration(bucketName);
        }
        catch (AmazonServiceException ase) {
            printException(ase);
            assertThat(false, "Failed to run largeLifecycle");
        }
    }

    @Test
    public void replaceLifecycle() throws Exception {
        final int numRules = 20;

        testInfo(this.getClass().getSimpleName() + " - largeLifecycle");
        try {
            print("creating a lifecycle configuration with " + numRules + " rules");

            List<BucketLifecycleConfiguration.Rule> rules = Lists.newArrayList();
            for (int idx = 1; idx <= numRules; idx++) {
                BucketLifecycleConfiguration.Rule lifecycleRule = new BucketLifecycleConfiguration.Rule()
                        .withId("" + idx)
                        .withPrefix("" + idx)
                        .withExpirationInDays(idx)
                        .withStatus(BucketLifecycleConfiguration.ENABLED.toString());
                rules.add(lifecycleRule);
            }

            BucketLifecycleConfiguration lifecycle = new BucketLifecycleConfiguration();
            lifecycle.setRules(rules);

            print("setting lifecycle configuration on bucket " + bucketName);
            s3.setBucketLifecycleConfiguration(bucketName, lifecycle);

            print("attempting to retrieve lifecycle configuration for bucket " + bucketName);
            BucketLifecycleConfiguration retrieved = s3.getBucketLifecycleConfiguration(bucketName);

            print("checking that lifecycle is correct");
            boolean matches[] = new boolean[numRules + 1];
            matches[0] = true;
            for (int idx = 1; idx < matches.length; idx++) {
                matches[idx] = false;
            }
            for (BucketLifecycleConfiguration.Rule retrievedRule : retrieved.getRules()) {
                Integer ruleId = Integer.parseInt( retrievedRule.getId() );
                Integer prefix = Integer.parseInt( retrievedRule.getPrefix() );
                if ( retrievedRule.getStatus().equals(BucketLifecycleConfiguration.ENABLED.toString())
                        && retrievedRule.getExpirationInDays() == ruleId.intValue()
                        && ruleId.intValue() == prefix.intValue()) { // looks valid so far

                    if ( matches[ruleId.intValue()] ) { // shouldn't be already true?!
                        fail("found a duplicate rule in retrieved rules, rule id is " + ruleId.intValue());
                    }
                    else {
                        matches[ruleId.intValue()] = true;
                    }
                }
                else {
                    fail("found rule with id - " + retrievedRule.getId() +
                            ", prefix - " + retrievedRule.getPrefix() +
                            ", status - " + retrievedRule.getStatus() +
                            ", and expiration days - " + retrievedRule.getExpirationInDays());
                }
            }

            for (int idx = 0; idx < matches.length; idx++) {
                assertTrue("did not find an enabled rule with expiration days, prefix and id - " + idx,
                        matches[idx]);
            }

            // now let's replace it with a new configuration
            rules = Lists.newArrayList();
            for (int idx = numRules; idx <= numRules + numRules; idx++) {
                BucketLifecycleConfiguration.Rule lifecycleRule = new BucketLifecycleConfiguration.Rule()
                        .withId("" + idx)
                        .withPrefix("" + idx)
                        .withExpirationInDays(idx)
                        .withStatus(BucketLifecycleConfiguration.ENABLED.toString());
                rules.add(lifecycleRule);
            }

            lifecycle = new BucketLifecycleConfiguration();
            lifecycle.setRules(rules);

            print("setting lifecycle configuration on bucket " + bucketName);
            s3.setBucketLifecycleConfiguration(bucketName, lifecycle);

            print("attempting to retrieve lifecycle configuration for bucket " + bucketName);
            retrieved = s3.getBucketLifecycleConfiguration(bucketName);
            print("checking that lifecycle is correct");
            matches = new boolean[numRules + 1];
            for (int idx = 0; idx < matches.length; idx++) {
                matches[idx] = false;
            }
            for (BucketLifecycleConfiguration.Rule retrievedRule : retrieved.getRules()) {
                Integer ruleId = Integer.parseInt( retrievedRule.getId() );
                Integer prefix = Integer.parseInt( retrievedRule.getPrefix() );
                if ( retrievedRule.getStatus().equals(BucketLifecycleConfiguration.ENABLED.toString())
                        && retrievedRule.getExpirationInDays() == ruleId.intValue()
                        && ruleId.intValue() == prefix.intValue()) { // looks valid so far

                    if ( matches[ruleId.intValue() - numRules] ) { // shouldn't be already true?!
                        fail("found a duplicate rule in retrieved rules, rule id is " + ruleId.intValue());
                    }
                    else {
                        matches[ruleId.intValue() - numRules] = true;
                    }
                }
                else {
                    fail("found rule with id - " + retrievedRule.getId() +
                            ", prefix - " + retrievedRule.getPrefix() +
                            ", status - " + retrievedRule.getStatus() +
                            ", and expiration days - " + retrievedRule.getExpirationInDays());
                }
            }

            print("deleting lifecycle configuration");
            s3.deleteBucketLifecycleConfiguration(bucketName);
        }
        catch (AmazonServiceException ase) {
            printException(ase);
            assertThat(false, "Failed to run largeLifecycle");
        }
    }

    @Test
    public void deletedBucket() throws Exception {
        final int numRules = 20;

        testInfo(this.getClass().getSimpleName() + " - largeLifecycle");
        try {
            print("creating a lifecycle configuration with " + numRules + " rules");

            List<BucketLifecycleConfiguration.Rule> rules = Lists.newArrayList();
            for (int idx = 1; idx <= numRules; idx++) {
                BucketLifecycleConfiguration.Rule lifecycleRule = new BucketLifecycleConfiguration.Rule()
                        .withId("" + idx)
                        .withPrefix("" + idx)
                        .withExpirationInDays(idx)
                        .withStatus(BucketLifecycleConfiguration.ENABLED.toString());
                rules.add(lifecycleRule);
            }

            BucketLifecycleConfiguration lifecycle = new BucketLifecycleConfiguration();
            lifecycle.setRules(rules);

            print("setting lifecycle configuration on bucket " + bucketName);
            s3.setBucketLifecycleConfiguration(bucketName, lifecycle);

            print("attempting to retrieve lifecycle configuration for bucket " + bucketName);
            BucketLifecycleConfiguration retrieved = s3.getBucketLifecycleConfiguration(bucketName);

            print("checking that lifecycle is correct");
            boolean matches[] = new boolean[numRules + 1];
            matches[0] = true;
            for (int idx = 1; idx < matches.length; idx++) {
                matches[idx] = false;
            }
            for (BucketLifecycleConfiguration.Rule retrievedRule : retrieved.getRules()) {
                Integer ruleId = Integer.parseInt( retrievedRule.getId() );
                Integer prefix = Integer.parseInt( retrievedRule.getPrefix() );
                if ( retrievedRule.getStatus().equals(BucketLifecycleConfiguration.ENABLED.toString())
                        && retrievedRule.getExpirationInDays() == ruleId.intValue()
                        && ruleId.intValue() == prefix.intValue()) { // looks valid so far

                    if ( matches[ruleId.intValue()] ) { // shouldn't be already true?!
                        fail("found a duplicate rule in retrieved rules, rule id is " + ruleId.intValue());
                    }
                    else {
                        matches[ruleId.intValue()] = true;
                    }
                }
                else {
                    fail("found rule with id - " + retrievedRule.getId() +
                            ", prefix - " + retrievedRule.getPrefix() +
                            ", status - " + retrievedRule.getStatus() +
                            ", and expiration days - " + retrievedRule.getExpirationInDays());
                }
            }

            for (int idx = 0; idx < matches.length; idx++) {
                assertTrue("did not find an enabled rule with expiration days, prefix and id - " + idx,
                        matches[idx]);
            }

            print("deleting bucket and re-creating");
            s3.deleteBucket(bucketName);

            s3.createBucket(bucketName);
            print("attempting to retrieve lifecycle configuration for bucket " + bucketName);
            retrieved = s3.getBucketLifecycleConfiguration(bucketName);
            assertTrue("did not expect a lifecycle to exist on the bucket since the bucket was deleted and recreated",
                    retrieved == null || retrieved.getRules() == null || retrieved.getRules().size() == 0);

        }
        catch (AmazonServiceException ase) {
            printException(ase);
            assertThat(false, "Failed to run largeLifecycle");
        }
    }

    private void printException(AmazonServiceException ase) {
        ase.printStackTrace();
        print("Caught Exception: " + ase.getMessage());
        print("HTTP Status Code: " + ase.getStatusCode());
        print("Amazon Error Code: " + ase.getErrorCode());
        print("Request ID: " + ase.getRequestId());
    }

}
