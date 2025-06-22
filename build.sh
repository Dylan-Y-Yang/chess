#!/usr/bin/env bash
set -e                       # stop immediately on any error

# ----- Python -----
pip install -r requirements.txt

# ----- Front-end -----
cd frontend
npm ci                       # or: pnpm install
npm run build                # puts the compiled files in frontend/dist
