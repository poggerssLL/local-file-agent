"""
Modelos de dados centrais e politicas de seguranca do Local File Agent.
Atende aos principios de aprovacao humana, dry-run por padrao e confinamento de escopo.
"""

import os
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# SecurityBoundaryError e definida na politica unica de fronteira (Etapa 2B) e
# reexportada aqui para preservar `from src.core.models import SecurityBoundaryError`.
from .boundary import SecurityBoundaryError, resolve_within


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
        dentro de base_dir.

        Desde a Etapa 2B, delega a ``boundary.resolve_within``:
        - ``source_path`` e ``destination_path`` devem ser RELATIVOS a base_dir
          (absolutos, UNC, unidades, ``..`` e construcoes ambiguas do Win32 sao
          rejeitados);
        - o confinamento e verificado por componentes, nunca por ``startswith``;
        - ``destination_path=None`` significa "sem destino"; string vazia e
          rejeitada (apontaria para a propria raiz).
        A validacao e lexical: nao resolve links nem elimina TOCTOU.
        """
        for action in self.actions:
            try:
                resolve_within(self.base_dir, action.source_path)
            except SecurityBoundaryError as exc:
                raise SecurityBoundaryError(
                    f"Fuga de seguranca: o caminho de origem '{action.source_path}' sai de '{self.base_dir}' ({exc})"
                ) from exc

            if action.destination_path is not None:
                try:
                    resolve_within(self.base_dir, action.destination_path)
                except SecurityBoundaryError as exc:
                    raise SecurityBoundaryError(
                        f"Fuga de seguranca: o caminho de destino '{action.destination_path}' sai de '{self.base_dir}' ({exc})"
                    ) from exc

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


@dataclass
class ScannerConfig:
    """
    Configuracao de seguranca e filtros para o inventario de arquivos.

    ``follow_symlinks``: False por padrao -- symlinks, junctions e reparse
    points de redirecionamento sao pulados e registrados em
    ``ScanReport.skipped``. Se True, apenas destinos FISICAMENTE internos a raiz
    sao seguidos, com prevencao deterministica de ciclos e duplicacao. Reparse
    points nao redirecionadores, como placeholders OneDrive, sao tratados como
    entradas comuns, sujeitos ao confinamento fisico (Etapa 2B).
    """
    include_hidden: bool = False
    follow_symlinks: bool = False
    max_depth: Optional[int] = None
    allowed_extensions: Optional[List[str]] = None
    max_files_limit: int = 50_000


@dataclass
class ScanReport:
    """
    Relatorio estruturado da varredura somente leitura.

    ``errors``: falhas de I/O e violacoes de fronteira, sanitizadas (caminho
    relativo + tipo da excecao + errno; sem mensagens do SO nem caminhos
    absolutos de entradas).
    ``skipped``: entradas intencionalmente nao seguidas/registradas (links,
    reparse points, destinos externos, ciclos/duplicatas), tambem sanitizadas.
    """
    base_dir: str
    total_files: int
    total_bytes: int
    items: List[FileItem] = field(default_factory=list)
    scan_duration_ms: float = 0.0
    errors: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)

    @property
    def extension_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for item in self.items:
            ext = item.extension or "(sem extensao)"
            counts[ext] = counts.get(ext, 0) + 1
        return counts
