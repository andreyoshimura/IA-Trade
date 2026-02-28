# IA-Trade

## Caracteristicas

- Backtester funcional
- Curva de capital
- Calculo de drawdown
- Metricas completas
- Estrutura preparada para multiplas estrategias

## Decisao Estrategica

Pullback intraday em BTC 15m e estruturalmente fragil.

Proximo modelo a ser implementado:

### Breakout Estrutural com Filtro de Tendencia

Timeframe principal: 15m  
Filtro macro: 1h EMA 200

#### Regras Compra

1. Close 1h > EMA 200
2. Rompimento da maxima das ultimas 20 velas (15m)
3. Volume acima da media 20
4. Stop = ATR * 1.5
5. Target = 2R

Venda espelhada.

#### Justificativa

- BTC responde melhor a expansao do que a pullback curto.
- Breakout tem estatistica mais favoravel em cripto.
- Matematica mais saudavel para R:R 2.

## Roadmap

### Fase 1 - Validacao Tecnica (Atual)

- Backtester implementado
- Estrategia 1 testada e descartada
- Metricas estatisticas funcionando

Proximo:

- Implementar breakout estrutural
- Rodar backtest com 2 anos de dados
- Validar:
  - Profit factor > 1.3
  - Winrate > 35%
  - Drawdown aceitavel (<20%)

### Fase 2 - Robustez Estatistica

- Paginacao para historico > 2 anos
- Walk-forward validation
- Analise de estabilidade de parametros
- Curva de capital visual
- Monte Carlo basico

### Fase 3 - Paper Trade

- Bot rodando em tempo real
- Sinais enviados via Telegram
- Registro automatico (n8n opcional)
- Diario automatico de trades

### Fase 4 - Semi-Automacao

- Ordem limite enviada automaticamente
- Stop e target automaticos
- Controle de risco ativo
- Monitoramento de falhas

### Fase 5 - Automacao Total

- Execucao completa
- Controle de drawdown automatico
- Pausa apos sequencia de perdas
- Relatorios automaticos
- Filtro de regime adaptativo

## Principios do Projeto

1. Nunca automatizar estrategia sem edge comprovado.
2. Nunca otimizar sistema negativo (evitar overfitting).
3. Primeiro validar estatistica, depois sofisticar.
4. Complexidade so entra quando ha base solida.
5. LLM sera camada auxiliar, nao motor principal.

## Proximos Passos Imediatos

1. Implementar estrategia breakout.
2. Rodar backtest com historico maior.
3. Avaliar metricas.
4. Decidir se ha edge real.

## Objetivo Final

Construir sistema quantitativo consistente, com:

- Expectancy positiva
- Drawdown controlado
- Gestao de risco disciplinada
- Evolucao para autonomia real

Sem promessas irreais.  
Sem alavancagem irresponsavel.  
Sem improviso.

`source venv/bin/activate` sempre que for usar.

---

# Financeiro Automation

Sistema automatizado de gestao financeira pessoal baseado em Gmail,
Google Drive e Google Sheets. Arquitetura preparada para evolucao futura
(n8n, PostgreSQL, Python Analytics).

## Objetivo

Automatizar:

- Processamento de e-mails financeiros (CPFL, IPTU, etc.)
- Organizacao automatica de documentos no Google Drive
- Registro estruturado de lancamentos no Google Sheets
- Controle de duplicidade via messageId
- Base solida para balanco mensal e anual

## Arquitetura V1

Gmail -> Apps Script -> Drive -> Sheets

- Gmail: Fonte de entrada
- Apps Script: Backend de automacao
- Drive: Armazenamento documental
- Sheets: Base de dados estruturada
- GitHub: Versionamento do codigo (via clasp)

## Estrutura do Projeto

```text
financeiro-automation/
|
|-- src/
|   |-- main.gs
|   |-- config.gs
|   |-- gmailService.gs
|   |-- driveService.gs
|   |-- sheetService.gs
|   |-- financeService.gs
|   `-- utils.gs
|
|-- docs/
|   |-- architecture-v1.md
|   |-- data-model-v1.md
|   |-- workflows-v1.md
|   `-- roadmap.md
|
|-- appsscript.json
|-- .gitignore
`-- README.md
```

## Estrutura no Google Drive

```text
/Financeiro/
   /AAAA/
      /MM-AAAA/
         /FORNECEDOR/
         /Resumo/
```

Exemplo:

```text
/Financeiro/2026/02-2026/CPFL/
```

## Modelo de Dados (V1)

Planilha: `Financeiro_Pessoal`  
Aba principal: `LANCAMENTOS`

Campos obrigatorios:

- id_unico
- message_id
- data_recebimento
- data_competencia
- ano
- mes
- fornecedor
- categoria
- tipo
- valor
- data_vencimento
- status
- link_arquivo

## Fluxo de Processamento

1. Gmail aplica label `FINANCEIRO/ENTRADA`
2. Trigger executa `processarEmails()`
3. Script:
- Identifica fornecedor
- Baixa anexo
- Cria pasta Ano/Mes/Fornecedor
- Salva PDF
- Extrai dados basicos
- Insere linha no Sheets
- Move e-mail para `PROCESSADO`

## Controle de Duplicidade

Cada lancamento salva o `message_id` do Gmail.  
Antes de inserir, o sistema verifica se ja existe registro.

## Triggers

- A cada 15 minutos -> `processarEmails()`
- Diario -> `verificarVencimentos()`

## Balanco

O balanco mensal e anual e calculado via formulas no Sheets.

Abas recomendadas:

- BALANCO_MENSAL
- BALANCO_ANUAL
- COMPARATIVO
- DASHBOARD

## Roadmap

### V1 - Base Operacional

- Apps Script modular
- Sheets como base
- Drive organizado automaticamente

### V2 - Orquestracao com n8n

- Workflows desacoplados
- Integracao avancada

### V3 - Banco PostgreSQL

- Banco relacional real
- Sheets como interface

### V4 - Camada Analitica Python

- Previsao de gastos
- Deteccao de anomalias

### V5 - Inteligencia Financeira

- Score financeiro
- Projecoes e simulacoes
- Sistema de metas

## Seguranca

- Script executado apenas no usuario proprietario
- Pasta raiz privada
- Nao versionar credenciais (`.clasp.json` ignorado)
- Uso de PropertiesService para IDs sensiveis

## Status

Versao atual: V1 (Base Operacional)
