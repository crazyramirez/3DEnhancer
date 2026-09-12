#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")"

python3 -m pip install -r requirements-build.txt
python3 -m PyInstaller --noconfirm --clean \
  --distpath release/macos \
  --workpath build/macos \
  3DEnhancer.spec

echo ""
echo "Aplicación creada en: release/macos/3D Enhancer.app"
