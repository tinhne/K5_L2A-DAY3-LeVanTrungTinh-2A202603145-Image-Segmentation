"""Tiny CVAT REST client (stdlib only) for a local server.

Auth: create a Personal Access Token in the CVAT UI (user menu -> Settings -> Access tokens)
and export it yourself:  export CVAT_TOKEN=...   (the tool never asks for or stores a password).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

FORMATS = {"semantic": "Segmentation mask 1.1", "coco": "COCO 1.0"}


class CvatError(RuntimeError):
    pass


class Cvat:
    def __init__(self, base="http://localhost:8081", token=None, scheme=None):
        self.base = base.rstrip("/")
        self.token = token or os.environ.get("CVAT_TOKEN")
        if not self.token:
            raise CvatError("set CVAT_TOKEN (personal access token from the CVAT UI)")
        self.scheme = scheme or os.environ.get("CVAT_AUTH_SCHEME", "Bearer")

    def _req(self, method, path, data=None, headers=None, raw=False):
        h = {"Authorization": f"{self.scheme} {self.token}", **(headers or {})}
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                body = r.read()
                return r.status, (body if raw else (json.loads(body) if body else {}))
        except urllib.error.HTTPError as e:
            if e.code == 401 and self.scheme == "Bearer" and not os.environ.get("CVAT_AUTH_SCHEME"):
                self.scheme = "Token"           # older servers / legacy auth keys
                return self._req(method, path, data, headers, raw)
            raise CvatError(f"{method} {path} -> HTTP {e.code}: {e.read()[:300]!r}") from None

    def find_task(self, name: str) -> dict:
        q = urllib.parse.urlencode({"search": name, "page_size": 50})
        _, res = self._req("GET", f"/api/tasks?{q}")
        hits = [t for t in res.get("results", []) if t["name"] == name]
        if not hits:
            raise CvatError(f"no CVAT task named '{name}'")
        return hits[0]

    def _wait(self, rq_id, timeout=300):
        end = time.time() + timeout
        while time.time() < end:
            _, r = self._req("GET", f"/api/requests/{rq_id}")
            if r.get("status") == "finished":
                return r
            if r.get("status") == "failed":
                raise CvatError(f"CVAT request failed: {r.get('message')}")
            time.sleep(1.5)
        raise CvatError("timed out waiting for CVAT")

    def export(self, task_id: int, kind: str) -> bytes:
        fmt = urllib.parse.quote(FORMATS[kind])
        _, res = self._req("POST", f"/api/tasks/{task_id}/dataset/export?format={fmt}&save_images=false")
        done = self._wait(res["rq_id"])
        url = done["result_url"]
        path = url[len(self.base):] if url.startswith(self.base) else url
        return self._req("GET", path, raw=True)[1]

    def import_annotations(self, task_id: int, kind: str, zip_bytes: bytes):
        """Replaces the task's annotations with the zip's content (server-side import)."""
        fmt = urllib.parse.quote(FORMATS[kind])
        b = uuid.uuid4().hex
        body = (f"--{b}\r\nContent-Disposition: form-data; name=\"annotation_file\"; filename=\"fixed.zip\"\r\n"
                "Content-Type: application/zip\r\n\r\n").encode() + zip_bytes + f"\r\n--{b}--\r\n".encode()
        _, res = self._req("PUT", f"/api/tasks/{task_id}/annotations?format={fmt}", body,
                           {"Content-Type": f"multipart/form-data; boundary={b}"})
        if isinstance(res, dict) and res.get("rq_id"):
            self._wait(res["rq_id"])
