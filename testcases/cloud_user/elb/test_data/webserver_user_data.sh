#!/bin/bash
if [ -e /etc/redhat-release ]; then
  yum -y install httpd
  chkconfig httpd on
  echo "NameVirtualHost *:80" >> /etc/httpd/conf/httpd.conf
  echo "CookieTracking on" >> /etc/httpd/conf/httpd.conf
  echo "CookieName test-cookie" >> /etc/httpd/conf/httpd.conf
  curl http://169.254.169.254/latest/meta-data/instance-id > /var/www/html/index.html
  echo "" >> /var/www/html/index.html
  service httpd start
else
  apt-get update
  apt-get install -y apache2

  # enable user tracking (for cookies and stickiness)
  echo "CookieTracking on" >> /etc/apache2/apache2.conf
  echo "CookieName test-cookie" >> /etc/apache2/apache2.conf
  a2enmod usertrack

  # write our own ssl key
  echo '-----BEGIN RSA PRIVATE KEY-----
MIICXAIBAAKBgQCoQdYwMwhOPldGxLljDIKpnAOrt3Q7uPt1hNC5yTnjjkZKdjP/
50OMwuznStIFtGRnDSqNmNyd5cSj6WMvhIOeAaLM5K+tOMyX04nmoNI4zLZyYmtD
AQbMznUiTZEvnOT/j5JKioi4d/+WTjE+ubNP1Gn79PyrsHRLEIMk6qc3BwIDAQAB
AoGAaHno+6jUgXEoVGMXEi/UemjLxrZ1UBg+2+wKhzIx5eCUOOxIwZ/iS+dFnyDQ
ZIZsyahdQesnIkxn27exxPGtn08g6Ow47+YPRACUpy/OMlRfqPENcVVu+Rn67U2O
UEm/BwuCdAG6djnHVns3UHuZpIs/O9KqBJAvfmiO1sU2jOECQQDapFTYY8V3vASI
2hf5rVyEjDYLOvSu5GsNa+Y6VZHNYXyfN9xOUE7frueF4p3yztDtUEPBOIVjAFNX
dLBf4PZfAkEAxQGdMddY+7adoocx6Dhvz7hpzm+KBzIbCfJnQ90UF0JIbjlLHlkz
YP8DZBUhq7cc0p5stm2hTM+b7Sl8J1hwWQJAcfaWAvR+SRrHgk2rkYi7YJt00AW6
5C5LXoOPTXisttDJlHQZcPiLJCyWoUKt8ZG7dPcRWfWMET5qMnuwM0mfIQJBAKtK
7voCKy2Zp9BESsGGKLnst5q14sbE6zun19/q3ugmSsID8OuvVXwV30XrFb6vVVFQ
TGgGRIR70zDPrFKtk+kCQCJgjQhxxjM/SfRUJcA+x5ggy3X//7e975AXFcAiMcOr
TFgtpamt/7y3wECO1prHZn4jZCrd1vM0Bmf+LyFikVE=
-----END RSA PRIVATE KEY-----' > /etc/ssl/private/ssl-cert-snakeoil.key

  # write our own ssl cert
  echo '-----BEGIN CERTIFICATE-----
MIICXjCCAccCAgPoMA0GCSqGSIb3DQEBBQUAMHcxCzAJBgNVBAYTAlVTMRMwEQYD
VQQIEwpDYWxpZm9ybmlhMRQwEgYDVQQHEwtHcmFuaXRlIEJheTETMBEGA1UEChMK
RXVjYWx5cHR1czEQMA4GA1UECxMHUXVhbGl0eTEWMBQGA1UEAxMNQ2FzY2FkZS5s
b2NhbDAeFw0xMzEyMTQwMDE1NDBaFw0yMzEyMTIwMDE1NDBaMHcxCzAJBgNVBAYT
AlVTMRMwEQYDVQQIEwpDYWxpZm9ybmlhMRQwEgYDVQQHEwtHcmFuaXRlIEJheTET
MBEGA1UEChMKRXVjYWx5cHR1czEQMA4GA1UECxMHUXVhbGl0eTEWMBQGA1UEAxMN
Q2FzY2FkZS5sb2NhbDCBnzANBgkqhkiG9w0BAQEFAAOBjQAwgYkCgYEAqEHWMDMI
Tj5XRsS5YwyCqZwDq7d0O7j7dYTQuck5445GSnYz/+dDjMLs50rSBbRkZw0qjZjc
neXEo+ljL4SDngGizOSvrTjMl9OJ5qDSOMy2cmJrQwEGzM51Ik2RL5zk/4+SSoqI
uHf/lk4xPrmzT9Rp+/T8q7B0SxCDJOqnNwcCAwEAATANBgkqhkiG9w0BAQUFAAOB
gQAyDQvZoPUfNGXur4hW6G8+rzchK/eX4Si6JBZWqBzi09r86vXwlr7ZEnbofnvA
RjcgihEC1t3Z/Ew1VEMf49kZAXuTwbcevPVaWwHjuD4R6fQ3GBfr6hrh/Y/ZA215
F3cpgmrg8e2tnHu6YAjkjQHbqSsUvxuG1R2fXj5uF+Q7ug==
-----END CERTIFICATE-----' > /etc/ssl/certs/ssl-cert-snakeoil.pem

  # enable ssl
  ln -s  /etc/apache2/sites-available/default-ssl /etc/apache2/sites-enabled/000-ssl
  a2enmod ssl

  # create a target that returns the instance name
  if [ -d /var/www/html ]; then
    curl http://169.254.169.254/latest/meta-data/instance-id > /var/www/html/instance-name
    echo "" >> /var/www/html/instance-name
  else
    curl http://169.254.169.254/latest/meta-data/instance-id > /var/www/instance-name
    echo "" >> /var/www/instance-name
  fi

  # restart apache so our changes are applied
  service apache2 restart
fi
