"""Classificacao deterministica de metadados recebidos, sem acesso ao filesystem."""

from collections import Counter
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
import math
import ntpath
import re
from typing import Optional, Tuple

from .boundary import SecurityBoundaryError, normalize_relative_path
from .models import FileItem, ScanReport


_TOKEN = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")


def _finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


@dataclass(frozen=True)
class ClassificationRule:
    """Condicoes AND; extensoes OR; datas UTC epoch em intervalo [inicio, fim)."""

    rule_id: str
    category: str
    priority: int = 0
    extensions: Tuple[str, ...] = ()
    name_pattern: Optional[str] = None
    modified_start: Optional[float] = None
    modified_end: Optional[float] = None

    def __post_init__(self):
        for value in (self.rule_id, self.category):
            if not isinstance(value, str) or not _TOKEN.fullmatch(value):
                raise ValueError("invalid_rule_token")
        if type(self.priority) is not int or not 0 <= self.priority <= 1_000_000:
            raise ValueError("invalid_rule_priority")
        if not isinstance(self.extensions, tuple) or len(self.extensions) > 64:
            raise ValueError("invalid_rule_extensions")
        normalized = []
        for extension in self.extensions:
            if (not isinstance(extension, str) or not 2 <= len(extension) <= 32
                    or not extension.startswith(".")
                    or any(c in extension[1:] for c in ".:/\\*?[]")
                    or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in extension)):
                raise ValueError("invalid_rule_extension")
            normalized.append(extension.casefold())
        object.__setattr__(self, "extensions", tuple(sorted(set(normalized))))
        if self.name_pattern is not None:
            if (not isinstance(self.name_pattern, str) or not 1 <= len(self.name_pattern) <= 256
                    or any(c in self.name_pattern for c in ":/\\")
                    or any(ord(c) < 32 or ord(c) == 127 for c in self.name_pattern)):
                raise ValueError("invalid_rule_name_pattern")
            object.__setattr__(self, "name_pattern", self.name_pattern.casefold())
        for value in (self.modified_start, self.modified_end):
            if value is not None and not _finite_number(value):
                raise ValueError("invalid_rule_date")
        if (self.modified_start is not None and self.modified_end is not None
                and self.modified_start >= self.modified_end):
            raise ValueError("invalid_rule_date_interval")
        if not (self.extensions or self.name_pattern is not None
                or self.modified_start is not None or self.modified_end is not None):
            raise ValueError("empty_rule_conditions")


def default_classification_rules():
    groups = {
        "documents": (".pdf", ".txt", ".md", ".doc", ".docx", ".odt", ".rtf"),
        "images": (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"),
        "audio": (".mp3", ".wav", ".flac", ".ogg", ".m4a"),
        "video": (".mp4", ".mkv", ".avi", ".mov", ".webm"),
        "archives": (".zip", ".7z", ".rar", ".gz", ".tar"),
        "source": (".py", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml"),
    }
    return tuple(ClassificationRule("extension_" + category, category,
                                    extensions=extensions)
                 for category, extensions in sorted(groups.items()))


@dataclass(frozen=True)
class ClassificationConfig:
    rules: Tuple[ClassificationRule, ...] = field(default_factory=default_classification_rules)
    max_items: int = 50_000

    def __post_init__(self):
        if (not isinstance(self.rules, tuple) or len(self.rules) > 256
                or any(not isinstance(rule, ClassificationRule) for rule in self.rules)):
            raise ValueError("invalid_rules")
        if len({rule.rule_id for rule in self.rules}) != len(self.rules):
            raise ValueError("duplicate_rule_id")
        if type(self.max_items) is not int or not 1 <= self.max_items <= 50_000:
            raise ValueError("invalid_max_items")
        object.__setattr__(self, "rules", tuple(sorted(
            self.rules, key=lambda rule: (-rule.priority, rule.rule_id))))


@dataclass(frozen=True)
class RuleMatch:
    rule_id: str
    category: str
    priority: int
    conditions: Tuple[str, ...]


@dataclass(frozen=True)
class ClassificationSuggestion:
    path: str
    status: str
    category: Optional[str] = None
    matches: Tuple[RuleMatch, ...] = ()
    reason_code: str = ""


@dataclass(frozen=True)
class ClassificationIssue:
    code: str
    item_index: Optional[int] = None
    path: Optional[str] = None
    count: int = 1


@dataclass(frozen=True)
class ClassificationReport:
    status: str
    total_items: int = 0
    suggestions: Tuple[ClassificationSuggestion, ...] = ()
    errors: Tuple[ClassificationIssue, ...] = ()
    inventory_error_count: int = 0
    scope: str = "provided_inventory"

    @property
    def category_counts(self):
        return dict(sorted(Counter(s.category for s in self.suggestions
                                   if s.status == "classified").items()))


class ClassificationSession:
    """Nao abre caminhos nem chama scanner/hasher; nunca altera itens ou planos."""

    def __init__(self, config=None):
        self.config = ClassificationConfig() if config is None else config
        if not isinstance(self.config, ClassificationConfig):
            raise ValueError("invalid_classification_config")

    def analyze(self, inventory):
        if (not isinstance(inventory, ScanReport)
                or not isinstance(inventory.items, (list, tuple))
                or not isinstance(inventory.errors, (list, tuple))):
            return ClassificationReport("invalid_inventory", errors=(
                ClassificationIssue("invalid_inventory"),))
        total = len(inventory.items)
        inherited = len(inventory.errors)
        if total > self.config.max_items:
            return ClassificationReport("limit_exceeded", total_items=total,
                                        inventory_error_count=inherited, errors=(
                                            ClassificationIssue("item_limit_exceeded"),))
        validated = []
        observed_paths = []
        errors = []
        for index, item in enumerate(inventory.items):
            if not isinstance(item, FileItem):
                errors.append(ClassificationIssue("invalid_item", item_index=index))
                continue
            try:
                path = normalize_relative_path(item.path)
            except (SecurityBoundaryError, TypeError, ValueError):
                # Nao copiar a excecao: a politica de fronteira inclui a entrada bruta.
                errors.append(ClassificationIssue("invalid_path", item_index=index))
                continue
            # Count lexical collisions even when one record's metadata is invalid.
            observed_paths.append(path)
            if (type(item.size_bytes) is not int or item.size_bytes < 0
                    or not _finite_number(item.modified_timestamp)):
                errors.append(ClassificationIssue("invalid_metadata", item_index=index))
                continue
            validated.append((path, item.modified_timestamp))
        counts = Counter(path.casefold() for path in observed_paths)
        duplicate_keys = {key for key, count in counts.items() if count > 1}
        representatives = {}
        for path in observed_paths:
            key = path.casefold()
            if key in duplicate_keys:
                representatives[key] = min(path, representatives.get(key, path))
        for key in sorted(duplicate_keys):
            errors.append(ClassificationIssue("duplicate_path", path=representatives[key],
                                               count=counts[key]))
        suggestions = []
        for path, modified in validated:
            if path.casefold() in duplicate_keys:
                suggestions.append(ClassificationSuggestion(path, "invalid",
                                                             reason_code="duplicate_path"))
                continue
            basename = path.rsplit("/", 1)[-1].casefold()
            extension = ntpath.splitext(basename)[1]
            matches = []
            for rule in self.config.rules:
                conditions = []
                if rule.extensions:
                    if extension not in rule.extensions:
                        continue
                    conditions.append("extension")
                if rule.name_pattern is not None:
                    if not fnmatchcase(basename, rule.name_pattern):
                        continue
                    conditions.append("name")
                if rule.modified_start is not None or rule.modified_end is not None:
                    if ((rule.modified_start is not None and modified < rule.modified_start)
                            or (rule.modified_end is not None and modified >= rule.modified_end)):
                        continue
                    conditions.append("modified_at")
                matches.append(RuleMatch(rule.rule_id, rule.category, rule.priority,
                                         tuple(conditions)))
            if not matches:
                suggestion = ClassificationSuggestion(path, "unmatched",
                                                       reason_code="no_matching_rule")
            else:
                categories = {m.category for m in matches if m.priority == matches[0].priority}
                if len(categories) == 1:
                    suggestion = ClassificationSuggestion(path, "classified", categories.pop(),
                                                           tuple(matches), "highest_priority")
                else:
                    suggestion = ClassificationSuggestion(path, "ambiguous", matches=tuple(matches),
                                                           reason_code="priority_conflict")
            suggestions.append(suggestion)
        suggestions.sort(key=lambda s: (s.path.casefold(), s.path, s.status, s.category or ""))
        return ClassificationReport("partial" if errors or inherited else "complete", total,
                                    tuple(suggestions), tuple(errors), inherited)
