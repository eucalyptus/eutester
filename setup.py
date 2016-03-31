# Software License Agreement (BSD License)
#
# Copyright (c) 2009-2011, Eucalyptus Systems, Inc.
# All rights reserved.
#
# Redistribution and use of this software in source and binary forms, with or
# without modification, are permitted provided that the following conditions
# are met:
#
#   Redistributions of source code must retain the above
#   copyright notice, this list of conditions and the
#   following disclaimer.
#
#   Redistributions in binary form must reproduce the above
#   copyright notice, this list of conditions and the
#   following disclaimer in the documentation and/or other
#   materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Author: Vic Iglesias vic.iglesias@eucalyptus.com
#         

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
import eutester

setup(name = "eutester",
      version = eutester.__version__,
      description = "Test Framework for AWS compatible clouds",
      long_description="Test Framework for AWS compatible clouds",
      author = "Victor Iglesias",
      author_email = "vic.iglesias@eucalyptus.com",
      url = "http://open.eucalyptus.com",
      install_requires = ['paramiko >= 1.7','boto >= 2.5.2', 'jinja2 >= 2.7', 'argparse',
                          'futures', 'python-dateutil', 'dnspython', 'pywinrm',
                          'BeautifulSoup', 'requests >= 1', 'prettytable'],
      packages = ["eutester","eucaops", "eucaweb", "testcases", "testcases.cloud_admin",
                  "testcases.cloud_admin.riak_cs", "testcases.cloud_admin.riak_cs.templates",
                  "testcases.cloud_user", "testcases.cloud_user.instances",
                  "testcases.cloud_user.s3", "testcases.cloud_user.load",
                  "testcases.cloud_user.images", "testcases.cloud_user.images.eustore",
                  "testcases.cloud_user.images.windows", "testcases.cloud_user.ebs",
                  "testcases.cloud_user.ebs.san_utils"],
      package_data      = {'testcases.cloud_admin.riak_cs.templates': ['*.template']},
      license = 'BSD (Simplified)',
      platforms = 'Posix; MacOS X; Windows',
      classifiers = [ 'Development Status :: 3 - Alpha',
                      'Intended Audience :: System Administrators',
                      'License :: OSI Approved :: BSD License',
                      'Operating System :: OS Independent',
                      'Topic :: System :: Systems Administration',
                      ],
      )
