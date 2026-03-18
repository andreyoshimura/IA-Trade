import logging

class SentimentFilter:
    """
    Módulo de Inteligência Adaptativa (Fase 9.1)
    Analisa dados externos para gerar um filtro de viés (Bias).
    """
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)

    def get_sentiment_score(self, symbol="BTC"):
        """
        Retorna um score de -1.0 a 1.0
        Atualmente: Placeholder para integração com NewsAPI/CryptoPanic
        """
        try:
            # TODO: Implementar request para API de notícias ou X/Twitter
            # sentiment = self._analyze_news(symbol)
            score = 0.0  # Neutro por padrão para não interferir na Fase 4
            return score
        except Exception as e:
            self.logger.error(f"Erro ao buscar sentimento: {e}")
            return 0.0

    def is_allowed_to_trade(self, side, threshold=0.2):
        """
        Verifica se o sentimento atual permite a operação.
        side: 'BUY' ou 'SELL'
        """
        score = self.get_sentiment_score()
        
        if side == 'BUY' and score < -threshold:
            self.logger.warning(f"Compra bloqueada por Sentimento Negativo: {score}")
            return False
        if side == 'SELL' and score > threshold:
            self.logger.warning(f"Venda bloqueada por Sentimento Positivo: {score}")
            return False
            
        return True

# Exemplo de uso no seu main.py ou strategy_executor.py:
# sentiment = SentimentFilter()
# if technical_signal == 'BUY' and sentiment.is_allowed_to_trade('BUY'):
#     execute_trade()
