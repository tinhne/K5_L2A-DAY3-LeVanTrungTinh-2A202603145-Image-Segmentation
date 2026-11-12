"""Single-file HTML report: each image with issue boxes drawn on it."""
from __future__ import annotations

import base64
import html
import io

import numpy as np
from PIL import Image, ImageDraw

from .checks import Issue, summarize
from .model import Submission, find_image

COLORS = {"error": (230, 40, 40), "warn": (255, 170, 0), "info": (80, 160, 255)}


def _palette(n):
    rng = np.random.RandomState(7)
    return [tuple(int(v) for v in rng.randint(60, 255, 3)) for _ in range(n)]


def _overlay(sub: Submission, info, img, issues):
    p = find_image(info, img.file_name)
    base = Image.open(p).convert("RGB").resize((img.w, img.h)) if p else Image.new("RGB", (img.w, img.h), (90, 90, 90))
    arr = np.array(base).astype(np.float32)
    if sub.kind == "semantic":
        pal = _palette(len(sub.sem_names))
        for cid in np.unique(img.sem):
            if cid:
                arr[img.sem == cid] = arr[img.sem == cid] * 0.55 + np.array(pal[cid]) * 0.45
    else:
        classes = sorted({i.cls for i in img.instances})
        pal = dict(zip(classes, _palette(len(classes))))
        for it in img.instances:
            arr[it.mask] = arr[it.mask] * 0.6 + np.array(pal[it.cls]) * 0.4
    out = Image.fromarray(arr.astype(np.uint8))
    d = ImageDraw.Draw(out)
    n = 0
    for it in issues:
        if it.bbox and it.level != "info":
            n += 1
            d.rectangle(it.bbox, outline=COLORS[it.level], width=max(2, img.w // 400))
            d.text((it.bbox[0] + 3, it.bbox[1] + 2), str(n), fill=(255, 255, 255))
    out.thumbnail((1100, 1100))
    buf = io.BytesIO(); out.save(buf, "JPEG", quality=82)
    return base64.b64encode(buf.getvalue()).decode()


def render(sub: Submission, info: dict, issues: list[Issue], title: str) -> str:
    summ = summarize(issues)
    parts = [f"<h1>SegAssist QC — {html.escape(title)}</h1>",
             "<p>" + (" · ".join(f"<b>{k}</b> {v}" for k, v in summ.items()) or "No warnings/errors") + "</p>",
             "<p class=n>Boxes: red = error, orange = warning. Numbers match the list. This report finds suspicious spots; you decide what is right.</p>"]
    for stem, img in sub.images.items():
        its = [i for i in issues if i.image in (stem,)]
        parts.append(f"<h2>{html.escape(img.file_name)}</h2>")
        parts.append(f"<img src='data:image/jpeg;base64,{_overlay(sub, info, img, its)}'>")
        rows, n = [], 0
        for it in its:
            num = ""
            if it.bbox and it.level != "info":
                n += 1; num = str(n)
            rows.append(f"<tr class={it.level}><td>{num}</td><td>{it.code}</td><td>{html.escape(it.msg)}</td></tr>")
        parts.append("<table>" + "".join(rows) + "</table>")
    glob = [i for i in issues if i.image == "-"]
    if glob:
        parts.append("<h2>Task-level</h2><table>" + "".join(
            f"<tr class={i.level}><td></td><td>{i.code}</td><td>{html.escape(i.msg)}</td></tr>" for i in glob) + "</table>")
    css = ("body{font:14px system-ui;margin:24px auto;max-width:1150px;padding:0 16px}img{max-width:100%;border-radius:6px}"
           "table{border-collapse:collapse;width:100%;margin:8px 0 24px}td{padding:4px 8px;border-bottom:1px solid #ddd}"
           "tr.error td{background:#fde8e8}tr.warn td{background:#fff4dc}tr.info td{color:#667}.n{color:#667}")
    return f"<!doctype html><meta charset=utf-8><title>SegAssist QC</title><style>{css}</style>" + "".join(parts)
