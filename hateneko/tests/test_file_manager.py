from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from hateneko.core.file_manager import FileManager


class FileManagerTest(unittest.TestCase):
    def test_move_avoids_name_collision_and_undo_restores(self) -> None:
        with TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            source = base / "image.png"
            source.write_bytes(b"first")

            ok_dir = base / "_hateneko_ok"
            ok_dir.mkdir()
            (ok_dir / "image.png").write_bytes(b"existing")

            manager = FileManager()
            record = manager.move_to_category(source, base, "ok")

            self.assertFalse(source.exists())
            self.assertEqual(record.destination, ok_dir / "image_001.png")
            self.assertTrue(record.destination.exists())

            restored = manager.undo_move(record)
            self.assertEqual(restored, source)
            self.assertTrue(source.exists())
            self.assertFalse(record.destination.exists())

    def test_delete_uses_deleted_folder_by_default(self) -> None:
        with TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            source = base / "画像.png"
            source.write_bytes(b"data")

            manager = FileManager()
            record = manager.move_to_category(source, base, "deleted")

            self.assertEqual(record.destination, base / "_hateneko_deleted" / "画像.png")
            self.assertTrue(record.undoable)
            self.assertTrue(record.destination.exists())


if __name__ == "__main__":
    unittest.main()

