# Core models and logic for Local File Agent
from .models import (
    FileItem,
    FileObservation,
    OperationType,
    OperationStatus,
    OperationAction,
    ExecutionPlan,
    SecurityBoundaryError,
    ScannerConfig,
    ScanReport,
)
from .boundary import (
    normalize_relative_path,
    is_within_boundary,
    resolve_within,
)
from .scanner import DirectoryScanner
from .hasher import HashConfig, HashSession, HashReport, HashResult, HashIssue, DuplicateGroup

__all__ = [
    "FileItem",
    "FileObservation",
    "HashConfig",
    "HashSession",
    "HashReport",
    "HashResult",
    "HashIssue",
    "DuplicateGroup",
    "OperationType",
    "OperationStatus",
    "OperationAction",
    "ExecutionPlan",
    "SecurityBoundaryError",
    "ScannerConfig",
    "ScanReport",
    "DirectoryScanner",
    "normalize_relative_path",
    "is_within_boundary",
    "resolve_within",
]
