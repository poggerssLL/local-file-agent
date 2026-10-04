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
