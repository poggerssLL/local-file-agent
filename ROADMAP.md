# Roadmap: Local File Agent

Atualizado em: 2026-10-05.

## Regra de Sequência

O roadmap orienta as próximas decisões. Trabalhe em uma única etapa por vez e só avance após revisão e testes satisfatórios da etapa anterior.

---

## Trilha de Implementação

1. **Etapa 1: Fundação e Política de Segurança (Concluída nesta fase):**
   - Criação do repositório, `.gitignore`, governança em `AGENTS.md` e `FOUNDATION.md`;
   - Definição dos contratos de dados centrais em `src/core/models.py`;
   - Implementação de regras invioláveis de aprovação humana e modo dry-run por padrão;
   - Suíte de testes unitários de fundação.
2. **Etapa 2: Inventário Somente Leitura (Concluída nesta fase):**
   - Varredura recursiva confinada a um diretório de entrada autorizado;
   - Coleta de metadados sem alteração de arquivos (tamanho, timestamps, extensões);
   - Relatório de inventário estruturado com `ScannerConfig` e `ScanReport`;
   - Testada com suíte sintética de testes (`tests/fixtures/synthetic_tree`).
3. **Etapa 2B: Hardening de Fronteira e Confinamento Físico (Concluída nesta fase):**
   - Eliminação definitiva de `startswith` em favor de comparação por componentes (`commonpath` com `normpath`/`normcase`);
   - Política unificada e estrita de caminhos relativos em planos de execução (`src/core/boundary.py`), rejeitando absolutos, UNC, unidades, drive-relative, ADS e escapes;
   - Scanner endurecido (`src/core/scanner.py`): raiz física obrigatória, classificação de links via bit *name surrogate* preservando placeholders em nuvem do OneDrive, prevenção determinística de ciclos e diretórios duplicados, ordenação alfabética e sanitização de mensagens de erros/skips sem vazamento de caminhos absolutos locais;
   - Reconhecimento e tratamento resiliente de corridas TOCTOU e separação explícita entre confinamento lexical e físico.
4. **Etapa 3: Hashes e Detecção de Duplicidades (Aprovada somente para fixtures NTFS locais sintéticas, incluindo complementos):**
   - Cálculo determinístico de hashes SHA-256 com leitura em blocos (*chunks*);
   - Sessão separada opt-in, snapshots de inventário e backend Windows local conservador;
   - Grupos determinísticos e redundância lógica, sem promessa de espaço recuperável;
   - Fixtures sintéticos e provas Windows nativas; symlink de arquivo sem privilégio permanece lacuna explícita;
   - Complementos: scope provided_inventory, contagem sanitizada de erros do inventário, documentação de limites/sharing/metadata e higiene BOM;
   - Gate inicial independente Antigravity aprovado; complementos aceitos pelo coordenador com phase-gate-reviewer e suíte independente 67/66/1;
   - Baseline 6d24cb0; symlink de folha e riscos residuais continuam limites. Etapa 3 publicada em `49c7dbe`; Etapa 4 implementada localmente, gate técnico aprovado.
   - Complemento de release 2026-10-05 concluído: falha na observação inicial da raiz retorna inventário vazio sanitizado, sem travessia; hashing recusa snapshot ausente antes de conteúdo. Três regressões simuladas; escritor e reviewer independente Codex gpt-6.1-sol high confirmaram 70/69/1, exit 0. Gate aceito exclusivamente em fixtures NTFS locais sintéticas. Commit/push autorizados nominalmente em 2026-10-05; preflight confirmou main remoto em 6d24cb0. A confirmação da publicação deve ser obtida pelo Git após o push.
5. **Etapa 4: Classificação Heurística e Determinística (implementada; gate técnico aprovado):**
   - Motor de regras por extensão, convenção de nomes e intervalos de datas;
   - Sugestões sobre metadados somente, regras auditáveis, sem I/O/planos/LLM;
   - 20 testes novos; suíte 90/89/1, exit 0, com limites sintéticos preservados;
   - Commit/push autorizados por Erick em 2026-10-05; publicação verificável no Git;
   - Próxima etapa planejada é a 5, ainda não iniciada.
6. **Etapa 5: Integração com Modelos de Linguagem para Casos Ambíguos:**
   - Classificação com saída estritamente estruturada (JSON schema) para arquivos sem padrão óbvio;
   - Suporte a modelos locais (via Ollama/GGUF) e simulação mock.
7. **Etapa 6: Gerador do Plano de Operações (*Operation Planner*):**
   - Agrupamento de ações propostas em um `ExecutionPlan` atômico;
   - Detecção prévia de colisões de nomes e caminhos de destino.
8. **Etapa 7: Mecanismo de Prévia e Aprovação Humana:**
   - Interface de revisão em linha de comando ou Markdown;
   - Validação da decisão explícita de Erick antes de prosseguir.
9. **Etapa 8: Motor de Execução Transacional:**
   - Aplicação física de renomeações e movimentações com tratamento de falhas;
   - Garantia de que arquivos com erro não corrompam a estrutura.
10. **Etapa 9: Diário de Auditoria (Audit Journal):**
    - Persistência em SQLite local de cada ação executada com metadados completos.
11. **Etapa 10: Mecanismo de Desfazer (*Undo*):**
    - Capacidade de reverter com 1 comando uma operação transacional gravada no diário.
12. **Etapa 11: Validação de Ponta a Ponta com Diretório Sintético:**
    - Teste do ciclo completo em diretório controlado gerado com arquivos de teste antes de qualquer uso real.
