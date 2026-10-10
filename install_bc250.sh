#!/usr/bin/env bash
# Installs the BC250-Phosphor theme into a turing-smart-screen-python checkout.
# Usage: ./install_bc250.sh /path/to/turing-smart-screen-python [options]
#   --user NAME    user in the "user@host:~$" prompt   (default: your login, $(whoami))
#   --host NAME    host in the prompt                  (default: $(hostname -s))
#   --title TEXT   header text                         (default: <LOGO>::<USER>)
#   --logo TEXT    big title of the boot splash        (default: BC-250)
#   --subtitle TEXT  line under it                     (default: STEAM MACHINE)
#   --cold C       temperatures fully green at/below C (default: 40)
#   --hot C        temperatures fully orange at/above C (default: 70)
#   --alert C      temperatures red and flashing HOT! from C (default: 80)
#   --pwr-low W    APU power fully green at/below W (default: 100)
#   --pwr-high W   APU power fully red at/above W (default: 200)
#   --dim-after M  dim after M minutes without game or download, 0 = never (default: 10)
#   --dim-brightness P   brightness % when dimmed (default: 5)
#   --night HH:MM-HH:MM  screen sleeps during these hours unless a game runs (default: never)
#   --night-mode off|dim (default: off)
#   --no-splash    skip the BIOS-style boot screen
#   --portrait     portrait layout (320x480) instead of landscape
# Re-run it any time to change these; it is safe to run repeatedly.
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
REPO="${1:-}"
if [[ -z "$REPO" || ! -f "$REPO/main.py" || ! -f "$REPO/library/sensors/sensors_custom.py" ]]; then
  sed -n '3,20p' "$0" | sed 's/^# \{0,1\}//' >&2
  exit 1
fi
shift

GEN_ARGS=(--user "$(whoami)" --host "$(hostname -s 2>/dev/null || hostname)")
while [[ $# -gt 0 ]]; do
  case "$1" in
    --user|--host|--title|--logo|--subtitle|--cold|--hot|--alert|--pwr-low|--pwr-high|--dim-after|--dim-brightness|--night|--night-mode) GEN_ARGS+=("$1" "${2:?$1 needs a value}"); shift 2 ;;
    --no-splash|--portrait) GEN_ARGS+=("$1"); shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

cp -r "$SRC/res/themes/BC250-Phosphor" "$REPO/res/themes/"
cp "$SRC/library/sensors/sensors_bc250.py" "$REPO/library/sensors/"
cp "$SRC/bc250_check.py" "$REPO/"
echo "Copied theme, sensors and bc250_check.py"

# Expose the BC-250 sensor classes to the theme's CUSTOM section
CUSTOM="$REPO/library/sensors/sensors_custom.py"
if ! grep -q "sensors_bc250" "$CUSTOM"; then
  printf '\n\n# BC250-Phosphor theme sensors\nfrom library.sensors.sensors_bc250 import *  # noqa: E402,F401,F403\n' >> "$CUSTOM"
  echo "Registered BC-250 sensors in sensors_custom.py"
fi

# Regenerate background + theme.yaml with your names / thresholds, using the Python that runs the monitor
PYTHON=""
for candidate in "$REPO/.venv/bin/python" "$REPO/venv/bin/python" python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import PIL" 2>/dev/null; then
    PYTHON="$candidate"
    break
  fi
done
if [[ -n "$PYTHON" ]]; then
  "$PYTHON" "$REPO/res/themes/BC250-Phosphor/make_theme.py" "${GEN_ARGS[@]}"
else
  echo "WARNING: no Python with Pillow found: kept the default 'steam@bc250' artwork." >&2
  echo "         Install the monitor's requirements, then re-run this script." >&2
fi

# Select the theme
CONFIG="$REPO/config.yaml"
sed -i 's/^\(  THEME:\).*/\1 BC250-Phosphor/' "$CONFIG"
echo "config.yaml: THEME set to BC250-Phosphor"

# Point the network widgets at the interface of the default route, unless ETH is already set
if grep -qE '^  ETH: ""' "$CONFIG"; then
  IFACE="$(ip -o route get 1.1.1.1 2>/dev/null | sed -n 's/.* dev \([^ ]*\).*/\1/p' || true)"
  if [[ -n "$IFACE" ]]; then
    sed -i "s/^  ETH: \"\"/  ETH: \"$IFACE\"/" "$CONFIG"
    echo "config.yaml: ETH set to $IFACE"
  fi
fi

echo
echo "To start the monitor at boot: $SRC/install_autostart.sh \"$REPO\"  (once; afterwards"
echo "  'systemctl --user restart turing-monitor' applies changes)"
echo "Done. Restart the monitor, then run the pre-flight check from the repo folder:"
echo "  cd \"$REPO\" && python3 bc250_check.py"
