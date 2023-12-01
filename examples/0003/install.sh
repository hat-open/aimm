#!/bin/bash

dataset_setup () {
    mkdir -p dataset
    curl https://raw.githubusercontent.com/numenta/NAB/master/data/realKnownCause/ambient_temperature_system_failure.csv --output dataset/ambient_temperature_system_failure.csv --silent
}

dataset_setup
yarn install --silent
