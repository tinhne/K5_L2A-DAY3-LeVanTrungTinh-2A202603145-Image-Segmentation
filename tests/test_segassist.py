"""SegAssist on synthetic CVAT-shaped exports with injected defects."""
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image
from pycocotools import mask as cocomask

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.segassist import checks, cli, fixes, model  # noqa: E402

H, W = 200, 300


def _semantic_zip(path, stem="7ee6d192-89e2408b"):
    lab = np.zeros((H, W, 3), np.uint8)
    colors = {"road": (128, 64, 128), "sky": (70, 130, 180)}
    lab[:100] = colors["sky"]
    lab[100:] = colors["road"]
    lab[50:53, 50:53] = colors["road"]        # speck of road inside sky
    lab[150:154, 100:104] = (0, 0, 0)         # pinhole in road
    lab[100:140, 200:300] = (0, 0, 0)         # big unlabeled gap
    buf = io.BytesIO(); Image.fromarray(lab).save(buf, "PNG")
    labelmap = "background:0,0,0::\nroad:128,64,128::\nsky:70,130,180::\n"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("labelmap.txt", labelmap)
        z.writestr(f"SegmentationClass/{stem}.png", buf.getvalue())
        z.writestr(f"SegmentationObject/{stem}.png", buf.getvalue())


def _rect(y0, y1, x0, x1):
    m = np.zeros((H, W), bool); m[y0:y1, x0:x1] = True
    return m


def _coco_zip(path, masks, stem="000000181542"):
    cats = [{"id": 1, "name": "person"}, {"id": 3, "name": "car"}]
    anns = []
    for i, (cid, m) in enumerate(masks, 1):
        rle = cocomask.encode(np.asfortranarray(m.astype(np.uint8)))
        rle["counts"] = rle["counts"].decode()
        anns.append({"id": i, "image_id": 1, "category_id": cid, "segmentation": rle,
                     "area": float(m.sum()), "iscrowd": 1, "bbox": [0, 0, 1, 1]})
    coco = {"images": [{"id": 1, "file_name": f"{stem}.jpg", "height": H, "width": W}],
            "categories": cats, "annotations": anns}
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("annotations/instances_default.json", json.dumps(coco))


class SegAssist(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_semantic_detects_and_fixes(self):
        info = model.task_info("easy_semantic")
        z = self.dir / "s.zip"; _semantic_zip(z)
        sub = model.load(z)
        codes = {i.code for i in checks.check(sub, info)}
        self.assertTrue({"SPECK", "PINHOLE", "GAP"} <= codes, codes)
        out = self.dir / "s.fixed.zip"
        sub = model.load(z)
        stats = fixes.fix(sub, info)
        model.write(sub, out)
        self.assertGreater(stats["speck"], 0)
        after = checks.check(model.load(out), info)
        after_codes = {i.code for i in after}
        self.assertNotIn("SPECK", after_codes)
        self.assertNotIn("PINHOLE", after_codes)
        self.assertIn("GAP", after_codes)         # big gaps are left to the human
        lab = model.load(out).images["7ee6d192-89e2408b"].sem
        self.assertTrue((lab[50:53, 50:53] == model.load(z).sem_names.index("sky")).all())

    def test_instance_detects_and_fixes(self):
        info = model.task_info("medium_instance")
        car = _rect(100, 160, 20, 120)
        ring = car.copy(); ring[120:130, 50:60] = False           # big hole (window cut out)
        dup = car.copy()
        near = _rect(100, 160, 100, 200)                          # overlaps car by 20 cols
        z = self.dir / "c.zip"
        _coco_zip(z, [(3, ring), (3, dup), (3, near), (1, _rect(10, 12, 10, 12))])
        sub = model.load(z)
        codes = {i.code for i in checks.check(sub, info)}
        self.assertTrue({"DUPLICATE", "OVERLAP", "HOLE", "TINY_INSTANCE"} <= codes, codes)
        sub = model.load(z)
        fixes.fix(sub, info, fill_all_holes=True)
        out = self.dir / "c.fixed.zip"; model.write(sub, out)
        fixed = model.load(out)
        after = {i.code for i in checks.check(fixed, info)}
        self.assertFalse(after & {"DUPLICATE", "OVERLAP", "HOLE", "TINY_INSTANCE"}, after)
        self.assertEqual(len(fixed.images["000000181542"].instances), 2)

    def test_clean_input_has_no_warnings(self):
        info = model.task_info("medium_instance")
        z = self.dir / "k.zip"; _coco_zip(z, [(3, _rect(100, 160, 20, 120)), (1, _rect(20, 80, 200, 230))])
        issues = checks.check(model.load(z), info)
        self.assertEqual(checks.summarize(issues), {})

    def test_cli_qc_and_report(self):
        z = self.dir / "s.zip"; _semantic_zip(z)
        html = self.dir / "r.html"
        cli.main(["qc", "easy_semantic", str(z), "--html", str(html)])
        self.assertIn("SegAssist QC", html.read_text())


if __name__ == "__main__":
    unittest.main()
