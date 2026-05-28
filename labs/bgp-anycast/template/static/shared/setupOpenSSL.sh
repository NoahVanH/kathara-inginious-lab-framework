#!/bin/bash
# This script generates a self-signed certificate for the DNS server and places it in the appropriate directory for BIND to use.
# Source : https://blog.meyerrj.com/creating-a-dot-and-doh-server-using-nginx-and-bind/
DNS_DOMAIN="$1"

mkdir -p /etc/bind/tls

openssl req -x509 -newkey rsa:2048 \
  -keyout /etc/bind/tls/key.pem \
  -out /etc/bind/tls/cert.pem \
  -days 365 -nodes \
  -subj "/CN=$DNS_DOMAIN"

chown -R bind:bind /etc/bind/tls
chmod 640 /etc/bind/tls/key.pem