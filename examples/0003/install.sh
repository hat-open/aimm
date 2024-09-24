#!/bin/bash

mkdir -p dataset
curl https://raw.githubusercontent.com/numenta/NAB/master/data/realKnownCause/ambient_temperature_system_failure.csv --output dataset/ambient_temperature_system_failure.csv --silent
yarn install --silent
