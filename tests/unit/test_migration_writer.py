from src.migration.writer import copy_vault_assets


def test_copies_both_obsidian_and_files(tmp_path):
    src = tmp_path / "source"
    dst = tmp_path / "target"
    (src / ".obsidian").mkdir(parents=True)
    (src / ".obsidian" / "app.json").write_text('{"theme":"dark"}')
    (src / "Files").mkdir()
    (src / "Files" / "image.png").write_bytes(b"\x89PNG")

    copy_vault_assets(str(src), str(dst))

    assert (dst / ".obsidian" / "app.json").read_text() == '{"theme":"dark"}'
    assert (dst / "Files" / "image.png").read_bytes() == b"\x89PNG"


def test_missing_files_dir_only_copies_obsidian(tmp_path):
    src = tmp_path / "source"
    dst = tmp_path / "target"
    (src / ".obsidian").mkdir(parents=True)
    (src / ".obsidian" / "core-plugins.json").write_text("[]")

    copy_vault_assets(str(src), str(dst))

    assert (dst / ".obsidian" / "core-plugins.json").exists()
    assert not (dst / "Files").exists()


def test_reapply_overwrites_existing(tmp_path):
    src = tmp_path / "source"
    dst = tmp_path / "target"
    (src / ".obsidian").mkdir(parents=True)
    (src / ".obsidian" / "app.json").write_text("v2")

    # Pre-existing stale data in target
    (dst / ".obsidian").mkdir(parents=True)
    (dst / ".obsidian" / "app.json").write_text("v1")
    (dst / ".obsidian" / "old-file.json").write_text("stale")

    copy_vault_assets(str(src), str(dst))

    assert (dst / ".obsidian" / "app.json").read_text() == "v2"
    assert not (dst / ".obsidian" / "old-file.json").exists()
