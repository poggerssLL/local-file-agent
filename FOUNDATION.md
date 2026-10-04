# Arquitetura e Fundação Viva: Local File Agent

Atualizado em: 2026-10-04.
Etapa atual: **Etapa 2B - Hardening de Fronteira e Confinamento Físico** (Concluída).

---

## 1. Visão Geral do Sistema

O `Local File Agent` é um agente de software local projetado para organizar, classificar e auditar arquivos e diretórios no computador do usuário, mantendo integridade transacional, aprovação humana e privacidade absoluta.

```text
                             Erick (Usuário)
                                   │
                           revisa e autoriza
                                   │
    [Scanner / Inventário] ──► [Motor de Regras & LLM] ──► [Planejador de Operações]
          (Read-Only)              (Classificação)                (ExecutionPlan)
                                                                       │
                                                                       ▼
    [Diário de Auditoria] ◄─── [Motor Transacional] ◄────── [Aprovação Explícita]
      (Log de Desfazer)            (Move/Rename)
```

---

## 2. Invariantes Arquiteturais

1. **Separação entre Planejamento e Execução:**
   - O planejador (`OperationPlanner`) gera um plano imutável (`ExecutionPlan`) contendo a lista de ações propostas.
   - O motor transacional (`TransactionEngine`) **recusa-se** a executar qualquer plano que não possua a flag `approved = True` atribuída por decisão humana.
2. **Determinismo em Primeiro Lugar:**
   - A classificação tenta regras heurísticas e determinísticas primeiro (extensões, padrões de data, prefixos conhecidos). Apenas casos ambíguos consultam modelos de linguagem locais com saída estruturada.
3. **Mecanismo de Desfazer (*Undo Journal*):**
   - Nenhuma movimentação de arquivo é feita sem antes registrar em log SQLite a tupla reversível: `{id, timestamp, original_path, target_path, original_hash}`.
4. **Política Rígida de Fronteira e Confinamento (Etapa 2B):**
   - **Validação Lexical (`src/core/boundary.py`):** Planos de execução aceitam exclusivamente caminhos relativos normalizados. Rejeição terminante de caminhos absolutos, UNC (`\\server\share`), unidades (`C:`), drive-relative (`C:rel`), fluxos alternativos NTFS (`ADS`), escapes (`..`) e nomes reservados de dispositivos Windows. Comparação estritamente por componentes (`commonpath` com `normpath`/`normcase`), eliminando vulnerabilidades de prefixo de texto (`startswith`).
   - **Confinamento Físico (`src/core/scanner.py`):** A raiz base (`base_dir`) não pode ser link ou junção; cada entrada é validada fisicamente via `realpath` contra a âncora real antes da visita. Reparse points de redirecionamento (*name surrogate*, como symlinks e junctions) são pulados por padrão; placeholders de nuvem (OneDrive) são inventariados normalmente sem bloqueio genérico. Ciclos e pastas duplicadas são prevenidos via chaves canônicas de caminhos reais. Erros e skips são sanitizados sem vazamento de caminhos absolutos locais.

---

## 3. Contratos de Dados Centrais (`src/core/models.py` e `src/core/boundary.py`)

- **`boundary` (`src/core/boundary.py`):** Funções `normalize_relative_path`, `is_within_boundary`, `resolve_within` e exceção `SecurityBoundaryError`.
- **`FileItem`:** Representa um arquivo inventariado (caminho relativo, tamanho em bytes, data de modificação, hash SHA-256 opcional).
- **`OperationType`:** Enumeração das operações suportadas (`RENAME`, `MOVE`, `TAG`, `SIMULATE`).
- **`OperationAction`:** Ação atômica contendo `source_path`, `destination_path`, `reason` e `status`.
- **`ExecutionPlan`:** Coleção de ações planejadas com validação de segurança via `resolve_within`, `dry_run: bool` (padrão `True`) e `approved: bool` (padrão `False`).
- **`ScannerConfig`:** Configurações de profundidade, filtros, limite de arquivos e flag `follow_symlinks` (padrão `False`).
- **`ScanReport`:** Relatório estruturado de varredura com contagem por extensão, tempos, lista sanitizada de `errors` e campo aditivo de `skipped`.

---

## 4. Evolução por Etapas

As fases subsequentes do projeto construirão gradualmente sobre esta fundação, conforme definido no [`ROADMAP.md`](file:///C:/Users/erick/OneDrive/Documentos/Local%20File%20Agent/ROADMAP.md).
