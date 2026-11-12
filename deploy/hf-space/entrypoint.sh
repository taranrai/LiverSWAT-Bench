#!/usr/bin/env bash
# Resume the Milestone 5 judge stage. Run only the pending judge steps (no model inference).
# Required Space secret: HF_TOKEN (write access to the private results repository).
# Required Space variable: LSB_RESULTS_REPO (a private dataset repository, OWNER/NAME).
set -euo pipefail

: "${HF_TOKEN:?Set HF_TOKEN as a Space secret}"
: "${LSB_RESULTS_REPO:?Set LSB_RESULTS_REPO (a private dataset repository) as a Space variable}"
CONFIG="${LSB_PILOT_CONFIG:-configs/experiments/m5-real-model-pilot.yaml}"
RESULTS_DIR="${LSB_RESULTS_DIR:-results/m5-real-model-pilot}"
SYNC_INTERVAL_S="${LSB_SYNC_INTERVAL_S:-300}"
AUTO_PAUSE="${LSB_AUTO_PAUSE:-1}"
STATUS_LOG="$HOME/status.log"
SYNC="python $HOME/repo/scripts/hf_results_sync.py"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" | tee -a "$STATUS_LOG"; }

python "$HOME/space/status_server.py" "$STATUS_LOG" &
cd "$LSB_REPO_DIR"
log "commit $(git rev-parse HEAD)"

ollama serve >"$HOME/ollama.log" 2>&1 &
until curl -sf http://127.0.0.1:11434/api/version >/dev/null; do sleep 1; done
log "ollama $(curl -s http://127.0.0.1:11434/api/version)"
if command -v nvidia-smi >/dev/null; then
  log "gpu $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | tr '\n' ';')"
else
  log "no GPU is visible; judge models run on the CPU"
fi

log "pull results from $LSB_RESULTS_REPO"
$SYNC pull --repo "$LSB_RESULTS_REPO" --results-dir "$RESULTS_DIR" 2>&1 | tee -a "$STATUS_LOG"

for model in $($SYNC judge-models --config "$CONFIG"); do
  log "ollama pull $model"
  ollama pull "$model" >>"$HOME/ollama.log" 2>&1
done

log "pending steps:"
liverswat pilot --config "$CONFIG" --judge-only --dry-run 2>&1 | tee -a "$STATUS_LOG"

( while sleep "$SYNC_INTERVAL_S"; do
    $SYNC push --repo "$LSB_RESULTS_REPO" --results-dir "$RESULTS_DIR" \
      --message "Checkpoint judge results" >/dev/null 2>&1 || log "push failed; retry later"
  done ) &
SYNC_LOOP_PID=$!

log "start judge stage"
set +e
liverswat pilot --config "$CONFIG" --judge-only 2>&1 | tee -a "$STATUS_LOG"
RC=${PIPESTATUS[0]}
set -e
kill "$SYNC_LOOP_PID" 2>/dev/null || true

log "judge stage exit code $RC; final push"
$SYNC push --repo "$LSB_RESULTS_REPO" --results-dir "$RESULTS_DIR" \
  --message "Judge stage finished (exit code $RC)" 2>&1 | tee -a "$STATUS_LOG"

if [ "$AUTO_PAUSE" = "1" ] && [ -n "${SPACE_ID:-}" ]; then
  log "pause Space $SPACE_ID to stop hardware use"
  $SYNC pause --space "$SPACE_ID" 2>&1 | tee -a "$STATUS_LOG"
fi
log "done"
wait
