#!/usr/bin/env bash
# Đóng gói mã + các phần split của dữ liệu train để upload làm Kaggle Dataset khi notebook không có Internet.
# Chạy trên máy bạn, trong repo:  bash kaggle/pack_repo.sh   ->  kaggle/datamate_code.zip
set -euo pipefail
cd "$(dirname "$0")/.."
out=kaggle/datamate_code.zip
rm -f "$out"   # chỉ xoá gói zip cũ do chính script này tạo
# mã đã commit, không kèm lịch sử git và không kèm thư mục dữ liệu (các phần split thêm riêng bên dưới)
git archive --format=zip --prefix=datamate/ -o "$out" HEAD -- . ':!data' ':!kaggle/datamate_code.zip'
if ls data/train/train.zip.part_* >/dev/null 2>&1; then
  zip -q -r "$out" data/train/train.zip.part_* data/train/rulebook.md data/train/calendar.csv
fi
ls -lh "$out"
