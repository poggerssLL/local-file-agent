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
from .classifier import (
    ClassificationRule, ClassificationConfig, ClassificationSession,
    ClassificationReport, ClassificationSuggestion, ClassificationIssue, RuleMatch,
    default_classification_rules,
)

__all__ = [
    "ClassificationRule",
    "ClassificationConfig",
    "ClassificationSession",
    "ClassificationReport",
    "ClassificationSuggestion",
    "ClassificationIssue",
    "RuleMatch",
    "default_classification_rules",
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
