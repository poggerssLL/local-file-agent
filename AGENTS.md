# Orientações Permanentes: Local File Agent

Este arquivo orienta qualquer agente ou tarefa do Codex/Antigravity aberta no projeto `Local File Agent`.
O papel deste projeto é fornecer **inventário, classificação e organização segura e determinística de arquivos locais**, com total controle humano, reversibilidade e privacidade.

---

## 1. Princípios Fundamentais e Regras de Ouro

1. **Aprovação Humana Obrigatória:**
   - O agente **NUNCA** move, renomeia, altera ou exclui arquivos em disco de forma autônoma.
   - Qualquer modificação exige a geração prévia de um **ExecutionPlan** com prévia detalhada (origem, destino, motivo) e aguarda confirmação explícita de Erick.
2. **Confinamento Rígido de Escopo:**
   - O agente opera **exclusivamente** dentro de diretórios explicitamente autorizados.
   - É terminantemente proibido escanear, enumerar ou manipular:
     - A raiz do perfil do usuário (`C:\Users\erick` como um todo);
     - Diretórios do sistema operacional (`C:\Windows`, `C:\Program Files`, `AppData`);
     - Pastas de outros projetos sem autorização nominal.
3. **Reversibilidade e Suporte a Desfazer (Undo):**
   - Toda operação transacional deve registrar metadados para permitir a reversão (*undo*) completa;
   - Modo padrão é sempre **Dry-Run (Simulação)** até confirmação em contrário.
4. **Privacidade e Operação 100% Offline:**
   - Metadados e índices ficam em banco SQLite local;
   - Nenhum conteúdo de arquivos pessoais ou documentos é transmitido para serviços externos de nuvem sem autorização expressa.
5. **Desenvolvimento por Etapas:**
   - Trabalhe em uma única etapa por vez. A Etapa 1 é estritamente de **Fundação e Política de Segurança** (nenhuma operação em disco autorizada).

---

## 2. Comunicação com Erick

- Comece toda mensagem visível com `Erick,`.
- Responda em português por padrão.
- Apresente primeiro a conclusão ou estado principal.
- Diferencie explicitamente:
  - o que já foi implementado;
  - o que foi testado com mocks/fixtures sintéticos;
  - o que foi validado em execução real;
  - o que é trabalho futuro ou planejado.
- Nunca realize `git commit` ou `git push` sem autorização nominal.

---

## 3. Estrutura e Governança

- **Um Escritor por Checkout:** Apenas um agente modifica arquivos por vez.
- **Relatórios Imutáveis:** Cada etapa concluída gera um relatório histórico em `docs/PHASE_XX_*.md` e atualiza a documentação viva (`PROJECT_STATE.md`, `FOUNDATION.md`, `ROADMAP.md`).
- **Proibição de Controle Visual:** Prefira sempre APIs, terminal e arquivos. Controle direto de mouse e teclado é proibido salvo autorização expressa.
