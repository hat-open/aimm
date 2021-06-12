#!/bin/bash

export PYTHONPATH=src_py

python src_py/fetch_view.py

python -m hat.orchestrator.main --conf ./conf/orchestrator.yaml
