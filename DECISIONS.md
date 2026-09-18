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
