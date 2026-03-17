from dotenv import load_dotenv
import os

load_dotenv()

# ===============================
# CREDENCIAIS
# ===============================

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# ===============================
# CONFIGURACOES GERAIS
# ===============================

SYMBOL = "BTC/USDT"
CAPITAL = 300
RISK_PER_TRADE = 0.003


# ===============================
# DADOS BACKTEST
# ===============================

DATA_PATH = "data/BTCUSDT_15m.csv"
TIMEFRAME = "15m"


# ===============================
# PARAMETROS ESTRATEGIA BREAKOUT
# ===============================

# Janela do breakout maior para reduzir ruído
BREAKOUT_LOOKBACK = 60
EMA_PERIOD = 200
ATR_PERIOD = 14
ATR_MULTIPLIER = 1.5
RR_RATIO = 2.5
VOLUME_LOOKBACK = 20
MIN_ADX = 30
MIN_VOLUME_FACTOR = 1.8
TRADE_COOLDOWN_CANDLES = 36

# Buffer adicional para confirmar rompimento (multiplicador de ATR)
BREAKOUT_BUFFER = 1.4

# ===============================
# FUTURO (PREPARACAO)
# ===============================

USE_MULTI_TIMEFRAME = False
HIGHER_TIMEFRAME = "1h"
HIGHER_TIMEFRAME_EMA = 200

ENABLE_ML_FILTER = False
ENABLE_MARKET_HEAT = False

ENABLE_LIVE_TRADING = False
ENABLE_NOTIFICATIONS = True

# ===============================
# PAPER TRADE
# ===============================

PAPER_TRADE_CAPITAL = CAPITAL
PAPER_POLL_INTERVAL_SECONDS = 30
PAPER_OHLCV_LIMIT = 500
PAPER_LOG_DIR = "logs"
PAPER_STATE_FILE = "logs/paper_state.json"
PAPER_SIGNAL_LOG = "logs/paper_signals.csv"
PAPER_TRADE_LOG = "logs/paper_trades.csv"
PAPER_EVENT_LOG = "logs/paper_events.jsonl"
PAPER_REPORT_DIR = "logs/reports"

# ===============================
# FILTRO DE EXPANSAO DE VOLATILIDADE
# ===============================

ATR_EXPANSION_FILTER = True
ATR_EXPANSION_LOOKBACK = 50
ATR_EXPANSION_FACTOR = 1.2

# ===============================
# CUSTOS OPERACIONAIS BACKTEST
# ===============================

# Taxa por lado (entrada ou saída). Ex.: 0.0004 = 0.04%
FEE_RATE = 0.0004

# Slippage base por lado aplicado de forma adversa na execução.
# Ex.: 0.0002 = 0.02%
SLIPPAGE_RATE = 0.0002

# Modelo de slippage variável.
# Ajusta o slippage com base em volatilidade (ATR), distância do breakout
# e excesso de volume no candle de execução.
ENABLE_VARIABLE_SLIPPAGE = True
SLIPPAGE_MIN_RATE = 0.0001
SLIPPAGE_MAX_RATE = 0.0015
SLIPPAGE_ATR_WEIGHT = 0.02
SLIPPAGE_BREAKOUT_WEIGHT = 0.03
SLIPPAGE_VOLUME_WEIGHT = 0.00005
