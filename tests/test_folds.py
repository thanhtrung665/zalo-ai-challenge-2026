from __future__ import annotations

from datamate.eval.folds import infer_industry, make_folds


def test_infer_industry_keywords() -> None:
    assert infer_industry("Thuốc Panadol hộp 10 vỉ, hoạt chất paracetamol, thuốc kê đơn") == "pharmacy"
    assert infer_industry("Xi măng Hà Tiên bao 50kg, gạch ống, thép cuộn") == "building_materials"
    assert infer_industry("Cà phê sữa (M), trà sữa trân châu, bạc xỉu") == "cafe"
    assert infer_industry("đĩa mực nướng, rau muống xào tỏi, cánh gà chiên nước mắm, phí phục vụ") == "restaurant"
    assert infer_industry("số đơn hôm nay là bao nhiêu") == "unknown"


def _fake(n_shops: int) -> tuple[dict, dict]:
    inds = ["pharmacy", "cafe", "grocery", "restaurant", "building_materials"]
    by_biz = {f"s{i:02d}": [{"id": f"s{i:02d}_q{j}"} for j in range(40 if i % 4 == 0 else 118)] for i in range(n_shops)}
    industries = {b: inds[i % len(inds)] for i, b in enumerate(sorted(by_biz))}
    return by_biz, industries


def test_folds_disjoint_complete_and_deterministic() -> None:
    by_biz, industries = _fake(30)
    a = make_folds(by_biz, industries)
    b = make_folds(by_biz, industries)
    assert a == b
    groups = [set(f["businesses"]) for f in a["folds"]] + [set(a["locked"]["businesses"])]
    assert sum(len(g) for g in groups) == len(set().union(*groups)) == 30
    all_ids = [i for f in a["folds"] for i in f["ids"]] + a["locked"]["ids"]
    assert len(all_ids) == len(set(all_ids)) == sum(len(v) for v in by_biz.values())
    assert len(a["locked"]["businesses"]) == 3
    sizes = [f["n_questions"] for f in a["folds"]]
    assert max(sizes) - min(sizes) <= 120  # cân bằng trong khoảng một shop lớn
    for f in a["folds"]:
        assert len({industries[s] for s in f["businesses"]}) >= 4  # mỗi fold có nhiều ngành
