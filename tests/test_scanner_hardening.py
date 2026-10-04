"""
Testes unitarios para o endurecimento do DirectoryScanner (Etapa 2B).
Cobre deteccao/pulo de links, distincao de placeholders OneDrive,
prevencao de ciclos e duplicatas, ordenacao deterministica e sanitizacao de erros.
"""

import os
import stat
import unittest
from unittest.mock import MagicMock, patch

from src.core.boundary import SecurityBoundaryError
from src.core.models import ScannerConfig, ScanReport
from src.core.scanner import (
    DirectoryScanner,
    classify_link,
    classify_path,
    _redirect_kind_from_stat,
    _describe_os_error,
    REPARSE_TAG_NAME_SURROGATE,
    _FILE_ATTRIBUTE_REPARSE_POINT,
    LINK_SYMLINK,
    LINK_JUNCTION,
    LINK_REDIRECT_REPARSE,
)

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "synthetic_tree")


class TestScannerHardening(unittest.TestCase):
    def test_describe_os_error_sanitization(self):
        err_fnf = FileNotFoundError(2, "Arquivo sumiu no disco: C:/Segredo/Privado.txt")
        desc = _describe_os_error(err_fnf)
        self.assertEqual(desc, "FileNotFoundError (errno=2)")
        self.assertNotIn("Segredo", desc)
        self.assertNotIn("C:", desc)

        err_perm = PermissionError(13, "Acesso negado: D:/Outro/Diretorio")
        desc_perm = _describe_os_error(err_perm)
        self.assertEqual(desc_perm, "PermissionError (errno=13)")
        self.assertNotIn("Outro", desc_perm)

    def test_redirect_kind_from_stat_onedrive_vs_surrogate(self):
        # 1. Arquivo comum (sem atributo reparse)
        st_regular = MagicMock(spec=os.stat_result)
        st_regular.st_file_attributes = 0
        st_regular.st_reparse_tag = 0
        self.assertIsNone(_redirect_kind_from_stat(st_regular))

        # 2. Placeholder de nuvem OneDrive (IO_REPARSE_TAG_CLOUD = 0x9000001A)
        # Nao possui o bit REPARSE_TAG_NAME_SURROGATE (0x20000000)
        st_onedrive = MagicMock(spec=os.stat_result)
        st_onedrive.st_file_attributes = _FILE_ATTRIBUTE_REPARSE_POINT
        st_onedrive.st_reparse_tag = 0x9000001A
        self.assertIsNone(
            _redirect_kind_from_stat(st_onedrive),
            "Placeholders OneDrive nao redirecionam caminhos e nao devem ser classificados como link de redirecionamento",
        )

        # 3. Reparse point de redirecionamento (possui REPARSE_TAG_NAME_SURROGATE)
        st_surrogate = MagicMock(spec=os.stat_result)
        st_surrogate.st_file_attributes = _FILE_ATTRIBUTE_REPARSE_POINT
        st_surrogate.st_reparse_tag = REPARSE_TAG_NAME_SURROGATE | 0x03
        self.assertEqual(_redirect_kind_from_stat(st_surrogate), LINK_REDIRECT_REPARSE)

    def test_scanner_rejects_link_or_junction_as_root(self):
        with patch("src.core.scanner.classify_path", return_value=LINK_SYMLINK):
            with self.assertRaises(SecurityBoundaryError) as ctx:
                DirectoryScanner(FIXTURE_DIR)
            self.assertIn("symlink", str(ctx.exception))

        with patch("src.core.scanner.classify_path", return_value=LINK_JUNCTION):
            with self.assertRaises(SecurityBoundaryError) as ctx:
                DirectoryScanner(FIXTURE_DIR)
            self.assertIn("junction", str(ctx.exception))

    def test_scanner_onedrive_cloud_file_included_not_skipped(self):
        scanner = DirectoryScanner(FIXTURE_DIR)
        report = scanner.scan()
        # Valida que todos os arquivos do fixture sao lidos e nenhum vai para skipped
        self.assertEqual(len(report.skipped), 0)
        self.assertEqual(report.total_files, 5)

    def test_scanner_skips_symlinks_by_default(self):
        # Simula entrada com symlink dentro do diretorio
        scanner = DirectoryScanner(FIXTURE_DIR)

        # Mock de classify_link para uma entrada especifica
        original_classify = classify_link

        def mock_classify(entry):
            if entry.name == "apresentacao.docx":
                return LINK_SYMLINK
            return original_classify(entry)

        with patch("src.core.scanner.classify_link", side_effect=mock_classify):
            report = scanner.scan()

        self.assertEqual(report.total_files, 4)
        self.assertTrue(any("apresentacao.docx': symlink nao seguido" in s for s in report.skipped))

    def test_scanner_cycle_prevention(self):
        # Configura com follow_symlinks=True
        config = ScannerConfig(follow_symlinks=True)
        scanner = DirectoryScanner(FIXTURE_DIR, config=config)

        # Simula que o diretorio 'documentos' aponta de volta para FIXTURE_DIR (ciclo para a raiz)
        real_fixture_key = os.path.normcase(os.path.normpath(os.path.realpath(FIXTURE_DIR)))

        original_realpath = os.path.realpath

        def mock_realpath(path):
            if "documentos" in path:
                return original_realpath(FIXTURE_DIR)
            return original_realpath(path)

        with patch("os.path.realpath", side_effect=mock_realpath):
            report = scanner.scan()

        self.assertTrue(
            any("ciclo ou duplicata" in s for s in report.skipped),
            "Deve detectar e registrar o ciclo em report.skipped sem entrar em loop infinito",
        )

    def test_scanner_physical_boundary_violation_caught(self):
        config = ScannerConfig(follow_symlinks=True)
        scanner = DirectoryScanner(FIXTURE_DIR, config=config)

        original_realpath = os.path.realpath

        def mock_realpath(path):
            if "documentos" in path:
                return "C:/Windows/System32"
            return original_realpath(path)

        with patch("src.core.scanner.classify_link", return_value=LINK_SYMLINK):
            with patch("os.path.realpath", side_effect=mock_realpath):
                report = scanner.scan()

        self.assertTrue(
            any("fora da fronteira fisica" in s for s in report.skipped),
            "Deve impedir o scanner de seguir links para fora da fronteira fisica",
        )

    def test_scanner_handles_os_error_as_inventory_failure(self):
        scanner = DirectoryScanner(FIXTURE_DIR)

        # Simula erro de I/O em um arquivo especifico durante stat
        original_process = scanner._process_entry

        def mock_process(entry, rel_path, state):
            if entry.name == "anotacoes_aula.txt":
                raise FileNotFoundError(2, "Arquivo inacessivel em C:/Temp/anotacoes.txt")
            return original_process(entry, rel_path, state)

        with patch.object(scanner, "_process_entry", side_effect=mock_process):
            report = scanner.scan()

        self.assertEqual(report.total_files, 4)
        self.assertEqual(len(report.errors), 1)
        err = report.errors[0]
        self.assertIn("FileNotFoundError (errno=2)", err)
        self.assertIn("notas/anotacoes_aula.txt", err)
        # Nao vaza caminhos absolutos locais
        self.assertNotIn("C:/Temp", err)

    def test_scanner_deterministic_sort(self):
        scanner = DirectoryScanner(FIXTURE_DIR)
        report1 = scanner.scan()
        report2 = scanner.scan()

        paths1 = [item.path for item in report1.items]
        paths2 = [item.path for item in report2.items]
        self.assertEqual(paths1, paths2)
        self.assertEqual(paths1, sorted(paths1))


if __name__ == "__main__":
    unittest.main()
