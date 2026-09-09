import hashlib
import pytest
from fw import storage


def test_workspace_and_figure_folders():
    wf = storage.workspace_folder("SA-Osteomyelitis")
    assert wf.exists() and wf.name == "SA-Osteomyelitis"
    assert (wf / "原始数据").is_dir()
    assert (wf / ".trash").is_dir()
    ff = storage.figure_folder("SA-Osteomyelitis", "Figure 1")
    assert ff.exists() and ff.name == "Figure1"


def test_save_upload_returns_sha_and_unique():
    wf = storage.workspace_folder("P001")
    bytes_data = b"hello figure"
    rel1 = storage.save_upload(wf, bytes_data, "a.xlsx")
    rel2 = storage.save_upload(wf, bytes_data, "a.xlsx")
    assert rel1 != rel2 and (wf / rel2).exists()
    assert storage.sha256_bytes(bytes_data) == hashlib.sha256(bytes_data).hexdigest()
    # unique_name dedupe produced a " (2)" name
    assert " (2)" in rel2


def test_trash_moves_file():
    wf = storage.workspace_folder("P1")
    rel = storage.save_upload(wf, b"x", "keep.txt")
    storage.move_to_trash(wf, rel)
    assert not (wf / rel).exists()
    assert (wf / ".trash").exists()


def test_save_upload_into_subdir_and_preview():
    wf = storage.workspace_folder("P2")
    rel = storage.save_upload(wf, b"\x89PNG", "preview.png", dest_rel="Figure1")
    assert rel == "Figure1/preview.png"
    assert (wf / "Figure1" / "preview.png").exists()


def test_save_upload_rejects_path_traversal_filename():
    wf = storage.workspace_folder("P3")
    with pytest.raises(ValueError):
        storage.save_upload(wf, b"x", "../escaped.txt")
    assert not (wf.parent / "escaped.txt").exists()


def test_save_upload_rejects_escaping_dest_rel():
    wf = storage.workspace_folder("P4")
    with pytest.raises(ValueError):
        storage.save_upload(wf, b"x", "a.txt", dest_rel="../..")
    assert not (wf.parent / "a.txt").exists()


def test_save_upload_basename_strips_windows_drive():
    wf = storage.workspace_folder("P5")
    rel = storage.save_upload(wf, b"x", r"C:\evil\payload.txt")
    assert rel == "payload.txt"
    assert (wf / "payload.txt").exists()


def test_move_to_trash_ignores_outside_path():
    wf = storage.workspace_folder("P6")
    outside = wf.parent / "secret.txt"
    outside.write_text("keep")
    storage.move_to_trash(wf, "../secret.txt")  # must no-op
    assert outside.exists()


def test_sha256_file_roundtrip():
    wf = storage.workspace_folder("P7")
    p = wf / "raw.bin"
    data = b"round trip bytes"
    p.write_bytes(data)
    assert storage.sha256_file(p) == storage.sha256_bytes(data)
