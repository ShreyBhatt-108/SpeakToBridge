#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3-venv python3-pip ca-certificates wget libnuma1 libnuma-dev libatomic1 libgfortran5
if [ ! -x /opt/amd-ai/bin/python ]; then
  python3 -m venv /opt/amd-ai
fi
/opt/amd-ai/bin/python -m pip install --upgrade pip
/opt/amd-ai/bin/python -m pip install --no-cache-dir --index-url https://repo.amd.com/rocm/whl-multi-arch/ 'torch[device-gfx1151]==2.12.0+rocm7.14.1'
/opt/amd-ai/bin/python -m pip install --no-cache-dir 'transformers==4.57.6' 'huggingface-hub==0.36.2' 'tokenizers==0.22.2' numpy safetensors
mkdir -p /opt/amd-ai/setup
wget -O /opt/amd-ai/setup/rocdxg-roct_1.2.1_amd64.deb https://github.com/ROCm/librocdxg/releases/download/v1.2.1/rocdxg-roct_1.2.1_amd64.deb
apt-get install -y /opt/amd-ai/setup/rocdxg-roct_1.2.1_amd64.deb
/opt/amd-ai/bin/python -m pip check
