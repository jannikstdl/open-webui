#!/bin/bash
PORT="${PORT:-8080}"
export PYTHONPATH=$PYTHONPATH:.
/home/jannik/miniconda3/envs/owui-fits/bin/python -m uvicorn open_webui.main:app --port $PORT --host 0.0.0.0 --forwarded-allow-ips '*' --reload 