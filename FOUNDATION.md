# Arquitetura e Fundação Viva: Local File Agent

Atualizado em: 2026-09-18.
Etapa atual: **Etapa 1 - Fundação e Política de Segurança**.

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
   - A classificação tenta regras heurísticas e determinísticas primeiro (extensões, padrões de data, prefixos conhecidos). Apenas casos ambíguos consultam modelos de linguagem locais com saída estruturada.
3. **Mecanismo de Desfazer (*Undo Journal*):**
   - Nenhuma movimentação de arquivo é feita sem antes registrar em log SQLite a tupla reversível: `{id, timestamp, original_path, target_path, original_hash}`.
4. **Isolamento de Diretórios de Trabalho:**
   - O agente só recebe caminhos relativos ou subdiretórios estritamente permitidos. Caminhos fora da fronteira declarada disparam exceção de segurança imediata.

---

## 3. Contratos de Dados Centrais (`src/core/models.py`)

- **`FileItem`:** Representa um arquivo inventariado (caminho relativo, tamanho em bytes, data de modificação, hash SHA-256 opcional).
- **`OperationType`:** Enumeração das operações suportadas (`RENAME`, `MOVE`, `TAG`, `SIMULATE`).
- **`OperationAction`:** Ação atômica contendo `source_path`, `destination_path`, `reason` e `status`.
- **`ExecutionPlan`:** Coleção de ações planejadas com `dry_run: bool` (padrão `True`) e `approved: bool` (padrão `False`).

---

## 4. Evolução por Etapas

As fases subsequentes do projeto construirão gradualmente sobre esta fundação, conforme definido no [`ROADMAP.md`](file:///C:/Users/erick/OneDrive/Documentos/Local%20File%20Agent/ROADMAP.md).
