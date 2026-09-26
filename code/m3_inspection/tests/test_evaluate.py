from common.config import load_config
from m3_inspection import evaluate

CFG = load_config()
NOMINAL = CFG["inspection"]["hole_nominal_mm"]


def test_good_part():
    r = evaluate(CFG, "69420", NOMINAL, True)
    assert r.is_good and not r.reasons


def test_each_defect_makes_part_bad():
    assert not evaluate(CFG, None, NOMINAL, True).is_good
    assert not evaluate(CFG, "ab", NOMINAL, True).is_good
    assert not evaluate(CFG, "69420", NOMINAL + 1.0, True).is_good
    assert not evaluate(CFG, "69420", None, True).is_good
    assert not evaluate(CFG, "69420", NOMINAL, False).is_good


def test_multiple_reasons_reported():
    r = evaluate(CFG, None, None, False)
    assert len(r.reasons) == 3
