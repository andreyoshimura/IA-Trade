from config import CAPITAL, RISK_PER_TRADE

def calculate_position(entry, stop):
    risk_usd = CAPITAL * RISK_PER_TRADE
    stop_distance = abs(entry - stop)
    position_size = risk_usd / stop_distance
    return position_size
