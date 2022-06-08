#!/bin/bash

rm data/aimm.db -f
export PYTHONPATH=src_py
python -m hat.orchestrator.main --conf ./conf/orchestrator.yaml
