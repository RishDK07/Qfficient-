#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "====================================================================="
echo "Starting Thermodynamic QUBO Microgrid Review Dashboard..."
echo "====================================================================="

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

streamlit run app.py --server.port 8501 --server.address 0.0.0.0
