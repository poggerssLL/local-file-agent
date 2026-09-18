# Limitações e Problemas Conhecidos: Local File Agent

Atualizado em: 2026-09-18.

## Limitações da Etapa 1 (Fundação e Política de Segurança)

1. **Ausência de Varredura em Disco:** O sistema atualmente possui apenas os modelos de dados e regras de validação; a varredura real do sistema de arquivos será implementada na Etapa 2 (Inventário Somente Leitura).
2. **Execução de Operações Bloqueada:** O motor transacional físico não está implementado (programado para a Etapa 8). Qualquer tentativa de execução física nesta etapa é bloqueada por design.
3. **Classificação Manual:** A classificação por regras determinísticas e por LLM será introduzida nas Etapas 4 e 5.
