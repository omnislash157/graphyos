#!/usr/bin/env bash
tsend() {
  local pane="$1"; shift; local msg="$*"
  tmux capture-pane -p -t "$pane" >/dev/null 2>&1 || { echo "tsend: no pane $pane" >&2; return 2; }
  [ "$(tmux display-message -p -t "$pane" '#{pane_in_mode}')" = "1" ] && tmux send-keys -t "$pane" Escape
  tmux send-keys -t "$pane" C-u
  tmux send-keys -t "$pane" -l -- "$msg"
  local i
  for i in 1 2 3 4; do
    sleep 0.45
    tmux send-keys -t "$pane" Enter
  done
  sleep 0.4
  local bottom; bottom=$(tmux capture-pane -p -t "$pane" 2>/dev/null | tail -3)
  if printf '%s' "$bottom" | grep -qF "${msg:0:16}"; then
    echo "tsend: WARN $pane — message may still be in the input box; capture to confirm" >&2; return 1
  fi
  echo "tsend: $pane submitted ✓"; return 0
}
