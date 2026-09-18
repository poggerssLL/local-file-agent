# Local File Agent

Assistente local e determinístico para inventário, classificação e organização segura de arquivos com total controle humano, reversibilidade e privacidade.

---

## 1. O que é o Local File Agent?

O `Local File Agent` é um componente do ecossistema de inteligência artificial local de Erick.
Seu objetivo é analisar pastas caóticas (como downloads ou documentos desorganizados), identificar duplicidades, sugerir nomes padronizados e propor categorias limpas de organização.

### Pilares Fundamentais:
- **Aprovação Humana Obrigatória:** O agente gera uma prévia e nunca altera nada sem você autorizar explicitamente;
- **Reversibilidade Total (*Undo*):** Todas as movimentações podem ser desfeitas com 1 comando;
- **Privacidade Local:** Metadados ficam no seu computador em SQLite; nenhum arquivo pessoal vai para a nuvem;
- **Segurança Confinada:** O agente só atua dentro da pasta exata que você autorizar.

---

## 2. Estrutura do Projeto

```text
Local File Agent/
├── AGENTS.md            # Regras permanentes e políticas de contenção
├── FOUNDATION.md        # Arquitetura viva e contratos
├── ROADMAP.md           # As 11 etapas do projeto
├── PROJECT_STATE.md     # Fotografia factual atual
├── DECISIONS.md         # Registro de decisões (ADRs)
├── KNOWN_ISSUES.md      # Limitações atuais
├── src/
│   └── core/            # Modelos de dados e contratos de segurança
└── tests/               # Testes unitários de fundação
```

---

## 3. Como Rodar os Testes

```powershell
python -m unittest discover tests
```
