# Arquitetura e Fundação Viva: Local File Agent

Atualizado em: 2026-10-05.
Etapa atual: **Etapa 4 - Classificação determinística**, implementada localmente,
gate técnico independente aprovado e aceito pelo coordenador. Etapa 3 publicada em `49c7dbe`; limites preservados.

---

## 1. Visão Geral do Sistema

O `Local File Agent` é um agente de software local projetado para organizar, classificar e auditar arquivos e diretórios no computador do usuário, mantendo integridade transacional, aprovação humana e privacidade absoluta.

```text
                             Erick (Usuário)
                                   │
                           revisa e autoriza
                                   │
    [Scanner / Inventário] ──► [Motor de Regras & LLM] ──► [Planejador de Operações]
          (Read-Only)              (Classificação)                (ExecutionPlan)
                                                                       │
                                                                       ▼
    [Diário de Auditoria] ◄─── [Motor Transacional] ◄────── [Aprovação Explícita]
      (Log de Desfazer)            (Move/Rename)
```

---

## 2. Invariantes Arquiteturais

1. **Separação entre Planejamento e Execução:**
   - O planejador (`OperationPlanner`) gera um plano imutável (`ExecutionPlan`) contendo a lista de ações propostas.
   - O motor transacional (`TransactionEngine`) **recusa-se** a executar qualquer plano que não possua a flag `approved = True` atribuída por decisão humana.
2. **Determinismo em Primeiro Lugar:**
   - A classificação tenta regras heurísticas e determinísticas primeiro (extensões, padrões de data, prefixos conhecidos). A consulta a modelos locais nos casos ambíguos é planejada para a Etapa 5.
3. **Mecanismo de Desfazer (*Undo Journal*):**
   - Nenhuma movimentação de arquivo é feita sem antes registrar em log SQLite a tupla reversível: `{id, timestamp, original_path, target_path, original_hash}`.
4. **Política Rígida de Fronteira e Confinamento (Etapa 2B):**
   - **Validação Lexical (`src/core/boundary.py`):** Planos de execução aceitam exclusivamente caminhos relativos normalizados. Rejeição terminante de caminhos absolutos, UNC (`\\server\share`), unidades (`C:`), drive-relative (`C:rel`), fluxos alternativos NTFS (`ADS`), escapes (`..`) e nomes reservados de dispositivos Windows. Comparação estritamente por componentes (`commonpath` com `normpath`/`normcase`), eliminando vulnerabilidades de prefixo de texto (`startswith`).
   - **Confinamento Físico (`src/core/scanner.py`):** A raiz base (`base_dir`) não pode ser link ou junção; cada entrada é validada fisicamente via `realpath` contra a âncora real antes da visita. Reparse points de redirecionamento (*name surrogate*, como symlinks e junctions) são pulados por padrão; placeholders de nuvem (OneDrive) são inventariados normalmente sem bloqueio genérico. Ciclos e pastas duplicadas são prevenidos via chaves canônicas de caminhos reais. Erros e skips são sanitizados sem vazamento de caminhos absolutos locais.

---

## 3. Contratos de Dados Centrais (`src/core/models.py` e `src/core/boundary.py`)

- **`boundary` (`src/core/boundary.py`):** Funções `normalize_relative_path`, `is_within_boundary`, `resolve_within` e exceção `SecurityBoundaryError`.
- **`FileItem`:** Representa um arquivo inventariado (caminho relativo, tamanho em bytes, data de modificação, hash SHA-256 opcional).
- **`OperationType`:** Enumeração das operações suportadas (`RENAME`, `MOVE`, `TAG`, `SIMULATE`).
- **`OperationAction`:** Ação atômica contendo `source_path`, `destination_path`, `reason` e `status`.
- **`ExecutionPlan`:** Coleção de ações planejadas com validação de segurança via `resolve_within`, `dry_run: bool` (padrão `True`) e `approved: bool` (padrão `False`).
- **`ScannerConfig`:** Configurações de profundidade, filtros, limite de arquivos e flag `follow_symlinks` (padrão `False`).
- **`ScanReport`:** Relatório estruturado de varredura com contagem por extensão, tempos, lista sanitizada de `errors` e campo aditivo de `skipped`.

### Contratos aditivos da Etapa 3

`ScanReport.root_observation=None` e `item_observations={}` foram acrescentados
ao fim do construtor. `FileItem` e `ScannerConfig` mantêm seus construtores.
`FileObservation` imutável registra `device/inode/size/mtime_ns/ctime_ns/nlink/kind`
(os respectivos `st_*`, com tipo file/directory/special), atributos e reparse tag.
O scanner coleta identidade com `os.stat` durante o inventário: `DirEntry.stat`
pode retornar zeros no Windows. Há observações de diretórios ancestrais também.
O inventário é metadados somente; snapshots não são atômicos. Relatórios legados
continuam utilizáveis como inventário, mas não autorizam hashing sem snapshots.

Complemento de release (2026-10-05): OSError na captura inicial por lstat da
raiz, depois do constructor, produz ScanReport vazio com erro sanitizado
`Erro ao acessar '.': <tipo> (errno=<numero>)` (errno omitido quando ausente).
root_observation permanece None, sem travessia nem tentativa tardia de snapshot.
Assinaturas e base_dir do relatório são preservados; a sanitização cobre errors,
sem copiar mensagem do SO ou filename absoluto. HashSession enabled com backend
suportado recusa root_snapshot_missing antes de pin_root/conteúdo, sem mudança
no hasher. Três regressões simuladas; suíte do escritor 70/69/1, exit 0.
Gate independente Codex gpt-6.1-sol high aprovado e aceito pelo coordenador,
com execução independente 70/69/1, exit 0: pronto para commit somente no escopo
NTFS local sintético. Sem commit/push; dados reais seguem fora do escopo.

`HashSession(base_dir, config).analyze(scan_report)` é separado do scanner.
`HashConfig` nasce disabled, chunk padrão 262144 bytes, intervalo inclusivo
65536..1048576, `max_file_bytes=1073741824` e `max_total_bytes=4294967296`.
Limites são inteiros positivos finitos; bool é recusado como inteiro. O orçamento
é por análise, inclui bytes efetivos de leituras malsucedidas e reserva capacidade
para sondar até um byte após o tamanho esperado. Por isso um arquivo de tamanho
igual a `max_file_bytes` é recusado. EOF sem transferência não consome orçamento.
Short reads positivos são acumulados; truncamento/crescimento/mutação/falha
descartam digest. Nenhum arquivo crescente é perseguido além do limite previsto.

O backend `windows_hash_backend.py` usa stdlib/ctypes e Windows NTFS local em
drive FIXED. UNC/drives remotos/desconhecidos são recusados antes de CreateFile;
filesystem/flags e case sensitivity são verificados. APIs/capacidades desconhecidas
falham fechadas. Fora de Windows, `unsupported` implica zero reads, sem backend
POSIX. Handles da raiz e de todos os ancestrais dentro dela são mantidos abertos
com share READ (sem WRITE/DELETE). READ_ATTRIBUTES sozinho não estabiliza
share-access: o bloqueio de escritores/deleters comuns vem do handle de dados
com GENERIC_READ e a recusa de rename ancestral é observada com descendente
aberto. A janela anterior a ReOpenFile é detectada por identidade/metadados/
namespace, não bloqueada pelos handles de metadados. Metadados usam OPEN_REPARSE_POINT/BACKUP_SEMANTICS/
OPEN_NO_RECALL e OPEN_EXISTING. São verificados identidade, tipo, attrs/tag, volume
e caminho final por handle. Volume de 64 bits e FileId de 128 bits vêm de
FileIdInfo, coerentes com Python 3.12 Windows. Dados são abertos por ReOpenFile
do objeto validado, com nova verificação; nunca por segunda abertura de dados
por path. ReOpenFile não aceita OPEN_NO_RECALL: a recusa de cloud/recall/reparse
ocorre no objeto fixado antes dessa chamada. Todos os handles fecham em finally.
As aberturas de metadados por path podem atravessar componentes intermediários,
inclusive symlinks permitidos por Developer Mode, e eventualmente contactar SMB
antes da recusa por final path/attrs. OPEN_REPARSE_POINT protege a folha dessa
abertura, não toda a travessia. Não se promete zero rede absoluto sob namespace
concorrente; NtCreateFile/abertura relativa a diretório não foram implementados.
Root namespace é revalidado ao uso; ancestrais e folha são checados durante e
depois da leitura, com ChangeTime adicional observado no handle. Erro individual
é parcial; erro raiz invalida inclusive digests anteriores e encerra a sessão.

Reparse points de qualquer tag, cloud/OFFLINE/RECALL, arquivos especiais e
hardlinks (`nlink != 1`) são recusados. Inventariar um placeholder não equivale
a autorizar leitura de conteúdo: a política do hasher é mais conservadora.
O original não é mutado; sha256 recebido em FileItem é ignorado. HashReport
contém resultados, grupos, erros sanitizados, status e bytes lidos; falha nunca
retém digest parcial. Input path inválido produz erro sem raw input, nem path.
Os outros erros usam apenas path relativo validado, código e tipo/errno permitido.

`HashReport.scope="provided_inventory"` explicita que o relatório abrange apenas
os itens recebidos. `inventory_error_count=0` é um campo aditivo; conta erros do
scanner sem copiar suas mensagens. Se o inventário contém erros, a análise de
hash preserva os sucessos válidos e retorna partial (salvo estado disabled,
unsupported ou invalid_root). Complete significa sucesso dos itens recebidos,
nunca cobertura integral de uma árvore, de arquivos excluídos por filtros ou
profundidade. Esses limites continuam valendo mesmo quando a contagem é zero.

Grupos são formados apenas por sucessos distintos em `(size_bytes, SHA256)`;
paths e grupos (tuplas de paths) são ordenados por pontos de código Unicode,
sem locale/casefold. Duplicar item/path/objeto não aumenta a redundância lógica:
`(objetos distintos válidos - 1) * size_bytes` por grupo, inclusive vazios.
Esse valor não é espaço recuperável e não autoriza exclusão ou outra operação.
Limites residuais e evidências estão em KNOWN_ISSUES e no relatório da Etapa 3.
Autorização de base_dir é responsabilidade do chamador; a API não implementa
allowlist de consentimento. Delete direto não recebeu teste nativo neste gate.
OPEN_NO_RECALL/recusa de cloud não garantem ausência absoluta de hidratação ou
contato remoto diante de mudanças nos componentes intermediários. OneDrive/AV
podem interferir nas fixtures e não foram diagnosticados como causa das falhas.

---

## 4. Evidências históricas da Etapa 3

Gate inicial: auditoria independente Antigravity / Claude Opus 5.5 high,
manual conforme contrato. Complementos: revisão delimitada aprovada pelo
coordenador com phase-gate-reviewer, sem novo despacho Antigravity. Suíte
reexecutada pelo coordenador: 67 executados, 66 pass, 1 skip, exit 0; runtime
limpo e diff-check sem erros. Baseline 6d24cb0, alterações ainda sem commit.
Skip de symlink de folha e riscos residuais permanecem; nenhuma aprovação
para dados reais, nuvem ou Etapa 4 foi concedida.

As fases subsequentes seguem o [ROADMAP](ROADMAP.md). Os módulos de
execução, SQLite e undo no desenho são planejados. A classificação determinística
da Etapa 4 está implementada; modelos de linguagem permanecem para a Etapa 5.

## Contrato da Etapa 4

ClassificationSession recebe ScanReport e devolve relatório imutável sobre metadados,
sem I/O ou mutação. Extensão, glob do basename e intervalo UTC epoch [início,fim)
combinam por AND; maior prioridade vence, empate entre categorias é ambiguous.
Todos os matches ficam auditáveis. Complete cobre apenas provided_inventory,
sem provar cobertura integral ou classificação sem ambiguidade. Erros herdados
são contados e tornam partial sem copiar mensagens. Sugestões omitem entradas
inválidas, preservam todas as duplicatas como invalid e usam ordenação casefold
com desempate por path Unicode. IDs/categorias são tokens, nunca destinos.
Limites: 50.000 itens e 256 regras; nenhum plano, SQLite ou LLM é chamado.
Contrato completo: docs/PHASE_04_DETERMINISTIC_CLASSIFICATION_2026-10-05.md.
