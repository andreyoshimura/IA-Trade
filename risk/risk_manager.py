"""
risk_manager.py

Responsável pelo cálculo do tamanho da posição (position sizing).

IMPORTANTE:
- O risco deve sempre ser baseado no capital atual.
- Nunca usar capital inicial fixo.
- Isso garante adaptação automática ao drawdown e crescimento.
"""


def calculate_position(entry, stop, current_capital, risk_per_trade):
    """
    Calcula o tamanho da posição baseado em risco percentual do capital atual.

    Parâmetros:
    - entry: preço de entrada
    - stop: preço de stop loss
    - current_capital: capital atual do sistema
    - risk_per_trade: percentual de risco por trade (ex: 0.01 = 1%)

    Retorna:
    - tamanho da posição (quantidade)
    """

    # Valor em USD que estamos dispostos a arriscar neste trade
    risk_usd = current_capital * risk_per_trade

    # Distância entre entrada e stop
    stop_distance = abs(entry - stop)

    # Proteção contra divisão por zero
    if stop_distance == 0:
        return 0

    # Position size = quanto posso perder / distância até o stop
    position_size = risk_usd / stop_distance

    return position_size
