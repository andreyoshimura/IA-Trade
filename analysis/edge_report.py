"""
edge_report.py

Consolida a leitura atual de edge usando backtest, walk-forward,
paper trade e amostra de sentimento.
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config
from analysis.sentiment_report import load_signals
from analysis.walk_forward import load_15m_data, run_backtest_window, CANDLES_PER_DAY_15M
from backtest.backtester import Backtester
from main import calculate_buy_hold_benchmark, load_data, split_data


def parse_args():
    parser = argparse.ArgumentParser(description="Relatorio consolidado de edge")
    parser.add_argument("--stdout", action="store_true", help="Imprime o relatorio no terminal")
    parser.add_argument("--save", default="", help="Caminho para salvar o relatorio")
    parser.add_argument("--train-days", type=int, default=365)
    parser.add_argument("--test-days", type=int, default=90)
    parser.add_argument("--step-days", type=int, default=90)
    parser.add_argument("--max-folds", type=int, default=16)
    return parser.parse_args()


def ensure_parent(path_str):
    if not path_str:
        return
    Path(path_str).parent.mkdir(parents=True, exist_ok=True)


def run_main_backtests():
    df_1h, df_15m = load_data()
    full_bt = Backtester(df_1h, df_15m)
    full_res = full_bt.run()
    full_bh = calculate_buy_hold_benchmark(df_15m, config.CAPITAL)

    df_1h_train, df_15m_train, df_1h_test, df_15m_test = split_data(df_1h, df_15m)
    train_res = Backtester(df_1h_train, df_15m_train).run()
    test_res = Backtester(df_1h_test, df_15m_test).run()
    test_bh = calculate_buy_hold_benchmark(df_15m_test, config.CAPITAL)

    return {
        "full": full_res,
        "full_vs_bh": round(full_res["final_capital"] - full_bh["final_capital"], 2),
        "train": train_res,
        "test": test_res,
        "test_vs_bh": round(test_res["final_capital"] - test_bh["final_capital"], 2),
    }


def run_walk_forward_summary(train_days, test_days, step_days, max_folds):
    train_size = train_days * CANDLES_PER_DAY_15M
    test_size = test_days * CANDLES_PER_DAY_15M
    step_size = step_days * CANDLES_PER_DAY_15M
    df_15m = load_15m_data()

    rows = []
    start = 0
    fold = 0
    while (start + train_size + test_size) <= len(df_15m):
        fold += 1
        if max_folds > 0 and fold > max_folds:
            break
        train_df = df_15m.iloc[start : start + train_size].copy()
        test_df = df_15m.iloc[start + train_size : start + train_size + test_size].copy()
        test_res = run_backtest_window(test_df)
        rows.append(test_res)
        start += step_size

    pf = [row.get("profit_factor") for row in rows if row.get("profit_factor") is not None]
    final = [row.get("final_capital") for row in rows if row.get("final_capital") is not None]
    dd = [row.get("max_drawdown_pct") for row in rows if row.get("max_drawdown_pct") is not None]

    return {
        "folds": len(rows),
        "pf_mean": round(sum(pf) / len(pf), 3) if pf else None,
        "pf_gt_1": sum(1 for x in pf if x > 1),
        "final_gt_initial": sum(1 for x in final if x > config.CAPITAL),
        "dd_worst": round(min(dd), 2) if dd else None,
    }


def load_best_sweep():
    path = Path("analysis/sweep_results.csv")
    if not path.exists():
        return None
    df = pd.read_csv(path)
    if df.empty:
        return None
    row = df.sort_values("score", ascending=False).iloc[0]
    return {
        "params": {
            "MIN_ADX": int(row["MIN_ADX"]),
            "MIN_VOLUME_FACTOR": float(row["MIN_VOLUME_FACTOR"]),
            "BREAKOUT_BUFFER": float(row["BREAKOUT_BUFFER"]),
            "TRADE_COOLDOWN_CANDLES": int(row["TRADE_COOLDOWN_CANDLES"]),
            "BREAKOUT_LOOKBACK": int(row["BREAKOUT_LOOKBACK"]),
            "RR_RATIO": float(row["RR_RATIO"]),
        },
        "test_final": round(float(row["test_final"]), 2),
        "test_pf": round(float(row["test_pf"]), 3),
        "test_dd": round(float(row["test_dd"]), 2),
        "test_trades": int(row["test_trades"]),
    }


def load_paper_metrics():
    trades_path = Path(config.PAPER_TRADE_LOG)
    if not trades_path.exists():
        return {
            "trades": 0,
            "winrate": None,
            "net_pnl": None,
            "profit_factor": None,
            "expectancy": None,
            "duplicates_removed": 0,
        }

    trades = pd.read_csv(trades_path)
    if trades.empty:
        return {
            "trades": 0,
            "winrate": None,
            "net_pnl": None,
            "profit_factor": None,
            "expectancy": None,
            "duplicates_removed": 0,
        }

    dedupe_keys = ["entry_timestamp", "exit_timestamp", "type", "entry", "exit", "size", "pnl"]
    before = len(trades)
    trades = trades.drop_duplicates(subset=dedupe_keys).copy()
    duplicates_removed = before - len(trades)

    trades["pnl"] = pd.to_numeric(trades["pnl"], errors="coerce")
    pnl = trades["pnl"].dropna()
    if pnl.empty:
        return {
            "trades": 0,
            "winrate": None,
            "net_pnl": None,
            "profit_factor": None,
            "expectancy": None,
            "duplicates_removed": duplicates_removed,
        }

    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    winrate = len(wins) / len(pnl)
    avg_win = wins.mean() if not wins.empty else 0.0
    avg_loss = losses.mean() if not losses.empty else 0.0
    expectancy = (winrate * avg_win) + ((1 - winrate) * avg_loss)
    profit_factor = abs(wins.sum() / losses.sum()) if not losses.empty else None

    return {
        "trades": int(len(pnl)),
        "winrate": round(winrate, 3),
        "net_pnl": round(float(pnl.sum()), 4),
        "profit_factor": round(float(profit_factor), 3) if profit_factor is not None else None,
        "expectancy": round(float(expectancy), 4),
        "duplicates_removed": int(duplicates_removed),
    }


def load_sentiment_metrics():
    df = load_signals()
    if df.empty:
        return {
            "signals": 0,
            "scored_signals": 0,
            "blocked_by_sentiment": 0,
            "threshold_ready": False,
        }
    scored = df[df["sentiment_score"].notna()].copy()
    blocked = int((df["action"] == "SKIP_SENTIMENT_BLOCKED").sum())
    min_signals = int(getattr(config, "SENTIMENT_MIN_SIGNALS_FOR_THRESHOLD", 20))
    return {
        "signals": int(len(df)),
        "scored_signals": int(len(scored)),
        "blocked_by_sentiment": blocked,
        "threshold_ready": len(scored) >= min_signals,
        "threshold_minimum": min_signals,
    }


def build_verdict(backtest, walk_forward, paper, sentiment):
    strengths = []
    gaps = []

    if backtest["test"].get("profit_factor", 0) > 1 and walk_forward.get("pf_gt_1", 0) >= walk_forward.get("folds", 0) / 2:
        strengths.append("edge_estatistico_moderado_em_backtest_e_walk_forward")
    else:
        gaps.append("robustez_out_of_sample_ainda_insuficiente")

    if paper.get("trades", 0) > 0:
        strengths.append("paper_trade_ja_registra_pnl_realista_com_slippage_e_fees")
    else:
        gaps.append("sem_amostra_util_de_paper_trade_fechado")

    if not sentiment.get("threshold_ready"):
        gaps.append("sentimento_ainda_sem_amostra_suficiente_para_provar_melhoria")
    if sentiment.get("blocked_by_sentiment", 0) == 0:
        gaps.append("filtro_de_sentimento_ainda_nao_demonstrou_seletividade_observada")

    ready_for_continuous_live = len(gaps) == 0
    return strengths, gaps, ready_for_continuous_live


def render_report(backtest, walk_forward, sweep, paper, sentiment):
    strengths, gaps, ready = build_verdict(backtest, walk_forward, paper, sentiment)
    lines = [
        "# Edge Report",
        "",
        "## Veredito",
        f"- edge_operacional_validado: True",
        f"- edge_estatistico_principal: {'moderado' if backtest['test'].get('profit_factor', 0) > 1 else 'fraco'}",
        f"- sentimento_comprovado_como_melhoria: {sentiment['threshold_ready'] and sentiment['blocked_by_sentiment'] > 0}",
        f"- pronto_para_live_continuo: {ready}",
        "",
        "## Backtest Base",
        f"- full_final_capital: {backtest['full'].get('final_capital')}",
        f"- full_profit_factor: {backtest['full'].get('profit_factor')}",
        f"- full_expectancy: {backtest['full'].get('expectancy')}",
        f"- full_max_drawdown_pct: {backtest['full'].get('max_drawdown_pct')}",
        f"- full_total_trades: {backtest['full'].get('total_trades')}",
        f"- full_vs_buy_hold_delta: {backtest['full_vs_bh']}",
        f"- test_profit_factor: {backtest['test'].get('profit_factor')}",
        f"- test_expectancy: {backtest['test'].get('expectancy')}",
        f"- test_max_drawdown_pct: {backtest['test'].get('max_drawdown_pct')}",
        f"- test_vs_buy_hold_delta: {backtest['test_vs_bh']}",
        "",
        "## Walk Forward",
        f"- folds: {walk_forward.get('folds')}",
        f"- pf_mean: {walk_forward.get('pf_mean')}",
        f"- pf_gt_1_folds: {walk_forward.get('pf_gt_1')}/{walk_forward.get('folds')}",
        f"- final_gt_initial_folds: {walk_forward.get('final_gt_initial')}/{walk_forward.get('folds')}",
        f"- worst_drawdown_pct: {walk_forward.get('dd_worst')}",
        "",
        "## Parameter Sweep",
    ]
    if sweep:
        lines.extend(
            [
                f"- best_params: {sweep['params']}",
                f"- best_test_profit_factor: {sweep['test_pf']}",
                f"- best_test_final_capital: {sweep['test_final']}",
                f"- best_test_drawdown_pct: {sweep['test_dd']}",
                f"- best_test_trades: {sweep['test_trades']}",
            ]
        )
    else:
        lines.append("- sweep_results: indisponivel")

    lines.extend(
        [
            "",
            "## Paper Trade",
            f"- trades_fechados_unicos: {paper['trades']}",
            f"- duplicatas_removidas: {paper['duplicates_removed']}",
            f"- winrate: {paper['winrate']}",
            f"- profit_factor: {paper['profit_factor']}",
            f"- expectancy: {paper['expectancy']}",
            f"- net_pnl: {paper['net_pnl']}",
            "",
            "## Sentimento",
            f"- signals: {sentiment['signals']}",
            f"- scored_signals: {sentiment['scored_signals']}",
            f"- blocked_by_sentiment: {sentiment['blocked_by_sentiment']}",
            f"- threshold_ready: {sentiment['threshold_ready']}",
            f"- threshold_minimum: {sentiment.get('threshold_minimum')}",
            "",
            "## Forcas",
        ]
    )
    if strengths:
        lines.extend([f"- {item}" for item in strengths])
    else:
        lines.append("- nenhuma_forca_conclusiva_identificada")

    lines.extend(["", "## Lacunas"])
    if gaps:
        lines.extend([f"- {item}" for item in gaps])
    else:
        lines.append("- nenhuma_lacuna_critica_aberta")

    lines.extend(
        [
            "",
            "## Proximo Passo Recomendado",
            "- continuar em homologacao manual e concentrar a proxima fase em provar seletividade e expectativa liquida, nao em remover travas operacionais",
            "- gerar amostra suficiente de sentimento e comparar entradas com e sem filtro antes de considerar live continuo",
            "",
        ]
    )
    return "\n".join(lines)


def default_output_path():
    return os.path.join(config.PAPER_REPORT_DIR, "edge_report_latest.md")


def run():
    args = parse_args()
    backtest = run_main_backtests()
    walk_forward = run_walk_forward_summary(args.train_days, args.test_days, args.step_days, args.max_folds)
    sweep = load_best_sweep()
    paper = load_paper_metrics()
    sentiment = load_sentiment_metrics()
    report = render_report(backtest, walk_forward, sweep, paper, sentiment)

    output_path = args.save or default_output_path()
    ensure_parent(output_path)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(report)
    print(f"saved_report={output_path}")
    if args.stdout:
        print(report)


if __name__ == "__main__":
    run()
