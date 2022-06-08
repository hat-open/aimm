#!/bin/bash

dataset_setup () {
    mkdir -p dataset
    curl https://archive.ics.uci.edu/ml/machine-learning-databases/00360/AirQualityUCI.zip --output dataset/AirQualityUCI.zip --silent
    unzip -o dataset/AirQualityUCI.zip -d dataset -x "AirQualityUCI.xlsx"
    rm -f dataset/AirQualityUCI.zip

    awk -F';' '{print $4","$13","$14","$15}'  dataset/AirQualityUCI.csv > dataset/sanatized_.csv
    cut -d, -f1-4 dataset/sanatized_.csv > dataset/sanatized.csv

    rm -f dataset/AirQualityUCI.csv
    rm -f dataset/sanatized_.csv
}

dataset_setup
yarn install --silent
node_modules/.bin/webpack --config webpack.config.js


