#!/bin/bash

export PYTHONPATH=src_py

mkdir -p data
python -m hat.orchestrator.main --conf ./conf/orchestrator.yaml
