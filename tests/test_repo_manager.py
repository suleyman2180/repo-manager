"""repo-manager Birim Testleri (Unit Tests)

Bu dosya, çekirdek yardımcı fonksiyonları, güvenlik kontrollerini
ve lisans oluşturma modülünü test eder.
"""
import sys
import unittest
from pathlib import Path

# Proje kök dizinini sys.path'e ekle
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from licenses import has_license, get_license_text, write_license, TEMPLATES
import repo_manager_gui as rmg


class TestLicenses(unittest.TestCase):
    def test_templates_exist(self):
        self.assertIn("MIT", TEMPLATES)
        self.assertIn("Apache-2.0", TEMPLATES)
        self.assertIn("GPL-3.0", TEMPLATES)

    def test_get_license_text_mit(self):
        text = get_license_text("MIT", author="Test Kullanıcısı")
        self.assertIn("MIT License", text)
        self.assertIn("Test Kullanıcısı", text)
        self.assertIn("Permission is hereby granted", text)

    def test_get_license_text_apache(self):
        text = get_license_text("Apache-2.0", author="Acme Corp")
        self.assertIn("Apache License", text)
        self.assertIn("Version 2.0", text)
        self.assertIn("Acme Corp", text)

    def test_get_license_text_gpl(self):
        text = get_license_text("GPL-3.0", author="Özgür Yazılımcı")
        self.assertIn("GNU GENERAL PUBLIC LICENSE", text)
        self.assertIn("Version 3", text)
        self.assertIn("Özgür Yazılımcı", text)

    def test_has_license_and_write_license(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Başlangıçta lisans yok
            self.assertFalse(has_license(tmp_path))

            # Lisans yaz
            created = write_license(tmp_path, "MIT", author="Test Dev")
            self.assertIsNotNone(created)
            self.assertTrue(created.exists())
            self.assertTrue(has_license(tmp_path))

            content = created.read_text(encoding="utf-8")
            self.assertIn("MIT License", content)
            self.assertIn("Test Dev", content)


class TestGuiHelpers(unittest.TestCase):
    def test_clean_path(self):
        self.assertEqual(rmg.clean("  '/home/test/path'  "), "/home/test/path")
        self.assertEqual(rmg.clean('  "/var/log" '), "/var/log")

    def test_dangerous_paths(self):
        home = str(Path.home())
        self.assertTrue(rmg.dangerous("/"))
        self.assertTrue(rmg.dangerous(home))
        self.assertTrue(rmg.dangerous(f"{home}/Downloads"))
        self.assertTrue(rmg.dangerous(f"{home}/Desktop"))
        # Güvenli özel alt dizin
        self.assertFalse(rmg.dangerous(f"{home}/projects/my-cool-app"))

    def test_fsize(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            dummy_file = Path(tmp_dir) / "hello.txt"
            dummy_file.write_text("1234567890", encoding="utf-8")
            self.assertEqual(rmg.fsize(dummy_file), 10)

    def test_load_config_defaults(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_cfg = Path(tmp_dir) / "fake_config"
            fake_cfg.write_text(
                'KAYITLI_GIT_NAME="Ali Veli"\nVARSAYILAN_VISIBILITY="2"\n',
                encoding="utf-8"
            )
            orig_cfg = rmg.CONFIG_FILE
            try:
                rmg.CONFIG_FILE = fake_cfg
                cfg = rmg.load_config()
                self.assertEqual(cfg["KAYITLI_GIT_NAME"], "Ali Veli")
                self.assertEqual(cfg["VARSAYILAN_VISIBILITY"], "2")
                self.assertEqual(cfg["KAYITLI_GIT_EMAIL"], "")
            finally:
                rmg.CONFIG_FILE = orig_cfg


if __name__ == "__main__":
    unittest.main()
