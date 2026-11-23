#!/bin/sh
# Create a disposable CA and IP-SAN server certificate in a new directory.
set -eu
umask 077
tls_dir=${1:?Usage: sh make-lab-tls.sh /absolute/path/to/new-directory}
mkdir "$tls_dir"
cd "$tls_dir"
openssl req -x509 -newkey rsa:2048 -nodes -days 7 \
  -subj '/CN=Secure Claude Component 2A disposable CA' -keyout ca.key -out ca.pem
openssl req -new -newkey rsa:2048 -nodes -subj '/CN=127.0.0.1' \
  -keyout server.key -out server.csr
printf '%s\n' 'subjectAltName=IP:127.0.0.1' 'extendedKeyUsage=serverAuth' \
  'basicConstraints=critical,CA:FALSE' > server.ext
openssl x509 -req -in server.csr -CA ca.pem -CAkey ca.key -CAcreateserial \
  -out server.pem -days 7 -sha256 -extfile server.ext
rm ca.key ca.srl server.csr server.ext
