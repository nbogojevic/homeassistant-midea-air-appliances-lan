#! /bin/bash

# Fix discontinuing of git support by GitHub
sed 's/git:/https:/' -i /usr/share/container/upgrade

# Create custom components dummy module file
touch custom_components/__init__.py

# Install home assistant
# container install
pip install -r requirements-dev.txt