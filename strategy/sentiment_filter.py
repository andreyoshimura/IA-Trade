import logging
from datetime import datetime, timedelta, timezone

import requests


class SentimentFilter:
    """
    Modulo de Inteligencia Adaptativa (Fase 9.1)
    Analisa dados externos para gerar um filtro de vies (Bias).
    """

    def __init__(self, api_key=None, language="en", lookback_days=3, max_articles=20):
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
        self.base_url = "https://www.alphavantage.co/query"
        self.language = language
        self.lookback_days = lookback_days
        self.max_articles = max_articles

    def _build_tickers(self, symbol):
        normalized = str(symbol).upper()
        aliases = {
            "BTC": ["CRYPTO:BTC", "COIN"],
            "ETH": ["CRYPTO:ETH", "CRYPTO:BTC"],
        }
        return aliases.get(normalized, [f"CRYPTO:{normalized}"])

    def _time_from(self):
        return (datetime.now(timezone.utc) - timedelta(days=self.lookback_days)).strftime("%Y%m%dT%H%M")

    def _fetch_articles(self, symbol="BTC"):
        if not self.api_key:
            self.logger.info("Sentiment API key ausente; usando score neutro.")
            return []

        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": ",".join(self._build_tickers(symbol)),
            "time_from": self._time_from(),
            "limit": self.max_articles,
            "sort": "LATEST",
            "apikey": self.api_key,
        }
        response = requests.get(self.base_url, params=params, timeout=10)
        response.raise_for_status()
        payload = response.json()
        return payload.get("feed", [])

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

    def _score_alpha_vantage_article(self, article, symbol):
        normalized = str(symbol).upper()
        for item in article.get("ticker_sentiment", []) or []:
            ticker = str(item.get("ticker", "")).upper()
            if ticker == normalized or ticker == f"CRYPTO:{normalized}":
                try:
                    return float(item.get("ticker_sentiment_score", 0.0))
                except (TypeError, ValueError):
                    pass

        try:
            return float(article.get("overall_sentiment_score", 0.0))
        except (TypeError, ValueError):
            text = " ".join(
                [
                    str(article.get("title") or ""),
                    str(article.get("summary") or ""),
                ]
            )
            return self._score_article_text(text)

    def _aggregate_article_scores(self, articles, symbol):
        if not articles:
            return 0.0

        scores = [self._score_alpha_vantage_article(article, symbol) for article in articles]
        if not scores:
            return 0.0

        average_score = sum(scores) / len(scores)
        return max(-1.0, min(1.0, average_score))

    def get_sentiment_score(self, symbol="BTC"):
        """
        Retorna um score de -1.0 a 1.0
        Usa Alpha Vantage NEWS_SENTIMENT quando configurado; fallback neutro em caso de erro.
        """
        try:
            articles = self._fetch_articles(symbol=symbol)
            return self._aggregate_article_scores(articles, symbol=symbol)
        except Exception as exc:
            self.logger.error(f"Erro ao buscar sentimento: {exc}")
            return 0.0

    def evaluate_trade(self, side, symbol="BTC", threshold=0.2):
        """
        Retorna (allowed, score) para a operacao proposta.
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
        Verifica se o sentimento atual permite a operacao.
        side: 'BUY' ou 'SELL'
        """
        allowed, _ = self.evaluate_trade(side=side, threshold=threshold)
        return allowed
