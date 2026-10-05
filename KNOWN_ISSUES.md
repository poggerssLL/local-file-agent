# Limitações e Problemas Conhecidos: Local File Agent

Atualizado em: 2026-10-05.

## Limitações Ativas da Etapa 2B (Hardening de Fronteira e Confinamento)

1. **Condição de Corrida TOCTOU (Time-of-Check to Time-of-Use):**
   - Nenhuma verificação lexical ou checagem prévia em disco é capaz de eliminar por completo condições de corrida no sistema de arquivos. Um arquivo pode ser removido, alterado ou substituído por link entre a listagem de diretório (`scandir`), a validação de fronteira e a obtenção de metadados (`stat`).
   - Mitigação implementada: O `DirectoryScanner` detecta falhas transitórias (`FileNotFoundError`, `PermissionError`, `OSError`) no momento do acesso e registra erros sanitizados em `ScanReport.errors`. Falhas de entradas permitem continuar; falha na observação inicial da raiz encerra sem travessia e retorna relatório vazio com `root_observation=None` (complemento de release 2026-10-05).
2. **Separação entre Confinamento Lexical e Físico:**
   - As funções de `src/core/boundary.py` (`normalize_relative_path`, `is_within_boundary`, `resolve_within`) são estritamente lexicais e não acessam o disco.
   - O confinamento físico contra links simbólicos, junctions e reparse points é de responsabilidade exclusiva dos módulos que interagem com o sistema de arquivos (`src/core/scanner.py`), utilizando `realpath` e inspeção de atributos/tags Win32.
3. **Execução de Operações em Disco Bloqueada:**
   - O motor transacional de aplicação física em disco permanece não implementado por design (previsto para a Etapa 8). Qualquer plano de execução permanece estritamente em modo `dry_run=True` e `approved=False`.
4. **Scanner e Hashes Separados:**
   - O scanner continua metadados somente. O hasher da Etapa 3 lê conteúdo apenas
     com opt-in, snapshots completos e backend Windows suportado; o gate atual
     usa exclusivamente fixtures sintéticos, sem validar dados reais.

## Limitações da Etapa 3

- Regressão da captura inicial da raiz corrigida em 2026-10-05: OSError após
  o constructor não propaga mensagem/filename do SO; erro usa apenas '.', tipo
  e errno opcional. Não há snapshot tardio. Hashing enabled com backend
  suportado recusa root_snapshot_missing com zero bytes e sem pin_root.
  Prova nova é simulada (desaparecimento/acesso/I/O), sem remoção real de raiz
  ou alteração de ACL. Exceções no constructor e fora de OSError mantêm os
  contratos existentes. ScanReport.base_dir continua absoluto por compatibilidade;
  sanitização das mensagens não torna o relatório inteiro anônimo. Suíte do
  escritor e execução independente do reviewer Codex gpt-6.1-sol high 70/69/1,
  exit 0; gate aceito exclusivamente para fixtures NTFS locais sintéticas.
  Sem commit/push; estado atual do remoto desconhecido, sem fetch/rede.

- Não há snapshot atômico nem confinamento absoluto. READ_ATTRIBUTES sozinho
  não estabiliza share-access. O handle de dados com GENERIC_READ e share READ
  recusa escritores/deleters comuns; rename ancestral é recusado com descendente
  aberto. A janela anterior a ReOpenFile é detectada, não bloqueada. Mappings já
  existentes, filtros/kernel, mutadores privilegiados e metadados restaurados
  são riscos residuais. Um SHA256 concluído representa bytes observados, não
  prova imutabilidade futura nem comparação byte a byte sem risco de colisão.
- A fixação de ancestrais cobre a raiz autorizada e seus descendentes. A raiz
  é revalidada por path/handle ao uso; o namespace acima dela não é integralmente
  fixado. Abertura inicial de metadados ainda pode ser afetada por mudanças em
  componentes acima da raiz. Não se promete ausência absoluta de I/O de metadata
  externo sob mutadores de namespace privilegiados; dados só são lidos após
  validação do objeto, volume e caminho final. Drives remotos e UNC são recusados
  antes da abertura, inclusive quando simulados em testes sem rede.
- A travessia intermediária de metadata ainda usa paths: OPEN_REPARSE_POINT
  protege a folha, não componentes intermediários. Uma substituição concorrente
  por symlink (inclusive permitido em Developer Mode) ou junction pode causar
  eventual contato SMB antes da recusa por final path/attrs/identidade. Não há
  promessa de zero rede absoluto nesse cenário. Nenhum SMB real foi acessado
  no gate; NtCreateFile/aberturas relativas a handles ficam fora desta etapa.
- Suporte conservador: Windows/NTFS em drive local FIXED, FileIdInfo,
  atributos/tag/case sensitivity/final path conhecidos. Falha de capacidade
  recusa conteúdo; OS não Windows retorna unsupported. Sem fallback POSIX.
  Coerência de timestamps/identidade foi executada em Python 3.12.9 Windows;
  outras versões/filesystems não receberam validação real neste gate.
- Todos os reparse/cloud/OFFLINE/RECALL são recusados, mesmo locais ou seguros
  para inventário. Nuvem é simulada; não houve conta/provedor real. Hardlinks
  são skipped; não há deduplicação física, exclusão, undo ou motor transacional.
- Um byte de margem é obrigatório nos dois budgets para sondagem de EOF;
  arquivos exatamente no limite são recusados. Falhas e crescimento consomem
  os bytes já transferidos e deixam digest None. Não há cache/persistência.
- Mudanças inofensivas de metadados ou root namespace podem invalidar toda a
  sessão. Inventários antigos sem snapshots devem ser refeitos, sem fabricar
  observações tardias. Inventário com filtros/profundidade/erros não representa
  todos os arquivos; os grupos abrangem somente os sucessos apresentados.
- Symlink real de folha para sentinela externa à raiz testada foi skipped por
  privilégio indisponível (winerror 1314). Isso bloqueia a alegação específica
  de prova nativa com symlink de folha. Há prova nativa de junction ancestral,
  hardlink externo e simulações de folha/handle/final path; nenhuma substitui
  esse cenário. Gate inicial aprovado apenas para fixtures NTFS locais sintéticas;
  complementos aceitos na revisão delimitada do coordenador com phase-gate-reviewer.
- Algumas mutações preparatórias de fixtures sofreram PermissionError transitório
  na execução de desenvolvimento; reexecução direcionada passou. Não foi alterada
  a política de sharing nem habilitado privilégio para contornar essas falhas.
- Conteúdo, size e mtime foram preservados em fixtures de hashing; atime não
  é prometido. A fixture antiga e o relatório 2B não foram modificados.
- HashReport tem scope provided_inventory e inventory_error_count sanitizado.
  Complete cobre somente os itens recebidos; filtros/profundidade e exclusões
  não são prova de cobertura integral. Erros do inventário tornam status partial
  preservando hashes válidos, sem copiar mensagens do scanner.
- Ressalvas adicionais do gate: delete direto não foi testado (sharing/rename
  foram). A autorização da raiz depende do chamador: HashSession recebe uma
  raiz absoluta, não consulta uma allowlist ou prova consentimento humano.
  OneDrive/antivírus podem interferir nas fixtures; a causa das PermissionError
  transitórias não foi diagnosticada. OPEN_NO_RECALL e recusa de cloud são
  controles conservadores, sem garantia absoluta contra hidratação/contato
  remoto quando componentes intermediários mudam.
- Limites não bloqueantes registrados no gate: itens repetidos com mesmo path
  normalizado e tamanho são deduplicados silenciosamente (conflito de tamanho
  é erro); isso não é evidência de qualidade/cobertura do inventário recebido.
  Exceções inesperadas fora de HashFailure/OSError podem propagar em vez de
  gerar HashReport sanitizado. Não foi ampliado o tratamento de exceções nesta
  etapa; consumidores devem tratar falhas inesperadas sem publicar tracebacks.
