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


