import logging
from datetime import datetime, timedelta, timezone

import requests


class SentimentFilter:
    """
    Módulo de Inteligência Adaptativa (Fase 9.1)
    Analisa dados externos para gerar um filtro de viés (Bias).
    """
    def __init__(self, api_key=None, language="en", lookback_days=3, max_articles=20):
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
        self.base_url = "https://newsapi.org/v2/everything"
        self.language = language
        self.lookback_days = lookback_days
        self.max_articles = max_articles

    def _build_query(self, symbol):
        normalized = str(symbol).upper()
        aliases = {
            "BTC": ["Bitcoin", "BTC", "crypto market"],
            "ETH": ["Ethereum", "ETH", "crypto market"],
        }
        terms = aliases.get(normalized, [normalized, "crypto market"])
        return " OR ".join(terms)

    def _fetch_articles(self, symbol="BTC"):
        if not self.api_key:
            self.logger.info("Sentiment API key ausente; usando score neutro.")
            return []

        from_date = (datetime.now(timezone.utc) - timedelta(days=self.lookback_days)).date().isoformat()
        params = {
            "q": self._build_query(symbol),
            "language": self.language,
            "sortBy": "publishedAt",
            "pageSize": self.max_articles,
            "from": from_date,
        }
        headers = {"X-Api-Key": self.api_key}
        response = requests.get(self.base_url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        payload = response.json()
        return payload.get("articles", [])

    def _score_article_text(self, text):
        content = str(text or "").lower()
        if not content.strip():
            return 0.0

        positive_terms = (
            "surge",
            "rally",
            "bullish",
            "gain",
            "breakout",
            "adoption",
            "approval",
            "growth",
        )
        negative_terms = (
            "crash",
            "bearish",
            "loss",
            "drop",
            "hack",
            "ban",
            "fraud",
            "selloff",
        )

        score = 0.0
        for term in positive_terms:
            if term in content:
                score += 1.0
        for term in negative_terms:
            if term in content:
                score -= 1.0
        return score

    def _aggregate_article_scores(self, articles):
        if not articles:
            return 0.0

        scores = []
        for article in articles:
            text = " ".join(
                [
                    str(article.get("title") or ""),
                    str(article.get("description") or ""),
                    str(article.get("content") or ""),
                ]
            )
            scores.append(self._score_article_text(text))

        if not scores:
            return 0.0

        max_abs_score = max(abs(score) for score in scores) or 1.0
        normalized_average = sum(scores) / len(scores)
        return max(-1.0, min(1.0, normalized_average / max_abs_score))

    def get_sentiment_score(self, symbol="BTC"):
        """
        Retorna um score de -1.0 a 1.0
        Usa NewsAPI quando configurado; fallback neutro em caso de erro.
        """
        try:
            articles = self._fetch_articles(symbol=symbol)
            return self._aggregate_article_scores(articles)
        except Exception as e:
            self.logger.error(f"Erro ao buscar sentimento: {e}")
            return 0.0

    def evaluate_trade(self, side, symbol="BTC", threshold=0.2):
        """
        Retorna (allowed, score) para a operação proposta.
        """
        score = self.get_sentiment_score(symbol=symbol)

        if side == "BUY" and score < -threshold:
            self.logger.warning(f"Compra bloqueada por Sentimento Negativo: {score}")
            return False, score
        if side == "SELL" and score > threshold:
            self.logger.warning(f"Venda bloqueada por Sentimento Positivo: {score}")
            return False, score

        return True, score

    def is_allowed_to_trade(self, side, threshold=0.2):
        """
        Verifica se o sentimento atual permite a operação.
        side: 'BUY' ou 'SELL'
        """
        allowed, _ = self.evaluate_trade(side=side, threshold=threshold)
        return allowed

# Exemplo de uso no seu main.py ou strategy_executor.py:
# sentiment = SentimentFilter()
# if technical_signal == 'BUY' and sentiment.is_allowed_to_trade('BUY'):
#     execute_trade()
