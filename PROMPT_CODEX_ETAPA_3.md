# Prompt de implementação — Etapa 3

**Entrega original concluída:** texto abaixo é registro da preparação histórica,
não uma instrução para relançar implementação. Complemento de release da raiz
concluído em 2026-10-05, suíte do escritor e execução independente do reviewer
Codex gpt-6.1-sol high 70/69/1, exit 0; gate recebido e aceito somente para
fixtures NTFS locais sintéticas. Pronto para commit, sem commit/push; remoto
atual desconhecido. Escopo exclusivo: scanner, regressões e documentação,
sem relançar hashes/backend ou iniciar Etapa 4. Ver relatório do complemento
em docs/PHASE_03_COMPLEMENT_ROOT_SNAPSHOT_2026-10-05.md.

Preparado em 2026-10-04, antes da implementação. Projeto: Local File Agent.
Confirme raiz Git igual ao diretório de trabalho autorizado. Baseline confirmado:
`main`, `6d24cb05f0502d08df12be28529ba2e9f2b6be67`, upstream `origin/main`,
working tree limpa, 32/32 testes legados aprovados.

Executor Codex, modelo gpt-6.1-sol, esforço medium, perfil
organizer-codex-sol-medium, fallback none. Arquitetura independente Codex high e
QA Codex medium já despachados; escritor único Codex medium; gate independente
pendente. Não criar outros workers. Preserve o perfil informado; escale falhas
concretas de segurança sem relaxar contratos ou trocar executor silenciosamente.

Leia AGENTS, FOUNDATION, PROJECT_STATE, ROADMAP, KNOWN_ISSUES, DECISIONS, README,
boundary/scanner/models/exports e testes. Use orientação e preparação de prompt
quando aplicáveis e disponíveis. Implemente somente SHA256 e duplicidades.

Escrita autorizada: hasher/backend Windows separado; metadados aditivos no
scanner/models/exports; novos testes/fixtures isolados; este prompt;
documentação viva acima; novo docs/PHASE_03_HASHES_AND_DUPLICATES_2026-10-04.md.
Preserve relatórios históricos e synthetic_tree. Escrita de código/documentação
e criação/remoção segura de fixtures estão autorizadas. I/O sobre arquivos de
usuário permanece somente leitura, sem uso de dados reais neste gate.

Contrato: HashConfig(enabled=False, chunk_size=262144, limites finitos positivos
max_file_bytes/max_total_bytes), bool não é inteiro, chunks 65536..1048576.
HashSession(base_dir, config).analyze(ScanReport) separado do scanner. Disabled e
unsupported: zero reads. Snapshots aditivos do inventário (raiz/arquivos/pastas)
com defaults, ausência recusa hash; sem identidade tardia. Ignorar hashes de
entrada e não mutar relatório. Windows local, capacidades comprovadas, stdlib e
ctypes; nenhum fallback POSIX ou segunda abertura de dados por path. Fixar raiz
e ancestrais, validar identidade/tipo/attrs/tag/caminho final pelo handle antes
de read e depois; dados via ReOpenFile do mesmo objeto validado. Rejeitar UNC,
remoto, case-sensitive, especiais, reparse/cloud/offline/recall e hardlinks.
Fechar handles em finally. Caminhos relativos validados pela boundary antes de
syscalls; erros sanitizados sem raw input, absolutos ou str(exc). Falha raiz
encerra/invalida sessão. Ler no máximo tamanho esperado + 1 byte de sondagem,
orçamento antes de cada read, bytes efetivos contabilizados inclusive falhas.
Short read positivo não é EOF. Digest parcial None. Grupos somente sucessos
por (size,SHA256), paths/grupos Unicode ordenados. Duplicar path/item não gera
redundância. Redundância lógica não significa espaço recuperável.

Fixtures mutáveis: TemporaryDirectory sob tests/fixtures/phase3_runtime, limpeza
apenas após checagem da subárvore, sem seguir links. Sentinelas fora da raiz
TESTADA ficam dentro da fixture do projeto. Sem nuvem real/dados pessoais.
Testar vetores/chunks/budgets/ordenação/pares/trios/vazios, input hostil,
snapshots ausentes/stale/root mismatch, falhas/cleanup, truncar/crescer/mudar e
trocar identidade mesmo size/mtime, folha/ancestral externos antes de read.
Validar Windows nativo identidade/sharing/junction/hardlink; skips são lacunas e
bloqueiam alegações correspondentes. Provar conteúdo/size/mtime preservados em
fixtures de leitura; não prometer atime/snapshot atômico/confinamento absoluto.
Documentar riscos residuais: metadados restaurados, mappings, filtros e
mutadores privilegiados. Distinguir mocks, sintético e Windows real.

Executar python -B -m unittest discover tests -v e git diff --check. Revisar diff
higiene e limites. Sem rede/installs/credenciais/GUI/commit/push/merge/publicação,
motores de operação ou Etapa 4. Correções e nova validação dentro da etapa
estão autorizadas; ampliação exige intervenção. Registrar papéis reais sem IDs
runtime/caminhos pessoais; não aprovar antecipadamente o gate independente.
Reportar resultado, evidências e limitações; parar antes da próxima etapa.

## Complementos autorizados após gate inicial

Gate inicial aprovado somente para fixtures NTFS locais sintéticas. Na mesma
Etapa 3, acrescentar HashReport.inventory_error_count (default 0, sem mensagens
do scanner) e scope provided_inventory. Inventário com erros produz partial
preservando hashes válidos; complete cobre só itens recebidos, nunca árvore
integral/filtros. Testar erro/limite de inventário, original preservado e mensagem
sensível não copiada. Corrigir documentação: READ_ATTRIBUTES não estabiliza
sozinho share-access; bloqueio comum vem do handle de dados/descendente aberto,
janela antes de ReOpenFile detectada e não bloqueada. Metadata por path pode
atravessar symlink intermediário permitido em Developer Mode e contactar SMB
antes da recusa; sem promessa de zero rede absoluto concorrente. Não implementar
NtCreateFile. Remover somente os BOMs introduzidos em README, PROJECT_STATE e
neste prompt. Registrar dedupe silencioso/exceções inesperadas como limites não
bloqueantes, sem ampliar implementação. Atualizar evidências, validar e congelar
a árvore para nova revisão independente antes de concluir a entrega.

Registro final: gate inicial Antigravity / Claude Opus 5.5 high aprovado somente
para fixtures NTFS locais sintéticas; complementos aprovados em revisão
delimitada do coordenador com phase-gate-reviewer, sem novo despacho Antigravity.
Coordenador confirmou suíte independente 67/66/1, exit 0, runtime limpo e
diff-check sem erros. Baseline 6d24cb0, alterações sem commit/push. Skip de
symlink de folha e riscos residuais mantidos; Etapa 4/dados reais fora do escopo.
