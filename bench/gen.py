"""Generate pricers: k samples per (model, task). Skips outputs that already exist.

usage: gen.py <k> <model> [<model> ...]      models: opus sonnet deepseek-pro deepseek-flash gemini-pro openai
A reply without a code block is retried once; the failed reply is kept as <name>.try1.
"""
import concurrent.futures as cf, json, os, re, shutil, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
GEN, EMPTY = os.path.join(HERE, "gen"), os.path.join(HERE, "empty")
TASKS = ["T1", "T2", "T3"]
CLAUDE_MODELS = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5"}
NO_TOOLS = ["Bash", "Edit", "Write", "Read", "Glob", "Grep", "WebFetch", "WebSearch", "Agent", "NotebookEdit"]


def post(url, body, headers, timeout=3600):
    req = urllib.request.Request(url, json.dumps(body).encode(), headers)
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def ask(model, prompt):
    if model in CLAUDE_MODELS:
        p = subprocess.run([shutil.which("claude"), "-p", "--model", CLAUDE_MODELS[model], "--disallowedTools", *NO_TOOLS],
                           input=prompt, capture_output=True, text=True, encoding="utf-8", cwd=EMPTY, timeout=5400, shell=False)
        if p.returncode != 0 or not p.stdout.strip() or (
                len(p.stdout) < 300 and re.search(r"hit your (session|usage|weekly) limit", p.stdout, re.I)):
            # CLI failure (process creation, quota, auth): not a model answer
            raise RuntimeError(f"claude rc={p.returncode} out={p.stdout[:100]!r} stderr={p.stderr[-200:]!r}")
        return p.stdout, p.stderr[-500:]
    if model.startswith("deepseek"):
        d = post("https://api.deepseek.com/chat/completions",
                 {"model": "deepseek-v4-pro" if model == "deepseek-pro" else "deepseek-flash", "max_tokens": 250000,
                  "messages": [{"role": "user", "content": prompt}]},
                 {"Content-Type": "application/json", "Authorization": "Bearer " + os.environ["DEEPSEEK_API_KEY"]})
        c = d["choices"][0]
        return c["message"].get("content") or "", json.dumps({"finish": c.get("finish_reason"), "usage": d.get("usage")})
    if model == "gemini-pro":
        # Streaming with thought summaries: the proxy drops connections that stay silent during long
        # thinking (RemoteDisconnected). Summaries only change what is returned, not the computation.
        req = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-pro-preview:streamGenerateContent?alt=sse&key="
            + os.environ["GEMINI_API_KEY"],
            json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"thinkingConfig": {"includeThoughts": True}}}).encode(),
            {"Content-Type": "application/json"})
        text, finish, usage = [], None, None
        with urllib.request.urlopen(req, timeout=3600) as resp:
            for line in resp:
                line = line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                d = json.loads(line[5:])
                for cand in d.get("candidates", []):
                    for p in cand.get("content", {}).get("parts", []):
                        if not p.get("thought"):
                            text.append(p.get("text", ""))
                    finish = cand.get("finishReason") or finish
                usage = d.get("usageMetadata") or usage
        return "".join(text), json.dumps({"finish": finish, "usage": usage, "stream": True})
    if model == "openai":
        out = os.path.join(EMPTY, f"codex_{time.time_ns()}.txt")
        p = subprocess.run([shutil.which("codex"), "exec", "-s", "read-only", "--skip-git-repo-check", "-C", EMPTY, "-o", out, prompt],
                           capture_output=True, text=True, encoding="utf-8", timeout=3600)
        txt = open(out, encoding="utf-8").read() if os.path.exists(out) else ""
        if os.path.exists(out): os.remove(out)
        if p.returncode != 0 or not txt.strip():
            raise RuntimeError(f"codex rc={p.returncode} stderr={p.stderr[-200:]!r}")
        return txt, p.stderr[-500:]
    raise ValueError(model)


def one(model, task, k):
    name = f"{model}__{task}__{k}"; raw = os.path.join(GEN, name + ".raw")
    if os.path.exists(raw):
        return name, "exists"
    prompt = open(os.path.join(HERE, "prompts", task + ".txt"), encoding="utf-8").read()
    for attempt in (1, 2):
        t0 = time.time()
        try:
            txt, meta = ask(model, prompt)
        except Exception as e:
            # infrastructure failure (network, auth, quota): not a model answer, so nothing is recorded
            return name, "INFRA ERROR " + repr(e)[:200]
        meta = json.dumps({"attempt": attempt, "seconds": round(time.time() - t0), "meta": meta})
        if re.search(r"```", txt) or attempt == 2:
            open(raw, "w", encoding="utf-8").write(txt)
            open(os.path.join(GEN, name + ".meta"), "w", encoding="utf-8").write(meta)
            return name, f"attempt {attempt}, {len(txt)} chars"
        open(os.path.join(GEN, name + ".try1"), "w", encoding="utf-8").write(txt + "\n\n<!-- " + meta + " -->")


def main():
    k = int(sys.argv[1]); models = sys.argv[2:]
    os.makedirs(GEN, exist_ok=True); os.makedirs(EMPTY, exist_ok=True)
    workers = {"opus": 4, "sonnet": 1, "deepseek-pro": 8, "deepseek-flash": 8, "gemini-pro": 6, "openai": 2}
    pools = {m: cf.ThreadPoolExecutor(workers[m]) for m in models}
    futs = [pools[m].submit(one, m, t, i) for m in models for t in TASKS for i in range(1, k + 1)]
    for f in cf.as_completed(futs):
        print(*f.result(), flush=True)


if __name__ == "__main__":
    main()
