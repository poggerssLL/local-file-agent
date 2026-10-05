# Etapa 3 — complemento de release: snapshot inicial da raiz

Data: 2026-10-05. Implementação, validação e gate independente concluídos;
pronto para commit exclusivamente para fixtures NTFS locais sintéticas.
Sem commit/push; autorização nominal de Erick ainda necessária para publicação.

## Mandato, baseline e proveniência

Complemento autorizado por Erick, recebido como Task com Dispatch ativo no
runtime supervisionado Orca. Escritor único Codex gpt-6.1-sol medium,
perfil organizer-codex-sol-medium, fallback none; coordenador integra/revisa.
IDs de Task/Dispatch ficam apenas nas mensagens de lifecycle, não neste arquivo.
Nenhum worker adicional foi criado pelo escritor. Skills orientation,
orchestration e implementation-prompt-builder lidas, sem relançar a Etapa 3.

Raiz Git confirmada: Local File Agent, main, upstream origin/main, HEAD
`6d24cb05f0502d08df12be28529ba2e9f2b6be67`. Baseline não limpo: 15 entradas
preexistentes da Etapa 3 (10 modificadas, 5 não rastreadas), sem commit/push.
Suíte baseline reexecutada: 67 testes, 66 aprovados, 1 skip, exit 0.
Histórico original, fixtures antigas, hasher/backend/models/exports preservados.

## Defeito e correção

O lstat inicial da raiz em scan() estava fora de try. Se a raiz desaparecesse,
perdesse acesso ou sofresse outra falha de I/O após a construção, OSError
propagava com mensagem do SO e filename absoluto em vez de ScanReport.
Três regressões novas foram executadas antes da correção e falharam nesse
ponto (quatro cenários, incluindo OSError sem errno), reproduzindo o defeito.

Agora OSError é capturado na observação inicial. O mesmo helper sanitizador
existente gera `Erro ao acessar '.': <tipo> (errno=<numero>)`, omitindo errno
quando ausente. O retorno comum de ScanReport permanece: contagens zero,
listas/mapa vazios, duração medida, root_observation=None e erro sanitizado.
A árvore não é percorrida; não há retry nem fabricação de snapshot tardio.
Assinaturas, base_dir e modo metadata-only são preservados. O hasher não mudou:
enabled com backend suportado retorna invalid_root/root_snapshot_missing,
inventory_error_count=1, zero bytes/resultados/grupos antes de pin_root.

## Matriz de evidências e limites

| Critério | Evidência observada | Limite |
|---|---|---|
| Desaparecimento após construção | Mock lstat FileNotFoundError(2), relatório vazio e erro exato sanitizado | Não houve remoção real da raiz |
| Perda de acesso após construção | Mock PermissionError(13), sem mensagem ou filename no erro | Sem alteração real de ACL |
| I/O genérico | Mock OSError(5) e OSError sem errno, sanitização estável | Simulação determinística |
| Não percorrer nem observar tardiamente | Spies _walk/scandir não chamados; lstat chamado uma única vez | Restrito à falha inicial |
| Hashing recusado antes de conteúdo | Backend mock suportado, pin_root não chamado; builtins.open não chamado; bytes_read=0 | Não é prova nova de ReadFile nativo ou contato remoto |
| Compatibilidade | Suíte completa após última mudança funcional: 70 testes/69 aprovados/1 skip, exit 0 | Skip nativo de symlink de folha winerror 1314 permanece |
| Preservação e higiene | Comparação por hashes com entrada, diff e revisão de arquivos não rastreados | Mudanças preexistentes continuam sem commit |

Comando: `python -B -m unittest discover tests -v`. Os 67 testes preexistentes
foram reexecutados, incluindo cenários Windows nativos sintéticos do backend;
69 testes passaram e somente o skip anterior permaneceu. Nenhuma conta cloud,
SMB real, dados pessoais, instalação, administração ou GUI foi usada.
Os testes novos não criam fixtures: usam mocks após construir o scanner na
fixture sintética antiga, sem alterar seus arquivos. A suíte preexistente cria
e limpa runtime somente sob tests/fixtures/phase3_runtime; ao final resta .gitignore.

## Escopo e condição de parada

Arquivos deste complemento: src/core/scanner.py, tests/test_scanner_hardening.py,
PROJECT_STATE, FOUNDATION, ROADMAP, KNOWN_ISSUES, DECISIONS, README,
PROMPT_CODEX_ETAPA_3 e este relatório. Alterações prévias nesses documentos e no
scanner foram preservadas; nenhum outro arquivo de implementação foi alterado.
O relatório original docs/PHASE_03_HASHES_AND_DUPLICATES_2026-10-04.md é imutável.
Sem stage/commit/push/fetch, rede, refatoração do backend, LLM ou Etapa 4.

Exceções no constructor e exceções fora de OSError continuam fora deste ajuste.
ScanReport.base_dir permanece absoluto por compatibilidade: os erros sanitizados
não tornam o relatório inteiro anônimo. Snapshot atômico, confinamento absoluto,
zero rede concorrente, dados reais e symlink de folha nativo não foram provados.
Persistem os riscos e limites da Etapa 3 registrados em KNOWN_ISSUES.

Após verificações de diff/whitespace/BOM/privacidade/preservação, congelar a árvore
e solicitar gate independente ao coordenador via ask. Aprovações anteriores não
aprovam automaticamente este complemento; decisão final deve ser registrada
somente após resposta do gate, mediante autorização documental do coordenador.

## Decisão final recebida e aceita

Após congelamento e ask, o coordenador informou e aceitou o gate independente
do reviewer Codex gpt-6.1-sol high: **PRONTO PARA COMMIT exclusivamente para
fixtures NTFS locais sintéticas**, sem bloqueadores materiais. O reviewer
executou independentemente a suíte: 70 executados, 69 aprovados, 1 skip,
exit 0; os 17 candidatos da árvore foram aceitos. Esse resultado foi recebido
pelo escritor via runtime, sem atribuir ao escritor autoria da revisão.

O coordenador autorizou somente este registro final e docs vivos pertinentes.
Código/testes permaneceram congelados; nenhuma nova execução da suíte foi
necessária por mudança exclusivamente documental. Revisão final limitada a
diff, coerência, whitespace/BOM, privacidade e conferência dos 17 caminhos.
Diff-check sem erros; inspeção tracked/untracked sem whitespace final, BOM,
IDs runtime, padrões de caminhos privados ou tokens; runtime somente .gitignore.
Hashes de entrada confirmaram preservação integral dos arquivos fora do escopo,
inclusive histórico original/fixtures antigas/hasher/backend/models/exports.

O skip de symlink nativo de folha (winerror 1314) e todos os limites anteriores
permanecem. Sem aprovação para dados reais, nuvem ou Etapa 4. Baseline local
main/6d24cb0, upstream configurado origin/main, alterações sem commit/push.
O estado atual do remoto é desconhecido: nenhum fetch ou acesso de rede foi
feito. Commit/push aguardam autorização nominal de Erick. Após conferência de
follow-ups e worker_done, o escritor encerra o Dispatch e fica idle.
