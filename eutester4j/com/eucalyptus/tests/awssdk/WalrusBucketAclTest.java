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

import com.amazonaws.services.s3.model.AccessControlList;
import com.amazonaws.services.s3.model.CannedAccessControlList;
import com.amazonaws.services.s3.model.CanonicalGrantee;
import com.amazonaws.services.s3.model.EmailAddressGrantee;
import com.amazonaws.services.s3.model.Grant;
import com.amazonaws.services.s3.model.GroupGrantee;
import com.amazonaws.services.s3.model.Owner;
import com.amazonaws.services.s3.model.Permission;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.List;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

/**
 *
 */
public class WalrusBucketAclTest extends WalrusTestSupport {

    @Test
    public void basicGetBucketAclTest() throws Exception {

        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        List<CleanupTask> cleanupTasks = new ArrayList<>();

        try {
            final String testBucketName = generateBucketName();
            print("creating bucket with name - " + testBucketName);
            s3.createBucket(testBucketName);

            cleanupTasks.add( new CleanupTask("delete-bucket") {
                @Override
                public void run() {
                    cleanBucket(testBucketName, s3);
                }
            } );

            print("retrieving acl for bucket");
            AccessControlList acl = s3.getBucketAcl(testBucketName);

            assertTrue("expected to get an ACL for the bucket", acl != null);

            print("checking acl contents");
            Grant grant = (Grant) acl.getGrants().toArray()[0];
            Owner owner = acl.getOwner();

            String firstGrantId = grant.getGrantee().getIdentifier();
            String ownerId = owner.getId();
            assertTrue("expected first grant to be the owner",
                    firstGrantId.equals(ownerId));

            String permName = grant.getPermission().name();
            String permString = grant.getPermission().toString();
            String permHdrName = grant.getPermission().getHeaderName();
            assertTrue("expected permission name to be FullControl but was " + permName,
                    "FullControl".equals(permName));
            assertTrue("expected permission string to be FULL_CONTROL but was " + permString,
                    "FULL_CONTROL".equals(permString));
            assertTrue("expected header name to be x-amz-grant-full-control but was " + permHdrName,
                    "x-amz-grant-full-control".equals(permHdrName));

        }
        finally {
            cleanup(cleanupTasks);
        }


    }

    @Test
    public void addedAclGetBucketAclTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        List<CleanupTask> cleanupTasks = new ArrayList<>();

        try {
            final String testBucketName = generateBucketName();
            print("creating bucket with name - " + testBucketName);
            s3.createBucket(testBucketName);

            cleanupTasks.add( new CleanupTask("delete-bucket") {
                @Override
                public void run() {
                    cleanBucket(testBucketName, s3);
                }
            } );

            print("pulling down bucket acl");
            AccessControlList acl = s3.getBucketAcl(testBucketName);
            print("adding canonical grantee with read permission to retrieved acl");
            CanonicalGrantee grantee = new CanonicalGrantee(acl.getOwner().getId());
            grantee.setDisplayName(acl.getOwner().getDisplayName());
            acl.grantPermission(grantee, Permission.Read);

            print("setting bucket acl with modified retrieved acl");
            s3.setBucketAcl(testBucketName, acl);
            print("re-retrieving bucket acl");
            AccessControlList updatedAcl = s3.getBucketAcl(testBucketName);

            boolean foundOwnerAcl = false;
            boolean foundAddedAcl = false;
            print("looping over grants in acl");
            for (Grant grant : updatedAcl.getGrants()) {

                String permString = grant.getPermission().toString();
                if ("READ".equals(permString)) {
                    print("checking read grant to make sure it matches expectations");
                    foundAddedAcl = true;

                    String permName = grant.getPermission().name();
                    String permHdrName = grant.getPermission().getHeaderName();
                    assertTrue("expected permission name to be Read but was " + permName,
                            "Read".equals(permName));
                    assertTrue("expected permission string to be READ but was " + permString,
                            "READ".equals(permString));
                    assertTrue("expected header name to be x-amz-grant-read but was " + permHdrName,
                            "x-amz-grant-read".equals(permHdrName));

                }
                else if ("FULL_CONTROL".equals(permString)) {
                    print("checking full control grant to make sure it matches expectations");
                    foundOwnerAcl = true;

                    String permName = grant.getPermission().name();
                    String permHdrName = grant.getPermission().getHeaderName();
                    assertTrue("expected permission name to be FullControl but was " + permName,
                            "FullControl".equals(permName));
                    assertTrue("expected permission string to be FULL_CONTROL but was " + permString,
                            "FULL_CONTROL".equals(permString));
                    assertTrue("expected header name to be x-amz-grant-full-control but was " + permHdrName,
                            "x-amz-grant-full-control".equals(permHdrName));

                    assertTrue("expected acl to be for the owner",
                            updatedAcl.getOwner().getId().equals(grant.getGrantee().getIdentifier()));
                }
            }

            assertTrue("expected to find added ACL permission in the grants", foundAddedAcl);
            assertTrue("expected to find owner's full control ACL in the grants", foundOwnerAcl);

        }
        finally {
            cleanup(cleanupTasks);
        }

    }

    /* this test will fail until dev/wwannemacher/EUCA-5512 is merged
    private static final String ALT_ACCOUNT_EMAIL = "someadminuser@eucalyptus.com";
    @Test
    public void addedAclByEmailAddressGetBucketAclTest() throws Exception {

        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        List<CleanupTask> cleanupTasks = new ArrayList<>();

        try {
            final String testBucketName = generateBucketName();
            print("creating bucket with name - " + testBucketName);
            s3.createBucket(testBucketName);

            cleanupTasks.add( new CleanupTask("delete-bucket") {
                @Override
                public void run() {
                    cleanBucket(testBucketName, s3);
                }
            } );

            print("retrieving bucket acl for bucket - " + testBucketName);
            AccessControlList acl = s3.getBucketAcl(testBucketName);

            print("adding an email address grantee to acl with address - " + ALT_ACCOUNT_EMAIL);
            EmailAddressGrantee grantee = new EmailAddressGrantee(ALT_ACCOUNT_EMAIL);
            acl.grantPermission(grantee, Permission.Read);

            print("updating acl for bucket - " + testBucketName);
            s3.setBucketAcl(testBucketName, acl);
            AccessControlList updatedAcl = s3.getBucketAcl(testBucketName);

            boolean foundOwnerAcl = false;
            boolean foundAddedAcl = false;
            for (Grant grant : updatedAcl.getGrants()) {

                String permString = grant.getPermission().toString();
                if ("READ".equals(permString)) {
                    print("checking read grant to make sure it matches expectations");
                    foundAddedAcl = true;

                    String permName = grant.getPermission().name();
                    String permHdrName = grant.getPermission().getHeaderName();
                    assertTrue("expected permission name to be Read but was " + permName,
                            "Read".equals(permName));
                    assertTrue("expected permission string to be READ but was " + permString,
                            "READ".equals(permString));
                    assertTrue("expected header name to be x-amz-grant-read but was " + permHdrName,
                            "x-amz-grant-read".equals(permHdrName));

                }
                else if ("FULL_CONTROL".equals(permString)) {
                    print("checking full control grant to make sure it matches expectations");
                    foundOwnerAcl = true;

                    String permName = grant.getPermission().name();
                    String permHdrName = grant.getPermission().getHeaderName();
                    assertTrue("expected permission name to be FullControl but was " + permName,
                            "FullControl".equals(permName));
                    assertTrue("expected permission string to be FULL_CONTROL but was " + permString,
                            "FULL_CONTROL".equals(permString));
                    assertTrue("expected header name to be x-amz-grant-full-control but was " + permHdrName,
                            "x-amz-grant-full-control".equals(permHdrName));

                    assertTrue("expected acl to be for the owner",
                            updatedAcl.getOwner().getId().equals(grant.getGrantee().getIdentifier()));
                }
            }

            assertTrue("expected to find added ACL permission in the grants", foundAddedAcl);
            assertTrue("expected to find owner's full control ACL in the grants", foundOwnerAcl);

        }
        finally {
            cleanup(cleanupTasks);
        }

    }
    */


    @Test
    public void addedGroupAclGetBucketAclTest() throws Exception {

        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        List<CleanupTask> cleanupTasks = new ArrayList<>();

        try {
            final String testBucketName = generateBucketName();
            print("creating bucket named - " + testBucketName);
            s3.createBucket(testBucketName);

            cleanupTasks.add( new CleanupTask("delete-bucket") {
                @Override
                public void run() {
                    cleanBucket(testBucketName, s3);
                }
            } );

            print("getting acl for bucket named - " + testBucketName);
            AccessControlList acl = s3.getBucketAcl(testBucketName);

            print("adding authenticated-users canned acl");
            acl.grantPermission(GroupGrantee.AuthenticatedUsers, Permission.Read);

            print("setting bucket acl with updated acl");
            s3.setBucketAcl(testBucketName, acl);

            print("re-retrieving bucket acl for bucket - " + testBucketName);
            AccessControlList updatedAcl = s3.getBucketAcl(testBucketName);

            boolean foundOwnerAcl = false;
            boolean foundAddedAcl = false;
            print("looping over grants in acl");
            for (Grant grant : updatedAcl.getGrants()) {

                String permString = grant.getPermission().toString();
                if ("READ".equals(permString)) {
                    print("checking read grant to make sure it matches expectations");
                    foundAddedAcl = true;

                    String permName = grant.getPermission().name();
                    String permHdrName = grant.getPermission().getHeaderName();
                    assertTrue("expected permission name to be Read but was " + permName,
                            "Read".equals(permName));
                    assertTrue("expected permission string to be READ but was " + permString,
                            "READ".equals(permString));
                    assertTrue("expected header name to be x-amz-grant-read but was " + permHdrName,
                            "x-amz-grant-read".equals(permHdrName));

                    String granteeId = grant.getGrantee().getIdentifier();
                    String granteeTypeId = grant.getGrantee().getTypeIdentifier();
                    assertTrue("expected the type to be uri, but was " + granteeTypeId,
                            "uri".equals(granteeTypeId));
                    assertTrue("expected the id to be http://acs.amazonaws.com/groups/global/AuthenticatedUsers, but was " + granteeId,
                            "http://acs.amazonaws.com/groups/global/AuthenticatedUsers".equals(granteeId));

                }
                else if ("FULL_CONTROL".equals(permString)) {
                    print("checking full control grant to make sure it matches expectations");
                    foundOwnerAcl = true;

                    String permName = grant.getPermission().name();
                    String permHdrName = grant.getPermission().getHeaderName();
                    assertTrue("expected permission name to be FullControl but was " + permName,
                            "FullControl".equals(permName));
                    assertTrue("expected permission string to be FULL_CONTROL but was " + permString,
                            "FULL_CONTROL".equals(permString));
                    assertTrue("expected header name to be x-amz-grant-full-control but was " + permHdrName,
                            "x-amz-grant-full-control".equals(permHdrName));

                    assertTrue("expected acl to be for the owner",
                            updatedAcl.getOwner().getId().equals(grant.getGrantee().getIdentifier()));
                }
            }

            assertTrue("expected to find added ACL permission in the grants", foundAddedAcl);
            assertTrue("expected to find owner's full control ACL in the grants", foundOwnerAcl);


        }
        finally {
            cleanup(cleanupTasks);
        }

    }

    @Test
    public void setGroupAclGetBucketAclTest() throws Exception {

        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        List<CleanupTask> cleanupTasks = new ArrayList<>();

        try {
            final String testBucketName = generateBucketName();
            print("creating bucket named - " + testBucketName);
            s3.createBucket(testBucketName);

            cleanupTasks.add( new CleanupTask("delete-bucket") {
                @Override
                public void run() {
                    cleanBucket(testBucketName, s3);
                }
            } );

            print("creating acl with existing owner as owner and adding read permission for authenticated-users as a grant");
            AccessControlList acl = new AccessControlList();
            acl.setOwner(s3.getS3AccountOwner());
            acl.grantPermission(GroupGrantee.AuthenticatedUsers, Permission.Read);

            print("setting bucket acl with updated acl");
            s3.setBucketAcl(testBucketName, acl);

            print("re-retrieving bucket acl for bucket - " + testBucketName);
            AccessControlList updatedAcl = s3.getBucketAcl(testBucketName);

            assertTrue("did not expect to find more than one grant on acl, but found " + updatedAcl.getGrants().size(),
                    1 == updatedAcl.getGrants().size());

            boolean foundAddedAcl = false;
            print("looping over grants in acl");
            for (Grant grant : updatedAcl.getGrants()) {

                String permString = grant.getPermission().toString();
                if ("READ".equals(permString)) {
                    print("checking read grant to make sure it matches expectations");
                    foundAddedAcl = true;

                    String permName = grant.getPermission().name();
                    String permHdrName = grant.getPermission().getHeaderName();
                    assertTrue("expected permission name to be Read but was " + permName,
                            "Read".equals(permName));
                    assertTrue("expected permission string to be READ but was " + permString,
                            "READ".equals(permString));
                    assertTrue("expected header name to be x-amz-grant-read but was " + permHdrName,
                            "x-amz-grant-read".equals(permHdrName));

                    String granteeId = grant.getGrantee().getIdentifier();
                    String granteeTypeId = grant.getGrantee().getTypeIdentifier();
                    assertTrue("expected the type to be uri, but was " + granteeTypeId,
                            "uri".equals(granteeTypeId));
                    assertTrue("expected the id to be http://acs.amazonaws.com/groups/global/AuthenticatedUsers, but was " + granteeId,
                            "http://acs.amazonaws.com/groups/global/AuthenticatedUsers".equals(granteeId));

                }
            }

            assertTrue("expected to find added ACL permission in the grants", foundAddedAcl);

        }
        finally {
            cleanup(cleanupTasks);
        }

    }

    @Test
    public void authenticatedReadCannedAclGetBucketAclTest() throws Exception {

        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        List<CleanupTask> cleanupTasks = new ArrayList<>();

        try {
            final String testBucketName = generateBucketName();
            print("creating bucket named - " + testBucketName);
            s3.createBucket(testBucketName);

            cleanupTasks.add( new CleanupTask("delete-bucket") {
                @Override
                public void run() {
                    cleanBucket(testBucketName, s3);
                }
            } );

            print("setting authenticated-read canned acl on bucket named - " + testBucketName);
            s3.setBucketAcl(testBucketName, CannedAccessControlList.AuthenticatedRead);

            print("re-retrieving bucket acl for bucket - " + testBucketName);
            AccessControlList updatedAcl = s3.getBucketAcl(testBucketName);

            boolean foundOwnerAcl = false;
            boolean foundCannedAcl = false;
            print("looping over grants in acl");
            for (Grant grant : updatedAcl.getGrants()) {
                String permString = grant.getPermission().toString();
                if ("READ".equals(permString)) {
                    print("checking read grant to make sure it matches expectations");
                    foundCannedAcl = true;

                    String permName = grant.getPermission().name();
                    String permHdrName = grant.getPermission().getHeaderName();
                    assertTrue("expected permission name to be Read but was " + permName,
                            "Read".equals(permName));
                    assertTrue("expected permission string to be READ but was " + permString,
                            "READ".equals(permString));
                    assertTrue("expected header name to be x-amz-grant-read but was " + permHdrName,
                            "x-amz-grant-read".equals(permHdrName));

                    String granteeId = grant.getGrantee().getIdentifier();
                    String granteeTypeId = grant.getGrantee().getTypeIdentifier();
                    assertTrue("expected the type to be uri, but was " + granteeTypeId,
                            "uri".equals(granteeTypeId));
                    assertTrue("expected the id to be http://acs.amazonaws.com/groups/global/AuthenticatedUsers, but was " + granteeId,
                            "http://acs.amazonaws.com/groups/global/AuthenticatedUsers".equals(granteeId));

                }
                else if ("FULL_CONTROL".equals(permString)) {
                    print("checking full control grant to make sure it matches expectations");
                    foundOwnerAcl = true;

                    String permName = grant.getPermission().name();
                    String permHdrName = grant.getPermission().getHeaderName();
                    assertTrue("expected permission name to be FullControl but was " + permName,
                            "FullControl".equals(permName));
                    assertTrue("expected permission string to be FULL_CONTROL but was " + permString,
                            "FULL_CONTROL".equals(permString));
                    assertTrue("expected header name to be x-amz-grant-full-control but was " + permHdrName,
                            "x-amz-grant-full-control".equals(permHdrName));

                    assertTrue("expected acl to be for the owner",
                            updatedAcl.getOwner().getId().equals(grant.getGrantee().getIdentifier()));
                }
            }

            assertTrue("expected to find canned ACL permission in the grants", foundCannedAcl);
            assertTrue("expected to find owner's full control ACL in the grants", foundOwnerAcl);

        }
        finally {
            cleanup(cleanupTasks);
        }

    }


    @Test
    public void privateCannedAclGetBucketAclTest() throws Exception {

        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        List<CleanupTask> cleanupTasks = new ArrayList<>();

        try {
            final String testBucketName = generateBucketName();
            print("creating bucket named - " + testBucketName);
            s3.createBucket(testBucketName);

            cleanupTasks.add( new CleanupTask("delete-bucket") {
                @Override
                public void run() {
                    cleanBucket(testBucketName, s3);
                }
            } );

            print("setting private canned acl on bucket named - " + testBucketName);
            s3.setBucketAcl(testBucketName, CannedAccessControlList.Private);

            print("re-retrieving bucket acl for bucket - " + testBucketName);
            AccessControlList updatedAcl = s3.getBucketAcl(testBucketName);

            boolean foundOwnerAcl = false;
            print("looping over grants in acl");
            for (Grant grant : updatedAcl.getGrants()) {
                String permString = grant.getPermission().toString();
                if ("FULL_CONTROL".equals(permString)) {
                    print("checking full control grant to make sure it matches expectations");
                    foundOwnerAcl = true;

                    String permName = grant.getPermission().name();
                    String permHdrName = grant.getPermission().getHeaderName();
                    assertTrue("expected permission name to be FullControl but was " + permName,
                            "FullControl".equals(permName));
                    assertTrue("expected permission string to be FULL_CONTROL but was " + permString,
                            "FULL_CONTROL".equals(permString));
                    assertTrue("expected header name to be x-amz-grant-full-control but was " + permHdrName,
                            "x-amz-grant-full-control".equals(permHdrName));

                    assertTrue("expected acl to be for the owner",
                            updatedAcl.getOwner().getId().equals(grant.getGrantee().getIdentifier()));
                }
            }

            assertTrue("expected to find owner's full control ACL in the grants", foundOwnerAcl);

        }
        finally {
            cleanup(cleanupTasks);
        }

    }

    @Test
    public void publicReadCannedAclGetBucketAclTest() throws Exception {

        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        List<CleanupTask> cleanupTasks = new ArrayList<>();

        try {
            final String testBucketName = generateBucketName();
            print("creating bucket named - " + testBucketName);
            s3.createBucket(testBucketName);

            cleanupTasks.add( new CleanupTask("delete-bucket") {
                @Override
                public void run() {
                    cleanBucket(testBucketName, s3);
                }
            } );

            print("setting public-read canned acl on bucket named - " + testBucketName);
            s3.setBucketAcl(testBucketName, CannedAccessControlList.PublicRead);

            print("re-retrieving bucket acl for bucket - " + testBucketName);
            AccessControlList updatedAcl = s3.getBucketAcl(testBucketName);

            boolean foundOwnerAcl = false;
            boolean foundCannedAcl = false;
            print("looping over grants in acl");
            for (Grant grant : updatedAcl.getGrants()) {
                String permString = grant.getPermission().toString();
                if ("READ".equals(permString)) {
                    print("checking read grant to make sure it matches expectations");
                    foundCannedAcl = true;

                    String permName = grant.getPermission().name();
                    String permHdrName = grant.getPermission().getHeaderName();
                    assertTrue("expected permission name to be Read but was " + permName,
                            "Read".equals(permName));
                    assertTrue("expected permission string to be READ but was " + permString,
                            "READ".equals(permString));
                    assertTrue("expected header name to be x-amz-grant-read but was " + permHdrName,
                            "x-amz-grant-read".equals(permHdrName));

                    String granteeId = grant.getGrantee().getIdentifier();
                    String granteeTypeId = grant.getGrantee().getTypeIdentifier();
                    assertTrue("expected the type to be uri, but was " + granteeTypeId,
                            "uri".equals(granteeTypeId));
                    assertTrue("expected the id to be http://acs.amazonaws.com/groups/global/AllUsers, but was " + granteeId,
                            "http://acs.amazonaws.com/groups/global/AllUsers".equals(granteeId));

                }
                else if ("FULL_CONTROL".equals(permString)) {
                    print("checking full control grant to make sure it matches expectations");
                    foundOwnerAcl = true;

                    String permName = grant.getPermission().name();
                    String permHdrName = grant.getPermission().getHeaderName();
                    assertTrue("expected permission name to be FullControl but was " + permName,
                            "FullControl".equals(permName));
                    assertTrue("expected permission string to be FULL_CONTROL but was " + permString,
                            "FULL_CONTROL".equals(permString));
                    assertTrue("expected header name to be x-amz-grant-full-control but was " + permHdrName,
                            "x-amz-grant-full-control".equals(permHdrName));

                    assertTrue("expected acl to be for the owner",
                            updatedAcl.getOwner().getId().equals(grant.getGrantee().getIdentifier()));
                }
            }

            assertTrue("expected to find canned ACL permission in the grants", foundCannedAcl);
            assertTrue("expected to find owner's full control ACL in the grants", foundOwnerAcl);

        }
        finally {
            cleanup(cleanupTasks);
        }

    }

    @Test
    public void publicReadWriteCannedAclGetBucketAclTest() throws Exception {

        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        List<CleanupTask> cleanupTasks = new ArrayList<>();

        try {
            final String testBucketName = generateBucketName();
            print("creating bucket named - " + testBucketName);
            s3.createBucket(testBucketName);

            cleanupTasks.add( new CleanupTask("delete-bucket") {
                @Override
                public void run() {
                    cleanBucket(testBucketName, s3);
                }
            } );

            print("setting public-readwrite canned acl on bucket named - " + testBucketName);
            s3.setBucketAcl(testBucketName, CannedAccessControlList.PublicReadWrite);

            print("re-retrieving bucket acl for bucket - " + testBucketName);
            AccessControlList updatedAcl = s3.getBucketAcl(testBucketName);

            boolean foundOwnerAcl = false;
            boolean foundCannedAclForRead = false;
            boolean foundCannedAclForWrite = false;
            print("looping over grants in acl");
            for (Grant grant : updatedAcl.getGrants()) {
                String permString = grant.getPermission().toString();
                if ("READ".equals(permString)) {
                    print("checking read grant to make sure it matches expectations");
                    foundCannedAclForRead = true;

                    String permName = grant.getPermission().name();
                    String permHdrName = grant.getPermission().getHeaderName();
                    assertTrue("expected permission name to be Read but was " + permName,
                            "Read".equals(permName));
                    assertTrue("expected permission string to be READ but was " + permString,
                            "READ".equals(permString));
                    assertTrue("expected header name to be x-amz-grant-read but was " + permHdrName,
                            "x-amz-grant-read".equals(permHdrName));

                    String granteeId = grant.getGrantee().getIdentifier();
                    String granteeTypeId = grant.getGrantee().getTypeIdentifier();
                    assertTrue("expected the type to be uri, but was " + granteeTypeId,
                            "uri".equals(granteeTypeId));
                    assertTrue("expected the id to be http://acs.amazonaws.com/groups/global/AllUsers, but was " + granteeId,
                            "http://acs.amazonaws.com/groups/global/AllUsers".equals(granteeId));

                }
                else if ("WRITE".equals(permString)) {
                    print("checking write grant to make sure it matches expectations");
                    foundCannedAclForWrite = true;

                    String permName = grant.getPermission().name();
                    String permHdrName = grant.getPermission().getHeaderName();
                    assertTrue("expected permission name to be Write but was " + permName,
                            "Write".equals(permName));
                    assertTrue("expected permission string to be WRITE but was " + permString,
                            "WRITE".equals(permString));
                    assertTrue("expected header name to be x-amz-grant-write but was " + permHdrName,
                            "x-amz-grant-write".equals(permHdrName));

                    String granteeId = grant.getGrantee().getIdentifier();
                    String granteeTypeId = grant.getGrantee().getTypeIdentifier();
                    assertTrue("expected the type to be uri, but was " + granteeTypeId,
                            "uri".equals(granteeTypeId));
                    assertTrue("expected the id to be http://acs.amazonaws.com/groups/global/AllUsers, but was " + granteeId,
                            "http://acs.amazonaws.com/groups/global/AllUsers".equals(granteeId));

                }
                else if ("FULL_CONTROL".equals(permString)) {
                    print("checking full control grant to make sure it matches expectations");
                    foundOwnerAcl = true;

                    String permName = grant.getPermission().name();
                    String permHdrName = grant.getPermission().getHeaderName();
                    assertTrue("expected permission name to be FullControl but was " + permName,
                            "FullControl".equals(permName));
                    assertTrue("expected permission string to be FULL_CONTROL but was " + permString,
                            "FULL_CONTROL".equals(permString));
                    assertTrue("expected header name to be x-amz-grant-full-control but was " + permHdrName,
                            "x-amz-grant-full-control".equals(permHdrName));

                    assertTrue("expected acl to be for the owner",
                            updatedAcl.getOwner().getId().equals(grant.getGrantee().getIdentifier()));
                }
            }

            assertTrue("expected to find canned ACL permission in the grants",
                    foundCannedAclForRead && foundCannedAclForWrite);
            assertTrue("expected to find owner's full control ACL in the grants", foundOwnerAcl);

        }
        finally {
            cleanup(cleanupTasks);
        }

    }

    @Test
    public void logDeliveryWriteCannedAclGetBucketAclTest() throws Exception {

        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        List<CleanupTask> cleanupTasks = new ArrayList<>();

        try {
            final String testBucketName = generateBucketName();
            print("creating bucket named - " + testBucketName);
            s3.createBucket(testBucketName);

            cleanupTasks.add( new CleanupTask("delete-bucket") {
                @Override
                public void run() {
                    cleanBucket(testBucketName, s3);
                }
            } );

            print("setting log-delivery-write canned acl on bucket named - " + testBucketName);
            s3.setBucketAcl(testBucketName, CannedAccessControlList.LogDeliveryWrite);

            print("re-retrieving bucket acl for bucket - " + testBucketName);
            AccessControlList updatedAcl = s3.getBucketAcl(testBucketName);

            boolean foundOwnerAcl = false;
            boolean foundCannedAclForRead = false;
            boolean foundCannedAclForWrite = false;
            print("looping over grants in acl");
            for (Grant grant : updatedAcl.getGrants()) {
                String permString = grant.getPermission().toString();
                if ("READ_ACP".equals(permString)) {
                    print("checking read-acp grant to make sure it matches expectations");
                    foundCannedAclForRead = true;

                    String permName = grant.getPermission().name();
                    String permHdrName = grant.getPermission().getHeaderName();
                    assertTrue("expected permission name to be ReadAcp but was " + permName,
                            "ReadAcp".equals(permName));
                    assertTrue("expected permission string to be READ but was " + permString,
                            "READ_ACP".equals(permString));
                    assertTrue("expected header name to be x-amz-grant-read-acp but was " + permHdrName,
                            "x-amz-grant-read-acp".equals(permHdrName));

                    String granteeId = grant.getGrantee().getIdentifier();
                    String granteeTypeId = grant.getGrantee().getTypeIdentifier();
                    assertTrue("expected the type to be uri, but was " + granteeTypeId,
                            "uri".equals(granteeTypeId));
                    assertTrue("expected the id to be http://acs.amazonaws.com/groups/s3/LogDelivery, but was " + granteeId,
                            "http://acs.amazonaws.com/groups/s3/LogDelivery".equals(granteeId));

                }
                else if ("WRITE".equals(permString)) {
                    print("checking write grant to make sure it matches expectations");
                    foundCannedAclForWrite = true;

                    String permName = grant.getPermission().name();
                    String permHdrName = grant.getPermission().getHeaderName();
                    assertTrue("expected permission name to be Write but was " + permName,
                            "Write".equals(permName));
                    assertTrue("expected permission string to be WRITE but was " + permString,
                            "WRITE".equals(permString));
                    assertTrue("expected header name to be x-amz-grant-write but was " + permHdrName,
                            "x-amz-grant-write".equals(permHdrName));

                    String granteeId = grant.getGrantee().getIdentifier();
                    String granteeTypeId = grant.getGrantee().getTypeIdentifier();
                    assertTrue("expected the type to be uri, but was " + granteeTypeId,
                            "uri".equals(granteeTypeId));
                    assertTrue("expected the id to be http://acs.amazonaws.com/groups/s3/LogDelivery, but was " + granteeId,
                            "http://acs.amazonaws.com/groups/s3/LogDelivery".equals(granteeId));

                }
                else if ("FULL_CONTROL".equals(permString)) {
                    print("checking full control grant to make sure it matches expectations");
                    foundOwnerAcl = true;

                    String permName = grant.getPermission().name();
                    String permHdrName = grant.getPermission().getHeaderName();
                    assertTrue("expected permission name to be FullControl but was " + permName,
                            "FullControl".equals(permName));
                    assertTrue("expected permission string to be FULL_CONTROL but was " + permString,
                            "FULL_CONTROL".equals(permString));
                    assertTrue("expected header name to be x-amz-grant-full-control but was " + permHdrName,
                            "x-amz-grant-full-control".equals(permHdrName));

                    assertTrue("expected acl to be for the owner",
                            updatedAcl.getOwner().getId().equals(grant.getGrantee().getIdentifier()));
                }
            }

            assertTrue("expected to find canned ACL permission in the grants",
                    foundCannedAclForRead && foundCannedAclForWrite);
            assertTrue("expected to find owner's full control ACL in the grants", foundOwnerAcl);

        }
        finally {
            cleanup(cleanupTasks);
        }

    }

    @Test
    public void bucketOwnerFullControlCannedAclGetBucketAclTest() throws Exception {

        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        List<CleanupTask> cleanupTasks = new ArrayList<>();

        try {
            final String testBucketName = generateBucketName();
            print("creating bucket named - " + testBucketName);
            s3.createBucket(testBucketName);

            cleanupTasks.add( new CleanupTask("delete-bucket") {
                @Override
                public void run() {
                    cleanBucket(testBucketName, s3);
                }
            } );

            print("setting bucket-owner-full-control canned acl on bucket named - " + testBucketName);
            s3.setBucketAcl(testBucketName, CannedAccessControlList.BucketOwnerFullControl);

            print("re-retrieving bucket acl for bucket - " + testBucketName);
            AccessControlList updatedAcl = s3.getBucketAcl(testBucketName);

            boolean foundOwnerAcl = false;
            print("looping over grants in acl");
            for (Grant grant : updatedAcl.getGrants()) {
                String permString = grant.getPermission().toString();
                if ("FULL_CONTROL".equals(permString)) {
                    print("checking full control grant to make sure it matches expectations");
                    foundOwnerAcl = true;

                    String permName = grant.getPermission().name();
                    String permHdrName = grant.getPermission().getHeaderName();
                    assertTrue("expected permission name to be FullControl but was " + permName,
                            "FullControl".equals(permName));
                    assertTrue("expected permission string to be FULL_CONTROL but was " + permString,
                            "FULL_CONTROL".equals(permString));
                    assertTrue("expected header name to be x-amz-grant-full-control but was " + permHdrName,
                            "x-amz-grant-full-control".equals(permHdrName));

                    assertTrue("expected acl to be for the owner",
                            updatedAcl.getOwner().getId().equals(grant.getGrantee().getIdentifier()));
                }
            }

            assertTrue("expected to find owner's full control ACL in the grants", foundOwnerAcl);

        }
        finally {
            cleanup(cleanupTasks);
        }

    }

}
