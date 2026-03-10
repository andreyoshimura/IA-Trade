# IA-Trade

Sistema quantitativo de trading com foco em robustez estatistica, configurabilidade e evolucao gradual ate automacao completa.

## Estado Atual

- Fase atual: `Fase 3 - Paper Trade`
- Estrategia ativa: `Breakout estrutural BTC/USDT 15m com filtro de tendencia em 1h`
- Status operacional:
  - paper trade em tempo real via Binance
  - alertas via Telegram
  - logs estruturados de sinais, trades e eventos
  - relatorio diario via Telegram

## Objetivo Principal

Construir um sistema automatizado, adaptativo e validado estatisticamente, capaz de operar de forma disciplinada em diferentes regimes de mercado.

Principios:

1. Nunca automatizar estrategia sem edge comprovado.
2. Nunca otimizar sistema negativo.
3. Primeiro validar estatistica, depois sofisticar.
4. Complexidade so entra quando ha base solida.
5. Sobrevivencia vem antes de maximizacao de retorno.

## Estrategia Atual

Modelo implementado: `Breakout Estrutural com Filtro de Tendencia`

- Timeframe principal: `15m`
- Filtro macro: `1h`
- Filtro de tendencia: `EMA 200`
- Filtro de regime: `ADX`
- Filtro de expansao: `ATR`
- Confirmacao: buffer de breakout + volume
- Gestao: stop por ATR, target por `RR_RATIO`, cooldown entre trades

Logica resumida:

1. Detecta tendencia e regime no `1h`.
2. Busca rompimento estrutural no `15m`.
3. Exige expansao de volatilidade e confirmacao de volume.
4. Simula entrada, stop e target com custos operacionais.

## Configuracao Atual

- `RISK_PER_TRADE = 0.003`
- `MIN_ADX = 30`
- `MIN_VOLUME_FACTOR = 1.8`
- `BREAKOUT_BUFFER = 1.4`
- `TRADE_COOLDOWN_CANDLES = 36`
- `BREAKOUT_LOOKBACK = 60`
- `RR_RATIO = 2.5`
- `FEE_RATE = 0.0004`
- `SLIPPAGE_RATE = 0.0002`

## Roadmap

### Fase 1 - Validacao Tecnica

- Backtester implementado
- Estrategia inicial descartada
- Metricas estatisticas funcionando
- Estrategia breakout validada

### Fase 2 - Robustez Estatistica

- Historico com mais de 2 anos
- Walk-forward
- Analise de estabilidade de parametros
- Monte Carlo basico

### Fase 3 - Paper Trade

- Bot em tempo real
- Alertas via Telegram
- Registro estruturado
- Diario automatico

### Fase 4 - Semi-Automacao

- Envio automatico de ordens limite
- Stop e target automaticos
- Controle de risco ativo
- Monitoramento de falhas

### Fase 5 - Automacao Total

- Execucao completa
- Controle automatico de drawdown
- Pausa apos sequencia de perdas
- Relatorios automaticos
- Filtro de regime adaptativo

## Resultado Validado

### Backtest Principal

- Backtest completo: `final_capital 343.57`, `profit_factor 1.342`, `max_drawdown -7.45%`, `186 trades`
- Treino 70%: `final_capital 321.19`, `profit_factor 1.210`, `max_drawdown -6.12%`, `142 trades`
- Teste 30%: `final_capital 318.62`, `profit_factor 1.569`, `max_drawdown -1.83%`, `54 trades`

### Walk-Forward 365/90/90

- Folds: `16`
- `test_pf_mean 1.436`
- `test_pf_median 1.346`
- Folds com `test_pf > 1`: `9/16`
- `test_final_mean 300.99`
- `test_final_median 302.17`
- Folds com `final_capital > 300`: `9/16`
- `test_dd_mean -1.55%`
- Pior fold: `-3.72%`

Leitura pratica:

- ha edge estatistico moderado
- drawdown esta controlado
- a estrategia ainda nao supera buy and hold em retorno absoluto no agregado
- a fase atual serve para validar execucao ao vivo e qualidade dos sinais

## Operacao Atual

### Paper Trade

Teste local com CSV:

```bash
./venv/bin/python paper_trade.py --source csv --once --reset-state
```

Execucao continua usando exchange:

```bash
./venv/bin/python paper_trade.py --source exchange
```

Arquivos gerados em `logs/`:

- `paper_state.json`: estado persistido do runner
- `paper_signals.csv`: entradas e sinais ignorados
- `paper_trades.csv`: trades fechados com PnL
- `paper_events.jsonl`: eventos operacionais
- `reports/`: relatorios diarios e semanais

Observacoes:

- o runner nunca envia ordens reais
- entradas e saidas sao simuladas com custos
- notificacoes dependem de `ENABLE_NOTIFICATIONS = True`

### Relatorio Diario

Gerar localmente:

```bash
./venv/bin/python analysis/paper_journal.py --period daily --stdout
```

Enviar para Telegram:

```bash
./venv/bin/python analysis/paper_journal.py --period daily --send-telegram
```

Relatorio semanal:

```bash
./venv/bin/python analysis/paper_journal.py --period weekly --stdout
```

## Automacao

Scripts:

- `scripts/run_paper_trade.sh`
- `scripts/send_daily_report.sh`

Cron configurado:

- `@reboot /media/msx/SD200/VSCODE/github/IA-Trade/scripts/run_paper_trade.sh`
- `55 23 * * * /media/msx/SD200/VSCODE/github/IA-Trade/scripts/send_daily_report.sh`

## Requisitos de Ambiente

No `.env`:

- `API_KEY`
- `API_SECRET`
- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`

Ativacao:

```bash
source venv/bin/activate
```

## Analise e Pesquisa

### Sweep de Parametros

Grid rapido:

```bash
./venv/bin/python analysis/parameter_sweep.py --engine grid --profile quick --workers 4 --top 5
```

Grid amplo:

```bash
./venv/bin/python analysis/parameter_sweep.py --engine grid --profile balanced --workers 8 --top 10 --csv analysis/sweep_results.csv
```

Optuna:

```bash
./venv/bin/python analysis/parameter_sweep.py --engine optuna --trials 40 --workers 2 --top 10 --csv analysis/optuna_results.csv
```

### Walk-Forward

Execucao padrao:

```bash
./venv/bin/python analysis/walk_forward.py --train-days 365 --test-days 90 --step-days 90
```

Execucao rapida:

```bash
./venv/bin/python analysis/walk_forward.py --train-days 365 --test-days 90 --step-days 90 --max-folds 3
```

## Proximos Passos

1. Observar 24-72h de paper trade sem alterar a estrategia.
2. Validar se sinais, horarios e trades ao vivo fazem sentido.
3. Comparar frequencia e comportamento real com o backtest.
4. Revisar qualidade por regime antes de avancar para semi-automacao.

## Objetivo Final

Construir um sistema quantitativo consistente com:

- expectancy positiva
- drawdown controlado
- gestao de risco disciplinada
- adaptacao a regime de mercado
- evolucao para autonomia real

Sem promessas irreais.
Sem alavancagem irresponsavel.
Sem improviso.
