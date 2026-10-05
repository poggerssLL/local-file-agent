"""
Modulo de Varredura Somente Leitura (Scanner) do Local File Agent.
Desenvolvido em conformidade com as regras de confinamento e politicas de seguranca.

Endurecimento da Etapa 2B:
- A raiz e confinada fisicamente: ``base_dir`` nao pode ser symlink, junction
  ou reparse point de redirecionamento (tag *name surrogate*), e serve de ancora
  via ``realpath``.
- Cada entrada e confinada fisicamente (``realpath`` + comparacao por
  componentes de ``boundary.is_within_boundary``) ANTES de descer ou registrar.
- Por padrao, symlinks, junctions e reparse points de redirecionamento sao
  pulados e registrados de forma sanitizada em ``ScanReport.skipped``.
  Reparse points que NAO redirecionam (ex.: placeholders de nuvem do OneDrive)
  sao tratados como entradas comuns, ainda sujeitas ao confinamento fisico.
- Com ``follow_symlinks=True``, somente destinos fisicamente internos sao
  seguidos; diretorios e arquivos ja visitados (por caminho real) nao sao
  revisitados, prevenindo ciclos e duplicacao de forma deterministica.
- Travessia iterativa (pilha explicita), entradas ordenadas por nome: a ordem
  de visita e a escolha de "quem vence" em duplicatas sao deterministicas.
- Falhas de ``scandir``/``stat``/``realpath`` (inclusive ``FileNotFoundError``
  por corrida TOCTOU) viram erros sanitizados; a varredura continua.

Limitacao explicita: nada aqui ELIMINA condicoes de corrida TOCTOU -- o disco
pode mudar entre a checagem de fronteira e a coleta de metadados. A varredura
apenas le metadados; nenhum conteudo e aberto, alterado, movido ou excluido.
"""

import os
import stat as stat_module
import time
from typing import List, Optional, Set, Tuple

from .boundary import is_within_boundary
from .models import (
    FileItem,
    FileObservation,
    ScannerConfig,
    ScanReport,
    SecurityBoundaryError,
)

# Bit "name surrogate" das tags de reparse do Windows (IsReparseTagNameSurrogate):
# indica que o reparse point redireciona para outro caminho (symlink, junction).
REPARSE_TAG_NAME_SURROGATE = 0x20000000
_FILE_ATTRIBUTE_REPARSE_POINT = getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

# Classificacoes de link (redirecionadores).
LINK_SYMLINK = "symlink"
LINK_JUNCTION = "junction"
LINK_REDIRECT_REPARSE = "reparse point de redirecionamento"


def _describe_os_error(exc: BaseException) -> str:
    """Descricao sanitizada: tipo + errno, sem mensagem do SO nem caminho."""
    errno = getattr(exc, "errno", None)
    if errno is None:
        return type(exc).__name__
    return f"{type(exc).__name__} (errno={errno})"


def _canonical_key(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def _redirect_kind_from_stat(st: os.stat_result) -> Optional[str]:
    """
    Considera redirecionador apenas reparse points com tag *name surrogate*.
    ``FILE_ATTRIBUTE_REPARSE_POINT`` sozinho NAO basta: placeholders de nuvem
    (OneDrive) e outros filtros tambem o usam sem redirecionar o caminho.
    """
    attributes = getattr(st, "st_file_attributes", 0) or 0
    if attributes & _FILE_ATTRIBUTE_REPARSE_POINT:
        tag = getattr(st, "st_reparse_tag", 0) or 0
        if tag & REPARSE_TAG_NAME_SURROGATE:
            return LINK_REDIRECT_REPARSE
    return None


def classify_link(entry: os.DirEntry) -> Optional[str]:
    """
    Classifica uma entrada de ``os.scandir`` como redirecionador sem segui-la.
    Retorna None para entradas comuns. Pode propagar OSError.
    """
    if entry.is_symlink():
        return LINK_SYMLINK
    is_junction = getattr(entry, "is_junction", None)  # Python 3.12+
    if is_junction is not None and is_junction():
        return LINK_JUNCTION
    return _redirect_kind_from_stat(entry.stat(follow_symlinks=False))


def classify_path(path: str) -> Optional[str]:
    """Equivalente a ``classify_link`` para um caminho (usado na raiz)."""
    if os.path.islink(path):
        return LINK_SYMLINK
    isjunction = getattr(os.path, "isjunction", None)  # Python 3.12+
    if isjunction is not None and isjunction(path):
        return LINK_JUNCTION
    return _redirect_kind_from_stat(os.lstat(path))


class DirectoryScanner:
    """
    Realiza varredura recursiva de arquivos de forma estritamente somente leitura.
    Garante confinamento fisico a base_dir e coleta de metadados sem alteracao em disco.
    """

    def __init__(self, base_dir: str, config: Optional[ScannerConfig] = None):
        if not os.path.exists(base_dir):
            raise FileNotFoundError(f"Diretorio base nao encontrado: '{base_dir}'")
        if not os.path.isdir(base_dir):
            raise NotADirectoryError(f"O caminho informado nao e um diretorio: '{base_dir}'")

        root_kind = classify_path(base_dir)
        if root_kind is not None:
            raise SecurityBoundaryError(
                f"A raiz autorizada nao pode ser um {root_kind}; informe o diretorio fisico real."
            )

        self.base_dir = os.path.abspath(base_dir)
        # Ancora fisica: todas as entradas sao comparadas contra este caminho real.
        self.real_base_dir = os.path.realpath(self.base_dir)
        self.config = config or ScannerConfig()

    def scan(self) -> ScanReport:
        """
        Executa o inventario e retorna um ScanReport estruturado.
        """
        start_time = time.perf_counter()
        walk = _ScanState(real_base_key=_canonical_key(self.real_base_dir))
        root_observation = None
        try:
            root_observation = FileObservation.from_stat(os.lstat(self.base_dir))
        except OSError as root_err:
            walk.errors.append(f"Erro ao acessar '.': {_describe_os_error(root_err)}")
        else:
            # Sem observacao inicial da raiz, nao percorrer nem criar snapshots tardios.
            self._walk(walk)
        duration_ms = (time.perf_counter() - start_time) * 1000

        return ScanReport(
            base_dir=self.base_dir,
            total_files=len(walk.items),
            total_bytes=sum(item.size_bytes for item in walk.items),
            items=walk.items,
            scan_duration_ms=duration_ms,
            errors=walk.errors,
            skipped=walk.skipped,
            root_observation=root_observation,
            item_observations=walk.observations,
        )

    # ------------------------------------------------------------------ helpers

    def _relative(self, path: str) -> str:
        """Caminho relativo a base_dir (lexical) com separador '/'; '.' para a raiz."""
        try:
            rel = os.path.relpath(path, self.base_dir)
        except ValueError:
            return "<fora da raiz>"
        return rel.replace("\\", "/")

    def _limit_reached(self, state: "_ScanState") -> bool:
        if len(state.items) < self.config.max_files_limit:
            return False
        if not state.limit_reported:
            state.errors.append(
                f"Limite maximo de arquivos atingido ({self.config.max_files_limit}). Varredura interrompida."
            )
            state.limit_reported = True
        return True

    # --------------------------------------------------------------------- walk

    def _walk(self, state: "_ScanState") -> None:
        """Travessia iterativa em profundidade, com entradas ordenadas por nome."""
        stack: List[Tuple[str, int]] = [(self.base_dir, 0)]
        while stack:
            current_dir, depth = stack.pop()

            # Limite de profundidade se configurado
            if self.config.max_depth is not None and depth > self.config.max_depth:
                continue
            # Limite maximo de seguranca contra estouro de memoria
            if self._limit_reached(state):
                return

            try:
                with os.scandir(current_dir) as iterator:
                    entries = sorted(iterator, key=lambda e: e.name)
            except OSError as dir_err:
                state.errors.append(
                    f"Erro ao listar diretorio '{self._relative(current_dir)}': {_describe_os_error(dir_err)}"
                )
                continue

            subdirs: List[str] = []
            for entry in entries:
                if self._limit_reached(state):
                    return

                # Trata arquivos/pastas ocultos
                if not self.config.include_hidden and entry.name.startswith("."):
                    continue

                rel_path = self._relative(entry.path)
                try:
                    subdir = self._process_entry(entry, rel_path, state)
                except OSError as entry_err:
                    # Inclui FileNotFoundError/PermissionError (ex.: corrida TOCTOU).
                    state.errors.append(f"Erro ao acessar '{rel_path}': {_describe_os_error(entry_err)}")
                    continue
                if subdir is not None:
                    subdirs.append(subdir)

            # Empilha em ordem reversa para visitar os subdiretorios em ordem alfabetica.
            for subdir in reversed(subdirs):
                stack.append((subdir, depth + 1))

    def _process_entry(self, entry: os.DirEntry, rel_path: str, state: "_ScanState") -> Optional[str]:
        """
        Aplica a politica a uma entrada. Registra arquivos em ``state.items`` e
        retorna o caminho do subdiretorio a descer (ou None).
        """
        link_kind = classify_link(entry)
        is_link = link_kind is not None
        if is_link and not self.config.follow_symlinks:
            state.skipped.append(f"'{rel_path}': {link_kind} nao seguido")
            return None

        # Confinamento fisico ANTES de descer ou registrar.
        real_path = os.path.realpath(entry.path)
        if not is_within_boundary(self.real_base_dir, real_path):
            if is_link:
                state.skipped.append(f"'{rel_path}': destino de {link_kind} fora da fronteira fisica")
            else:
                state.errors.append(f"Fronteira fisica violada em '{rel_path}': entrada resolve fora da raiz")
            return None

        key = _canonical_key(real_path)

        if entry.is_dir(follow_symlinks=self.config.follow_symlinks):
            if key == state.real_base_key or key in state.visited_dirs:
                state.skipped.append(f"'{rel_path}': diretorio ja visitado (ciclo ou duplicata)")
                return None
            state.visited_dirs.add(key)
            state.observations[rel_path] = FileObservation.from_stat(
                os.stat(entry.path, follow_symlinks=False))
            return entry.path

        if not entry.is_file(follow_symlinks=self.config.follow_symlinks):
            # Dispositivos, sockets, links quebrados etc. nao sao inventariados.
            return None

        # Filtro de extensoes permitidas se configurado
        _, ext = os.path.splitext(entry.name)
        if self.config.allowed_extensions:
            allowed_lower = [e.lower() for e in self.config.allowed_extensions]
            if ext.lower() not in allowed_lower:
                return None

        if key in state.seen_files:
            state.skipped.append(f"'{rel_path}': arquivo ja inventariado por outro caminho")
            return None

        # DirEntry.stat no Windows pode conter st_ino/st_dev/st_nlink zero.
        # Observar identidade durante o inventario, nunca tardiamente no hasher.
        stat_info = os.stat(entry.path, follow_symlinks=self.config.follow_symlinks)
        state.observations[rel_path] = FileObservation.from_stat(stat_info)
        state.seen_files.add(key)
        state.items.append(
            FileItem(
                path=rel_path,
                size_bytes=stat_info.st_size,
                modified_timestamp=stat_info.st_mtime,
            )
        )
        return None


class _ScanState:
    """Estado mutavel interno de uma unica execucao de ``scan``."""

    def __init__(self, real_base_key: str):
        self.real_base_key = real_base_key
        self.items: List[FileItem] = []
        self.errors: List[str] = []
        self.skipped: List[str] = []
        self.visited_dirs: Set[str] = set()
        self.seen_files: Set[str] = set()
        self.observations = {}
        self.limit_reported = False
