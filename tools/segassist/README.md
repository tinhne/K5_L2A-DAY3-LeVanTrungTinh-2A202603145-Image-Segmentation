# SegAssist — QC + tự sửa an toàn cho export CVAT (Day 3)

Chạy từ thư mục repo, dùng `.venv` (numpy, pillow, pycocotools, scipy, shapely):

```bash
# 1) Từ ZIP đã export
.venv/bin/python -m tools.segassist qc easy_semantic submissions/easy_semantic.zip --html qc.html
.venv/bin/python -m tools.segassist fix medium_instance submissions/medium_instance.zip -o fixed.zip

# 2) Nối thẳng CVAT local (8081): tạo Access Token trong CVAT UI rồi tự export
export CVAT_TOKEN=...            # tool không hỏi và không lưu mật khẩu
.venv/bin/python -m tools.segassist qc easy_semantic --cvat --html qc.html
.venv/bin/python -m tools.segassist fix easy_semantic --cvat --push --yes   # ghi ĐÈ annotation, có backup .backup.zip
```

Tool bắt: SPECK (mảnh nhiễu), PINHOLE (lỗ nhỏ), GAP (vùng chưa gán lớn), HOLE (khoét kính/khe, cp1),
SPLIT (một object nhiều mảng: occlusion cp5 hay tách nhầm cp2), DUPLICATE, OVERLAP, TINY_INSTANCE,
BAD_POLYGON, CLASS_NOT_IN_TASK. Tự sửa chỉ phần cơ học (nhiễu, lỗ nhỏ, trùng, chồng lấn thing-thing);
GAP lớn, gộp/tách object, sai class **để người quyết**. `--fill-all-holes` cho cp1.
Instance/panoptic ghi lại dạng RLE (CVAT import thành mask như Brush).
