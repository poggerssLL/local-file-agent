"""
Testes unitarios para a politica de fronteira e confinamento (Etapa 2B).
Valida rejeicao de escapes, caminhos absolutos, UNC, drive-relative, ADS e
comparacao por componentes sem startswith.
"""

import os
import unittest
from src.core.boundary import (
    SecurityBoundaryError,
    normalize_relative_path,
    is_within_boundary,
    resolve_within,
)
from src.core.models import (
    ExecutionPlan,
    OperationAction,
    OperationType,
)


class TestBoundaryPolicy(unittest.TestCase):
    def test_normalize_relative_path_valid(self):
        self.assertEqual(normalize_relative_path("documentos/relatorio.pdf"), "documentos/relatorio.pdf")
        self.assertEqual(normalize_relative_path("documentos\\subpasta\\relatorio.pdf"), "documentos/subpasta/relatorio.pdf")
        self.assertEqual(normalize_relative_path("simples.txt"), "simples.txt")
        self.assertEqual(normalize_relative_path("a/./b/./c.txt"), "a/b/c.txt")

    def test_normalize_relative_path_rejects_absolutes(self):
        for raw in ["/abs/path", "\\abs\\path", "C:/abs/path", "C:\\abs\\path", "\\\\?\\C:\\abs"]:
            with self.subTest(raw=raw):
                with self.assertRaises(SecurityBoundaryError):
                    normalize_relative_path(raw)

    def test_normalize_relative_path_rejects_unc(self):
        for raw in ["\\\\server\\share\\file.txt", "//server/share/file.txt", "\\\\127.0.0.1\\c$\\secret"]:
            with self.subTest(raw=raw):
                with self.assertRaises(SecurityBoundaryError):
                    normalize_relative_path(raw)

    def test_normalize_relative_path_rejects_drive_relative(self):
        for raw in ["C:file.txt", "D:subdir/file.txt", "c:relative"]:
            with self.subTest(raw=raw):
                with self.assertRaises(SecurityBoundaryError):
                    normalize_relative_path(raw)

    def test_normalize_relative_path_rejects_ads(self):
        for raw in ["file.txt:stream", "file.txt:$DATA", "sub/arquivo.pdf:hidden"]:
            with self.subTest(raw=raw):
                with self.assertRaises(SecurityBoundaryError):
                    normalize_relative_path(raw)

    def test_normalize_relative_path_rejects_traversal(self):
        for raw in ["..", "../file.txt", "docs/../../file.txt", "docs/..", "a/b/../../../c"]:
            with self.subTest(raw=raw):
                with self.assertRaises(SecurityBoundaryError):
                    normalize_relative_path(raw)

    def test_normalize_relative_path_rejects_trailing_dot_or_space(self):
        for raw in ["file.txt.", "file.txt ", "sub./file.txt", "sub /file.txt", "...", ". ."]:
            with self.subTest(raw=raw):
                with self.assertRaises(SecurityBoundaryError):
                    normalize_relative_path(raw)

    def test_normalize_relative_path_rejects_control_chars_and_empty(self):
        for raw in ["", "   ", "file\x00.txt", "file\n.txt", "file\r.txt", ".", "./."]:
            with self.subTest(raw=raw):
                with self.assertRaises(SecurityBoundaryError):
                    normalize_relative_path(raw)

        with self.assertRaises(SecurityBoundaryError):
            normalize_relative_path(None)  # type: ignore

    def test_normalize_relative_path_rejects_reserved_devices(self):
        for raw in ["CON", "prn", "aux.txt", "NUL.json", "COM1", "com1.txt", "LPT2.dat", "CONIN$", "CONOUT$"]:
            with self.subTest(raw=raw):
                with self.assertRaises(SecurityBoundaryError):
                    normalize_relative_path(raw)

    def test_is_within_boundary_eliminates_startswith_vulnerability(self):
        base = "C:/Users/erick/Downloads/Teste"
        sibling = "C:/Users/erick/Downloads/Teste2/arquivo.txt"
        self.assertFalse(
            is_within_boundary(base, sibling),
            "Diretorio irmao com mesmo prefixo nao pode estar dentro da fronteira (falha de startswith)",
        )

        child = "C:/Users/erick/Downloads/Teste/subpasta/arquivo.txt"
        self.assertTrue(is_within_boundary(base, child))

        root_itself = "C:/Users/erick/Downloads/Teste"
        self.assertTrue(is_within_boundary(base, root_itself))

        parent = "C:/Users/erick/Downloads"
        self.assertFalse(is_within_boundary(base, parent))

    def test_is_within_boundary_windows_normalization(self):
        base = "C:/Users/erick/Downloads/Teste"
        child_diff_case = "c:/users/erick/downloads/teste/SUB/arquivo.txt"
        self.assertTrue(is_within_boundary(base, child_diff_case))

        diff_drive = "D:/Users/erick/Downloads/Teste/sub"
        self.assertFalse(is_within_boundary(base, diff_drive))

        self.assertFalse(is_within_boundary("", child_diff_case))
        self.assertFalse(is_within_boundary(base, ""))
        self.assertFalse(is_within_boundary(None, child_diff_case))  # type: ignore

    def test_resolve_within(self):
        base = "C:/Users/erick/Downloads/Teste"
        resolved = resolve_within(base, "docs/manual.pdf")
        expected = os.path.normpath("C:/Users/erick/Downloads/Teste/docs/manual.pdf")
        self.assertEqual(resolved, expected)

        with self.assertRaises(SecurityBoundaryError):
            resolve_within(base, "../escape.txt")

        with self.assertRaises(SecurityBoundaryError):
            resolve_within("", "docs/manual.pdf")

    def test_execution_plan_validation_hardening(self):
        base = "C:/Users/erick/Downloads/Teste"

        # Rejeita caminho absoluto em source
        plan_abs_src = ExecutionPlan(
            plan_id="p-abs-src",
            base_dir=base,
            actions=[
                OperationAction(
                    action_id="a1",
                    operation_type=OperationType.MOVE,
                    source_path="C:/Users/erick/Downloads/Teste/file.txt",
                    destination_path="sub/file.txt",
                )
            ],
        )
        with self.assertRaises(SecurityBoundaryError):
            plan_abs_src.validate_safety()

        # Rejeita ADS em destination
        plan_ads = ExecutionPlan(
            plan_id="p-ads",
            base_dir=base,
            actions=[
                OperationAction(
                    action_id="a2",
                    operation_type=OperationType.RENAME,
                    source_path="file.txt",
                    destination_path="file.txt:hidden",
                )
            ],
        )
        with self.assertRaises(SecurityBoundaryError):
            plan_ads.validate_safety()

        # Rejeita tentativa de fuga via pasta irma com mesmo prefixo
        plan_sibling = ExecutionPlan(
            plan_id="p-sib",
            base_dir=base,
            actions=[
                OperationAction(
                    action_id="a3",
                    operation_type=OperationType.MOVE,
                    source_path="file.txt",
                    destination_path="../Teste2/file.txt",
                )
            ],
        )
        with self.assertRaises(SecurityBoundaryError):
            plan_sibling.validate_safety()

        # Rejeita destination vazia
        plan_empty_dst = ExecutionPlan(
            plan_id="p-empty-dst",
            base_dir=base,
            actions=[
                OperationAction(
                    action_id="a4",
                    operation_type=OperationType.MOVE,
                    source_path="file.txt",
                    destination_path="",
                )
            ],
        )
        with self.assertRaises(SecurityBoundaryError):
            plan_empty_dst.validate_safety()

        # Aceita destination=None (operacao sem destino, ex: tag)
        plan_none_dst = ExecutionPlan(
            plan_id="p-none-dst",
            base_dir=base,
            actions=[
                OperationAction(
                    action_id="a5",
                    operation_type=OperationType.TAG,
                    source_path="file.txt",
                    destination_path=None,
                )
            ],
        )
        self.assertTrue(plan_none_dst.validate_safety())


if __name__ == "__main__":
    unittest.main()
