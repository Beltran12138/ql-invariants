#!/bin/bash
# usage: gen.sh <A|B>
P=/d/dev/ql-invariants/pilot_ai; X=$1; PR="$(cat $P/prompts/$X.txt)"; cd $P/empty
( claude -p --model claude-opus-5-5 --tools "" "$PR" > $P/gen/claude_$X.raw 2>$P/gen/claude_$X.err ) &
( codex exec -s read-only --skip-git-repo-check -C $P/empty -o $P/gen/openai_$X.raw "$PR" > /dev/null 2>$P/gen/openai_$X.err ) &
( grok -p "$PR" > $P/gen/grok_$X.raw 2>$P/gen/grok_$X.err ) &
( python -I - "$X" <<'PY'
import json, os, sys, urllib.request
X = sys.argv[1]; P = "D:/dev/ql-invariants/pilot_ai"; pr = open(f"{P}/prompts/{X}.txt").read()
def post(url, body, headers):
    req = urllib.request.Request(url, json.dumps(body).encode(), headers)
    return json.load(urllib.request.urlopen(req, timeout=600))
try:
    d = post("https://api.deepseek.com/chat/completions", {"model": "deepseek-v4-pro", "messages": [{"role": "user", "content": pr}]},
             {"Content-Type": "application/json", "Authorization": "Bearer " + os.environ["DEEPSEEK_API_KEY"]})
    open(f"{P}/gen/deepseek_{X}.raw", "w", encoding="utf-8").write(d["choices"][0]["message"]["content"])
except Exception as e: open(f"{P}/gen/deepseek_{X}.err", "w").write(repr(e))
try:
    d = post("https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-pro-preview:generateContent?key=" + os.environ["GEMINI_API_KEY"],
             {"contents": [{"parts": [{"text": pr}]}]}, {"Content-Type": "application/json"})
    open(f"{P}/gen/gemini_{X}.raw", "w", encoding="utf-8").write("".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"]))
except Exception as e: open(f"{P}/gen/gemini_{X}.err", "w").write(repr(e))
PY
) &
wait
