# Estado Atual do Projeto: Local File Agent

Atualizado em: 2026-10-04.

## Resumo Factual

- **Repositório:** `Local File Agent`
- **Caminho Local:** `C:/Users/erick/OneDrive/Documentos/Local File Agent`
- **Branch:** `main`
- **Etapa Atual:** **Etapa 2B - Hardening de Fronteira e Confinamento Físico** (Concluída)
- **Status do Sistema:** Hardening completo de fronteira e inventário consolidado antes da introdução de hashes. Política unificada em `src/core/boundary.py` (eliminação definitiva de `startswith`, validação por componentes com `commonpath`, rejeição estrita de absolutos, UNC, drive-relative, ADS e escapes). Scanner robustecido em `src/core/scanner.py` com ancoragem física via `realpath`, distinção precisa de links via bit *name surrogate* (sem bloqueio genérico a placeholders do OneDrive), prevenção determinística de ciclos e duplicatas, ordenação alfabética e sanitização de mensagens de erro/skips sem vazamento de caminhos absolutos.

## Evidências

- **Módulos Centrais:** `src/core/boundary.py`, `src/core/models.py`, `src/core/scanner.py`.
- **Testes de Unidade:** 32 de 32 testes aprovados em `tests/test_foundation.py`, `tests/test_scanner.py`, `tests/test_boundary.py` e `tests/test_scanner_hardening.py`.
- **Invariantes Ativas:** Confinamento lexical e físico; planos inexecutáveis sem aprovação humana expressa (`approved = False` e `dry_run = True` por padrão); sem leitura de conteúdo de arquivos nem cálculo de hash SHA-256 no core (escopo estritamente respeitado).
