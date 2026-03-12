import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from noodswap.cards import generation_value_multiplier
from noodswap.settings import DB_PATH, GENERATION_MAX, GENERATION_MIN


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Report generation-economy metrics from the current database snapshot and "
            "compare against a theoretical inverse-value (tau) distribution."
        )
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DB_PATH,
        help=f"Path to SQLite database (default: {DB_PATH})",
    )
    parser.add_argument(
        "--tau",
        type=float,
        default=0.95,
        help="Exponent for inverse-value target distribution: P(gen) ∝ 1 / multiplier(gen)^tau",
    )
    parser.add_argument(
        "--active-days",
        type=int,
        default=7,
        help="Window for active pullers based on players.last_pull_at (default: 7)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of plain text",
    )
    return parser.parse_args()


def _pct(value: float) -> str:
    return f"{value * 100:.4f}%"


def _inv(value: float) -> str:
    if value <= 0:
        return "n/a"
    return f"1 in {round(1.0 / value):,}"


def _query_scalar(
    conn: sqlite3.Connection, sql: str, params: tuple[object, ...] = ()
) -> float:
    row = conn.execute(sql, params).fetchone()
    if row is None:
        return 0.0
    raw = row[0]
    return float(raw) if raw is not None else 0.0


def _theoretical_distribution(tau: float) -> dict[str, float]:
    generations = list(range(GENERATION_MIN, GENERATION_MAX + 1))
    multipliers = [generation_value_multiplier(g) for g in generations]
    weights = [1.0 / (m**tau) for m in multipliers]
    total_weight = sum(weights)
    probs = [w / total_weight for w in weights]

    p1 = probs[0]
    p10 = sum(probs[:10])
    p100 = sum(probs[:100])
    p500 = sum(probs[:500])
    expected_generation = sum(g * p for g, p in zip(generations, probs, strict=True))
    expected_multiplier = sum(m * p for m, p in zip(multipliers, probs, strict=True))

    return {
        "p1": p1,
        "p10": p10,
        "p100": p100,
        "p500": p500,
        "expected_generation": expected_generation,
        "expected_multiplier": expected_multiplier,
    }


def _snapshot_metrics(conn: sqlite3.Connection, active_days: int) -> dict[str, float]:
    total_instances = _query_scalar(conn, "SELECT COUNT(*) FROM card_instances")
    count_gen_1 = _query_scalar(
        conn, "SELECT COUNT(*) FROM card_instances WHERE generation = 1"
    )
    count_gen_le_10 = _query_scalar(
        conn, "SELECT COUNT(*) FROM card_instances WHERE generation <= 10"
    )
    count_gen_le_100 = _query_scalar(
        conn, "SELECT COUNT(*) FROM card_instances WHERE generation <= 100"
    )
    count_gen_le_500 = _query_scalar(
        conn, "SELECT COUNT(*) FROM card_instances WHERE generation <= 500"
    )

    avg_generation = _query_scalar(conn, "SELECT AVG(generation) FROM card_instances")
    avg_multiplier = _query_scalar(
        conn,
        (
            "SELECT AVG(1.0 + (2 * POWER((? - generation) * 1.0 / (? - ?), 2))"
            " + (9 * POWER((? - generation) * 1.0 / (? - ?), 9))"
            " + (49 * POWER((? - generation) * 1.0 / (? - ?), 49))) "
            "FROM card_instances"
        ),
        (
            GENERATION_MAX,
            GENERATION_MAX,
            GENERATION_MIN,
            GENERATION_MAX,
            GENERATION_MAX,
            GENERATION_MIN,
            GENERATION_MAX,
            GENERATION_MAX,
            GENERATION_MIN,
        ),
    )

    cutoff = time.time() - (max(1, active_days) * 24 * 60 * 60)
    active_pullers = _query_scalar(
        conn, "SELECT COUNT(*) FROM players WHERE last_pull_at >= ?", (cutoff,)
    )

    if total_instances <= 0:
        p1 = p10 = p100 = p500 = 0.0
    else:
        p1 = count_gen_1 / total_instances
        p10 = count_gen_le_10 / total_instances
        p100 = count_gen_le_100 / total_instances
        p500 = count_gen_le_500 / total_instances

    per_1k_active_gen_1 = (
        (count_gen_1 * 1000.0 / active_pullers) if active_pullers > 0 else 0.0
    )
    per_1k_active_gen_2_10 = (
        ((count_gen_le_10 - count_gen_1) * 1000.0 / active_pullers)
        if active_pullers > 0
        else 0.0
    )
    per_1k_active_gen_11_100 = (
        ((count_gen_le_100 - count_gen_le_10) * 1000.0 / active_pullers)
        if active_pullers > 0
        else 0.0
    )

    return {
        "total_instances": total_instances,
        "active_pullers": active_pullers,
        "p1": p1,
        "p10": p10,
        "p100": p100,
        "p500": p500,
        "avg_generation": avg_generation,
        "avg_multiplier": avg_multiplier,
        "gen_1_per_1k_active": per_1k_active_gen_1,
        "gen_2_10_per_1k_active": per_1k_active_gen_2_10,
        "gen_11_100_per_1k_active": per_1k_active_gen_11_100,
    }


def _text_report(
    db_path: Path,
    tau: float,
    active_days: int,
    theo: dict[str, float],
    snap: dict[str, float],
) -> str:
    lines: list[str] = []
    lines.append("Noodswap generation economy report")
    lines.append(f"DB: {db_path}")
    lines.append(f"tau: {tau:.3f}")
    lines.append("")

    lines.append("Theoretical target (inverse-value distribution)")
    lines.append(f"- P(gen=1):    {_pct(theo['p1'])} ({_inv(theo['p1'])})")
    lines.append(f"- P(gen<=10):  {_pct(theo['p10'])} ({_inv(theo['p10'])})")
    lines.append(f"- P(gen<=100): {_pct(theo['p100'])} ({_inv(theo['p100'])})")
    lines.append(f"- P(gen<=500): {_pct(theo['p500'])} ({_inv(theo['p500'])})")
    lines.append(f"- E[generation]: {theo['expected_generation']:.2f}")
    lines.append(f"- E[multiplier]: {theo['expected_multiplier']:.4f}x")
    lines.append("")

    lines.append("Database snapshot (owned inventory only)")
    lines.append(f"- Total instances: {int(snap['total_instances']):,}")
    lines.append(f"- P(gen=1):    {_pct(snap['p1'])} ({_inv(snap['p1'])})")
    lines.append(f"- P(gen<=10):  {_pct(snap['p10'])} ({_inv(snap['p10'])})")
    lines.append(f"- P(gen<=100): {_pct(snap['p100'])} ({_inv(snap['p100'])})")
    lines.append(f"- P(gen<=500): {_pct(snap['p500'])} ({_inv(snap['p500'])})")
    lines.append(f"- AVG(generation): {snap['avg_generation']:.2f}")
    lines.append(f"- AVG(multiplier): {snap['avg_multiplier']:.4f}x")
    lines.append("")

    lines.append(
        f"Top-end supply normalization (per 1k active pullers over last {active_days}d)"
    )
    lines.append(f"- Active pullers: {int(snap['active_pullers']):,}")
    lines.append(f"- Gen 1 per 1k active: {snap['gen_1_per_1k_active']:.4f}")
    lines.append(f"- Gen 2-10 per 1k active: {snap['gen_2_10_per_1k_active']:.4f}")
    lines.append(f"- Gen 11-100 per 1k active: {snap['gen_11_100_per_1k_active']:.4f}")
    lines.append("")

    lines.append("Estimated pulls needed (theoretical)")
    lines.append(f"- First gen<=100: {_inv(theo['p100'])}")
    lines.append(f"- First gen<=10:  {_inv(theo['p10'])}")
    lines.append(f"- First gen=1:    {_inv(theo['p1'])}")
    lines.append("")

    lines.append("Notes")
    lines.append(
        "- Snapshot metrics are based on current ownership, not historical pulls."
    )
    lines.append(
        "- Burns, trades, and churn bias snapshot rarity; use as directional signals."
    )
    lines.append(
        "- Add a pull/burn/trade ledger table for true day-by-day economy telemetry."
    )

    return "\n".join(lines)


def main() -> None:
    args = _parse_args()
    db_path = args.db.expanduser().resolve()
    if args.tau < 0:
        raise ValueError("--tau must be >= 0")

    conn = sqlite3.connect(db_path)
    try:
        theo = _theoretical_distribution(args.tau)
        snap = _snapshot_metrics(conn, args.active_days)
    finally:
        conn.close()

    payload = {
        "db_path": str(db_path),
        "tau": float(args.tau),
        "active_days": int(args.active_days),
        "theoretical": theo,
        "snapshot": snap,
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    print(_text_report(db_path, args.tau, args.active_days, theo, snap))


if __name__ == "__main__":
    main()
