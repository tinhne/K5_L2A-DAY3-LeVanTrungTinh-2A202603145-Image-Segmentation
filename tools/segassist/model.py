"""Load / write CVAT exports (Segmentation mask 1.1, COCO 1.0) as numpy masks."""
from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import numpy as np
from PIL import Image
from pycocotools import mask as cocomask

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


@dataclass
class Instance:
    cls: str
    mask: np.ndarray                 # HxW bool
    ann_id: int | None = None
    polygons: list | None = None     # raw COCO polygons, if the source had them


@dataclass
class ImageData:
    stem: str
    file_name: str
    h: int
    w: int
    sem: np.ndarray | None = None            # semantic: HxW int16, 0 = unlabeled
    instances: list[Instance] = field(default_factory=list)


@dataclass
class Submission:
    kind: str                                # "semantic" | "coco"
    images: dict[str, ImageData]
    members: dict[str, bytes]                # original zip members (for re-writing)
    sem_names: list[str] = field(default_factory=list)   # semantic: id -> class name
    sem_colors: list[tuple] = field(default_factory=list)
    coco: dict | None = None
    unknown_colors: dict[str, int] = field(default_factory=dict)


# ----------------------------------------------------------------- tasks
def load_registry() -> dict:
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    return manifest["tasks"]


def task_info(name: str) -> dict:
    reg = load_registry()
    if name not in reg:
        raise SystemExit(f"unknown task '{name}'. known: {', '.join(sorted(reg))}")
    info = dict(reg[name])
    base = DATA / info["path"]
    classes = json.loads((base / "classes.json").read_text(encoding="utf-8"))
    info.update(name=name, base=base, classes=classes["classes"],
                stuff=classes.get("stuff", []))
    return info


def find_image(info: dict, file_name: str):
    p = info["base"] / "images" / Path(file_name).name
    return p if p.exists() else None


# ------------------------------------------------------------------ read
def read_members(path) -> dict[str, bytes]:
    out = {}
    with zipfile.ZipFile(path) as z:
        for item in z.infolist():
            if item.is_dir():
                continue
            p = PurePosixPath(item.filename)
            if p.is_absolute() or ".." in p.parts:
                raise ValueError(f"unsafe path in zip: {item.filename}")
            out[item.filename] = z.read(item)
    return out


def parse_labelmap(text: str):
    names, colors = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) < 2 or not parts[1]:
            continue
        try:
            rgb = tuple(int(x) for x in parts[1].split(","))
        except ValueError:
            continue
        names.append(parts[0]); colors.append(rgb)
    return names, colors


def load(path) -> Submission:
    members = read_members(path)
    if any(k.endswith("labelmap.txt") for k in members):
        return _load_semantic(members)
    return _load_coco(members)


def _load_semantic(members) -> Submission:
    key = next(k for k in members if k.endswith("labelmap.txt"))
    names, colors = parse_labelmap(members[key].decode("utf-8", "ignore"))
    if "background" not in names:
        names.insert(0, "background"); colors.insert(0, (0, 0, 0))
    bg = names.index("background")
    # ids: 0 = background/unlabeled, others by labelmap order
    order = [bg] + [i for i in range(len(names)) if i != bg]
    names = [names[i] for i in order]; colors = [colors[i] for i in order]
    sub = Submission("semantic", {}, members, names, colors)
    for k, b in members.items():
        if "SegmentationClass/" not in k or not k.lower().endswith(".png"):
            continue
        rgb = np.array(Image.open(io.BytesIO(b)).convert("RGB"))
        lab = np.zeros(rgb.shape[:2], np.int16)
        known = np.zeros(rgb.shape[:2], bool)
        for i, (r, g, bl) in enumerate(colors):
            m = (rgb[..., 0] == r) & (rgb[..., 1] == g) & (rgb[..., 2] == bl)
            lab[m] = i; known |= m
        stem = Path(k).stem
        if (~known).any():
            sub.unknown_colors[stem] = int((~known).sum())
        h, w = lab.shape
        sub.images[stem] = ImageData(stem, stem + ".jpg", h, w, sem=lab)
    return sub


def rasterize(seg, h, w):
    if isinstance(seg, list):
        if not seg:
            return None
        rle = cocomask.merge(cocomask.frPyObjects(seg, h, w))
    elif isinstance(seg.get("counts"), list):
        rle = cocomask.frPyObjects(seg, h, w)
    else:
        rle = seg
    return cocomask.decode(rle).astype(bool)


def _load_coco(members) -> Submission:
    cands = [k for k in members if k.endswith(".json")]
    if not cands:
        raise ValueError("no labelmap.txt or COCO json found in zip")
    key = sorted(cands, key=lambda k: ("annotation" not in k.lower(), len(k)))[0]
    coco = json.loads(members[key].decode("utf-8"))
    cats = {c["id"]: c["name"] for c in coco["categories"]}
    sub = Submission("coco", {}, members, coco=coco)
    sub.members_json_key = key  # type: ignore[attr-defined]
    for im in coco["images"]:
        sub.images[Path(im["file_name"]).stem] = ImageData(
            Path(im["file_name"]).stem, im["file_name"], im["height"], im["width"])
    by_id = {im["id"]: im for im in coco["images"]}
    for a in coco["annotations"]:
        im = by_id[a["image_id"]]
        m = rasterize(a.get("segmentation"), im["height"], im["width"]) \
            if a.get("segmentation") is not None else None
        if m is None:
            continue
        seg = a["segmentation"]
        sub.images[Path(im["file_name"]).stem].instances.append(
            Instance(cats.get(a["category_id"], f"?{a['category_id']}"), m, a.get("id"),
                     seg if isinstance(seg, list) else None))
    return sub


# ----------------------------------------------------------------- write
def _mask_to_ann(mask: np.ndarray):
    """Compressed RLE with iscrowd=1: CVAT imports it as a mask object (like the Brush tool)."""
    rle = cocomask.encode(np.asfortranarray(mask.astype(np.uint8)))
    rle["counts"] = rle["counts"].decode("ascii")
    return rle, 1


def write(sub: Submission, out_path) -> None:
    members = dict(sub.members)
    if sub.kind == "semantic":
        for stem, img in sub.images.items():
            rgb = np.zeros((img.h, img.w, 3), np.uint8)
            for i, c in enumerate(sub.sem_colors):
                rgb[img.sem == i] = c
            buf = io.BytesIO(); Image.fromarray(rgb).save(buf, "PNG")
            for k in list(members):
                if Path(k).stem == stem and ("SegmentationClass/" in k or "SegmentationObject/" in k):
                    members[k] = buf.getvalue()
    else:
        coco = json.loads(json.dumps(sub.coco))
        cat_id = {c["name"]: c["id"] for c in coco["categories"]}
        id_of = {Path(im["file_name"]).stem: im["id"] for im in coco["images"]}
        anns, nxt = [], 1
        for stem, img in sub.images.items():
            for inst in img.instances:
                seg, crowd = _mask_to_ann(inst.mask)
                ys, xs = np.where(inst.mask)
                if not len(xs):
                    continue
                x0, y0 = int(xs.min()), int(ys.min())
                anns.append({
                    "id": nxt, "image_id": id_of[stem], "category_id": cat_id[inst.cls],
                    "segmentation": seg, "area": float(inst.mask.sum()), "iscrowd": crowd,
                    "bbox": [x0, y0, int(xs.max()) - x0 + 1, int(ys.max()) - y0 + 1],
                    "attributes": {"occluded": False}})
                nxt += 1
        coco["annotations"] = anns
        members[sub.members_json_key] = json.dumps(coco).encode("utf-8")  # type: ignore[attr-defined]
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for k, b in members.items():
            z.writestr(k, b)
