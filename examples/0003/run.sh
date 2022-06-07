#!/bin/bash
# napravi curl za dataset
yarn install --silent
node_modules/.bin/webpack --config webpack.config.js
# gore ide posebno

rm data/aimm.db -f
export PYTHONPATH=src_py
python -m hat.orchestrator.main --conf ./conf/orchestrator.yaml
