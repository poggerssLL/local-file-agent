# Core models and logic for Local File Agent
from .models import (
    FileItem,
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

__all__ = [
    "FileItem",
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
