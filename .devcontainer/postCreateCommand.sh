#! /bin/bash

# Fix discontinuing of git support by GitHub
sed 's/git:/https:/' -i /usr/share/container/upgrade

container install