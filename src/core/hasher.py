"""SHA-256 opt-in. Inventario e hashing sao operacoes separadas.

O backend privado e injetavel para testes; em producao somente Windows nativo.
Ordenacao: pontos de codigo Unicode dos paths normalizados, sem locale/casefold.
"""
import hashlib
import os
from dataclasses import dataclass, field
from typing import Optional

from .boundary import normalize_relative_path, resolve_within, SecurityBoundaryError
from .models import FileObservation, ScanReport


class HashFailure(Exception):
    """Codigo estavel, sem mensagem do SO ou path bruto."""
    def __init__(self, code, *, root=False, bytes_read=0):
        super().__init__(code)
        self.code = code
        self.root = root
        self.bytes_read = bytes_read


@dataclass(frozen=True)
class HashConfig:
    enabled: bool = False
    chunk_size: int = 262144
    max_file_bytes: int = 1_073_741_824
    max_total_bytes: int = 4_294_967_296

    def __post_init__(self):
        if type(self.enabled) is not bool:
            raise ValueError('enabled deve ser bool')
        for name in ('chunk_size', 'max_file_bytes', 'max_total_bytes'):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f'{name} deve ser inteiro positivo')
        if not 65536 <= self.chunk_size <= 1048576:
            raise ValueError('chunk_size fora de 65536..1048576')


@dataclass(frozen=True)
class HashIssue:
    code: str
    path: Optional[str] = None  # None para input invalido/erro da raiz
    error_type: Optional[str] = None
    errno: Optional[int] = None


@dataclass(frozen=True)
class HashResult:
    path: str
    size_bytes: int
    sha256_hash: Optional[str]
    status: str
    bytes_read: int = 0


@dataclass(frozen=True)
class DuplicateGroup:
    size_bytes: int
    sha256_hash: str
    paths: tuple[str, ...]

    @property
    def logical_redundant_bytes(self):
        return (len(self.paths) - 1) * self.size_bytes


@dataclass
class HashReport:
    status: str
    results: list[HashResult] = field(default_factory=list)
    groups: list[DuplicateGroup] = field(default_factory=list)
    errors: list[HashIssue] = field(default_factory=list)
    bytes_read: int = 0
    inventory_error_count: int = 0
    scope: str = 'provided_inventory'

    @property
    def logical_redundant_bytes(self):
        return sum(g.logical_redundant_bytes for g in self.groups)


def check_observation(expected, current, *, directory=False):
    """Falha fechada para observacoes incompletas, especiais ou mutadas."""
    if not isinstance(expected, FileObservation) or not isinstance(current, FileObservation):
        raise HashFailure('snapshot_missing')
    kind = 'directory' if directory else 'file'
    for obs in (expected, current):
        if any(type(getattr(obs, name)) is not int for name in
               ('device', 'inode', 'size', 'mtime_ns', 'ctime_ns', 'nlink')):
            raise HashFailure('snapshot_invalid')
        if obs.device < 0 or obs.size < 0 or obs.nlink < 1:
            raise HashFailure('snapshot_invalid')
        if (type(obs.attributes) is not int or type(obs.reparse_tag) is not int
                or obs.attributes < 0 or obs.reparse_tag < 0):
            raise HashFailure('capability_unknown')
    if current.kind != kind or expected.kind != kind:
        raise HashFailure('special_file')
    for obs in (expected, current):
        if obs.attributes is None or obs.reparse_tag is None or obs.inode <= 0:
            raise HashFailure('capability_unknown')
        # REPARSE_POINT, OFFLINE, RECALL_ON_OPEN, RECALL_ON_DATA_ACCESS.
        if obs.attributes & (0x400 | 0x1000 | 0x40000 | 0x400000) or obs.reparse_tag:
            raise HashFailure('unsafe_attributes')
        if not directory and obs.nlink != 1:
            raise HashFailure('hardlink_skipped')
    if current != expected:
        raise HashFailure('snapshot_changed')


def _issue(exc, path=None):
    if isinstance(exc, HashFailure):
        return HashIssue(exc.code, path)
    allowed = {FileNotFoundError: 'FileNotFoundError', PermissionError: 'PermissionError',
               OSError: 'OSError'}
    kind = allowed.get(type(exc), 'OSError')
    number = getattr(exc, 'errno', None)
    return HashIssue('io_failure', path, kind, number if type(number) is int else None)


class HashSession:
    def __init__(self, base_dir: str, config: Optional[HashConfig] = None, *, _backend=None):
        if not isinstance(base_dir, str) or not os.path.isabs(base_dir):
            raise ValueError('base_dir deve ser uma raiz absoluta explicitamente autorizada')
        self.base_dir = os.path.normpath(base_dir)
        self.config = config if config is not None else HashConfig()
        self._backend = _backend

    def analyze(self, inventory: ScanReport) -> HashReport:
        # Somente contagem: mensagens do scanner podem conter dados sensiveis.
        report = HashReport('disabled', inventory_error_count=(
            len(inventory.errors) if isinstance(inventory, ScanReport) else 0))
        if not self.config.enabled:
            return report
        backend = self._backend
        if backend is None:
            from .windows_hash_backend import WindowsHashBackend
            backend = WindowsHashBackend()
        if not backend.supported:
            report.status = 'unsupported'
            report.errors.append(HashIssue('backend_unsupported'))
            return report
        report.status = 'complete'
        if (not isinstance(inventory, ScanReport)
                or os.path.normcase(os.path.normpath(inventory.base_dir)) != os.path.normcase(self.base_dir)):
            report.status = 'invalid_root'
            report.errors.append(HashIssue('root_mismatch'))
            return report
        if not isinstance(inventory.root_observation, FileObservation):
            report.status = 'invalid_root'
            report.errors.append(HashIssue('root_snapshot_missing'))
            return report

        # Validacao de TODOS os paths antes de qualquer syscall de item.
        candidates = {}
        conflicts = set()
        for item in inventory.items:
            try:
                path = normalize_relative_path(item.path)
                resolve_within(self.base_dir, path)
            except (SecurityBoundaryError, TypeError, AttributeError):
                report.errors.append(HashIssue('invalid_path'))
                continue
            if path in candidates:
                if item.size_bytes != candidates[path].size_bytes:
                    conflicts.add(path)
                continue
            candidates[path] = item

        identities = set()
        try:
            with backend.pin_root(self.base_dir, inventory.root_observation) as root:
                for path in sorted(candidates):
                    item = candidates[path]
                    start_bytes = report.bytes_read
                    digest = None
                    status = 'failed'
                    try:
                        if path in conflicts:
                            raise HashFailure('conflicting_item')
                        obs = inventory.item_observations.get(path)
                        if not isinstance(obs, FileObservation):
                            raise HashFailure('snapshot_missing')
                        check_observation(obs, obs)
                        if type(item.size_bytes) is not int or item.size_bytes < 0 or item.size_bytes != obs.size:
                            raise HashFailure('invalid_size')
                        if obs.size + 1 > self.config.max_file_bytes:
                            raise HashFailure('file_budget')
                        # Uma sondagem de EOF obrigatoria; orçamento insuficiente = zero reads.
                        if obs.size + 1 > self.config.max_total_bytes - report.bytes_read:
                            raise HashFailure('total_budget')
                        with root.open_file(path, obs, inventory.item_observations) as stream:
                            root.check()
                            check_observation(obs, stream.observe())
                            identity = (obs.device, obs.inode)
                            if identity in identities:
                                raise HashFailure('duplicate_object')
                            sha = hashlib.sha256()
                            remaining = obs.size
                            while remaining:
                                root.check()
                                stream.check_namespace()
                                request = min(remaining, self.config.chunk_size)
                                if request > self.config.max_total_bytes - report.bytes_read:
                                    raise HashFailure('total_budget')
                                data = stream.read(request)
                                report.bytes_read += len(data)
                                if len(data) > request:
                                    raise HashFailure('backend_read_overflow')
                                if not data:
                                    raise HashFailure('early_eof')
                                sha.update(data)
                                remaining -= len(data)
                            root.check()
                            stream.check_namespace()
                            if report.bytes_read >= self.config.max_total_bytes:
                                raise HashFailure('total_budget')
                            probe = stream.read(1)
                            report.bytes_read += len(probe)
                            if probe:
                                raise HashFailure('file_grew')
                            check_observation(obs, stream.observe())
                            stream.check_namespace()
                            root.check()
                            digest = sha.hexdigest()
                            identities.add(identity)
                            status = 'success'
                    except (HashFailure, OSError) as exc:
                        # Win32 pode reportar bytes transferidos junto com falha.
                        report.bytes_read += getattr(exc, 'bytes_read', 0)
                        report.errors.append(_issue(exc, None if getattr(exc, 'root', False) else path))
                        if getattr(exc, 'root', False):
                            raise
                    finally:
                        report.results.append(HashResult(path, item.size_bytes, digest, status,
                                                         report.bytes_read - start_bytes))
                root.check()
        except (HashFailure, OSError) as exc:
            report.status = 'invalid_root'
            issue = _issue(exc)
            if issue not in report.errors:
                report.errors.append(issue)
            # Uma falha da raiz invalida ate os resultados previamente completos.
            report.results = [HashResult(r.path, r.size_bytes, None, 'invalid_root', r.bytes_read)
                              for r in report.results]
            return report

        grouped = {}
        for result in report.results:
            if result.status == 'success':
                grouped.setdefault((result.size_bytes, result.sha256_hash), []).append(result.path)
        report.groups = [DuplicateGroup(size, sha, tuple(sorted(paths)))
                         for (size, sha), paths in grouped.items() if len(paths) > 1]
        report.groups.sort(key=lambda group: group.paths)
        if report.errors or report.inventory_error_count:
            report.status = 'partial'
        return report
