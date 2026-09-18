"""
Testes unitarios de fundacao e politicas de seguranca do Local File Agent.
"""

import unittest
from src.core.models import (
    FileItem,
    OperationType,
    OperationStatus,
    OperationAction,
    ExecutionPlan,
    SecurityBoundaryError,
)


class TestFoundationModels(unittest.TestCase):
    def test_file_item_properties(self):
        item = FileItem(
            path="documentos/fatura_2026.pdf",
            size_bytes=1024,
            modified_timestamp=1789740000.0,
            sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )
        self.assertEqual(item.extension, ".pdf")
        self.assertEqual(item.filename, "fatura_2026.pdf")

    def test_execution_plan_default_invariants(self):
        plan = ExecutionPlan(
            plan_id="plan-001",
            base_dir="C:/Users/erick/Downloads/Teste",
        )
        # Invariantes fundamentais de seguranca
        self.assertFalse(plan.approved, "O plano NUNCA deve nascer aprovado por padrao.")
        self.assertTrue(plan.dry_run, "O plano DEVE estar em modo dry_run por padrao.")
        self.assertFalse(plan.can_execute(), "can_execute() deve ser Falso sem aprovacao.")

    def test_security_boundary_blocks_path_traversal(self):
        plan = ExecutionPlan(
            plan_id="plan-unsafe",
            base_dir="C:/Users/erick/Downloads/Teste",
            actions=[
                OperationAction(
                    action_id="act-1",
                    operation_type=OperationType.MOVE,
                    source_path="../../secret.txt",  # Tentativa de fuga da raiz
                    destination_path="safe.txt",
                )
            ],
        )
        with self.assertRaises(SecurityBoundaryError):
            plan.validate_safety()

    def test_security_boundary_blocks_destination_traversal(self):
        plan = ExecutionPlan(
            plan_id="plan-unsafe-dst",
            base_dir="C:/Users/erick/Downloads/Teste",
            actions=[
                OperationAction(
                    action_id="act-2",
                    operation_type=OperationType.RENAME,
                    source_path="arquivo.txt",
                    destination_path="../../../Windows/System32/hacked.dll",
                )
            ],
        )
        with self.assertRaises(SecurityBoundaryError):
            plan.validate_safety()

    def test_valid_plan_approval_cycle(self):
        plan = ExecutionPlan(
            plan_id="plan-valid",
            base_dir="C:/Users/erick/Downloads/Teste",
            actions=[
                OperationAction(
                    action_id="act-3",
                    operation_type=OperationType.RENAME,
                    source_path="documentos/nota.pdf",
                    destination_path="documentos/2026_nota_fiscal.pdf",
                    reason="Padronizacao de nomenclatura",
                )
            ],
        )
        self.assertTrue(plan.validate_safety())
        self.assertFalse(plan.can_execute())

        # Aprovacao humana
        plan.approve()
        self.assertTrue(plan.approved)
        self.assertTrue(plan.can_execute())

        summary = plan.summary()
        self.assertEqual(summary["total_actions"], 1)
        self.assertEqual(summary["actions_summary"][0]["type"], "rename")


if __name__ == "__main__":
    unittest.main()
