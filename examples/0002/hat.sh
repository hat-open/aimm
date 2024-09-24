#!/bin/bash

export PYTHONPATH=src_py

mkdir -p data
python ./src_py/simulation.py &
python -m hat.orchestrator.main --conf ./conf/orchestrator.yaml
