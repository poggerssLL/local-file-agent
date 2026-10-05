# Registro de Decisões de Arquitetura (ADRs): Local File Agent

## ADR-001: Separação Estrita entre Planejamento e Execução Transacional
- **Status:** Aprovada (2026-09-18).
- **Contexto:** Agentes autônomos que operam diretamente no sistema de arquivos representam alto risco de perda acidental de dados se executarem operações em tempo real enquanto pensam.
- **Decisão:** Todo trabalho de organização deve ser dividido em duas etapas obrigatórias:
  1. *Fase de Planejamento:* Gera um objeto `ExecutionPlan` contendo a lista completa de ações propostas. Nenhuma alteração física em disco ocorre nessa fase;
  2. *Fase de Aprovação e Execução:* O plano só pode ser executado se o usuário aprovar expressamente (`approved = True`).
- **Consequências:** Elimina operações acidentais ou alucinações de exclusão de arquivos; adiciona uma etapa deliberada de confirmação humana.

---

## ADR-002: Modelagem em Python Puro com Dataclasses
- **Status:** Aprovada (2026-09-18).
- **Contexto:** A fundação deve ser leve, rápida e executável em qualquer ambiente sem necessidade de instalar pacotes pesados como Pydantic ou SQLAlchemy na Etapa 1.
- **Decisão:** Utilizar o módulo nativo `dataclasses` do Python 3.12 para representar `FileItem`, `OperationAction` e `ExecutionPlan`.
- **Consequências:** Zero dependências externas no início do projeto, facilidade de teste e execução rápida.

---

## ADR-003: Confinamento Estrito de Diretórios de Trabalho
- **Status:** Aprovada (2026-09-18).
- **Contexto:** Prevenir que o agente escape do diretório autorizado através de caminhos relativos (`..`) ou caminhos absolutos arbitrários.
- **Decisão:** Todos os caminhos de entrada e saída devem ser validados contra uma raiz base declarada (`base_dir`), disparando exceção de segurança imediata diante de tentativas de fuga.
- **Consequências:** Garante que dados pessoais fora da pasta de teste permaneçam 100% intocados.

---

## ADR-004: Endurecimento de Fronteira e Confinamento Físico (Etapa 2B)
- **Status:** Aprovada (2026-10-04).
- **Contexto:** A verificação de fronteira anterior baseada em `startswith` apresentava vulnerabilidade crítica a diretórios irmãos com prefixo coincidente (ex.: `C:/dir2` sendo aceito em `C:/dir`). Além disso, construções de caminhos do Windows (UNC, caminhos absolutos em planos, unidades relativas como `C:foo`, fluxos alternativos NTFS/ADS, junctions e symlinks) exigiam controle rigoroso antes da introdução de cálculo de hashes.
- **Decisão:**
  1. Eliminar integralmente `startswith` para verificações de confinamento, adotando comparação por componentes via `os.path.commonpath` com normalização de separadores e caixa (`normpath`, `normcase`);
  2. Concentrar a política lexical no módulo `src/core/boundary.py` (`normalize_relative_path`, `is_within_boundary`, `resolve_within`), aceitando estritamente caminhos relativos em `ExecutionPlan` e rejeitando absolutos, UNC, drive-relative, ADS, traversal e nomes reservados do Windows;
  3. No scanner (`DirectoryScanner`), exigir raiz física (rejeitando symlinks e junctions como `base_dir`) e verificar cada entrada contra a raiz real via `realpath` e `is_within_boundary`;
  4. Tratar reparse points de redirecionamento (bit *name surrogate* `0x20000000`, cobrindo symlinks e junctions) como links pulados por padrão, sem bloquear o atributo genérico `FILE_ATTRIBUTE_REPARSE_POINT`, preservando o inventário normal de placeholders em nuvem do OneDrive;
  5. Prevenir ciclos e duplicatas de diretórios por controle canônico de caminhos reais visitados;
  6. Ordenar travessia de forma determinística por nome;
  7. Sanitizar mensagens de erro e de itens pulados sem vazar caminhos absolutos locais, tratando `OSError` e `FileNotFoundError` como falhas parciais de inventário sem interromper a varredura global;
  8. Reconhecer a impossibilidade de eliminar fisicamente corridas TOCTOU, mantendo tratamento resiliente e documentando o risco residual.
- **Consequências:** Confinamento lexical e físico robusto e determinístico, preservação total dos contratos de `FileItem` e `ScannerConfig`, e introdução de campo aditivo `skipped` em `ScanReport`.

---

## ADR-005: Hashing opt-in por objetos fixados, Windows conservador

- **Status:** Implementada em 2026-10-04; gate inicial aprovado somente para
  fixtures NTFS locais sintéticas; complementos aprovados pelo coordenador na
  revisão delimitada com phase-gate-reviewer. Baseline 6d24cb0, sem commit/push.
- **Contexto:** Checks lexicais/realpath não fixam objetos durante leitura; uma
  abertura por path posterior à validação reintroduz troca de objeto/ancestral.
- **Decisão:** Scanner somente metadados, snapshots aditivos no inventário e
  HashSession separado. Backend stdlib/ctypes fixando raiz/ancestrais/folha,
  share READ, FileIdInfo 64/128 bits, final paths/attrs/tags/tipo e ReOpenFile
  do mesmo objeto. Recusar APIs desconhecidas, remoto/case-sensitive,
  reparse/cloud/recall/especiais/hardlinks; nenhuma segunda abertura de dados por
  path nem backend POSIX. Handles de metadata não bloqueiam sozinhos share-access;
  bloqueio comum vem do handle de dados/descendente aberto. Janela anterior a
  ReOpenFile é detectada, não bloqueada. A travessia intermediária de metadata
  por path pode contactar SMB antes da recusa, inclusive com symlink permitido
  por Developer Mode; não se promete zero rede absoluto concorrente. Leitura de
  dados somente após validação do objeto. ReOpenFile usa flags que a API aceita,
  após recusa conservadora dos atributos de cloud/recall no handle fixado.
- **Decisão de budgets:** chunks 64 KiB..1 MiB, padrão 256 KiB; budgets positivos
  finitos, reserva de uma sondagem, bytes efetivos contados inclusive falhas.
  Digest parcial None; erro raiz invalida todos os resultados da sessão.
- **Decisão de grupos:** somente sucessos e objetos distintos por tamanho/hash;
  ordenação Unicode por paths. Redundância lógica não é espaço recuperável.
  Nenhuma operação de organização/exclusão é implementada ou autorizada aqui.
- **Consequências:** Recusa conservadora pode exigir novo inventário. Preservados
  construtores legados e relatórios. Evidências simuladas/sintéticas/Windows real
  são distintas; skip de symlink nativo permanece lacuna. Riscos residuais de
  namespace acima da raiz, mappings, filtros, mutadores privilegiados e metadados
  restaurados impedem alegar isolamento absoluto/snapshot atômico.
- **Complemento do gate inicial:** aprovado exclusivamente para fixtures NTFS
  locais sintéticas; revisão dos complementos aceita pelo coordenador, com
  suíte independente 67 executados/66 pass/1 skip e exit 0. HashReport explicita
  scope provided_inventory e conta erros do inventário sem copiar mensagens;
  esses erros tornam a análise partial preservando sucessos. Complete não prova
  cobertura de toda a árvore. Dedupe silencioso e exceções inesperadas ficam
  documentados como limites não bloqueantes, sem ampliar a implementação.

## Complemento da ADR-005: falha no snapshot inicial da raiz

- **Status:** Concluído em 2026-10-05; gate independente Codex gpt-6.1-sol high
  recebido e aceito: pronto para commit somente para fixtures NTFS locais sintéticas.
- **Decisão:** Capturar OSError no lstat inicial de scan(), retornar ScanReport
  vazio com erro relativo '.' e descrição sanitizada de tipo/errno, manter
  root_observation=None e não iniciar travessia. Não reconstruir snapshot tardio.
  O hasher existente recusa root_snapshot_missing antes de pin_root/conteúdo
  quando enabled e suportado. Assinaturas e modo metadata-only preservados.
- **Evidência:** Três regressões com mocks após construção; suite do escritor
  70 executados/69 aprovados/1 skip, exit 0. Nenhuma falha real de ACL/remoção
  de raiz foi induzida. Baseline 6d24cb0 com Etapa 3 preexistente sem commit/push.
- **Aceite:** Reviewer com execução independente confirmou 70/69/1, exit 0,
  17 candidatos aceitos e ausência de bloqueadores materiais. Código/testes
  congelados; registro final exclusivamente documental, sem repetir suíte.
  Commit/push aguardam autorização nominal; remoto atual desconhecido.
- **Limites:** Aprovações históricas continuam restritas ao escopo sintético;
  este complemento não autoriza dados reais, mudanças no backend ou Etapa 4.
