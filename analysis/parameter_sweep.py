"""
parameter_sweep.py

Busca de parametros com duas abordagens:
1) Grid search (com paralelizacao via multiprocessing)
2) Otimizacao bayesiana via Optuna (se instalado)
"""

import argparse
import csv
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config
from backtest.backtester import Backtester
from main import load_data, split_data
from strategy.breakout_structural import prepare_indicators


PARAM_KEYS = [
    "MIN_ADX",
    "MIN_VOLUME_FACTOR",
    "BREAKOUT_BUFFER",
    "TRADE_COOLDOWN_CANDLES",
    "BREAKOUT_LOOKBACK",
    "RR_RATIO",
]

# Dados em memoria por processo worker
WORKER_DATA = {}


def get_quick_candidates() -> List[Dict[str, float]]:
    return [
        {"MIN_ADX": 24, "MIN_VOLUME_FACTOR": 1.6, "BREAKOUT_BUFFER": 1.2, "TRADE_COOLDOWN_CANDLES": 24, "BREAKOUT_LOOKBACK": 50, "RR_RATIO": 2.5},
        {"MIN_ADX": 24, "MIN_VOLUME_FACTOR": 1.6, "BREAKOUT_BUFFER": 1.2, "TRADE_COOLDOWN_CANDLES": 24, "BREAKOUT_LOOKBACK": 50, "RR_RATIO": 2.8},
        {"MIN_ADX": 24, "MIN_VOLUME_FACTOR": 1.6, "BREAKOUT_BUFFER": 1.2, "TRADE_COOLDOWN_CANDLES": 28, "BREAKOUT_LOOKBACK": 50, "RR_RATIO": 2.8},
        {"MIN_ADX": 24, "MIN_VOLUME_FACTOR": 1.6, "BREAKOUT_BUFFER": 1.4, "TRADE_COOLDOWN_CANDLES": 24, "BREAKOUT_LOOKBACK": 50, "RR_RATIO": 2.8},
        {"MIN_ADX": 24, "MIN_VOLUME_FACTOR": 1.6, "BREAKOUT_BUFFER": 1.4, "TRADE_COOLDOWN_CANDLES": 28, "BREAKOUT_LOOKBACK": 50, "RR_RATIO": 2.8},
        {"MIN_ADX": 24, "MIN_VOLUME_FACTOR": 1.6, "BREAKOUT_BUFFER": 1.4, "TRADE_COOLDOWN_CANDLES": 28, "BREAKOUT_LOOKBACK": 60, "RR_RATIO": 2.8},
        {"MIN_ADX": 26, "MIN_VOLUME_FACTOR": 1.6, "BREAKOUT_BUFFER": 1.2, "TRADE_COOLDOWN_CANDLES": 24, "BREAKOUT_LOOKBACK": 50, "RR_RATIO": 2.5},
        {"MIN_ADX": 26, "MIN_VOLUME_FACTOR": 1.6, "BREAKOUT_BUFFER": 1.4, "TRADE_COOLDOWN_CANDLES": 24, "BREAKOUT_LOOKBACK": 50, "RR_RATIO": 2.8},
        {"MIN_ADX": 26, "MIN_VOLUME_FACTOR": 1.6, "BREAKOUT_BUFFER": 1.4, "TRADE_COOLDOWN_CANDLES": 28, "BREAKOUT_LOOKBACK": 60, "RR_RATIO": 2.8},
        {"MIN_ADX": 28, "MIN_VOLUME_FACTOR": 1.6, "BREAKOUT_BUFFER": 1.2, "TRADE_COOLDOWN_CANDLES": 24, "BREAKOUT_LOOKBACK": 50, "RR_RATIO": 2.2},
        {"MIN_ADX": 28, "MIN_VOLUME_FACTOR": 1.6, "BREAKOUT_BUFFER": 1.4, "TRADE_COOLDOWN_CANDLES": 28, "BREAKOUT_LOOKBACK": 60, "RR_RATIO": 2.8},
        {"MIN_ADX": 28, "MIN_VOLUME_FACTOR": 1.6, "BREAKOUT_BUFFER": 1.2, "TRADE_COOLDOWN_CANDLES": 28, "BREAKOUT_LOOKBACK": 60, "RR_RATIO": 2.8},
    ]


def get_balanced_candidates() -> List[Dict[str, float]]:
    candidates = []
    for adx in [24, 26, 28]:
        for volume_factor in [1.4, 1.6]:
            for buffer in [1.2, 1.4]:
                for cooldown in [24, 28]:
                    for lookback in [50, 60]:
                        for rr in [2.5, 2.8]:
                            candidates.append({
                                "MIN_ADX": adx,
                                "MIN_VOLUME_FACTOR": volume_factor,
                                "BREAKOUT_BUFFER": buffer,
                                "TRADE_COOLDOWN_CANDLES": cooldown,
                                "BREAKOUT_LOOKBACK": lookback,
                                "RR_RATIO": rr,
                            })
    return candidates


def apply_params(params: Dict[str, float]) -> None:
    for key, value in params.items():
        setattr(config, key, value)


def snapshot_params() -> Dict[str, float]:
    return {key: getattr(config, key) for key in PARAM_KEYS}


def init_worker() -> None:
    df_1h, df_15m = load_data()
    df_1h_train, df_15m_train, df_1h_test, df_15m_test = split_data(df_1h, df_15m)
    WORKER_DATA["train_raw"] = (df_1h_train.copy(), df_15m_train.copy())
    WORKER_DATA["test_raw"] = (df_1h_test.copy(), df_15m_test.copy())
    WORKER_DATA["prepared_cache"] = {}


def get_prepared_split(split_name: str, breakout_lookback: int):
    cache_key = (split_name, breakout_lookback)
    prepared_cache = WORKER_DATA["prepared_cache"]

    if cache_key in prepared_cache:
        return prepared_cache[cache_key]

    raw_1h, raw_15m = WORKER_DATA[f"{split_name}_raw"]
    original_lookback = config.BREAKOUT_LOOKBACK
    config.BREAKOUT_LOOKBACK = breakout_lookback
    try:
        prepared = prepare_indicators(raw_1h, raw_15m)
    finally:
        config.BREAKOUT_LOOKBACK = original_lookback

    prepared_cache[cache_key] = prepared
    return prepared


def evaluate_params(params: Dict[str, float]) -> Dict[str, float]:
    apply_params(params)

    start = time.time()

    breakout_lookback = int(params["BREAKOUT_LOOKBACK"])
    df_1h_train, df_15m_train = get_prepared_split("train", breakout_lookback)
    df_1h_test, df_15m_test = get_prepared_split("test", breakout_lookback)

    train = Backtester(df_1h_train, df_15m_train, prepared_data=True).run()
    test = Backtester(df_1h_test, df_15m_test, prepared_data=True).run()

    elapsed = round(time.time() - start, 2)

    return {
        **params,
        "train_final": train.get("final_capital"),
        "train_pf": train.get("profit_factor"),
        "train_dd": train.get("max_drawdown_pct"),
        "train_trades": train.get("total_trades"),
        "test_final": test.get("final_capital"),
        "test_pf": test.get("profit_factor"),
        "test_dd": test.get("max_drawdown_pct"),
        "test_trades": test.get("total_trades"),
        "elapsed_s": elapsed,
    }


def score_result(r: Dict[str, float]) -> float:
    # Score para priorizar OOS PF/retorno e penalizar DD excessivo.
    test_pf = r.get("test_pf") or 0.0
    test_final = r.get("test_final") or 0.0
    test_dd = r.get("test_dd") or -100.0
    train_pf = r.get("train_pf") or 0.0

    dd_penalty = 0.0
    if test_dd < -15:
        dd_penalty = abs(test_dd + 15) * 0.03

    return (test_pf * 100) + (train_pf * 25) + ((test_final - config.CAPITAL) * 0.2) - dd_penalty


def rank_results(results: List[Dict[str, float]]) -> List[Dict[str, float]]:
    scored = []
    for r in results:
        item = dict(r)
        item["score"] = round(score_result(r), 4)
        scored.append(item)

    return sorted(scored, key=lambda r: r["score"], reverse=True)


def maybe_save_csv(path: str, rows: List[Dict[str, float]]) -> None:
    if not path or not rows:
        return

    headers = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    print(f"CSV salvo em: {path}")


def run_grid_parallel(candidates: List[Dict[str, float]], workers: int) -> List[Dict[str, float]]:
    total = len(candidates)
    results = []

    with ProcessPoolExecutor(max_workers=workers, initializer=init_worker) as ex:
        future_map = {ex.submit(evaluate_params, params): (idx, params) for idx, params in enumerate(candidates, start=1)}

        done_count = 0
        for fut in as_completed(future_map):
            idx, _ = future_map[fut]
            row = fut.result()
            row["idx"] = idx
            done_count += 1
            results.append(row)
            print(
                f"[{done_count}/{total}] "
                f"idx={idx} test_final={row['test_final']} "
                f"test_pf={row['test_pf']} test_dd={row['test_dd']} trades={row['test_trades']}"
            )

    return results


def run_grid_sequential(candidates: List[Dict[str, float]]) -> List[Dict[str, float]]:
    init_worker()
    total = len(candidates)
    results = []

    for idx, params in enumerate(candidates, start=1):
        row = evaluate_params(params)
        row["idx"] = idx
        results.append(row)
        print(
            f"[{idx}/{total}] "
            f"test_final={row['test_final']} "
            f"test_pf={row['test_pf']} test_dd={row['test_dd']} trades={row['test_trades']}"
        )

    return results


def run_optuna(trials: int, workers: int) -> Tuple[List[Dict[str, float]], Dict[str, float]]:
    try:
        import optuna
    except ImportError as exc:
        raise RuntimeError(
            "Optuna nao encontrado no ambiente. Instale com: ./venv/bin/pip install optuna"
        ) from exc

    # Para evitar carregar o dataset por trial, mantemos por worker.
    init_worker()

    all_results = []

    def objective(trial):
        params = {
            "MIN_ADX": trial.suggest_int("MIN_ADX", 20, 32, step=2),
            "MIN_VOLUME_FACTOR": trial.suggest_float("MIN_VOLUME_FACTOR", 1.2, 1.8, step=0.1),
            "BREAKOUT_BUFFER": trial.suggest_float("BREAKOUT_BUFFER", 0.8, 1.6, step=0.1),
            "TRADE_COOLDOWN_CANDLES": trial.suggest_int("TRADE_COOLDOWN_CANDLES", 8, 36, step=4),
            "BREAKOUT_LOOKBACK": trial.suggest_int("BREAKOUT_LOOKBACK", 20, 80, step=10),
            "RR_RATIO": trial.suggest_float("RR_RATIO", 1.8, 3.2, step=0.1),
        }

        row = evaluate_params(params)
        row["idx"] = trial.number + 1
        row["score"] = round(score_result(row), 4)
        all_results.append(row)

        # Pruning simples para cenarios claramente ruins.
        trial.report(row["score"], step=0)
        if (row.get("test_pf") or 0) < 0.85 and (row.get("test_final") or 0) < config.CAPITAL * 0.95:
            raise optuna.exceptions.TrialPruned()

        return row["score"]

    sampler = optuna.samplers.TPESampler(seed=42)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.optimize(objective, n_trials=trials, n_jobs=workers)

    return all_results, study.best_params


def parse_args():
    parser = argparse.ArgumentParser(description="Busca de parametros da estrategia breakout")
    parser.add_argument("--engine", choices=["grid", "optuna"], default="grid")
    parser.add_argument("--profile", choices=["quick", "balanced"], default="quick")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--trials", type=int, default=40, help="Usado apenas em --engine optuna")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--max-candidates", type=int, default=0)
    parser.add_argument("--csv", default="")
    return parser.parse_args()


def run():
    args = parse_args()
    base_params = snapshot_params()

    if args.engine == "grid":
        candidates = get_quick_candidates() if args.profile == "quick" else get_balanced_candidates()
        if args.max_candidates > 0:
            candidates = candidates[: args.max_candidates]

        print(f"Engine: grid | Perfil: {args.profile} | Workers: {args.workers}")
        print(f"Total de combinacoes: {len(candidates)}")

        try:
            results = run_grid_parallel(candidates, workers=args.workers)
        except PermissionError:
            print("Multiprocessing indisponivel no ambiente atual; usando modo sequencial.")
            results = run_grid_sequential(candidates)
        ranked = rank_results(results)

    else:
        print(f"Engine: optuna | Trials: {args.trials} | Workers: {args.workers}")
        try:
            results, best_params = run_optuna(trials=args.trials, workers=args.workers)
        except RuntimeError as err:
            print(str(err))
            return

        ranked = rank_results(results)
        print("\nMelhores parametros (Optuna):")
        print(json.dumps(best_params, ensure_ascii=True))

    apply_params(base_params)

    print("\nTOP RESULTADOS:")
    for row in ranked[: args.top]:
        print(json.dumps(row, ensure_ascii=True))

    maybe_save_csv(args.csv, ranked)


if __name__ == "__main__":
    run()
