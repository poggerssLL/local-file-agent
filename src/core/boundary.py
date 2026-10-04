"""
Politica unica de fronteira de caminhos do Local File Agent (Etapa 2B).

Este modulo concentra TODAS as decisoes de confinamento de caminhos:

1. ``normalize_relative_path``: validacao lexical (sem tocar o disco) de um
   caminho que DEVE ser relativo a uma raiz autorizada. Rejeita caminhos
   absolutos, UNC/dispositivo (``\\\\server\\share``, ``\\\\?\\``, ``\\\\.\\``),
   unidades (``C:``, ``C:foo``), caminhos enraizados (``/x``, ``\\x``),
   componentes ``..``, componentes com pontos/espacos finais (que o Win32
   descarta silenciosamente), nomes de dispositivo reservados do Windows,
   ``:`` (fluxos alternativos/ADS) e caracteres de controle.
2. ``is_within_boundary``: comparacao por COMPONENTES de dois caminhos
   absolutos, com ``normcase``/``normpath`` (insensivel a caixa e a separador
   no Windows). Nunca usa ``startswith`` -- ``C:/x/Teste2`` NAO esta dentro de
   ``C:/x/Teste``.
3. ``resolve_within``: combina (1) e (2) para produzir um caminho absoluto
   lexicalmente confinado.

Limites conhecidos (documentados em KNOWN_ISSUES.md):
- As funcoes deste modulo sao puramente lexicais; o confinamento FISICO
  (symlinks, junctions, reparse points) e responsabilidade de quem toca o disco
  (``DirectoryScanner``), usando ``os.path.realpath`` antes de comparar.
- Nenhuma verificacao elimina condicoes de corrida TOCTOU entre a checagem e o
  uso de um caminho.
"""

import ntpath
import os
import re
from typing import Iterable

__all__ = [
    "SecurityBoundaryError",
    "normalize_relative_path",
    "is_within_boundary",
    "resolve_within",
]


class SecurityBoundaryError(ValueError):
    """Disparada quando uma acao tenta escapar da raiz do diretorio autorizado."""
    pass


# Separadores aceitos na entrada (ambos os estilos sao tratados como separador
# independentemente da plataforma, para que a politica seja deterministica).
_SEPARATORS = re.compile(r"[\\/]+")

# Nomes de dispositivo reservados do Windows (comparacao insensivel a caixa,
# considerando apenas o "stem" antes do primeiro ponto).
_RESERVED_DEVICE_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"COM{i}" for i in "123456789\u00b9\u00b2\u00b3"}
    | {f"LPT{i}" for i in "123456789\u00b9\u00b2\u00b3"}
)


def _reject(raw: object, reason: str) -> "SecurityBoundaryError":
    return SecurityBoundaryError(f"Caminho rejeitado pela politica de fronteira ({reason}): {raw!r}")


def _validate_component(raw: str, component: str) -> None:
    if component == "..":
        raise _reject(raw, "componente '..' (traversal)")
    stripped = component.rstrip(" .")
    if not stripped:
        # '...', '. .', ' ' etc. -- o Win32 os reduz a vazio/'.'/'..'.
        raise _reject(raw, "componente composto apenas de pontos/espacos")
    if stripped != component:
        # 'nome.' e 'nome ' sao apelidos de 'nome' no Win32: ambiguo.
        raise _reject(raw, "componente com ponto ou espaco final")
    stem = component.split(".", 1)[0].rstrip(" ").upper()
    if stem in _RESERVED_DEVICE_NAMES:
        raise _reject(raw, "nome de dispositivo reservado do Windows")


def normalize_relative_path(rel_path: str) -> str:
    """
    Valida lexicalmente um caminho que deve ser RELATIVO a uma raiz autorizada
    e retorna sua forma canonica com separador ``/`` (ex.: ``"docs/a.pdf"``).

    Nao acessa o disco. Componentes vazios e ``.`` sao descartados; qualquer
    outra construcao suspeita dispara ``SecurityBoundaryError``.
    """
    if not isinstance(rel_path, str):
        raise _reject(rel_path, "tipo invalido; esperado str")
    if not rel_path or not rel_path.strip():
        raise _reject(rel_path, "caminho vazio")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in rel_path):
        raise _reject(rel_path, "caractere de controle")
    if rel_path[0] in ("/", "\\"):
        # Cobre '/abs', '\\enraizado', UNC '\\\\srv\\share' e '\\\\?\\', '\\\\.\\'.
        raise _reject(rel_path, "caminho absoluto, enraizado ou UNC")
    drive, _ = ntpath.splitdrive(rel_path)
    if drive:
        raise _reject(rel_path, "unidade ou UNC")
    if ":" in rel_path:
        # 'C:foo' (relativo a unidade) e fluxos alternativos 'arq.txt:ads'.
        raise _reject(rel_path, "caractere ':' (unidade ou fluxo alternativo)")
    if os.path.isabs(rel_path):
        # Defesa adicional dependente da plataforma.
        raise _reject(rel_path, "caminho absoluto")

    components = [c for c in _SEPARATORS.split(rel_path) if c not in ("", ".")]
    if not components:
        raise _reject(rel_path, "caminho sem componentes (refere-se a propria raiz)")
    for component in components:
        _validate_component(rel_path, component)
    return "/".join(components)


def _canonical(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def is_within_boundary(base: str, candidate: str) -> bool:
    """
    Retorna True se ``candidate`` for ``base`` ou estiver abaixo de ``base``,
    comparando por componentes apos ``abspath``/``normpath``/``normcase``.

    Nao resolve links: para confinamento fisico, passe caminhos ja resolvidos
    com ``os.path.realpath``. Unidades diferentes retornam False.
    """
    if not isinstance(base, str) or not isinstance(candidate, str):
        return False
    if not base.strip() or not candidate.strip():
        return False
    canonical_base = _canonical(base)
    canonical_candidate = _canonical(candidate)
    try:
        common = os.path.commonpath([canonical_base, canonical_candidate])
    except ValueError:
        # Unidades diferentes, ou mistura de caminhos absolutos/relativos.
        return False
    return common == canonical_base


def resolve_within(base: str, rel_path: str) -> str:
    """
    Valida ``rel_path`` com ``normalize_relative_path``, junta-o a ``base`` e
    confirma o confinamento por componentes. Retorna o caminho absoluto
    normalizado (lexical; nao resolve links).
    """
    if not isinstance(base, str) or not base.strip():
        raise _reject(base, "raiz base invalida")
    normalized = normalize_relative_path(rel_path)
    absolute_base = os.path.normpath(os.path.abspath(base))
    parts: Iterable[str] = normalized.split("/")
    full = os.path.normpath(os.path.join(absolute_base, *parts))
    if not is_within_boundary(absolute_base, full):
        raise _reject(rel_path, "resultado fora da raiz autorizada")
    return full
