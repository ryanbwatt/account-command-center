#!/usr/bin/env bash
# install.sh — copy launchd templates into ~/Library/LaunchAgents with the real repo path.
# launchd does not expand $HOME or env vars, so the plists carry a __CC_DIR__ placeholder.
#   scripts/launchd/install.sh com.commandcenter.pulsetip [more labels...]
#   scripts/launchd/install.sh            # all templates
# Then: launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/<label>.plist
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
cc_dir="${CC_DIR:-$(cd "$here/../.." && pwd)}"
dest="$HOME/Library/LaunchAgents"
mkdir -p "$dest"
labels=("$@")
[[ ${#labels[@]} -gt 0 ]] || labels=($(cd "$here" && ls com.commandcenter.*.plist | sed 's/\.plist$//'))
for label in "${labels[@]}"; do
  src="$here/$label.plist"
  [[ -f "$src" ]] || { echo "no template: $src" >&2; exit 1; }
  sed "s|__CC_DIR__|$cc_dir|g" "$src" > "$dest/$label.plist"
  # launchd will not create the log directory itself.
  grep -o "$cc_dir/logs/[^/<]*" "$dest/$label.plist" | sort -u | xargs -n1 mkdir -p
  plutil -lint -s "$dest/$label.plist"
  echo "installed $dest/$label.plist"
done
