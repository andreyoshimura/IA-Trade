# IA-Trade

Sistema quantitativo de trading com foco em robustez estatistica, configurabilidade e evolucao gradual ate automacao completa.

## Estado Atual

- Fase atual: `Fase 4 inicial / pre-live operacional`
- Fase 3: `concluida tecnicamente`
- Estrategia ativa: `Breakout estrutural BTC/USDT 15m com filtro de tendencia em 1h em modo spot-first`
- Status operacional:
  - paper trade em tempo real via Binance
  - alertas via Telegram
  - logs estruturados de sinais, trades e eventos
  - relatorio diario via Telegram
  - broker spot validado com Binance
  - readiness e reconciliacao operacionais
  - envio real de entrada minima ja testado
  - automacao de saida apos fill implementada

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

- `EXCHANGE_MARKET_TYPE = "spot"`
- `ENABLE_SHORTS = False`
- `SPOT_LIVE_MIN_ENTRY_AMOUNT = 0.00008`
- `RISK_PER_TRADE = 0.003`
- `MIN_ADX = 30`
- `MIN_VOLUME_FACTOR = 1.8`
- `BREAKOUT_BUFFER = 1.4`
- `TRADE_COOLDOWN_CANDLES = 36`
- `BREAKOUT_LOOKBACK = 60`
- `RR_RATIO = 2.5`
- `FEE_RATE = 0.0004`
- `SLIPPAGE_RATE = 0.0002`
- `ENABLE_VARIABLE_SLIPPAGE = True`
- `SLIPPAGE_MIN_RATE = 0.0001`
- `SLIPPAGE_MAX_RATE = 0.0015`

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
- Status: `concluida tecnicamente`

### Fase 4 - Semi-Automacao

- Envio automatico de ordens limite
- Stop e target automaticos
- Controle de risco ativo
- Monitoramento de falhas
- Status: `em andamento`
- Sentimento de mercado em sentiment_filter.py

Base tecnica ja criada no repositorio:

- `execution/broker.py`: interface de broker + adaptador inicial para `ccxt`
- `execution/live_executor.py`: construcao de bracket orders para entrada, stop e target
- `execution/position_sync.py`: reconciliacao entre estado local e exchange
- `execution/safety_guard.py`: travas para evitar operacao insegura
- `semi_auto.py`: comando de readiness da Fase 4 sem enviar ordens por padrao

Marco atual da Fase 4:

- conta Spot conectada e validada
- reconciliacao com exchange funcionando
- ordem real minima de entrada ja testada
- entrada real ja executada e saida real ja testada
- fluxo Spot ajustado para enviar saidas apenas apos fill da entrada
- aprendizado operacional real incorporado: `0.00007 BTC` e pequeno demais para ciclo completo
- protecao Spot agora valida o minimo nocional antes de tentar enviar OCO

## Dinheiro Real

Status atual:

- ja houve teste real com dinheiro real em Spot
- o projeto ainda nao esta em live continuo
- o ciclo completo com entrada executada + protecao ativa + reconciliacao final ainda nao foi validado
- o projeto esta configurado em modo `spot-first`
- `ENABLE_LIVE_TRADING = False` em [config.py](/media/msx/SD200/VSCODE/github/IA-Trade/config.py#L62)
- `LIVE_REQUIRE_MANUAL_CONFIRMATION = True` em [config.py](/media/msx/SD200/VSCODE/github/IA-Trade/config.py#L69)

Onde configurar:

- tipo de mercado e shorts: [config.py](/media/msx/SD200/VSCODE/github/IA-Trade/config.py)
- chave principal de liberacao: [config.py](/media/msx/SD200/VSCODE/github/IA-Trade/config.py#L62)
- confirmacao manual obrigatoria: [config.py](/media/msx/SD200/VSCODE/github/IA-Trade/config.py#L69)
- limites operacionais da Fase 4: [config.py](/media/msx/SD200/VSCODE/github/IA-Trade/config.py#L70)
- tipos de ordem live e log operacional: [config.py](/media/msx/SD200/VSCODE/github/IA-Trade/config.py#L73)
- readiness operacional: [semi_auto.py](/media/msx/SD200/VSCODE/github/IA-Trade/semi_auto.py)

O projeto so deve passar para operacao real continua quando todos os pontos abaixo forem verdadeiros:

1. `ENABLE_LIVE_TRADING = True`
2. reconciliacao com exchange aprovada
3. `semi_auto.py --check-broker` sem bloqueios criticos
4. executor real de ordens com stop e target validado
5. capital minimo de entrada definido

Enquanto qualquer item acima faltar, o estado correto do projeto e `pre-live operacional`.

## Modo de Mercado

O projeto foi ajustado para funcionar com as limitacoes atuais da conta Binance, mas sem perder a possibilidade de voltar a derivativos no futuro.

Configuracao padrao:

- `EXCHANGE_MARKET_TYPE = "spot"`
- `ENABLE_SHORTS = False`

Efeito pratico:

- entradas `BUY` continuam permitidas
- novas entradas `SELL` ficam bloqueadas em modo spot
- sinais de venda passam a ser ignorados como abertura de short
- broker, data loader e executor live continuam configuraveis para voltar a `future` depois
- em live Spot, a entrada e enviada primeiro e as ordens de saida devem ser enviadas apenas depois do fill
- em live Spot, o minimo operacional seguro atual passa a ser `0.00008 BTC`

Validacao atual:

- `./venv/bin/python semi_auto.py --check-broker` respondeu com `broker_error=None`
- reconciliacao spot atual: `in_sync=True`, sem posicao aberta e sem ordens abertas

### Fase 5 - Automacao Total

- Execucao completa
- Controle automatico de drawdown
- Pausa apos sequencia de perdas
- Relatorios automaticos
- Filtro de regime adaptativo

### Fase 6 - Multi-Asset

- Validar a estrategia em multiplos ativos
- Reduzir dependencia exclusiva de BTC
- Comparar desempenho entre pares
- Identificar ativos com melhor aderencia ao modelo

Ativos candidatos:

- `BTCUSDT`
- `ETHUSDT`
- `SOLUSDT`
- `BNBUSDT`

### Fase 7 - Portfolio Allocation

- Alocar capital dinamicamente entre ativos
- Ajustar exposicao por volatilidade
- Considerar drawdown na distribuicao de risco
- Evoluir para selecao por retorno ajustado ao risco

### Fase 8 - Arbitragem Estrutural (Exploratoria)

- Estudar diferencas entre mercados e pares relacionados
- Investigar arbitragem triangular
- Mapear ineficiencias temporarias

Observacao:

- esta fase nao e prioridade enquanto o sistema direcional principal ainda esta sendo consolidado

### Fase 9 - Inteligencia Adaptativa (Melhorias de Edge)
*Esta fase adiciona camadas de dados não-estruturados e ajustes dinâmicos sem alterar a lógica core de execução.*

- **9.1 - Analise de Sentimento (NLP Engine):** - Integracao com APIs de noticias (NewsAPI/CryptoPanic) e redes sociais.
    - Implementacao de um `Sentiment Score` como filtro de confirmacao (ex: evitar compras em momentos de panico mediatico extremo).
- **9.2 - Autocorrecao de Algoritmo (Self-Healing):**
    - Monitoramento de *Model Drift* em tempo real (degradacao da performance vs backtest).
    - Ajuste automatico de parametros baseado na volatilidade e performance recente.

### Fase 10 - Expansao de Inteligencia
- **Deep Reinforcement Learning (RL):** Agentes que aprendem a otimizar o tamanho da posição e timing de saída.
- **Dados On-chain:** Filtros baseados em fluxo de baleias e reservas em exchanges.

## Benchmarking

## Resultado Validado

### Backtest Principal

- Backtest completo: `final_capital 313.59`, `profit_factor 1.171`, `max_drawdown -7.47%`, `110 trades`
- Treino 70%: `final_capital 305.04`, `profit_factor 1.079`, `max_drawdown -7.06%`, `85 trades`
- Teste 30%: `final_capital 305.01`, `profit_factor 1.245`, `max_drawdown -1.36%`, `30 trades`

### Monte Carlo Bootstrap (Teste 30%)

- `mean_final_capital 304.91`
- `worst_final_capital 280.32`
- `best_final_capital 334.42`
- `mean_max_drawdown_pct -2.40%`
- `worst_drawdown_pct -7.28%`

Leitura pratica:

- agora o Monte Carlo usa bootstrap com reposicao sobre retornos por trade
- a distribuicao terminal deixou de ser fixa e passou a refletir risco de sequencia
- o modelo agora inclui slippage variavel por ATR, breakout e excesso de volume
- o projeto agora roda em `spot-first`, sem abertura de novos shorts
- o edge ficou mais estreito, mas a leitura ficou mais honesta para fase de paper trade

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

### Sweep de Parametros

Resultado rapido (`quick`, 12 combinacoes):

- melhor combinacao: `MIN_ADX 28`, `MIN_VOLUME_FACTOR 1.6`, `BREAKOUT_BUFFER 1.4`, `TRADE_COOLDOWN_CANDLES 28`, `BREAKOUT_LOOKBACK 60`, `RR_RATIO 2.8`
- `test_final 320.89`
- `test_pf 1.562`
- `test_dd -2.10%`
- `58 trades`

Resultado amplo (`balanced`, 96 combinacoes):

- melhor combinacao: `MIN_ADX 28`, `MIN_VOLUME_FACTOR 1.6`, `BREAKOUT_BUFFER 1.4`, `TRADE_COOLDOWN_CANDLES 28`, `BREAKOUT_LOOKBACK 60`, `RR_RATIO 2.8`
- `train_final 322.79`
- `train_pf 1.193`
- `test_final 320.89`
- `test_pf 1.562`
- `test_dd -2.10%`
- `58 trades`
- ranking completo salvo em `analysis/sweep_results.csv`

Leitura pratica:

- ha edge estatistico moderado
- drawdown esta controlado
- a estrategia ainda nao supera buy and hold em retorno absoluto no agregado
- a fase atual serve para validar execucao ao vivo e qualidade dos sinais

### Desempenho das Rotinas

Tempos medidos localmente apos otimizacoes no motor:

- `main.py`: `0m05.88s`
- `analysis/walk_forward.py`: `0m09.94s`
- `analysis/parameter_sweep.py --profile quick`: `0m26.68s` para `12` combinacoes
- `analysis/parameter_sweep.py --profile balanced`: `3m26.99s` para `96` combinacoes
- `paper_trade.py --source csv --once --reset-state`: `0m02.78s`
- `analysis/paper_journal.py --period daily --stdout`: `0m00.85s`

Impacto pratico:

- o backtest principal caiu de cerca de `1m45s` para menos de `6s`
- o walk-forward caiu de cerca de `3m24s` para menos de `10s`
- o sweep caiu de cerca de `49s` por combinacao para aproximadamente `2s` por combinacao

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

Readiness check da Fase 4:

```bash
./venv/bin/python semi_auto.py
./venv/bin/python semi_auto.py --check-broker
```

Envio real de bracket order:

```bash
./venv/bin/python semi_auto.py --check-broker --place-bracket --side BUY --size 0.001 --entry-price 100000 --stop-price 99000 --target-price 102000 --confirm-live
```

Fluxo real em Spot:

- o comando envia apenas a ordem de entrada
- stop e target ficam registrados como `pending exits`
- as ordens de saida devem ser enviadas somente apos a entrada estar executada
- o arquivo `logs/live_state.json` guarda o estado da entrada live e das protecoes pendentes

Sincronizacao apos fill em Spot:

```bash
./venv/bin/python semi_auto.py --check-broker --sync-live
```

Comportamento:

- se a entrada ainda estiver aberta, o comando apenas registra que o fill ainda nao ocorreu
- se a entrada estiver executada, o comando envia `stop` e `target`
- se as saidas ja tiverem sido enviadas, o comando nao duplica ordens

Aprendizado do teste real:

- uma entrada de `0.00007 BTC` conseguiu executar
- uma saida real tambem foi executada para limpar a posicao de teste
- mas ficou pequena demais para completar a protecao/saida com folga por causa de taxa e filtros de notional da Binance
- por isso o minimo operacional recomendado para os proximos testes passou a ser `0.00008 BTC`
- se a quantidade liquida apos taxa e arredondamento cair abaixo do minimo nocional, o bot agora falha explicitamente em vez de insistir com a exchange

Interpretacao:

- ja foi provado que a conta consegue executar ordens reais
- se `safety_allowed=False`, nao e momento de operar continuamente com dinheiro real
- se houver `broker_state_desync`, a operacao deve continuar bloqueada
- live continuo so deve ser considerado quando os bloqueios de seguranca forem removidos de forma consciente
- toda tentativa de envio real fica registrada em `logs/live_orders.jsonl`

Arquivos gerados em `logs/`:

- `paper_state.json`: estado persistido do runner
- `paper_signals.csv`: entradas e sinais ignorados, com `entry_slippage_rate`
- `paper_trades.csv`: trades fechados com PnL, slippage efetivo e fees
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
- `0 22 * * * /media/msx/SD200/VSCODE/github/IA-Trade/scripts/send_daily_report.sh`

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
./venv/bin/python analysis/parameter_sweep.py --engine grid --profile quick --workers 1 --top 5
```

Grid amplo:

```bash
./venv/bin/python analysis/parameter_sweep.py --engine grid --profile balanced --workers 1 --top 10 --csv analysis/sweep_results.csv
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

### Validacao Local Recente

Rotinas executadas com sucesso em `2026-03-12`:

- `./venv/bin/python -m py_compile main.py analysis/monte_carlo.py analysis/parameter_sweep.py backtest/backtester.py`
- `./venv/bin/python main.py`
- `./venv/bin/python analysis/walk_forward.py`
- `./venv/bin/python analysis/parameter_sweep.py --engine grid --profile quick --workers 1 --top 5`
- `./venv/bin/python analysis/parameter_sweep.py --engine grid --profile balanced --workers 1 --top 10 --csv analysis/sweep_results.csv`
- `./venv/bin/python paper_trade.py --source csv --once --reset-state`
- `./venv/bin/python analysis/paper_journal.py --period daily --date 2026-03-11 --stdout`

## Proximos Passos

1. Validar um ciclo Spot completo com entrada executada, protecao ativa e reconciliacao final sem divergencia.
2. Confirmar o formato de saida protegida aceito pela Binance Spot para o tamanho operacional atual.
3. Repetir o teste live com `0.00008 BTC` ou maior, mantendo confirmacao manual.
4. So depois disso avaliar a liberacao controlada de operacao real continua.

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

## Metadados da Estrategia

- Versao da estrategia: `v3`
- Ativo principal: `BTCUSDT`
- Timeframe de execucao: `15m`
- Filtro de tendencia: `1h`
- Fonte de dados: OHLCV historico da Binance
- Janela de dados testada como referencia: `2022-2025`

## Benchmark e Interpretacao

O benchmark usado no projeto e buy and hold do ativo no mesmo periodo do backtest.

Leitura correta:

- o benchmark contextualiza retorno absoluto
- a estrategia busca retorno mais estavel e drawdown menor
- o objetivo nao e necessariamente vencer buy and hold em bull markets extremos
- o foco e disciplina, controle de risco e consistencia operacional

## Reprodutibilidade

Para reproduzir os resultados:

1. Usar dados OHLCV do mesmo periodo.
2. Manter os mesmos parametros da estrategia.
3. Executar o backtest no mesmo timeframe.
4. Comparar pelo menos `winrate`, `expectancy`, `profit_factor` e `max_drawdown`.

Isso permite auditoria tecnica e comparacao consistente entre versoes.

## Slippage Variavel

O projeto agora usa um modelo de slippage variavel para tornar o backtest e o paper trade menos otimistas.

Componentes do modelo:

- slippage base por lado
- ajuste por `ATR / preco`
- ajuste por distancia do breakout
- ajuste por excesso de volume no candle
- limites minimo e maximo para evitar valores irreais

Objetivo atual:

- aproximar melhor os custos de execucao em rompimentos
- medir degradacao real do edge quando o mercado acelera
- gerar logs suficientes para calibracao futura com dados observados

Proximo passo de calibracao:

1. Coletar uma amostra de trades do paper trade.
2. Comparar sinal, candle de disparo e contexto de volatilidade.
3. Revisar pesos de ATR, breakout e volume.
4. Reexecutar `main.py`, `walk_forward.py` e `parameter_sweep.py` com os pesos ajustados.
