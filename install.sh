#!/usr/bin/env bash
# Install Favilla for the current user. Root is only needed for the udev rules.
#   ./install.sh              install a copy of the current sources
#   ./install.sh --dev        editable install: edits to src/ apply after a restart
#   ./install.sh --uninstall  remove Favilla (your configuration is kept)
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

app_id=io.github.fontanamichele.Favilla
data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
units="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

if [[ "${1:-}" == "--uninstall" ]]; then
    systemctl --user disable --now favilla.service 2>/dev/null || true
    rm -f "$units/favilla.service" "$data_home/applications/$app_id.desktop" \
          "$data_home/icons/hicolor/scalable/apps/$app_id.svg"
    systemctl --user daemon-reload
    python3 -m pip uninstall --yes --quiet favilla || true
    echo "Favilla removed. Configuration left in ~/.config/favilla."
    exit 0
fi

missing=()
python3 -c "import gi" 2>/dev/null || missing+=("PyGObject (Fedora: sudo dnf install python3-gobject)")
python3 -c "import PySide6" 2>/dev/null || missing+=("PySide6 (Fedora: sudo dnf install python3-pyside6)")
python3 -c "import rivalcfg" 2>/dev/null || missing+=("rivalcfg (pip install --user rivalcfg)")
if (( ${#missing[@]} )); then
    echo "Missing dependencies:"
    printf '  - %s\n' "${missing[@]}"
    exit 1
fi

editable=()
[[ "${1:-}" == "--dev" ]] && editable=(--editable)
echo "Installing the Python package..."
python3 -m pip install --user --no-build-isolation --no-deps --quiet "${editable[@]}" .

bindir="$(python3 -c 'import os, site; print(os.path.join(site.USER_BASE, "bin"))')"
install -Dm644 src/favilla/gui/favilla.svg "$data_home/icons/hicolor/scalable/apps/$app_id.svg"
mkdir -p "$data_home/applications" "$units"
sed "s|@BINDIR@|$bindir|g" "data/applications/$app_id.desktop.in" > "$data_home/applications/$app_id.desktop"
sed "s|@BINDIR@|$bindir|g" data/systemd/favilla.service.in > "$units/favilla.service"

systemctl --user daemon-reload
systemctl --user enable --quiet favilla.service
systemctl --user restart favilla.service
echo "Favilla is running: open it from the application menu or run 'favilla'."

if ! compgen -G "/etc/udev/rules.d/*favilla*" > /dev/null; then
    echo
    echo "To use SteelSeries devices without root, install the udev rules once:"
    echo "  sudo install -m644 data/udev/60-favilla.rules /etc/udev/rules.d/"
    echo "  sudo udevadm control --reload && sudo udevadm trigger --subsystem-match=hidraw"
fi
