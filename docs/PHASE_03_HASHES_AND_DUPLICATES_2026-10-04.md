# Etapa 3 — SHA256 e duplicidades

Data: 2026-10-04. Gate inicial aprovado somente para fixtures NTFS sintéticas;
complementos implementados e aprovados na revisão delimitada do coordenador.
Decisão aceita exclusivamente para fixtures NTFS locais sintéticas.

## Mandato, baseline e proveniência

Implementação explicitamente autorizada por Erick para uma única etapa,
um escritor por checkout, I/O de teste exclusivamente sintético. Raiz Git
confirmada como Local File Agent, branch main, upstream origin/main, HEAD
`6d24cb05f0502d08df12be28529ba2e9f2b6be67`, árvore inicialmente limpa.
Baseline executado antes da implementação: 32/32 testes legados aprovados.
Sem commit/push/merge/publicação, rede, instalações, GUI, credenciais ou dados reais.

Papéis realmente despachados, informados pelo coordenador:

| Papel | Executor/perfil | Resultado no momento deste relatório |
|---|---|---|
| Arquitetura independente | Codex high | Contrato consolidado recebido |
| Plano de QA independente | Codex medium | Critérios consolidados recebidos |
| Escritor único | Codex gpt-6.1-sol medium, organizer-codex-sol-medium, fallback none | Implementação e validação desta entrega |
| Gate independente | Antigravity / Claude Opus 5.5 high, somente leitura | Gate inicial aprovado só para fixtures NTFS locais sintéticas |
| Revisão delimitada dos complementos | Coordenador / skill phase-gate-reviewer, somente leitura | Aprovada para o mesmo escopo; sem outro escritor ou novo despacho Antigravity |

Nenhum worker adicional foi criado pelo escritor. As observações do coordenador
sobre FileIdInfo e drive remoto antes da abertura foram incorporadas, com
provas correspondentes. Skills de orientação, orquestração e preparação de
prompt foram lidas; o prompt antigo foi corrigido antes da implementação de
hashes. A escrita de código/documentação/fixtures foi distinguida da proibição
de alterar dados de usuário. Nenhum relatório histórico anterior foi reescrito.
Essas skills descrevem somente o escritor. O auditor Antigravity não tinha
orientation/phase-gate-reviewer em seu catálogo e executou auditoria manual
conforme o contrato, segundo registro do coordenador. Não se atribui a ele uso
dessas skills. O coordenador usa phase-gate-reviewer para a revisão final
delimitada dos complementos; não foi criado outro escritor.

## Entrega implementada

- `src/core/hasher.py`: HashConfig, HashSession, HashReport, HashResult,
  HashIssue, DuplicateGroup, SHA256 em chunks e grupos de sucessos distintos.
- `src/core/windows_hash_backend.py`: pequeno backend stdlib/ctypes, sem download,
  metadados por handle, dados por ReOpenFile e fechamento em finally/ExitStack.
- `models.py`: FileObservation imutável; root_observation/item_observations
  aditivos no fim de ScanReport com defaults. FileItem/ScannerConfig compatíveis.
- `scanner.py`: snapshots de raiz, arquivos e diretórios no inventário,
  metadados via os.stat para identidade completa Windows. `scan()` nunca abre
  conteúdo. Exports atualizados em `src/core/__init__.py`.
- `tests/test_hasher.py`: testes de contrato, simulações e fixtures Windows.
  `tests/fixtures/phase3_runtime/.gitignore`: impede versionar runtime descartável.
- FOUNDATION, PROJECT_STATE, ROADMAP, KNOWN_ISSUES, DECISIONS, README e
  PROMPT_CODEX_ETAPA_3 atualizados. Synthetic_tree e relatório 2B preservados.

HashConfig nasce disabled, padrão 256 KiB, chunks 64 KiB..1 MiB, budgets de
1 GiB por arquivo/4 GiB por análise. Inteiros positivos finitos, bool recusado.
Há margem obrigatória de um byte nos budgets para sondagem de EOF. Bytes
efetivos, inclusive em falhas, são contabilizados; EOF sem transferência não
consome budget. Short read positivo não é EOF; truncamento, crescimento ou
mudança observada descartam digest. O teto de leitura é tamanho esperado +
uma sondagem, nunca perseguindo crescimento. Relatórios recebidos não são
mutados; hashes recebidos são ignorados; snapshots ausentes recusam conteúdo.

Antes de abrir itens, paths passam pela boundary. Invalid input não é ecoado.
Erros individuais são parciais e sanitizados (código, path relativo validado,
tipo/errno permitido); falha da raiz encerra e invalida todos os digests.
Somente sucessos entram nos grupos `(size,SHA256)`, por objetos distintos.
Paths são ordenados por pontos de código Unicode, grupos pela tupla de paths,
sem locale/casefold. Redundância lógica = `(objetos distintos válidos-1)*size`,
sem significado de espaço recuperável nem autorização de exclusão.

## Fronteira Windows e limites

Drive FIXED local é exigido antes de CreateFileW. UNC, remoto e desconhecido
são recusados sem open; filesystem NTFS/flags e case sensitivity são consultados
por handle. Capacidades desconhecidas falham fechadas. Não Windows é unsupported,
zero reads, sem backend POSIX. Handles da raiz e de cada ancestral dentro dela
ficam abertos durante leitura. READ_ATTRIBUTES sozinho não estabiliza share-access;
o bloqueio de escritores/deleters comuns vem do handle de dados com GENERIC_READ
e share READ, e rename ancestral é recusado com descendente aberto. A janela
anterior a ReOpenFile é detectada, não bloqueada pelos handles de metadata.
Metadados: OPEN_EXISTING, READ_ATTRIBUTES, OPEN_REPARSE_POINT, BACKUP_SEMANTICS,
OPEN_NO_RECALL. Identidade volume 64 bits/FileId 128 bits por FileIdInfo, tipo,
atributos/tag e final path coerentes são verificados antes/depois; ChangeTime
adicional do handle é monitorado durante uso. Dados: ReOpenFile do objeto já
validado, jamais segunda abertura de conteúdo por path, com nova verificação.
OPEN_NO_RECALL não é aceito por ReOpenFile; a recusa conservadora de reparse,
cloud/OFFLINE/RECALL precede essa chamada no objeto fixado. Hardlinks/especiais
são recusados. Todos os handles fecham, inclusive em falha.

Não há snapshot atômico ou promessa de confinamento absoluto. Namespace acima
da raiz não é integralmente fixado; alterações privilegiadas nesse namespace
podem afetar a abertura inicial de metadata. Mappings preexistentes, filtros,
kernel, mutadores privilegiados e metadados restaurados são riscos residuais.
Coerência de IDs/timestamps foi verificada em Python 3.12.9 Windows/NTFS;
outras plataformas/versões não foram promovidas a suportadas por inferência.

Metadata por path ainda pode atravessar componentes intermediários, inclusive
symlinks permitidos por Developer Mode, e eventualmente contactar SMB antes da
recusa por identidade/final path/attrs. OPEN_REPARSE_POINT protege a folha da
abertura, não a travessia completa. Não se promete zero rede absoluto sob
namespace concorrente; nenhum SMB real foi acessado nesta validação.
NtCreateFile/aberturas relativas a handle não foram implementados nesta etapa.

## Evidências separadas

Comando do escritor: `python -B -m unittest discover tests -v`.
Entrega inicial e gate inicial: **65 executados, 64 aprovados, 1 skip**.
Após complementos: **67 executados, 66 aprovados, 1 skip**, incluindo os 32 legados.
`git diff --check`: sem erros de whitespace (avisos LF/CRLF do Git não são falhas).

| Classe de evidência | Cobertura observada | Limite |
|---|---|---|
| M — simulação determinística | vazio/abc/binário, múltiplos chunks e limites, short reads, pares/trios/vazios, igual tamanho/diferentes conteúdos, 120 permutações/Unicode, orçamento/falhas, path hostil, snapshots/stale, mutação/truncamento/crescimento/troca de identidade, fechamento | Não prova sozinho Win32 nem segurança física |
| S — fixtures sintéticos | snapshots metadata-only, relatório original preservado, árvore runtime isolada e removida com validação de subárvore/sem seguir links | Nenhum dado real ou fixture antiga alterada |
| W — Windows nativo sintético | hashes, IDs 64/128, sharing/handles, conteúdo/size/mtime preservados, hardlinks, troca mesma size/mtime, root replacement, junction ancestral externa, hardlink de folha externo | Somente fixtures NTFS locais, sem atime garantido |
| M+W — injeções sobre APIs nativas | falhas/cleanup, cloud attrs, mapped remote/unknown/UNC zero opens, capability fail, ReOpenFile devolvendo objeto errado, final path ancestral externo | Nuvem/drive remoto real não foram acessados |

Sentinelas externas à raiz TESTADA ficaram dentro da fixture do projeto. Spies
de ReadFile provam zero chamadas nos cenários de junction externa, hardlink
externo, objeto de dados errado e final path externo. No teste da junction,
mtime da raiz foi restaurado para exercitar a rejeição do ancestral, evitando
atribuir o resultado apenas à invalidação precoce da raiz. Não houve leitura
de conteúdo externo pela sessão. Leituras de verificação do sentinela pertencem
ao teste autorizado e ficam dentro da mesma fixture sintética do projeto.

Skip explícito: `test_native_leaf_symlink_external_before_first_read`, privilégio
Windows indisponível, winerror 1314. **Isso bloqueia a alegação específica de
validação nativa do symlink de folha.** Hardlink externo, junction ancestral e
simulações de folha não substituem essa prova. Nenhuma conta cloud foi usada.

Durante desenvolvimento, falhas foram corrigidas sem relaxar controles:
DirEntry.stat retornava IDs zero; o volume Win32 legado DWORD divergia de Python
(corrigido por FileIdInfo); OPEN_NO_RECALL em ReOpenFile produzia WinError 87
(flags aceitos, mantendo rejeição prévia do objeto cloud/recall). Duas mutações
preparatórias de fixture sofreram PermissionError transitório, depois passaram
em reexecução direcionada e suíte final; não se mudou sharing nem privilégios.

## Gate inicial, complementos e condição de parada

O coordenador registrou o gate independente inicial como **aprovado somente
para fixtures NTFS locais sintéticas**, pelo Antigravity / Claude Opus 5.5 high,
com 65 executados/64 pass/1 skip confirmado. Isso não aprova dados reais ou
confinamento absoluto e preserva a lacuna de symlink de folha. Foram autorizados
somente estes complementos, nos mesmos arquivos/Etapa 3:

1. `HashReport.inventory_error_count=0` aditivo, contagem sanitizada sem copiar
   mensagens do scanner; scope explícito provided_inventory. Erros de inventário
   tornam o status partial preservando hashes válidos (estados disabled,
   unsupported e invalid_root mantêm prioridade). Complete cobre somente itens
   recebidos, nunca árvore integral/filtros. Dois testes novos: limite real do
   inventário com hash válido e original preservado; simulação com erros contendo
   mensagem sensível, sem cópia no HashReport, mantendo grupos/sucessos.
2. Correção das alegações de sharing: READ_ATTRIBUTES não estabiliza sozinho;
   bloqueio comum do handle de dados/descendente aberto; janela anterior a
   ReOpenFile detectada, não bloqueada.
3. Travessia intermediária de metadata por path/Developer Mode/eventual SMB
   documentada, sem promessa de zero rede absoluto e sem implementar NtCreateFile.
4. Remoção somente dos BOMs novos em README, PROJECT_STATE e PROMPT_CODEX_ETAPA_3,
   confirmados ausentes nos respectivos blobs do baseline. Outros arquivos não
   tiveram normalização de BOM solicitada ou aplicada.
5. Limites não bloqueantes registrados, sem ampliar implementação: itens com
   mesmo path normalizado/tamanho são deduplicados silenciosamente; conflitos
   de tamanho geram erro. Exceções inesperadas fora HashFailure/OSError podem
   propagar em vez de retornar HashReport sanitizado; consumidores não devem
   publicar tracebacks. Esses limites não provam qualidade/cobertura do inventário.
6. Ressalvas adicionais: delete direto não testado; autorização da raiz depende
   do chamador, sem allowlist de consentimento na API; OneDrive/AV podem interferir
   nas fixtures, sem diagnóstico da causa dos erros transitórios. OPEN_NO_RECALL
   e recusa de cloud são controles conservadores, sem garantia absoluta contra
   hidratação/contato remoto quando componentes intermediários mudam. O docstring
   do backend foi corrigido com os mesmos limites, sem mudar implementação.

Validação dos complementos pelo escritor: suíte completa 67/66/1, mesmos 32
legados aprovados, diff-check sem erros e runtime removido. Após congelamento,
o coordenador com phase-gate-reviewer conferiu fields/count-only/scope/partial,
os dois testes, docs A2/A3/A5/A6, docstring, os três BOMs e escopo Git. Reexecutou
independentemente `python -B -m unittest discover tests`: **67 executados,
66 pass, 1 skip, exit 0**, runtime somente .gitignore após cleanup e diff-check
limpo. A revisão delimitada foi **APROVADA** para o mesmo escopo sintético NTFS
local; não foi novo despacho Antigravity. Baseline permanece 6d24cb0 e a entrega
está sem commit/push. Ajuste posterior ao gate foi exclusivamente documental,
com diff-check e consistência, sem repetir testes ou criar novas fixtures.

| Critério | Evidência aceita | Limite preservado |
|---|---|---|
| Hashes e fronteira por handles | Gate inicial independente e testes Windows sintéticos | Sem confinamento absoluto; sem dados reais/nuvem |
| Inventário parcial sanitizado | Campos aditivos, dois testes novos, sucessos preservados | Complete cobre apenas provided_inventory |
| Sharing/metadata | Docs/docstring corrigidos e conferidos pelo coordenador | Janela pré-ReOpenFile detectada; eventual SMB/hidratação intermediária |
| Compatibilidade e higiene | 32 legados aprovados, suíte 67/66/1 exit 0, três BOMs ausentes, diff-check e runtime limpos | Baseline 6d24cb0, alterações não commitadas |
| Lacunas residuais | Skip 1314 e A5/A6 explícitos | Symlink de folha nativo pendente, delete direto não testado, autorização pelo chamador, dedupe/exceções/OneDrive-AV |

Decisão final dos complementos aceita. Symlink de folha, mappings, filtros,
metadados restaurados e mutadores privilegiados permanecem limites. Etapa 4,
motores de operação, dados reais, administração e publicação fora do escopo.
