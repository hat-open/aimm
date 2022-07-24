#!/bin/bash

rm -rf build/

yarn install --silent
node_modules/.bin/webpack --config webpack.config.js

rm data/aimm.db -f
export PYTHONPATH=src_py
python -m hat.orchestrator.main --conf ./conf/orchestrator.yaml
