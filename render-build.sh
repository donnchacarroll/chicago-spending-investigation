#!/usr/bin/env bash
set -e

echo "=== Installing Python dependencies ==="
pip install -r backend/requirements.txt

echo "=== Installing Node dependencies ==="
cd frontend
npm install
echo "=== Building React frontend ==="
npm run build
cd ..

echo "=== Running ETL pipeline ==="
python backend/etl/build_db.py

echo "=== Build complete ==="
ls -lh spending.duckdb
