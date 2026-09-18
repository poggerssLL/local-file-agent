"""
Modelos de dados centrais e politicas de seguranca do Local File Agent.
Atende aos principios de aprovacao humana, dry-run por padrao e confinamento de escopo.
"""

import os
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


class SecurityBoundaryError(ValueError):
    """Disparada quando uma acao tenta escapar da raiz do diretorio autorizado."""
    pass


class ExecutionNotApprovedError(RuntimeError):
    """Disparada quando uma execucao e tentada sem a aprovacao humana explicita."""
    pass


class OperationType(str, Enum):
    RENAME = "rename"
    MOVE = "move"
    TAG = "tag"
    SIMULATE = "simulate"


class OperationStatus(str, Enum):
    PLANNED = "planned"
    APPROVED = "approved"
    EXECUTED = "executed"
    FAILED = "failed"
    REVERTED = "reverted"


@dataclass
class FileItem:
    """Representa um arquivo inventariado no sistema."""
    path: str
    size_bytes: int
    modified_timestamp: float
    sha256_hash: Optional[str] = None
    category: Optional[str] = None

    @property
    def extension(self) -> str:
        _, ext = os.path.splitext(self.path)
        return ext.lower()

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)


@dataclass
class OperationAction:
    """Representa uma acao atomica planejada sobre um arquivo."""
    action_id: str
    operation_type: OperationType
    source_path: str
    destination_path: Optional[str] = None
    reason: str = ""
    status: OperationStatus = OperationStatus.PLANNED
    applied_at: Optional[float] = None


@dataclass
class ExecutionPlan:
    """
    Representa o plano imutavel de operacoes a serem revisadas por Erick.
    Invariantes:
    - dry_run e SEMPRE True por padrao;
    - approved e SEMPRE False por padrao;
    - validate_safety() garante que nenhum caminho saia do base_dir.
    """
    plan_id: str
    base_dir: str
    actions: List[OperationAction] = field(default_factory=list)
    approved: bool = False
    dry_run: bool = True
    created_at: float = field(default_factory=time.time)

    def validate_safety(self) -> bool:
        """
        Garante que todos os caminhos de origem e destino estejam estritamente
        dentro de base_dir, prevenindo que '..' escape para o sistema.
        """
        resolved_base = os.path.abspath(self.base_dir)

        for action in self.actions:
            # Valida source
            src_full = os.path.abspath(os.path.join(resolved_base, action.source_path))
            if not src_full.startswith(resolved_base):
                raise SecurityBoundaryError(
                    f"Fuga de seguranca: o caminho de origem '{action.source_path}' sai de '{self.base_dir}'"
                )

            # Valida destination se houver
            if action.destination_path:
                dst_full = os.path.abspath(os.path.join(resolved_base, action.destination_path))
                if not dst_full.startswith(resolved_base):
                    raise SecurityBoundaryError(
                        f"Fuga de seguranca: o caminho de destino '{action.destination_path}' sai de '{self.base_dir}'"
                    )

        return True

    def approve(self) -> None:
        """Marca o plano como aprovado expressamente pelo usuario."""
        self.validate_safety()
        self.approved = True

    def can_execute(self) -> bool:
        """Verifica se o plano satisfaz todas as pre-condicoes para execucao."""
        if not self.approved:
            return False
        return self.validate_safety()

    def summary(self) -> Dict[str, Any]:
        """Retorna resumo tabular do plano para inspecao humana."""
        return {
            "plan_id": self.plan_id,
            "base_dir": self.base_dir,
            "total_actions": len(self.actions),
            "approved": self.approved,
            "dry_run": self.dry_run,
            "actions_summary": [
                {
                    "type": a.operation_type.value,
                    "from": a.source_path,
                    "to": a.destination_path,
                    "reason": a.reason,
                    "status": a.status.value,
                }
                for a in self.actions
            ]
        }
