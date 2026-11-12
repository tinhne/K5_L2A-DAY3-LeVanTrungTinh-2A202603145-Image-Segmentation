"""Rule-based QC for CVAT segmentation exports. Finds problems; never judges 'correct'."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage as ndi
from shapely.geometry import Polygon

from .model import ImageData, Submission


@dataclass
class Config:
    speck_px: int = 40            # components smaller than this are noise
    pinhole_px: int = 60          # holes / unlabeled gaps smaller than this are fixable
    gap_report_frac: float = 0.002  # unlabeled region >= this fraction of image is reported
    split_min_frac: float = 0.02  # each part >= this fraction of an instance => "split"
    overlap_frac: float = 0.05    # thing/thing overlap above this fraction of smaller mask
    dup_iou: float = 0.85


@dataclass
class Issue:
    code: str
    level: str                    # error | warn | info
    image: str
    msg: str
    cls: str | None = None
    bbox: tuple | None = None     # x0,y0,x1,y1
    fixable: bool = False


def _bbox(mask):
    ys, xs = np.where(mask)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1) if len(xs) else None


def _comps(mask):
    lab, n = ndi.label(mask)
    if n == 0:
        return lab, []
    return lab, list(ndi.sum(mask, lab, index=range(1, n + 1)).astype(int))


def check(sub: Submission, info: dict, cfg: Config = Config()) -> list[Issue]:
    issues: list[Issue] = []
    allowed = set(info["classes"])
    if sub.kind == "semantic":
        for name in sub.sem_names[1:]:
            if name not in allowed:
                issues.append(Issue("CLASS_NOT_IN_TASK", "error", "-", f"class '{name}' is not in classes.json"))
        for stem, n in sub.unknown_colors.items():
            issues.append(Issue("UNKNOWN_COLOR", "warn", stem, f"{n} px have a colour missing from labelmap.txt"))
    for img in sub.images.values():
        if sub.kind == "semantic":
            _semantic(img, sub, allowed, cfg, issues)
        else:
            _instances(img, info, cfg, issues)
    return issues


def _semantic(img: ImageData, sub, allowed, cfg, issues):
    lab, area = img.sem, img.h * img.w
    present = set(np.unique(lab).tolist()) - {0}
    for cid, name in enumerate(sub.sem_names):
        if cid and name in allowed and cid not in present:
            issues.append(Issue("CLASS_ABSENT", "info", img.stem, f"'{name}' has no pixels in this image", name))
    for cid in present:
        name = sub.sem_names[cid]
        _, sizes = _comps(lab == cid)
        specks = [s for s in sizes if s < cfg.speck_px]
        if specks:
            comp_lab, _ = _comps(lab == cid)
            bad = np.isin(comp_lab, [i + 1 for i, s in enumerate(sizes) if s < cfg.speck_px])
            issues.append(Issue("SPECK", "warn", img.stem, f"{len(specks)} stray fragment(s) < {cfg.speck_px}px", name, _bbox(bad), True))
    unl_lab, sizes = _comps(lab == 0)
    covered = 1 - (lab == 0).sum() / area
    issues.append(Issue("COVERAGE", "info", img.stem, f"{covered:.1%} of pixels labelled"))
    gaps = [(s, i + 1) for i, s in enumerate(sizes) if s >= cfg.gap_report_frac * area]
    for s, comp in sorted(gaps, reverse=True)[:6]:
        issues.append(Issue("GAP", "warn", img.stem,
                            f"unlabeled region {s / area:.1%} of image — a task class missing here? (ego-car/other classes may be legitimately empty)",
                            None, _bbox(unl_lab == comp)))
    small = [i + 1 for i, s in enumerate(sizes) if s < cfg.pinhole_px]
    # only gaps enclosed by labelled pixels are real pinholes; border bits are skipped
    if small:
        m = np.isin(unl_lab, small)
        issues.append(Issue("PINHOLE", "warn", img.stem, f"{len(small)} tiny unlabeled gap(s) < {cfg.pinhole_px}px", None, _bbox(m), True))


def _instances(img: ImageData, info, cfg, issues):
    stuff, allowed = set(info["stuff"]), set(info["classes"])
    ins = img.instances
    counts: dict[str, int] = {}
    for k, it in enumerate(ins):
        counts[it.cls] = counts.get(it.cls, 0) + 1
        tag = f"{it.cls} #{k + 1}"
        if it.cls not in allowed:
            issues.append(Issue("CLASS_NOT_IN_TASK", "error", img.stem, f"{tag}: class not in classes.json", it.cls, _bbox(it.mask)))
        area = int(it.mask.sum())
        if area < cfg.speck_px:
            issues.append(Issue("TINY_INSTANCE", "warn", img.stem, f"{tag}: only {area}px", it.cls, _bbox(it.mask), True))
            continue
        lab, sizes = _comps(it.mask)
        big = [i + 1 for i, s in enumerate(sizes) if s >= cfg.split_min_frac * area]
        tiny = [i + 1 for i, s in enumerate(sizes) if s < cfg.speck_px]
        if tiny:
            issues.append(Issue("SPECK", "warn", img.stem, f"{tag}: {len(tiny)} stray fragment(s)", it.cls, _bbox(np.isin(lab, tiny)), True))
        if len(big) >= 2:
            level = "info" if it.cls in stuff else "warn"
            issues.append(Issue("SPLIT", level,
                                img.stem, f"{tag}: {len(big)} separate parts. OK if one object is occluded (cp5); if two objects were merged/split wrongly (cp2), fix",
                                it.cls, _bbox(it.mask)))
        filled = ndi.binary_fill_holes(it.mask)
        holes = filled & ~it.mask
        if holes.any():
            hl, hs = _comps(holes)
            small_h = [i + 1 for i, s in enumerate(hs) if s < cfg.pinhole_px]
            big_h = len(hs) - len(small_h)
            if small_h:
                issues.append(Issue("PINHOLE", "warn", img.stem, f"{tag}: {len(small_h)} tiny hole(s)", it.cls, _bbox(np.isin(hl, small_h)), True))
            if big_h and it.cls not in stuff:
                issues.append(Issue("HOLE", "warn", img.stem,
                                    f"{tag}: {big_h} hole(s) cut out. Windows/gaps usually stay INSIDE the mask (cp1)",
                                    it.cls, _bbox(holes & ~np.isin(hl, small_h))))
        if it.polygons:
            for poly in it.polygons:
                pts = np.array(poly).reshape(-1, 2)
                if len(pts) < 3:
                    issues.append(Issue("BAD_POLYGON", "error", img.stem, f"{tag}: polygon has <3 points", it.cls, _bbox(it.mask)))
                elif not Polygon(pts).is_valid:
                    issues.append(Issue("BAD_POLYGON", "warn", img.stem, f"{tag}: self-intersecting polygon", it.cls, _bbox(it.mask), True))
    for cls, n in counts.items():
        if cls not in stuff and n:
            issues.append(Issue("COUNT", "info", img.stem, f"{n} x {cls}", cls))
    # pairwise overlaps (thing over stuff is normal; skip it)
    for i in range(len(ins)):
        for j in range(i + 1, len(ins)):
            a, b = ins[i], ins[j]
            if a.cls in stuff and b.cls not in stuff or b.cls in stuff and a.cls not in stuff:
                continue
            inter = a.mask & b.mask
            ia = int(inter.sum())
            if not ia:
                continue
            union = int((a.mask | b.mask).sum())
            frac = ia / max(1, min(int(a.mask.sum()), int(b.mask.sum())))
            if a.cls == b.cls and ia / union >= cfg.dup_iou:
                issues.append(Issue("DUPLICATE", "error", img.stem,
                                    f"{a.cls} #{i + 1} and #{j + 1} are near-identical (IoU {ia / union:.2f})", a.cls, _bbox(inter), True))
            elif frac >= cfg.overlap_frac:
                issues.append(Issue("OVERLAP", "warn", img.stem,
                                    f"{a.cls} #{i + 1} overlaps {b.cls} #{j + 1} by {frac:.0%} of the smaller mask",
                                    a.cls, _bbox(inter), True))


def summarize(issues: list[Issue]) -> dict:
    out: dict[str, int] = {}
    for it in issues:
        if it.level != "info":
            out[it.code] = out.get(it.code, 0) + 1
    return out
