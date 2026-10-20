"""Minimal Arbitrum JSON-RPC helpers (read-only: eth_call / eth_getLogs / receipts)."""
import json, time, urllib.request

RPC = "https://arb1.arbitrum.io/rpc"


class RpcError(RuntimeError):
    """The node answered with an error (e.g. a revert): not retried."""


def rpc(method, params):
    for attempt in range(5):
        try:
            req = urllib.request.Request(RPC, json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                         {"Content-Type": "application/json", "User-Agent": "ql-invariants-audit/0.1"})
            d = json.load(urllib.request.urlopen(req, timeout=60))
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)
            continue
        if "error" in d:
            raise RpcError(d["error"])
        return d["result"]


def call(to, data, block="latest"):
    return rpc("eth_call", [{"to": to, "data": data}, block])
