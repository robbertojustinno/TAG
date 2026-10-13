#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
test -f admin/index.html
test -f viewer/index.html
mkdir -p admin/viewer
cp -R viewer/. admin/viewer/
# Keep relative Viewer assets correct for the URL without a trailing slash.
python3 - <<'PY'
from pathlib import Path
p = Path('admin/viewer/index.html')
s = p.read_text()
s = s.replace('<head>', '<head>\n    <base href="/viewer/" />', 1)
p.write_text(s)
PY
printf 'Admin and Viewer ready in admin/\n'
