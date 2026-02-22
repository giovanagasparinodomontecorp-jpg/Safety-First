# Safety First – Portal de Gestão de Ocorrências

Aplicação web para gestão interna de riscos, acidentes e problemas estruturais em ambiente corporativo/industrial.

## Funcionalidades implementadas

- **Dashboard inicial** com:
  - total de ocorrências abertas
  - totais por prioridade
  - distribuição por área
  - distribuição por status
  - tempo médio de resolução
  - filtro por período (7, 15, 30, 90 dias)
- **Registro de nova ocorrência** com:
  - área/local
  - tipo de ocorrência
  - descrição detalhada
  - prioridade
  - upload de múltiplas imagens
  - data automática
  - solicitante pelo login atual
  - responsável selecionável
- **Lógica de prioridade e notificação automática**:
  - Alta/Crítica: envio para responsável
  - Crítica: envio também para gestor superior
  - envio está implementado como **simulação por console** (ponto de integração SMTP)
- **Controle de status**:
  - Aberto, Em atendimento, Aguardando terceiros, Resolvido, Cancelado
  - comentários por alteração
  - histórico de alterações
  - registro de quem alterou
  - data de conclusão automática em status Resolvido
- **Relatórios e indicadores**:
  - ocorrências por área
  - por nível de risco
  - tempo médio de atendimento
  - índice de reincidência
  - evolução mensal
  - botões de exportação PDF/Excel (placeholder)
- **Controle de acesso por perfil**:
  - usuário comum
  - responsável de área
  - administrador
- **Banco de dados SQLite** com tabelas: `users`, `areas`, `occurrences`, `occurrence_history`, `occurrence_images`.

## Tecnologias

- Python 3
- Flask
- SQLite
- HTML/CSS

## Como executar

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Acesse: `http://localhost:5000`

## Usuários de exemplo

- `admin@safety.local` / `admin123`
- `maria@safety.local` / `123`
- `joao@safety.local` / `123`

## Próximos passos recomendados

1. Integrar envio real de e-mail via SMTP (ou serviço transacional).
2. Implementar exportação real em PDF e Excel.
3. Adicionar autenticação segura com hash de senha e políticas de segurança.
4. Criar API REST para integração com outros sistemas.
5. Incluir gráficos reais (ex.: Chart.js) e trilhas de auditoria avançadas.
