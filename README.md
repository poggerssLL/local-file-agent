# Local File Agent

Inventário local e determinístico, com controle humano e privacidade.
Etapas 1, 2 e 2B concluídas; Etapa 3 com gate inicial aprovado somente para
fixtures NTFS locais sintéticas e complementos aprovados na revisão delimitada
do coordenador. Baseline publicado da Etapa 3: `49c7dbe`. Etapa 4 concluída localmente,
publicação autorizada nominalmente em 2026-10-05; SHA e remoto confirmados pelo Git.
Classificação determinística da Etapa 4 implementada localmente, com gate técnico aprovado.
Persistência SQLite, execução transacional e undo são planejados.

O scanner coleta somente metadados. O hasher é separado e opt-in; por padrão
não lê conteúdo. O backend atual aceita Windows/NTFS local com capacidades
verificadas, fixa handles da raiz/ancestrais e lê por ReOpenFile do mesmo objeto.
Sem fallback POSIX. Reparse/cloud/OFFLINE/RECALL/especiais/hardlinks são recusados.
Inventários sem snapshots não podem ser usados para hash.

Grupos contêm apenas sucessos distintos por tamanho/SHA256, ordenados por
pontos de código Unicode dos paths. Redundância lógica não é espaço recuperável;
nenhum arquivo é excluído, movido ou renomeado pelo hasher.

## Testes

Execute da raiz Git:

```powershell
python -B -m unittest discover tests -v
git diff --check
```

Evidência após complemento da raiz (2026-10-05): 70 testes, 69 aprovados e 1 skip por ausência de privilégio
para symlink de arquivo. Fixtures mutáveis ficam exclusivamente em
`tests/fixtures/phase3_runtime`, removidas após verificação de escopo, sem seguir
links. `synthetic_tree` não é alterada. Há testes Windows reais de hashes,
sharing, identidade, hardlinks e junctions; cloud/remoto são simulados.

## Tutorial mínimo exclusivamente sintético

Sem fornecer dados reais, rode o teste didático que cria e limpa sua fixture:

```powershell
python -B -m unittest tests.test_hasher.TestWindowsNative.test_native_hash_identity_content_size_mtime_preserved -v
```

A API usada dentro de uma fixture já autorizada é:

```python
from src.core import DirectoryScanner, HashConfig, HashSession

# base_dir absoluto pertence a uma fixture sintética explicitamente autorizada.
inventory = DirectoryScanner(base_dir).scan()  # somente metadados
config = HashConfig(enabled=True, chunk_size=262144,
                    max_file_bytes=1_073_741_824, max_total_bytes=4_294_967_296)
report = HashSession(base_dir, config).analyze(inventory)
print(report.status, report.bytes_read, report.logical_redundant_bytes)
for group in report.groups:
    print(group.paths)
```

São necessários bytes de margem para uma sondagem após o tamanho esperado;
um arquivo exatamente no limite é recusado. Digest parcial é sempre None;
falha raiz invalida toda a sessão. Relatórios do scanner não são mutados e
hashes recebidos em FileItem são ignorados. Não se promete atime, isolamento
absoluto ou snapshot atômico. O teste de symlink de folha skipped impede afirmar
validação nativa desse cenário. Nenhuma conta cloud foi usada.

Contratos: [FOUNDATION](FOUNDATION.md). Limites: [KNOWN_ISSUES](KNOWN_ISSUES.md).

`report.scope` é provided_inventory. `inventory_error_count` conta erros do
scanner sem copiar mensagens. Com erros de inventário, hashes válidos são
preservados e o status é partial. Complete cobre apenas os itens recebidos;
nunca prova cobertura da árvore ou dos arquivos excluídos por filtros.
READ_ATTRIBUTES sozinho não estabiliza share-access; bloqueio comum vem do
handle de dados/descendente aberto. A janela anterior a ReOpenFile é detectada,
não bloqueada. Metadata por path atravessa componentes intermediários e pode
contactar SMB antes da recusa, inclusive por symlink permitido em Developer Mode;
não se promete zero rede absoluto sob namespace concorrente. NtCreateFile não
implementado. Dedupe silencioso e exceções inesperadas são limites documentados.
Autorização da raiz depende do chamador; delete direto não foi testado.
OPEN_NO_RECALL/recusa de cloud são conservadores, sem garantia absoluta contra
hidratação/contato remoto quando componentes intermediários mudam. OneDrive/AV
podem interferir nas fixtures; nenhuma causa foi diagnosticada.
Estado: [PROJECT_STATE](PROJECT_STATE.md). Plano: [ROADMAP](ROADMAP.md).
Histórico: [relatório da Etapa 3](docs/PHASE_03_HASHES_AND_DUPLICATES_2026-10-04.md).

O coordenador confirmou independentemente 67 executados, 66 pass, 1 skip,
exit 0 e diff-check limpo na revisão final com phase-gate-reviewer. O gate inicial
foi Antigravity / Claude Opus 5.5 high; não houve novo despacho Antigravity para
os complementos. A aprovação não cobre dados reais, nuvem ou Etapa 4; o skip
de symlink de folha e os riscos residuais permanecem registrados.

Complemento de release da raiz (2026-10-05): se lstat falha depois da construção
do scanner, scan() retorna inventário vazio com erro sanitizado para '.', sem
travessia e com root_observation=None. Hashing enabled com backend suportado
recusa root_snapshot_missing antes de abrir conteúdo. Os três testes novos
usam mocks; não houve remoção real de raiz nem mudança de permissões.
Gate independente Codex gpt-6.1-sol high aprovado e aceito pelo coordenador:
execução independente 70/69/1, exit 0, pronto para commit exclusivamente no
escopo NTFS local sintético. Sem commit/push; remoto atual desconhecido.
Evidências e limites: [relatório do complemento](docs/PHASE_03_COMPLEMENT_ROOT_SNAPSHOT_2026-10-05.md).

## Classificação determinística (Etapa 4)

Exemplo somente com metadados fictícios em memória, sem varrer disco:

```python
from src.core import FileItem, ScanReport, ClassificationSession
inventory = ScanReport("synthetic", 1, 0, [FileItem("fiction/note.txt", 0, 0)])
report = ClassificationSession().analyze(inventory)
assert report.category_counts == {"documents": 1}
```

Regras por extensão, glob do basename e intervalo UTC epoch [início,fim),
com prioridade explícita. Conflitos ficam ambiguous; desconhecidos, unmatched.
Complete cobre apenas provided_inventory. Nenhum arquivo é aberto, categorizado
no disco ou movido; não há geração/execução implícita de planos.
Suíte atual: 90 testes, 89 aprovados e o skip legado de symlink.
Clones limpos precisam preparar a fixture oculta sintética do teste legado
do scanner; o Git contém cinco dos seis arquivos esperados por esse teste.
Veja [contrato, evidências e limites](docs/PHASE_04_DETERMINISTIC_CLASSIFICATION_2026-10-05.md).
