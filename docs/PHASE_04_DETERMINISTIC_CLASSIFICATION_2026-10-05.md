# Etapa 4 — Classificação determinística de metadados

Data: 2026-10-05. Baseline Git: `49c7dbe`, Etapa 3 publicada.
Implementação autorizada por Erick, incluindo manutenção paralela.
Entrega local sem commit/push; gate independente pendente neste registro inicial.

## Implementação e contrato

`src/core/classifier.py` oferece `ClassificationSession.analyze(ScanReport)`,
configuração imutável e regras explícitas por extensão, glob do basename e data
de modificação UTC epoch. Usa somente os metadados recebidos; não consulta a raiz,
scanner, hasher, filesystem, relógio atual, LLM ou rede. Não altera FileItem,
ScanReport, hashes recebidos, categorias anteriores ou planos. A API é aditiva.

- Condições de uma regra são AND; extensões dentro da condição são OR.
- Extensão final e basename usam casefold. Não há regex nem inspeção de conteúdo.
  `.tar.gz` corresponde à extensão final `.gz`; dotfiles sem extensão usam nome.
- Datas: início inclusivo e fim exclusivo `[start, end)`, em UTC epoch numérico
  finito, sem parsing de datas em nomes nem dependência de timezone/locale.
- Prioridade inteira maior vence. Todos os matches ficam auditáveis e ordenados
  por `(-priority, rule_id)`. Empate entre categorias distintas é `ambiguous`;
  empate na mesma categoria é `classified`. Sem matches: `unmatched`.
- Categorias e IDs são tokens ASCII controlados, não destinos de organização.
  Regras padrão para documents/images/audio/video/archives/source; executáveis e
  extensões desconhecidas ficam unmatched. Configuração sem regras é permitida;
  uma regra sem condição é rejeitada.
- Até 256 regras, 64 extensões por regra, glob até 256 caracteres, IDs únicos,
  prioridade 0..1.000.000 e limite de inventário 1..50.000.
- Caminhos passam pela política lexical existente; não há resolução física.
  Dados inválidos produzem códigos genéricos sem reproduzir entradas/exceções.
- Duplicatas por caminho normalizado/casefold são recusadas em todas as entradas;
  não são deduplicadas silenciosamente. Representantes são coletados em uma
  passagem, evitando a varredura quadrática do rascunho inicial.
- Sugestões ordenadas por `(path.casefold(), path, status, category)`; esta regra
  pertence ao classificador e não altera a ordenação Unicode do hasher.

`ClassificationReport.scope=provided_inventory`. Complete significa análise dos
itens recebidos sem erros, não cobertura integral do disco nem ausência de
ambiguidades. Erros do scanner são contados sem copiar mensagens e produzem
partial preservando sugestões válidas. Entradas inválidas de tipo/path/metadados
ficam apenas em errors; duplicatas válidas lexicalmente também recebem sugestão
invalid. Logo `len(suggestions) <= total_items`. Índices de erros de entrada
referem-se à ordem recebida. Acima do budget: limit_exceeded sem sugestões.

## Evidências do coordenador

- 19 testes novos, somente metadados sintéticos em memória, aprovados.
- `python -B -m unittest discover tests -q`: exit 0, 89 testes, 88 aprovados e
  1 skip histórico de symlink nativo (winerror 1314).
- Cobertura: regras combinadas/datas, Unicode/case, precedência/conflito,
  permutações, duplicatas com 5.000 entradas, limites, entradas hostis, mensagens
  sensíveis, erros herdados, ausência de mutação e spies de I/O/scanner/hash/
  ExecutionPlan. Spies não equivalem a monitoramento da rede do sistema.
- A primeira suíte no checkout isolado encontrou um pré-requisito legado ausente:
  scanner espera seis arquivos, mas Git contém cinco arquivos visíveis e não
  contém a fixture oculta. Resultado: 1 falha/87 pass/1 skip. Foi criada somente
  nesse checkout uma sentinela sintética ignorada pelo Git em
  `tests/fixtures/synthetic_tree/.oculto/fixture.tmp`; a suíte passou em seguida.
  Nenhum byte de fixture versionada nem fixture original foi alterado. Clones
  limpos ainda precisam dessa preparação legada; não há correção de scanner.

## Delegação e limites

Preflight real Antigravity/Gemini 3.8 Flash high, modo plan com sandbox, recebeu
Task e Dispatch no Orca. Revisou o rascunho sem alterar arquivos do projeto.
Check e worker_done foram recusados com runtime_access_denied/EPERM. Turno final
foi observado; o coordenador encerrou a autoridade do Dispatch e registrou a
Task como failed, preservando o terminal. Não se declara lifecycle concluído
nem aprovação independente a partir dessa revisão. Achados aplicados: custo de
duplicatas e contrato de sugestões parciais.

Nenhum dado real, nuvem, modelo local, SQLite, plano, movimentação, rename,
exclusão ou undo foi usado/implementado. Regras classificam convenções, não o
significado real de arquivos. A leitura física e seus riscos permanecem sob os
contratos das etapas anteriores. Etapa 5 não iniciada.

## Complemento após auditoria independente

A primeira auditoria Codex Sol 6.1 high em sandbox read-only executou 19 testes
puramente em memória e diff-check, exit 0. Veredito: COMPLEMENTO NECESSÁRIO.
Achado: metadados inválidos eram descartados antes da contagem de colisões,
permitindo classificar o outro registro do mesmo path.
O coordenador passou a contar todos os caminhos lexicalmente válidos antes
de validar metadados e recusou também a entrada válida desse conflito. Nova
regressão cobre tamanho inválido, timestamp NaN/inf/bool e as duas permutações.
PROJECT_STATE distingue main principal de checkout isolado detached.
Suíte posterior: 90 testes, 89 aprovados e o mesmo skip, exit 0.
Total da Etapa 4: 20 testes de metadados sintéticos em memória. Código congelado
para revisão complementar; gate ainda pendente neste registro.

O reviewer tentou check/worker_done uma vez e recebeu CommandNotFoundException
para orca no shell restrito. Não houve troca de executável ou bypass. Turno
final observado, Dispatch abandonado e Task failed pelo coordenador. Isso
é evidência de revisão textual útil, não lifecycle concluído. O próximo
preflight pode qualificar o caminho do mesmo executável Orca já resolvido e
verificado pelo coordenador; não significa substituir binário nem remover sandbox.

## Fechamento técnico

Revisão complementar independente Codex gpt-6.1-sol high em sandbox read-only:
APROVADA a API pura no escopo revisado, sem outro bloqueador material.
Reviewer executou independentemente 20/20 testes em memória e diff-check com
exit 0. Confirmou correção de duplicatas com metadados inválidos e identificação
do checkout detached. Suíte completa do coordenador: 90/89/1, exit 0; o skip e
os limites nativos da Etapa 3 permanecem. Gate aceito pelo coordenador com
phase-gate-reviewer somente no escopo sintético, sem avançar à Etapa 5.

Canal de evidência: transcript/terminal real, revisado pelo coordenador. Não
houve worker_done durável: o mesmo executável Orca qualificado também recebeu
CommandNotFoundException no shell restrito. O turno final foi observado,
Dispatch abandonado e Task failed por falha do lifecycle, preservando o terminal.
Aprovação técnica do File Agent não é sucesso do lifecycle nem homologação do
Orca. Nenhuma troca silenciosa de modelo, executável ou bypass foi realizada.

Integração autorizada: somente dez arquivos de código/testes/docs da Etapa 4,
com baseline e hashes do checkout principal verificados antes da cópia e
preservação dos demais arquivos. Sem commit/push.
