import urlparse
import httplib
import base64
from hashlib import sha1
import hmac
from email.utils import formatdate

def lowercase_key(d):
    return dict((k.lower(), v) for k, v in d.iteritems())

def amz_headers(h):
    x_amz_keys = sorted(k for k in h if k.startswith('x-amz-'))
    for key in x_amz_keys:
        values = h[key]
        if isinstance(values, basestring):
            values = [values]

        value = ','.join(s.strip() for s in values)
        yield '%s:%s' % (key, value)

class Auth(object):
    def __init__(self, access_key, secret_key):
        self.access_key = access_key
        self.secret_key = secret_key

    def canonicalize(self, verb, resource, headers, x_amz_headerlist=None):
        if not resource.startswith('/'):
            resource = '/' + resource
        headers = lowercase_key(headers)
        signature_elements = [
            verb,
            headers.get("content-md5", ""),
            headers.get("content-type", ""),
            headers.get("date", ""),
        ]
        if x_amz_headerlist is None:
            x_amz_headerlist = amz_headers(headers)

        signature_elements.extend(x_amz_headerlist)
        signature_elements.append(resource)
        return '\n'.join(signature_elements)

    def sign(self, signature_str):
        h = hmac.new(self.secret_key, signature_str, sha1)
        d = h.digest()
        return base64.encodestring(d).strip()

    def header(self, verb, resource, headers, x_amz_headerlist):
        signature_str = self.canonicalize(verb, resource, headers, x_amz_headerlist)
        ####print "SIGNATURE", signature_str
        signature = self.sign(signature_str)
        return 'AWS %s:%s' % (self.access_key, signature)

class S3Connection(object):
    CONNECTOR = {
        'http': httplib.HTTPConnection,
        'https': httplib.HTTPSConnection,
    }

    def __init__(self, url, auth):
        self.auth = auth

        parts = urlparse.urlsplit(url)
        connector = self.CONNECTOR[parts.scheme]
        self.netloc = parts.netloc

        host, _, _ = parts.netloc.partition(':')
        port = parts.port
        self.basepath = parts.path.rstrip('/')

        self.conn = connector(host, port, timeout=15)
        
    def putheaders(self, headers):
        for header, values in headers.iteritems():
            if isinstance(values, basestring):
                values = [values]
            for v in values:
                self.conn.putheader(header, v)

    @property
    def is_aws(self):
        return 'amazonaws.com' in self.netloc

    # Guess the proper Host-header based on host
    def bucket_host(self, bucket):
        if self.is_aws:
            return bucket + '.' + self.netloc
        return bucket + '.walrus'
    
    def fix_resource(self, resource):
        if self.is_aws:
            return resource
        return '/services/Walrus' + resource

    def request(self, method, url, resource, data, headers, vhost=None, x_amz_headerlist=None):
        full_path = self.basepath + url

        headers.setdefault("Content-Type", "text/plain")
        headers.setdefault("Date", formatdate(usegmt=True))

        headers['Authorization'] = self.auth.header(method, resource, headers, x_amz_headerlist)
        headers['Content-Length'] = str(len(data))

        headers['Host'] = self.bucket_host(vhost) if vhost else self.netloc 

        ####self.conn.set_debuglevel(1)
        self.conn.connect()
        self.conn.putrequest(method, full_path, skip_host=True)
        self.putheaders(headers)
        self.conn.endheaders()
        self.conn.send(data)

        resp = self.conn.getresponse()
        status, data = resp.status, resp.read()
        self.conn.close()
        
        return status, data

