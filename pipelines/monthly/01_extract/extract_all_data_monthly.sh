#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

python3 1_fic1_extract_data_ddbb.py
python3 2_fic2_extract_data_ddbb.py
python3 3_fic1_extract_locations_ddbb.py
python3 4_fic2_extract_locations_ddbb.py
