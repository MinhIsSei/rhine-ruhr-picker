"""Optional remote storage for my_choices.csv, so choices survive on Streamlit Community Cloud.
Without the [github] secrets (e.g. when running on your own PC) nothing happens and the local file is used.

Secrets (Streamlit Cloud -> app settings -> Secrets, or .streamlit/secrets.toml locally):
    [github]
    token = "github_pat_..."          # fine-grained token, Contents: read & write, only on the data repo
    repo  = "your-name/rhine-ruhr-data"   # a PRIVATE repo that only holds your choices
"""
import base64, json, os, urllib.error, urllib.request

import streamlit as st

def _cfg():
    try:
        return st.secrets["github"]
    except Exception:
        return None

def enabled():
    return _cfg() is not None

def _call(method, path, body=None):
    cfg = _cfg()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{cfg['repo']}/contents/{path}",
        data=json.dumps(body).encode() if body else None, method=method,
        headers={"Authorization": f"Bearer {cfg['token']}", "Accept": "application/vnd.github+json",
                 "User-Agent": "rhine-ruhr-picker"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise

def pull(local_path):
    """Download the remote copy over the local file (call once per session)."""
    if not enabled():
        return
    res = _call("GET", os.path.basename(local_path))
    if res:
        with open(local_path, "wb") as f:
            f.write(base64.b64decode(res["content"]))
    elif os.path.exists(local_path):
        os.remove(local_path)  # nothing stored remotely yet: start clean

def push(local_path):
    """Upload the local file (or delete the remote one if the local file is gone)."""
    if not enabled():
        return
    name = os.path.basename(local_path)
    cur = _call("GET", name)
    sha = {"sha": cur["sha"]} if cur else {}
    if os.path.exists(local_path):
        _call("PUT", name, {"message": "update choices",
                            "content": base64.b64encode(open(local_path, "rb").read()).decode(), **sha})
    elif cur:
        _call("DELETE", name, {"message": "delete choices", **sha})
