#!/usr/bin/env bash

# Make the config dir
mkdir -p /tmp/config


# Symplink the custom_components dir
if [ -d "/tmp/config/custom_components" ]; then
  rm -rf /tmp/config/custom_components
fi
ln -sf "${PWD}/custom_components" /tmp/config/custom_components

ln -sf "${PWD}/tests/configuration.yaml" /tmp/config/configuration.yaml
ln -sf "${PWD}/tests/secrets.yaml" /tmp/config/secrets.yaml


# Start Home Assistant
sudo /var/lib/hass/.venv/bin/python /var/lib/hass/.venv/bin/hass --config /tmp/config