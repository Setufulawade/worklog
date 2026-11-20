#!/bin/sh
# Build worklog_<version>_all.deb using only dpkg-deb (no debhelper needed).
# Usage:  ./build-deb.sh            ->  dist/worklog_<version>_all.deb
set -eu
cd "$(dirname "$0")"

MAINTAINER="${DEB_MAINTAINER:-Your Name <you@example.com>}"
VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' worklog/__init__.py)
PKG="worklog_${VERSION}_all"
ROOT="build/${PKG}"

rm -rf build
mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/bin" "$ROOT/usr/lib/python3/dist-packages/worklog" \
         "$ROOT/usr/share/man/man1" "$ROOT/usr/share/doc/worklog" dist

cp worklog/*.py "$ROOT/usr/lib/python3/dist-packages/worklog/"

cat > "$ROOT/usr/bin/worklog" <<'EOF'
#!/usr/bin/python3
import sys
from worklog.cli import main
sys.exit(main())
EOF

gzip -9n -c packaging/worklog.1 > "$ROOT/usr/share/man/man1/worklog.1.gz"
cp packaging/copyright "$ROOT/usr/share/doc/worklog/copyright"
cp README.md "$ROOT/usr/share/doc/worklog/README.md"
{
  echo "worklog (${VERSION}) stable; urgency=medium"
  echo
  echo "  * Release ${VERSION}."
  echo
  echo " -- ${MAINTAINER}  $(date -R)"
} | gzip -9n -c > "$ROOT/usr/share/doc/worklog/changelog.Debian.gz"

# permissions
find "$ROOT" -type d -exec chmod 755 {} +
find "$ROOT" -type f -exec chmod 644 {} +
chmod 755 "$ROOT/usr/bin/worklog"

SIZE=$(du -sk "$ROOT" | cut -f1)
cat > "$ROOT/DEBIAN/control" <<EOF
Package: worklog
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.9)
Recommends: python3-pptx
Installed-Size: ${SIZE}
Maintainer: ${MAINTAINER}
Homepage: https://example.com/worklog
Description: daily work journal with AI reports and PowerPoint export
 worklog keeps a plain-text journal in your terminal: add entries line by
 line for today or any past day, browse a calendar to view or edit a day,
 and use your own AI API key to generate weekly, monthly and yearly reports
 or PowerPoint decks from what you logged.
EOF

cat > "$ROOT/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
case "$1" in
  remove|purge)
    rm -rf /usr/lib/python3/dist-packages/worklog/__pycache__
    rmdir /usr/lib/python3/dist-packages/worklog 2>/dev/null || true
    ;;
esac
exit 0
EOF
chmod 755 "$ROOT/DEBIAN/postrm"

dpkg-deb --build --root-owner-group "$ROOT" "dist/${PKG}.deb"
echo "Built dist/${PKG}.deb"
