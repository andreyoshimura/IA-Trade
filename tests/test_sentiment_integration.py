import unittest
from unittest.mock import patch

import pandas as pd

import config
from paper_trade import PaperTradeRuntime, build_sentiment_filter, evaluate_sentiment_trade, process_new_candles
from strategy.sentiment_filter import SentimentFilter


class FakeSentimentFilter:
    def __init__(self, allowed, score):
        self.allowed = allowed
        self.score = score

    def evaluate_trade(self, side, symbol="BTC", threshold=0.2):
        return self.allowed, self.score


class SentimentIntegrationTests(unittest.TestCase):
    def test_sentiment_filter_returns_neutral_without_api_key(self):
        sentiment_filter = SentimentFilter(api_key=None)

        score = sentiment_filter.get_sentiment_score("BTC")

        self.assertEqual(score, 0.0)

    def test_sentiment_filter_scores_positive_articles(self):
        sentiment_filter = SentimentFilter(api_key="key", max_articles=5)
        fake_articles = {
            "feed": [
                {"title": "Bitcoin rally", "summary": "Bullish adoption growth", "overall_sentiment_score": 0.6},
                {"title": "BTC surge", "summary": "gain gain", "overall_sentiment_score": 0.4},
            ]
        }

        with patch("strategy.sentiment_filter.requests.get") as get_mock:
            get_mock.return_value.json.return_value = fake_articles
            get_mock.return_value.raise_for_status.return_value = None
            score = sentiment_filter.get_sentiment_score("BTC")

        self.assertGreater(score, 0.0)

    def test_sentiment_filter_scores_negative_articles(self):
        sentiment_filter = SentimentFilter(api_key="key", max_articles=5)
        fake_articles = {
            "feed": [
                {"title": "Bitcoin crash", "summary": "bearish selloff", "overall_sentiment_score": -0.7},
            ]
        }

        with patch("strategy.sentiment_filter.requests.get") as get_mock:
            get_mock.return_value.json.return_value = fake_articles
            get_mock.return_value.raise_for_status.return_value = None
            score = sentiment_filter.get_sentiment_score("BTC")

        self.assertLess(score, 0.0)

    def test_build_sentiment_filter_returns_none_when_disabled(self):
        with patch.object(config, "ENABLE_SENTIMENT_FILTER", False):
            self.assertIsNone(build_sentiment_filter())

    def test_build_sentiment_filter_uses_project_config(self):
        with patch.object(config, "ENABLE_SENTIMENT_FILTER", True), \
            patch.object(config, "SENTIMENT_API_KEY", "abc"), \
            patch.object(config, "SENTIMENT_NEWS_LANGUAGE", "en"), \
            patch.object(config, "SENTIMENT_LOOKBACK_DAYS", 5), \
            patch.object(config, "SENTIMENT_MAX_ARTICLES", 12):
            sentiment_filter = build_sentiment_filter()

        self.assertIsInstance(sentiment_filter, SentimentFilter)
        self.assertEqual(sentiment_filter.api_key, "abc")
        self.assertEqual(sentiment_filter.lookback_days, 5)
        self.assertEqual(sentiment_filter.max_articles, 12)
        self.assertEqual(sentiment_filter.base_url, "https://www.alphavantage.co/query")

    def test_evaluate_sentiment_trade_defaults_to_allowed_without_filter(self):
        allowed, score = evaluate_sentiment_trade(None, "BUY")

        self.assertTrue(allowed)
        self.assertIsNone(score)

    def test_process_new_candles_skips_entry_when_sentiment_blocks_trade(self):
        runtime = PaperTradeRuntime(capital=config.PAPER_TRADE_CAPITAL)
        candle_timestamp = pd.Timestamp("2026-03-18T10:15:00")
        df_15m = pd.DataFrame(
            [
                {
                    "timestamp": candle_timestamp,
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.0,
                    "volume": 10.0,
                    "atr": 1.0,
                }
            ]
        )
        df_1h = pd.DataFrame([{"timestamp": candle_timestamp.floor("1h")}])
        sentiment_filter = FakeSentimentFilter(allowed=False, score=-0.8)

        with patch("paper_trade.check_signal", return_value="BUY"), \
            patch("paper_trade.supports_signal", return_value=True), \
            patch("paper_trade.candle_cooldown_done", return_value=True), \
            patch("paper_trade.manage_position"), \
            patch("paper_trade.open_position") as open_position_mock, \
            patch("paper_trade.append_csv") as append_csv_mock, \
            patch("paper_trade.log_event") as log_event_mock:
            processed = process_new_candles(runtime, df_1h, df_15m, sentiment_filter=sentiment_filter)

        self.assertEqual(processed, 1)
        open_position_mock.assert_not_called()
        self.assertEqual(runtime.position, None)
        logged_row = append_csv_mock.call_args.args[1]
        self.assertEqual(logged_row["action"], "SKIP_SENTIMENT_BLOCKED")
        self.assertEqual(logged_row["sentiment_score"], -0.8)
        log_event_mock.assert_called_once()

    def test_process_new_candles_opens_position_when_sentiment_allows_trade(self):
        runtime = PaperTradeRuntime(capital=config.PAPER_TRADE_CAPITAL)
        candle_timestamp = pd.Timestamp("2026-03-18T10:15:00")
        df_15m = pd.DataFrame(
            [
                {
                    "timestamp": candle_timestamp,
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.0,
                    "volume": 10.0,
                    "atr": 1.0,
                }
            ]
        )
        df_1h = pd.DataFrame([{"timestamp": candle_timestamp.floor("1h")}])
        sentiment_filter = FakeSentimentFilter(allowed=True, score=0.1)

        with patch("paper_trade.check_signal", return_value="BUY"), \
            patch("paper_trade.supports_signal", return_value=True), \
            patch("paper_trade.candle_cooldown_done", return_value=True), \
            patch("paper_trade.manage_position"), \
            patch("paper_trade.open_position") as open_position_mock:
            processed = process_new_candles(runtime, df_1h, df_15m, sentiment_filter=sentiment_filter)

        self.assertEqual(processed, 1)
        open_position_mock.assert_called_once()
        self.assertEqual(open_position_mock.call_args.kwargs["sentiment_score"], 0.1)


if __name__ == "__main__":
    unittest.main()
