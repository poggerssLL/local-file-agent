"""
Testes unitarios para o modulo DirectoryScanner do Local File Agent.
Valida o inventario somente leitura contra a arvore sintetica de teste.
"""

import os
import unittest
from src.core.models import ScannerConfig
from src.core.scanner import DirectoryScanner

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "synthetic_tree")


class TestDirectoryScanner(unittest.TestCase):
    def setUp(self):
        self.assertTrue(
            os.path.exists(FIXTURE_DIR),
            f"Diretorio de fixtures sinteticos nao encontrado em: {FIXTURE_DIR}",
        )

    def test_default_scan_ignores_hidden(self):
        scanner = DirectoryScanner(FIXTURE_DIR)
        report = scanner.scan()

        self.assertEqual(report.base_dir, os.path.abspath(FIXTURE_DIR))
        self.assertEqual(report.total_files, 5, "Deve encontrar exatamente 5 arquivos visiveis.")
        self.assertTrue(report.total_bytes > 0)
        self.assertEqual(len(report.errors), 0)

        # Confirma que o arquivo oculto foi devidamente ignorado
        paths = [item.path for item in report.items]
        self.assertFalse(any(".oculto" in p for p in paths))

        # Confirma contagem por extensao
        exts = report.extension_counts
        self.assertEqual(exts.get(".pdf"), 1)
        self.assertEqual(exts.get(".docx"), 1)
        self.assertEqual(exts.get(".png"), 1)
        self.assertEqual(exts.get(".exe"), 1)
        self.assertEqual(exts.get(".txt"), 1)

    def test_scan_including_hidden_files(self):
        config = ScannerConfig(include_hidden=True)
        scanner = DirectoryScanner(FIXTURE_DIR, config=config)
        report = scanner.scan()

        self.assertEqual(report.total_files, 6, "Com include_hidden=True, deve encontrar 6 arquivos.")
        paths = [item.path for item in report.items]
        self.assertTrue(any(".oculto" in p for p in paths))

    def test_scan_filter_by_extension(self):
        config = ScannerConfig(allowed_extensions=[".pdf", ".docx"])
        scanner = DirectoryScanner(FIXTURE_DIR, config=config)
        report = scanner.scan()

        self.assertEqual(report.total_files, 2)
        for item in report.items:
            self.assertIn(item.extension, [".pdf", ".docx"])

    def test_scan_max_depth_zero(self):
        # max_depth=0 analisa apenas a raiz imediata (onde nao ha arquivos avulsos)
        config = ScannerConfig(max_depth=0)
        scanner = DirectoryScanner(FIXTURE_DIR, config=config)
        report = scanner.scan()

        self.assertEqual(report.total_files, 0)

    def test_invalid_directory_raises_error(self):
        with self.assertRaises(FileNotFoundError):
            DirectoryScanner("C:/Caminho/Completamente/Inexistente_12345")


if __name__ == "__main__":
    unittest.main()
