#!/usr/bin/env bash
# Ghép các phần split (train.zip.part_*, public_test.zip.part_*) trong repo và giải nén ra .cache/split/<split>/.
# Chạy trong thư mục repo:  bash remote/fetch_data.sh
# Dữ liệu gốc trong repo giữ nguyên (chỉ đọc); bản giải nén nằm ở .cache/ (đã .gitignore).
set -euo pipefail
cd "$(dirname "$0")/.."

dest=.cache/split
tmp=.cache/tmp
mkdir -p "$dest" "$tmp"

for split in train public_test; do
  if [ -d "$dest/$split/data" ]; then
    echo "đã có $dest/$split"
    continue
  fi
  shopt -s nullglob
  parts=("data/$split/$split.zip.part_"*)
  shopt -u nullglob
  if [ "${#parts[@]}" -eq 0 ]; then
    echo "thiếu data/$split/$split.zip.part_* — kiểm tra đã git pull đúng nhánh chưa" >&2
    continue
  fi
  cat "${parts[@]}" > "$tmp/$split.zip"
  uv run python -m zipfile -e "$tmp/$split.zip" "$dest"
  rm -f "$tmp/$split.zip"
  echo "→ $dest/$split ($(find "$dest/$split/data" -mindepth 1 -maxdepth 1 -type d | wc -l) shop)"
done
