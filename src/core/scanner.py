"""
Modulo de Varredura Somente Leitura (Scanner) do Local File Agent.
Desenvolvido em conformidade com as regras de confinamento e politicas de seguranca.
"""

import os
import time
from typing import Optional, List
from .models import (
    FileItem,
    ScannerConfig,
    ScanReport,
    SecurityBoundaryError,
)


class DirectoryScanner:
    """
    Realiza varredura recursiva de arquivos de forma estritamente somente leitura.
    Garante confinamento a base_dir e coleta de metadados sem alteracao em disco.
    """

    def __init__(self, base_dir: str, config: Optional[ScannerConfig] = None):
        if not os.path.exists(base_dir):
            raise FileNotFoundError(f"Diretorio base nao encontrado: '{base_dir}'")
        if not os.path.isdir(base_dir):
            raise NotADirectoryError(f"O caminho informado nao e um diretorio: '{base_dir}'")

        self.base_dir = os.path.abspath(base_dir)
        self.config = config or ScannerConfig()

    def scan(self) -> ScanReport:
        """
        Executa o inventario recursivo e retorna um ScanReport imutavel.
        """
        start_time = time.perf_counter()
        items: List[FileItem] = []
        errors: List[str] = []
        total_bytes = 0

        self._walk_directory(
            current_dir=self.base_dir,
            current_depth=0,
            items=items,
            errors=errors,
        )

        duration_ms = (time.perf_counter() - start_time) * 1000

        for item in items:
            total_bytes += item.size_bytes

        return ScanReport(
            base_dir=self.base_dir,
            total_files=len(items),
            total_bytes=total_bytes,
            items=items,
            scan_duration_ms=duration_ms,
            errors=errors,
        )

    def _walk_directory(
        self,
        current_dir: str,
        current_depth: int,
        items: List[FileItem],
        errors: List[str],
    ) -> None:
        """Percorre recursivamente com os.scandir para maxima performance de I/O."""
        # Limite de profundidade se configurado
        if self.config.max_depth is not None and current_depth > self.config.max_depth:
            return

        # Limite maximo de seguranca contra estouro de memoria
        if len(items) >= self.config.max_files_limit:
            errors.append(f"Limite maximo de arquivos atingido ({self.config.max_files_limit}). Varredura interrompida.")
            return

        try:
            with os.scandir(current_dir) as entries:
                for entry in entries:
                    if len(items) >= self.config.max_files_limit:
                        break

                    name = entry.name

                    # Trata arquivos/pastas ocultos
                    if not self.config.include_hidden and name.startswith("."):
                        continue

                    # Confinamento: previne seguir symlinks se desabilitado
                    if entry.is_symlink() and not self.config.follow_symlinks:
                        continue

                    try:
                        if entry.is_dir(follow_symlinks=self.config.follow_symlinks):
                            self._walk_directory(
                                current_dir=entry.path,
                                current_depth=current_depth + 1,
                                items=items,
                                errors=errors,
                            )
                        elif entry.is_file(follow_symlinks=self.config.follow_symlinks):
                            rel_path = os.path.relpath(entry.path, self.base_dir).replace("\\", "/")

                            # Filtro de extensoes permitidas se configurado
                            _, ext = os.path.splitext(name)
                            if self.config.allowed_extensions:
                                allowed_lower = [e.lower() for e in self.config.allowed_extensions]
                                if ext.lower() not in allowed_lower:
                                    continue

                            stat_info = entry.stat(follow_symlinks=self.config.follow_symlinks)
                            item = FileItem(
                                path=rel_path,
                                size_bytes=stat_info.st_size,
                                modified_timestamp=stat_info.st_mtime,
                            )
                            items.append(item)
                    except (PermissionError, OSError) as entry_err:
                        errors.append(f"Erro ao acessar '{entry.path}': {entry_err}")

        except (PermissionError, OSError) as dir_err:
            errors.append(f"Erro ao listar diretorio '{current_dir}': {dir_err}")
