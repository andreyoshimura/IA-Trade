# Financeiro Automation

Sistema automatizado de gestão financeira pessoal baseado em Gmail,
Google Drive e Google Sheets. Arquitetura preparada para evolução futura
(n8n, PostgreSQL, Python Analytics).

------------------------------------------------------------------------

## 🎯 Objetivo

Automatizar:

-   Processamento de e-mails financeiros (CPFL, IPTU, etc.)
-   Organização automática de documentos no Google Drive
-   Registro estruturado de lançamentos no Google Sheets
-   Controle de duplicidade via messageId
-   Base sólida para balanço mensal e anual

------------------------------------------------------------------------

## 🏗 Arquitetura V1

Gmail → Apps Script → Drive → Sheets

-   Gmail: Fonte de entrada
-   Apps Script: Backend de automação
-   Drive: Armazenamento documental
-   Sheets: Base de dados estruturada
-   GitHub: Versionamento do código (via clasp)

------------------------------------------------------------------------

## 📁 Estrutura do Projeto

    financeiro-automation/
    │
    ├── src/
    │   ├── main.gs
    │   ├── config.gs
    │   ├── gmailService.gs
    │   ├── driveService.gs
    │   ├── sheetService.gs
    │   ├── financeService.gs
    │   └── utils.gs
    │
    ├── docs/
    │   ├── architecture-v1.md
    │   ├── data-model-v1.md
    │   ├── workflows-v1.md
    │   └── roadmap.md
    │
    ├── appsscript.json
    ├── .gitignore
    └── README.md

------------------------------------------------------------------------

## 📂 Estrutura no Google Drive

    /Financeiro/
       /AAAA/
          /MM-AAAA/
             /FORNECEDOR/
             /Resumo/

Exemplo:

    /Financeiro/2026/02-2026/CPFL/

------------------------------------------------------------------------

## 🗃 Modelo de Dados (V1)

Planilha: `Financeiro_Pessoal`\
Aba principal: `LANÇAMENTOS`

Campos obrigatórios:

-   id_unico
-   message_id
-   data_recebimento
-   data_competencia
-   ano
-   mes
-   fornecedor
-   categoria
-   tipo
-   valor
-   data_vencimento
-   status
-   link_arquivo

------------------------------------------------------------------------

## 🔁 Fluxo de Processamento

1.  Gmail aplica label `FINANCEIRO/ENTRADA`
2.  Trigger executa `processarEmails()`
3.  Script:
    -   Identifica fornecedor
    -   Baixa anexo
    -   Cria pasta Ano/Mês/Fornecedor
    -   Salva PDF
    -   Extrai dados básicos
    -   Insere linha no Sheets
    -   Move e-mail para `PROCESSADO`

------------------------------------------------------------------------

## 🔒 Controle de Duplicidade

Cada lançamento salva o `message_id` do Gmail.\
Antes de inserir, o sistema verifica se já existe registro.

------------------------------------------------------------------------

## ⏱ Triggers

-   A cada 15 minutos → `processarEmails()`
-   Diário → `verificarVencimentos()`

------------------------------------------------------------------------

## 📊 Balanço

O balanço mensal e anual é calculado via fórmulas no Sheets.

Abas recomendadas:

-   BALANCO_MENSAL
-   BALANCO_ANUAL
-   COMPARATIVO
-   DASHBOARD

------------------------------------------------------------------------

## 🚀 Roadmap

### V1 -- Base Operacional

-   Apps Script modular
-   Sheets como base
-   Drive organizado automaticamente

### V2 -- Orquestração com n8n

-   Workflows desacoplados
-   Integração avançada

### V3 -- Banco PostgreSQL

-   Banco relacional real
-   Sheets como interface

### V4 -- Camada Analítica Python

-   Previsão de gastos
-   Detecção de anomalias

### V5 -- Inteligência Financeira

-   Score financeiro
-   Projeções e simulações
-   Sistema de metas

------------------------------------------------------------------------

## 🛡 Segurança

-   Script executado apenas no usuário proprietário
-   Pasta raiz privada
-   Não versionar credenciais (.clasp.json ignorado)
-   Uso de PropertiesService para IDs sensíveis

------------------------------------------------------------------------

## 📌 Status

Versão atual: V1 (Base Operacional)
