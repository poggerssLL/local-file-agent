# Limitações e Problemas Conhecidos: Local File Agent

Atualizado em: 2026-10-04.

## Limitações Ativas da Etapa 2B (Hardening de Fronteira e Confinamento)

1. **Condição de Corrida TOCTOU (Time-of-Check to Time-of-Use):**
   - Nenhuma verificação lexical ou checagem prévia em disco é capaz de eliminar por completo condições de corrida no sistema de arquivos. Um arquivo pode ser removido, alterado ou substituído por link entre a listagem de diretório (`scandir`), a validação de fronteira e a obtenção de metadados (`stat`).
   - Mitigação implementada: O `DirectoryScanner` detecta falhas transitórias (`FileNotFoundError`, `PermissionError`, `OSError`) no momento do acesso, trata-as como falhas parciais de inventário registradas de forma sanitizada em `ScanReport.errors` e prossegue com a varredura sem interromper o processo nem vazar dados confidenciais.
2. **Separação entre Confinamento Lexical e Físico:**
   - As funções de `src/core/boundary.py` (`normalize_relative_path`, `is_within_boundary`, `resolve_within`) são estritamente lexicais e não acessam o disco.
   - O confinamento físico contra links simbólicos, junctions e reparse points é de responsabilidade exclusiva dos módulos que interagem com o sistema de arquivos (`src/core/scanner.py`), utilizando `realpath` e inspeção de atributos/tags Win32.
3. **Execução de Operações em Disco Bloqueada:**
   - O motor transacional de aplicação física em disco permanece não implementado por design (previsto para a Etapa 8). Qualquer plano de execução permanece estritamente em modo `dry_run=True` e `approved=False`.
4. **Hashes e Leitura de Conteúdo Não Implementados:**
   - O scanner realiza exclusivamente a leitura de metadados (`size_bytes`, `mtime`, nomes). A leitura de conteúdo e o cálculo em blocos de hashes SHA-256 serão introduzidos na Etapa 3.
