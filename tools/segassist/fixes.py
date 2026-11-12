"""Safe, conservative auto-fixes. Anything judgement-based (big gaps, merged objects,
wrong class) is deliberately left for the human."""
from __future__ import annotations

from collections import Counter

import numpy as np
from scipy import ndimage as ndi

from .checks import Config, _comps
from .model import ImageData, Instance, Submission


def _nearest_fill(lab: np.ndarray, refill: np.ndarray) -> np.ndarray:
    """Give `refill` pixels the label of the nearest labelled pixel outside refill."""
    valid = (lab != 0) & ~refill
    if not valid.any():
        return lab
    _, (iy, ix) = ndi.distance_transform_edt(~valid, return_indices=True)
    out = lab.copy()
    out[refill] = lab[iy[refill], ix[refill]]
    return out


def fix_semantic(img: ImageData, cfg: Config, stats: Counter):
    lab = img.sem
    refill = np.zeros(lab.shape, bool)
    for cid in np.unique(lab):
        if cid == 0:
            continue
        cl, sizes = _comps(lab == cid)
        for i, s in enumerate(sizes):
            if s < cfg.speck_px:
                refill |= cl == i + 1; stats["speck"] += 1
    unl, sizes = _comps(lab == 0)
    for i, s in enumerate(sizes):
        if s < cfg.pinhole_px:
            refill |= unl == i + 1; stats["pinhole"] += 1
    if refill.any():
        img.sem = _nearest_fill(np.where(refill & (lab != 0), 0, lab), refill)


def fix_instances(img: ImageData, info: dict, cfg: Config, stats: Counter, fill_all_holes=False):
    stuff = set(info["stuff"])
    kept: list[Instance] = []
    for it in img.instances:
        m = it.mask.copy()
        cl, sizes = _comps(m)
        for i, s in enumerate(sizes):
            if s < cfg.speck_px:
                m[cl == i + 1] = False; stats["speck"] += 1
        holes = ndi.binary_fill_holes(m) & ~m
        if holes.any():
            hl, hs = _comps(holes)
            for i, s in enumerate(hs):
                if s < cfg.pinhole_px or (fill_all_holes and it.cls not in stuff):
                    m[hl == i + 1] = True; stats["pinhole"] += 1
        if m.sum() < cfg.speck_px:
            stats["tiny_instance"] += 1
            continue
        kept.append(Instance(it.cls, m, it.ann_id))
    # drop near-duplicates (same class), keep the first
    final: list[Instance] = []
    for it in kept:
        dup = False
        for o in final:
            if o.cls == it.cls:
                u = int((o.mask | it.mask).sum())
                if u and (o.mask & it.mask).sum() / u >= cfg.dup_iou:
                    dup = True; break
        if dup:
            stats["duplicate"] += 1
        else:
            final.append(it)
    # thing/thing and same-stuff overlaps: smaller mask wins the pixels (mirrors the scorer)
    order = sorted(range(len(final)), key=lambda k: int(final[k].mask.sum()))
    for a_pos, a in enumerate(order):
        for b in order[a_pos + 1:]:
            A, B = final[a], final[b]
            if (A.cls in stuff) != (B.cls in stuff):
                continue
            inter = A.mask & B.mask
            if inter.any():
                B.mask = B.mask & ~inter; stats["overlap_px"] += int(inter.sum())
    img.instances = [it for it in final if it.mask.sum() >= cfg.speck_px]


def fix(sub: Submission, info: dict, cfg: Config = Config(), fill_all_holes=False) -> Counter:
    stats: Counter = Counter()
    for img in sub.images.values():
        if sub.kind == "semantic":
            fix_semantic(img, cfg, stats)
        else:
            fix_instances(img, info, cfg, stats, fill_all_holes)
    return stats
