# IA-Trade

Sistema de trading quantitativo evolutivo, iniciado com foco em validação estatística antes de qualquer automação.

Projeto estruturado para evoluir de:

Manual → Semi-automático → Automático → Autônomo

---

# Situação Atual

## Capital Base
- 300 USD
- Binance Futures (USDT-M)
- Risco por trade: 1%

## Estratégia Testada (Pullback 15m)

Lógica:
- Tendência 1h via EMA 50
- Pullback 15m
- RSI filtro
- Stop ATR * 1.8
- Target 2.5R

## Resultado do Backtest

Initial capital: 300  
Final capital: 264  
Total trades: 33  
Winrate: 18.2%  
Profit factor: 0.55  
Expectancy: negativa  
Max drawdown: -15.7%

### Conclusão

- Estratégia não possui edge.
- Profit factor < 1.
- Expectancy negativa.
- Não deve ser automatizada.

Decisão: abandonar modelo pullback.

---

# Arquitetura Atual

Estrutura modular pronta para escalar:

