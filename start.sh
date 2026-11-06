#!/bin/bash
set -e

# Module invocation works on Render without relying on Docker's PYTHONPATH.
# exec forwards shutdown signals to Python so active duel stakes are refunded.
echo "Starting SENSEI bot..."
exec python -m src.main
