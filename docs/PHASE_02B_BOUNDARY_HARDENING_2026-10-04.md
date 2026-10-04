# Fase: Etapa 2B - Hardening de Fronteira e Confinamento Físico - 2026-10-04

## 1. Decisão do Gate

**APROVADO no escopo de Hardening de Fronteira e Confinamento Físico (Modificações em disco: BLOQUEADO; Hashes/Duplicatas: BLOQUEADO).**

A Etapa 2B concluiu o endurecimento preventivo de todas as políticas de fronteira de diretório e caminhos antes do início do cálculo de hashes:
1. **Eliminação de Vulnerabilidade de Prefixo:** Substituído definitivamente o método `startswith` por comparação estrita de componentes de caminho (`os.path.commonpath`), com normalização canônica de maiúsculas/minúsculas e separadores do Windows (`normpath`, `normcase`), prevenindo ataques de desvio para diretórios irmãos com o mesmo prefixo textual;
2. **Política Estrita de Caminhos Relativos:** Planos de execução (`ExecutionPlan`) aceitam apenas caminhos relativos ao diretório autorizado, rejeitando terminantemente caminhos absolutos, UNC (`\\server\share`), unidades Win32 (`C:`), caminhos drive-relative (`C:rel`), fluxos alternativos NTFS (`ADS`), componentes de escape (`..`), caracteres de controle e nomes de dispositivos reservados do Windows (`CON`, `NUL`, `AUX`, `PRN`, `COM1-9`, `LPT1-9`, etc.);
3. **Confinamento Físico no Scanner:** O `DirectoryScanner` valida que a raiz base é um diretório físico real (rejeitando symlinks ou junctions como `base_dir`) e ancora todas as verificações no caminho resolvido via `realpath`;
4. **Classificação Precisa de Links e Reparse Points:** Identificação de redirecionadores via bit *name surrogate* (`0x20000000`, cobrindo symlinks e junctions), pulando-os por padrão em `ScanReport.skipped` sem bloquear atributos genéricos (`FILE_ATTRIBUTE_REPARSE_POINT`), assegurando suporte completo e inventário regular de arquivos em nuvem (placeholders do Microsoft OneDrive);
5. **Prevenção de Ciclos e Duplicatas:** Rastreamento determinístico de diretórios e arquivos por chave canônica de caminho real, impedindo loops infinitos ou repetições de varredura;
6. **Ordenação Determinística e Sanitização:** Travessia iterativa ordenada alfabeticamente por nome de entrada, com mensagens de erro (`errors`) e skips (`skipped`) sanitizadas (caminhos relativos + tipo de exceção + errno), sem vazamento de caminhos absolutos locais do sistema hospedeiro.

---

## 2. Escopo e Baseline

- **Repositório:** `Local File Agent`, branch `main`, commit base `026c5e00`.
- **Arquivos Criados/Modificados:**
  - `src/core/boundary.py` (novo): Política única e lexical de fronteira (`normalize_relative_path`, `is_within_boundary`, `resolve_within`, `SecurityBoundaryError`);
  - `src/core/models.py`: `ExecutionPlan.validate_safety()` integrado à política de fronteira; campo aditivo `skipped` em `ScanReport`; contratos `FileItem` e `ScannerConfig` estritamente preservados;
  - `src/core/scanner.py`: Scanner com âncora física, travessia determinística iterativa, detecção de *name surrogate*, prevenção de ciclos, tratamento resiliente de `OSError`/`FileNotFoundError` e sanitização de logs;
  - `src/core/__init__.py`: Reexportação dos símbolos públicos de fronteira;
  - `tests/test_boundary.py` (novo): 13 testes cobrindo validação lexical, rejeição de vetores de escape, normalização Windows e invariantes de planos;
  - `tests/test_scanner_hardening.py` (novo): 9 testes cobrindo classificação de links, distinção de placeholders OneDrive, prevenção de ciclos, confinamento físico e sanitização;
  - Documentação atualizada: `PROJECT_STATE.md`, `FOUNDATION.md`, `ROADMAP.md`, `KNOWN_ISSUES.md`, `DECISIONS.md` (ADR-004).

---

## 3. Evidências de Testes e Validação

### 3.1 Execução da Suíte de Testes
```text
python -m unittest discover tests
................................
----------------------------------------------------------------------
Ran 32 tests in 0.073s

OK
```
Total de 32 testes unitários aprovados cobrindo fundação (5), scanner básico (5), fronteira lexical e planos (13) e endurecimento físico do scanner (9).

### 3.2 Verificação de Integridade Git e Conformidade de Escopo
- `git diff --check`: 0 avisos de whitespace ou formatação;
- Auditoria de código em `src/core/`: Confirmada **ausência total** de `hashlib`, leitura de conteúdo de arquivos e rotinas de deduplicação (reservados para a Etapa 3).

---

## 4. Diferenciação Explícita de Implementação e Validação

- **O que foi implementado:**
  - Módulo de fronteira unificado com funções lexicais puras;
  - Scanner com checagem física prévia em cada nó da árvore de diretórios;
  - Classificador de reparse tags e name surrogates do Win32;
  - Dataclass e relatório estruturado de `ScanReport` com campo aditivo de skips.
- **O que foi testado com mocks e fixtures sintéticos:**
  - Simulação de reparse points com bit surrogate vs. tags de nuvem (OneDrive);
  - Simulação de symlinks externos e validação de interceptação de escape físico;
  - Simulação de referências circulares de diretórios para validação do corte de loop;
  - Injeção de `FileNotFoundError` em `_process_entry` e validação de sanitização de erros (`FileNotFoundError`, `PermissionError`).
- **O que foi validado em execução real:**
  - Varredura de árvore física de arquivos sintéticos em disco (`tests/fixtures/synthetic_tree`);
  - Normalização real de caminhos pelo runtime de Python 3.12 no sistema de arquivos NTFS do Windows 11.
- **O que é trabalho futuro ou planejado:**
  - **Etapa 3:** Cálculo determinístico de hashes SHA-256 lendo arquivos em blocos de memória e identificação de duplicidades reais.

---

## 5. Limitações Conhecidas e Risco Residual (TOCTOU)

- **Impossibilidade de Eliminação Física de TOCTOU:**
  Em qualquer sistema de arquivos concorrente, o estado do disco pode sofrer mutação entre a enumeração (`scandir`), a validação de fronteira física (`realpath`) e a leitura de metadados (`stat`). O sistema não tenta bloquear o sistema de arquivos; ao invés disso, detecta e descarta falhas de I/O em tempo de execução, registrando-as como erros parciais de inventário sem interromper a execução e sem vazar caminhos do host.
- **Modo Somente Leitura:**
  Nenhuma alteração, exclusão, movimentação ou gravação de arquivos de usuário foi realizada ou está habilitada.
