#!/bin/bash
set -e

echo "Running tests..."
pytest src/tests/ -v --cov=src --cov-report=term-missing
