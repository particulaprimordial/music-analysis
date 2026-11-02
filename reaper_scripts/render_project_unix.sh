#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 1 ]]; then
  echo 'Usage: ./render_project_unix.sh /path/to/project.rpp' >&2
  exit 2
fi
exec reaper -renderproject "$1"
