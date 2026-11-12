"""SegAssist CLI.

  qc   <task> <zip|--cvat>  [--html out.html]     find problems, draw them on the images
  fix  <task> <zip|--cvat>  [-o fixed.zip] [--push --yes]   conservative auto-fix, re-check
"""
from __future__ import annotations

import argparse
import io
import sys
import tempfile
from pathlib import Path

from . import checks, fixes, model, report
from .checks import Config

ICON = {"error": "✖", "warn": "▲", "info": "·"}


def _source(args, info):
    """Return (zip_path, cleanup, cvat_client, task_id)."""
    if args.zip:
        return Path(args.zip), None, None, None
    from .cvat import Cvat
    c = Cvat(args.cvat_url)
    t = c.find_task(args.task)
    kind = "semantic" if info["type"] == "semantic" else "coco"
    data = c.export(t["id"], kind)
    tmp = Path(tempfile.mkdtemp()) / f"{args.task}.zip"
    tmp.write_bytes(data)
    print(f"pulled task '{args.task}' (id {t['id']}) from {args.cvat_url}")
    return tmp, tmp, c, t["id"]


def _print(issues, verbose):
    s = checks.summarize(issues)
    print("summary:", ", ".join(f"{k}={v}" for k, v in s.items()) or "no warnings/errors")
    for it in issues:
        if it.level == "info" and not verbose:
            continue
        print(f" {ICON[it.level]} [{it.image}] {it.code}: {it.msg}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="segassist")
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("qc", "fix"):
        p = sp.add_parser(name)
        p.add_argument("task")
        p.add_argument("zip", nargs="?", help="CVAT export ZIP; omit with --cvat")
        p.add_argument("--cvat", dest="cvat", action="store_true", help="pull from CVAT (needs CVAT_TOKEN)")
        p.add_argument("--cvat-url", default="http://localhost:8081")
        p.add_argument("-v", "--verbose", action="store_true")
        p.add_argument("--html")
        p.add_argument("--speck", type=int, default=Config.speck_px)
        p.add_argument("--pinhole", type=int, default=Config.pinhole_px)
        if name == "fix":
            p.add_argument("-o", "--out")
            p.add_argument("--fill-all-holes", action="store_true", help="instance tasks: fill every hole in thing masks (cp1)")
            p.add_argument("--push", action="store_true", help="upload fixed annotations back into CVAT (replaces them)")
            p.add_argument("--yes", action="store_true", help="confirm --push")
    a = ap.parse_args(argv)
    if not a.zip and not a.cvat:
        ap.error("give a ZIP path or --cvat")
    info = model.task_info(a.task)
    cfg = Config(speck_px=a.speck, pinhole_px=a.pinhole)
    zpath, _, client, tid = _source(a, info)
    sub = model.load(zpath)
    issues = checks.check(sub, info, cfg)
    _print(issues, a.verbose)
    if a.cmd == "qc":
        if a.html:
            Path(a.html).write_text(report.render(sub, info, issues, a.task), encoding="utf-8")
            print("report ->", a.html)
        return 1 if any(i.level == "error" for i in issues) else 0

    stats = fixes.fix(sub, info, cfg, a.fill_all_holes)
    out = Path(a.out or f"{a.task}.fixed.zip")
    model.write(sub, out)
    print("\nfixed:", dict(stats) or "nothing to fix", "->", out)
    after = checks.check(model.load(out), info, cfg)
    print("after fix:"); _print(after, False)
    if a.html:
        fixed = model.load(out)
        Path(a.html).write_text(report.render(fixed, info, after, a.task + " (after fix)"), encoding="utf-8")
        print("report ->", a.html)
    if a.push:
        if not (client and a.yes):
            print("--push needs --cvat and --yes (it REPLACES the task's annotations)."); return 2
        backup = Path(f"{a.task}.backup.zip"); backup.write_bytes(Path(zpath).read_bytes())
        client.import_annotations(tid, "semantic" if info["type"] == "semantic" else "coco", out.read_bytes())
        print(f"pushed to CVAT task {tid}. backup of the original: {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
