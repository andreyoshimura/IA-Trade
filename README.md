
### Características

- Backtester funcional
- Curva de capital
- Cálculo de drawdown
- Métricas completas
- Estrutura preparada para múltiplas estratégias

---

# Decisão Estratégica

Pullback intraday em BTC 15m é estruturalmente frágil.

Próximo modelo a ser implementado:

## Breakout Estrutural com Filtro de Tendência

Timeframe principal: 15m  
Filtro macro: 1h EMA 200  

### Regras Compra

1. Close 1h > EMA 200  
2. Rompimento da máxima das últimas 20 velas (15m)  
3. Volume acima da média 20  
4. Stop = ATR * 1.5  
5. Target = 2R  

Venda espelhada.

### Justificativa

- BTC responde melhor a expansão do que a pullback curto.
- Breakout tem estatística mais favorável em cripto.
- Matemática mais saudável para R:R 2.

---

# Roadmap

## Fase 1 – Validação Técnica (Atual)

- Backtester implementado
- Estratégia 1 testada e descartada
- Métricas estatísticas funcionando

### Próximo
- Implementar breakout estrutural
- Rodar backtest com 2 anos de dados
- Validar:
  - Profit factor > 1.3
  - Winrate > 35%
  - Drawdown aceitável (<20%)

---

## Fase 2 – Robustez Estatística

- Paginação para histórico > 2 anos
- Walk-forward validation
- Análise de estabilidade de parâmetros
- Curva de capital visual
- Monte Carlo básico

---

## Fase 3 – Paper Trade

- Bot rodando em tempo real
- Sinais enviados via Telegram
- Registro automático (n8n opcional)
- Diário automático de trades

---

## Fase 4 – Semi-Automação

- Ordem limite enviada automaticamente
- Stop e target automáticos
- Controle de risco ativo
- Monitoramento de falhas

---

## Fase 5 – Automação Total

- Execução completa
- Controle de drawdown automático
- Pausa após sequência de perdas
- Relatórios automáticos
- Filtro de regime adaptativo

---

# Princípios do Projeto

1. Nunca automatizar estratégia sem edge comprovado.
2. Nunca otimizar sistema negativo (evitar overfitting).
3. Primeiro validar estatística, depois sofisticar.
4. Complexidade só entra quando há base sólida.
5. LLM será camada auxiliar, não motor principal.

---

# Próximos Passos Imediatos

1. Implementar estratégia breakout.
2. Rodar backtest com histórico maior.
3. Avaliar métricas.
4. Decidir se há edge real.

---

# Objetivo Final

Construir sistema quantitativo consistente, com:

- Expectancy positiva
- Drawdown controlado
- Gestão de risco disciplinada
- Evolução para autonomia real

Sem promessas irreais.  
Sem alavancagem irresponsável.  
Sem improviso.