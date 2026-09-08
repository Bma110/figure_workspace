from fw import naming


def test_folder_slug_removes_space_and_invalid():
    assert naming.folder_slug("Figure 1") == "Figure1"
    assert naming.folder_slug("3A") == "3A"


def test_folder_slug_keeps_cjk():
    assert naming.folder_slug("原始数据") == "原始数据"


def test_folder_slug_strips_illegal_windows_chars():
    assert naming.folder_slug('Fig:1/2*?"<>|') == "Fig12"


def test_unique_path_appends_number():
    names = ["a.xlsx", "a (2).xlsx"]
    # a (2).xlsx 已在 existing 中，须继续递增到 a (3).xlsx，避免覆盖已有副本。
    assert naming.unique_name("a.xlsx", names) == "a (3).xlsx"
    assert naming.unique_name("b.xlsx", names) == "b.xlsx"


def test_parse_sample_hint():
    assert naming.parse_sample_hint("qPCR_SA-MLOY4-001_IL6_v01.xlsx") == "SA-MLOY4-001"
    assert naming.parse_sample_hint("随便命名.txt") == ""


def test_parse_sample_hint_exp_code_alone_returns_empty():
    assert naming.parse_sample_hint("EXP024.txt") == ""


def test_parse_sample_hint_skips_pure_code_and_continues():
    assert naming.parse_sample_hint("EXP024_SA-MLOY4-001.xlsx") == "SA-MLOY4-001"


def test_folder_slug_strips_trailing_dot():
    assert naming.folder_slug("3A.") == "3A"


def test_parse_sample_hint_none_returns_empty():
    assert naming.parse_sample_hint(None) == ""
