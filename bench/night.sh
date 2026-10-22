#!/bin/bash
# Overnight: finish the Claude samples at concurrency 1, waiting out quota limits, then grade and analyze.
cd /d/dev/ql-invariants/bench
log() { echo "$(date '+%m-%d %H:%M:%S') $*" >> night.log; }
claude_count() { ls gen/ | grep -cE '^(opus|sonnet)__.*\.raw$'; }

log "start, claude raw=$(claude_count)/30"
for i in $(seq 1 40); do
  [ "$(claude_count)" -ge 30 ] && break
  before=$(wc -l < gen_log_night.txt 2>/dev/null || echo 0)
  python -I gen.py 5 sonnet >> gen_log_night.txt 2>&1
  python -I gen.py 5 opus >> gen_log_night.txt 2>&1
  if tail -n +$((before + 1)) gen_log_night.txt | grep -q "limit"; then
    log "iteration $i: quota limit hit, claude raw=$(claude_count); sleeping 30 min"
    sleep 1800
  else
    log "iteration $i: claude raw=$(claude_count)"
    sleep 60
  fi
done
log "generation loop ended, claude raw=$(claude_count)/30"

../.venv/Scripts/python.exe -I grade.py extract >> grade_log_night.txt 2>&1
../.venv/Scripts/python.exe -I grade.py run >> grade_log_night.txt 2>&1
../.venv/Scripts/python.exe -I analyze.py > analysis.txt 2>&1
log "graded and analyzed; see analysis.txt"
