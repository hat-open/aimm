#!/bin/bash

rm data/aimm.db
export PYTHONPATH=../../src_py
python -m hat.orchestrator.main --conf ./data/orchestrator.yaml
