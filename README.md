# IA-Trade

# 🔷 Objetivo Principal do Projeto

Construir um sistema quantitativo de trading totalmente automatizado, adaptativo, configurável e estatisticamente validado, capaz de operar múltiplos ativos de forma consistente em diferentes regimes de mercado.

O sistema deve ser estruturado desde o início para:

- Evoluir sem reestruturações profundas.
- Permitir ajustes rápidos de parâmetros.
- Suportar futura adaptação automática via ML/IA.
- Operar de forma disciplinada e controlada.
- Sobreviver a ciclos completos de mercado (bull, bear e lateral).

---

# 🔷 Visão Estrutural de Longo Prazo

O projeto será organizado em camadas independentes:

## 1. Camada de Pesquisa
- Backtesting robusto
- Validação estatística
- Walk-forward
- Estabilidade de parâmetros
- Monte Carlo

## 2. Camada de Estratégias
- Múltiplas estratégias modulares
- Totalmente parametrizáveis
- Independentes entre si

## 3. Camada de Orquestração
- Seleção de ativo
- Seleção de estratégia
- Ajuste de risco conforme regime

## 4. Camada de Inteligência (ML/IA)
- Classificação de regime de mercado
- Índice de “calor do mercado”
- Ranqueamento de ativos
- Ajuste dinâmico de exposição
- Ajustes automáticos controlados de parâmetros

## 5. Camada de Execução
- Execução automática
- Controle de drawdown
- Pausa após sequência de perdas
- Logs e monitoramento

---

# 🔷 Configurabilidade como Fundamento

O sistema deve ser totalmente configurável.

Parâmetros ajustáveis:

- Timeframes
- Períodos de médias
- ATR
- R:R
- Lista de ativos
- Filtros de regime
- Limites de risco
- Ativação/desativação de módulos

Nenhuma constante crítica deve permanecer hardcoded.

Configuração deve ficar centralizada (`config.py` ou arquivo externo futuramente).

A arquitetura deve permitir:

- Ajustes manuais rápidos
- Ajustes automáticos via ML (dentro de limites pré-definidos)
- Evolução sem reescrever o motor principal

---

# 🔷 Diferencial Estratégico

O sistema não busca prever o próximo candle.

Busca:

- Operar apenas quando há probabilidade estatística favorável
- Adaptar-se ao contexto do mercado
- Diversificar risco entre ativos
- Reduzir exposição em ambientes adversos
- Manter consistência ao longo do tempo

Não é apenas um bot.

É um sistema adaptativo multi-ativo, multi-estratégia e orientado a regime.

---

# Características

- Backtester funcional
- Curva de capital
- Cálculo de drawdown
- Métricas completas
- Estrutura preparada para múltiplas estratégias
- Base preparada para futura automação total

---

# Decisão Estratégica Atual

Pullback intraday em BTC 15m mostrou-se estruturalmente frágil.

Modelo atual implementado:

## Breakout Estrutural com Filtro de Tendência

Timeframe principal: 15m  
Filtro macro: 1h EMA 200  

### Regras de Compra

1. Close 1h > EMA 200  
2. ADX 1h acima de limiar mínimo configurável  
3. Rompimento da máxima das últimas 20 velas (15m), usando janela anterior (sem candle atual)  
4. Confirmação por buffer de ATR no rompimento  
5. Volume acima da média (fator mínimo configurável)  
6. Stop = ATR * multiplicador configurável  
7. Target = R:R configurável  
8. Cooldown entre operações para reduzir overtrading  

Venda espelhada.

### Justificativa

- BTC responde melhor a expansão do que a pullback curto.
- Breakout tende a ter estatística mais favorável em cripto.
- Relação risco-retorno mais saudável (2R).

---

# Roadmap

## Fase 1 - Validação Técnica (Concluída)

- Backtester implementado
- Estratégia 1 testada e descartada
- Métricas estatísticas funcionando
- Estratégia breakout estrutural implementada e validada

Critérios atingidos parcialmente:
- Profit factor > 1 em parte dos cenários
- Winrate próximo/acima de 35% em configurações filtradas
- Drawdown controlado abaixo de 20%

---

## Fase 2 - Robustez Estatística (Atual)

- Paginação para histórico > 2 anos
- Walk-forward validation
- Análise de estabilidade de parâmetros
- Curva de capital visual
- Monte Carlo básico

---

## Fase 3 - Paper Trade

- Bot rodando em tempo real
- Sinais enviados via Telegram
- Registro automático
- Diário automático de trades

---

## Fase 4 - Semi-Automação

- Ordem limite enviada automaticamente
- Stop e target automáticos
- Controle de risco ativo
- Monitoramento de falhas

---

## Fase 5 - Automação Total

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
5. ML será camada auxiliar, não motor principal.
6. Sistema deve ser configurável e preparado para evolução automática futura.
7. Sobrevivência vem antes de maximização de retorno.

---

# Próximos Passos Imediatos

1. Aumentar histórico para janela maior e repetir validação.
2. Separar benchmark fixo para comparação entre versões da estratégia.
3. Incluir custos reais (fee/slippage) no backtest.
4. Automatizar relatório de métricas por execução.

---

# Sweep de Parâmetros

Script para otimização de parâmetros (treino/teste out-of-sample):

- Grid paralelo (rápido):
  - `./venv/bin/python analysis/parameter_sweep.py --engine grid --profile quick --workers 4 --top 5`
- Grid paralelo (amplo):
  - `./venv/bin/python analysis/parameter_sweep.py --engine grid --profile balanced --workers 8 --top 10 --csv analysis/sweep_results.csv`
- Limitar número de combinações para teste rápido:
  - `./venv/bin/python analysis/parameter_sweep.py --engine grid --profile quick --max-candidates 3 --workers 3 --top 3`
- Otimização Bayesiana (Optuna):
  - `./venv/bin/python analysis/parameter_sweep.py --engine optuna --trials 40 --workers 2 --top 10 --csv analysis/optuna_results.csv`

---

# Atualização de Hoje (07/03/2026)

## O que foi feito

- Inclusão de custos operacionais no backtest (`FEE_RATE` e `SLIPPAGE_RATE`).
- Benchmark fixo de buy and hold para comparação entre versões.
- Automação da busca de parâmetros (`analysis/parameter_sweep.py`) com:
  - grid search paralelo;
  - fallback sequencial em ambiente restrito;
  - otimização bayesiana com Optuna.
- Seleção de nova configuração com foco em robustez out-of-sample.

## Configuração atual

- `RISK_PER_TRADE = 0.003`
- `MIN_ADX = 30`
- `MIN_VOLUME_FACTOR = 1.8`
- `BREAKOUT_BUFFER = 1.4`
- `TRADE_COOLDOWN_CANDLES = 36`
- `BREAKOUT_LOOKBACK = 60`
- `RR_RATIO = 2.5`
- `FEE_RATE = 0.0004`
- `SLIPPAGE_RATE = 0.0002`

## Resultado validado (main.py)

- Backtest completo: `final_capital 324.60`, `profit_factor 1.115`, `max_drawdown -7.99%`, `293 trades`
- Treino 70%: `final_capital 317.24`, `profit_factor 1.112`, `max_drawdown -6.83%`, `212 trades`
- Teste 30%: `final_capital 302.33`, `profit_factor 1.035`, `max_drawdown -3.72%`, `94 trades`

---

# Objetivo Final

Construir sistema quantitativo consistente com:

- Expectancy positiva
- Drawdown controlado
- Gestão de risco disciplinada
- Adaptação a regime de mercado
- Evolução para autonomia real

Sem promessas irreais.  
Sem alavancagem irresponsável.  
Sem improviso.

---

`source venv/bin/activate` sempre que for usar.
