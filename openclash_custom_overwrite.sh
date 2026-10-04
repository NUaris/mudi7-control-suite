#!/bin/sh
# Integration hook only; merge with existing user hooks instead of overwriting them.
CONFIG_FILE="$1"
ruby /etc/mudi7-management/openclash-dns-overwrite.rb "$CONFIG_FILE"
