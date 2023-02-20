#!/usr/bin/env bash

set -e

cd "$(dirname "$0")/.."

# Create custom components dummy module file
touch custom_components/__init__.py

# Install requirements
python3 -m pip install --requirement requirements.txt