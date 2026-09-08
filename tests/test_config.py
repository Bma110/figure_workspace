def test_root_default_override():
    from fw import config
    assert config.root_dir().name == "root"  # conftest 已覆盖为 tmp/root
