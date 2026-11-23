#!/usr/bin/env bash
# Build the Debian/Ubuntu package for ETC NetGuard.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

VERSION="$(awk -F': ' '/^Version:/{print $2}' packaging/linux/debian/control)"
ARCH="$(awk -F': ' '/^Architecture:/{print $2}' packaging/linux/debian/control)"
BUNDLE="build/linux-dist/ETC-NetGuard-Linux"
PKGROOT="build/deb-root"
OUT="dist/etc-netguard_${VERSION}_${ARCH}.deb"

if [ ! -x "$BUNDLE/ETC-NetGuard-Linux" ]; then
    echo "Linux bundle missing. Build it first with:" >&2
    echo "  pyinstaller --noconfirm --clean --onedir --windowed --name ETC-NetGuard-Linux --add-data 'assets:assets' --hidden-import PyQt5.QtSvg --distpath build/linux-dist --workpath build/linux-work run.py" >&2
    exit 1
fi

rm -rf "$PKGROOT"
install -d "$PKGROOT/DEBIAN" \
  "$PKGROOT/usr/lib/etc-netguard" \
  "$PKGROOT/usr/bin" \
  "$PKGROOT/usr/share/applications" \
  "$PKGROOT/usr/share/icons/hicolor/256x256/apps" \
  "$PKGROOT/usr/share/polkit-1/actions" \
  "$PKGROOT/usr/share/doc/etc-netguard"

cp -a "$BUNDLE"/. "$PKGROOT/usr/lib/etc-netguard/"
mv "$PKGROOT/usr/lib/etc-netguard/ETC-NetGuard-Linux" "$PKGROOT/usr/lib/etc-netguard/etc-netguard-bin"
chmod 755 "$PKGROOT/usr/lib/etc-netguard/etc-netguard-bin"

install -m 755 packaging/linux/launcher.sh "$PKGROOT/usr/bin/etc-netguard"
install -m 755 packaging/linux/launch-root.sh "$PKGROOT/usr/lib/etc-netguard/launch-root.sh"
install -m 644 packaging/linux/etc-netguard.desktop "$PKGROOT/usr/share/applications/etc-netguard.desktop"
install -m 644 assets/app.png "$PKGROOT/usr/share/icons/hicolor/256x256/apps/etc-netguard.png"
install -m 644 packaging/linux/etc.netguard.policy "$PKGROOT/usr/share/polkit-1/actions/etc.netguard.policy"
install -m 644 README.md "$PKGROOT/usr/share/doc/etc-netguard/README.md"
install -m 644 packaging/linux/debian/copyright "$PKGROOT/usr/share/doc/etc-netguard/copyright"
install -m 644 LICENSE "$PKGROOT/usr/share/doc/etc-netguard/LICENSE"
install -m 755 packaging/linux/debian/postinst "$PKGROOT/DEBIAN/postinst"

SIZE="$(du -sk "$PKGROOT" | awk '{print $1}')"
sed "s/__SIZE__/${SIZE}/" packaging/linux/debian/control > "$PKGROOT/DEBIAN/control"
dpkg-deb --build --root-owner-group "$PKGROOT" "$OUT"
echo "Built: $OUT"
dpkg-deb --info "$OUT" | sed -n '1,40p'
