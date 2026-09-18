# Roadmap: Local File Agent

Atualizado em: 2026-09-18.

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
3. **Etapa 3: Hashes e Detecção de Duplicidades (Próximo Passo - Codex na Segunda-feira):**
   - Cálculo determinístico de hashes SHA-256 com leitura em blocos (*chunks*);
   - Identificação de arquivos idênticos e cálculo de espaço duplicado.
4. **Etapa 4: Classificação Heurística e Determinística:**
   - Motor de regras por extensão, convenção de nomes e intervalos de datas;
   - Geração de sugestões automáticas de organização sem uso de inteligência artificial.
5. **Etapa 5: Integração com Modelos de Linguagem para Casos Ambíguos:**
   - Classificação com saída estritamente estruturada (JSON schema) para arquivos sem padrão óbvio;
   - Suporte a modelos locais (via Ollama/GGUF) e simulação mock.
6. **Etapa 6: Gerador do Plano de Operações (*Operation Planner*):**
   - Agrupamento de ações propostas em um `ExecutionPlan` atômico;
   - Detecção prévia de colisões de nomes e caminhos de destino.
7. **Etapa 7: Mecanismo de Prévia e Aprovação Humana:**
   - Interface de revisão em linha de comando ou Markdown;
   - Validação da decisão explícita de Erick antes de prosseguir.
8. **Etapa 8: Motor de Execução Transacional:**
   - Aplicação física de renomeações e movimentações com tratamento de falhas;
   - Garantia de que arquivos com erro não corrompam a estrutura.
9. **Etapa 9: Diário de Auditoria (Audit Journal):**
   - Persistência em SQLite local de cada ação executada com metadados completos.
10. **Etapa 10: Mecanismo de Desfazer (*Undo*):**
    - Capacidade de reverter com 1 comando uma operação transacional gravada no diário.
11. **Etapa 11: Validação de Ponta a Ponta com Diretório Sintético:**
    - Teste do ciclo completo em diretório controlado gerado com arquivos de teste antes de qualquer uso real.
