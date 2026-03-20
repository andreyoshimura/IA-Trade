import unittest

import pandas as pd

from analysis.log_dedup import dedupe_signal_rows, dedupe_trade_rows


class AnalysisDedupTests(unittest.TestCase):
    def test_dedupe_trade_rows_removes_replayed_trade_rows(self):
        df = pd.DataFrame([
            {"entry_timestamp": "2026-03-16T03:30:00", "exit_timestamp": "2026-03-16T08:30:00", "type": "BUY", "entry": 1, "exit": 2, "size": 0.1, "pnl": 0.5},
            {"entry_timestamp": "2026-03-16T03:30:00", "exit_timestamp": "2026-03-16T08:30:00", "type": "BUY", "entry": 1, "exit": 2, "size": 0.1, "pnl": 0.5},
        ])
        deduped, removed = dedupe_trade_rows(df)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(removed, 1)

    def test_dedupe_signal_rows_prefers_most_informative_signal_row(self):
        df = pd.DataFrame([
            {"timestamp": "2026-03-16T03:30:00", "action": "ENTRY", "signal": "BUY", "close": 1, "atr": 2, "capital": 300, "stop": 0.9, "target": 1.2, "size": 0.1, "entry_slippage_rate": 0.001, "sentiment_score": ""},
            {"timestamp": "2026-03-16T03:30:00", "action": "ENTRY", "signal": "BUY", "close": 1, "atr": 2, "capital": 300, "stop": 0.9, "target": 1.2, "size": 0.1, "entry_slippage_rate": 0.001, "sentiment_score": 0.12},
        ])
        deduped, removed = dedupe_signal_rows(df)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(removed, 1)
        self.assertEqual(float(deduped.iloc[0]["sentiment_score"]), 0.12)


if __name__ == "__main__":
    unittest.main()
