#! /bin/bash

# Add network testing tools
apt update
apt install -y iptables iproute2
update-alternatives --set iptables /usr/sbin/iptables-legacy

# Create custom components dummy module file
touch custom_components/__init__.py

# Install home assistant
container install
# pip install -r requirements-dev.txt