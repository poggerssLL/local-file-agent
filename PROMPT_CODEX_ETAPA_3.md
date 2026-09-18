# Prompt de Inicialização para o Codex - Etapa 3 (Local File Agent)

Data: 2026-09-21 (Segunda-feira)  
Projeto: `Local File Agent`  
Caminho: `C:/Users/erick/OneDrive/Documentos/Local File Agent`  
Baseline Esperado: Branch `main`, Commit `bcd8cac`, 10/10 testes unitários aprovados  

---

## Como Usar

Abra o chat do **Codex** diretamente no diretório do projeto `Local File Agent` e envie o texto abaixo:

```text
Atue como o arquiteto sênior e organizador do projeto Local File Agent (C:/Users/erick/OneDrive/Documentos/Local File Agent).

Antes de qualquer ação:
1. Confirme o diretório e a raiz Git com `git rev-parse --show-toplevel`;
2. Verifique o baseline esperado: branch `main`, commit `bcd8cac`, working tree limpa;
3. Leia o AGENTS.md, FOUNDATION.md, ROADMAP.md e docs/PHASE_02_READONLY_INVENTORY_2026-09-18.md;
4. Execute a suíte de testes existente com `python -m unittest discover tests` e confirme 10 de 10 testes aprovados.

Seu Objetivo (Etapa 3 - Hashes SHA-256 e Detecção de Duplicidades):
1. Auditar as Etapas 1 (Fundação e Segurança) e 2 (Inventário Somente Leitura) implementadas pela equipe Antigravity multi-agente;
2. Implementar a Etapa 3 do ROADMAP.md:
   - Criar módulo `src/core/hasher.py` com cálculo determinístico de hash SHA-256 lendo arquivos em blocos (chunks de 64 KB a 1 MB) para não estourar memória RAM;
   - Criar lógica determinística de agrupamento e detecção de arquivos duplicados (por tamanho e hash);
   - Integrar o cálculo de hash opcional ao `DirectoryScanner` ou `ScanReport`;
3. Criar a suíte de testes unitários para a Etapa 3 em `tests/test_hasher.py` utilizando a árvore de fixtures sintéticos (`tests/fixtures/synthetic_tree/`);
4. Atualizar ROADMAP.md, PROJECT_STATE.md e gerar o relatório em `docs/PHASE_03_HASHES_AND_DUPLICATES_2026-09-21.md`.

Regras Invioláveis:
- Operação 100% SOMENTE LEITURA: nenhuma modificação, deleção ou movimentação de arquivos em disco;
- Não acesse nem processe arquivos reais de Erick; trabalhe estritamente com os fixtures sintéticos;
- Mantenha 100% de confinamento ao diretório do projeto;
- Não execute git push sem aprovação nominal expressa de Erick.
```
