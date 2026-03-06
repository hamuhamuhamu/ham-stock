#!/usr/bin/env python3
"""Check if held Japanese stocks have daily lending fee (逆日歩/品貸料率)."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.request import urlopen

SHINA_CSV_URL = "https://www.taisyaku.jp/data/shina.csv"


HEADER_ALIASES = {
    "code": "コード",
    "name": "銘柄名",
    "today_fee": "当日品貸料率（円）",
    "today_days": "当日品貸日数",
    "prev_fee": "前日品貸料率（円）",
    "market": "取引所区分",
    "loan_excess": "貸株超過株数",
    "application_date": "貸借申込日",
    "settlement_date": "決済日",
}


def normalize_code(raw: str, *, strict: bool = False) -> str | None:
    m = re.search(r"(\d{4}|\d{3}[A-Za-z])", raw or "")
    if not m:
        if strict:
            raise ValueError(f"銘柄コードを解釈できません: {raw}")
        return None
    code = m.group(1).upper()
    return code


def to_float_or_none(value: str) -> float | None:
    text = (value or "").strip()
    if not text or text in {"*****", "-", "--"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_shina_csv(csv_text: str) -> list[dict[str, str]]:
    lines = [ln for ln in csv_text.splitlines() if ln.strip()]

    # Header line starts with "貸借申込日" in current format.
    start_idx = None
    for idx, line in enumerate(lines):
        if line.startswith("貸借申込日,"):
            start_idx = idx
            break

    if start_idx is None:
        raise RuntimeError("CSVヘッダー行を検出できませんでした。フォーマット変更の可能性があります。")

    reader = csv.DictReader(lines[start_idx:])
    return [row for row in reader]


def load_targets(config_path: Path) -> dict[str, str]:
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    targets: dict[str, str] = {}

    stocks = config.get("stocks")
    if not isinstance(stocks, list) or not stocks:
        raise ValueError("configのstocksに銘柄一覧を設定してください")

    for item in stocks:
        if isinstance(item, str):
            code = normalize_code(item, strict=True)
            targets[code] = code
            continue

        if not isinstance(item, dict):
            raise ValueError(f"stocks要素は文字列またはオブジェクトにしてください: {item}")

        code = normalize_code(str(item.get("code", "")), strict=True)
        alias = str(item.get("name") or code)
        targets[code] = alias

    return targets


def fetch_csv_text(url: str) -> str:
    with urlopen(url) as resp:  # nosec B310
        raw = resp.read()

    # taisyaku.jp CSV is usually cp932.
    for encoding in ("cp932", "utf-8-sig", "utf-8"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise RuntimeError("CSVの文字コードを判定できませんでした")


def make_result(rows: list[dict[str, str]], targets: dict[str, str]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []

    for row in rows:
        code = normalize_code(row.get(HEADER_ALIASES["code"], ""))
        if code is None:
            continue
        if code not in targets:
            continue

        today_fee_raw = row.get(HEADER_ALIASES["today_fee"], "")
        today_fee = to_float_or_none(today_fee_raw)
        is_flagged = today_fee is not None and today_fee > 0

        filtered.append(
            {
                "code": code,
                "alias": targets[code],
                "name": row.get(HEADER_ALIASES["name"], ""),
                "market": row.get(HEADER_ALIASES["market"], ""),
                "application_date": row.get(HEADER_ALIASES["application_date"], ""),
                "settlement_date": row.get(HEADER_ALIASES["settlement_date"], ""),
                "loan_excess": row.get(HEADER_ALIASES["loan_excess"], ""),
                "today_fee_raw": today_fee_raw,
                "today_fee": today_fee,
                "today_days": row.get(HEADER_ALIASES["today_days"], ""),
                "prev_fee": row.get(HEADER_ALIASES["prev_fee"], ""),
                "is_flagged": is_flagged,
            }
        )

    return sorted(filtered, key=lambda x: x["code"])


def load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {"updated_at": None, "flagged_codes": []}
    return json.loads(state_path.read_text(encoding="utf-8"))


def save_state(state_path: Path, flagged_codes: list[str]) -> None:
    payload = {
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "flagged_codes": flagged_codes,
    }
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def print_report(results: list[dict[str, Any]], only_flagged: bool, targets: dict[str, str]) -> list[str]:
    flagged_codes: list[str] = []

    print("=== 品貸料率チェック結果 ===")
    for item in results:
        if only_flagged and not item["is_flagged"]:
            continue

        status = "逆日歩あり" if item["is_flagged"] else "なし"
        if item["is_flagged"]:
            flagged_codes.append(item["code"])

        fee_disp = item["today_fee_raw"] or ""
        print(
            f"[{item['code']}] {item['alias']} / {item['name']} | {status} | "
            f"当日品貸料率={fee_disp} | 日数={item['today_days']} | 市場={item['market']}"
        )

    found = {item["code"] for item in results}
    missing = sorted(set(targets.keys()) - found)
    if not results:
        print("対象銘柄がCSVに見つかりませんでした。")
    if missing:
        print("=== CSV未掲載コード ===")
        for code in missing:
            print(f"{code} ({targets[code]})")

    if only_flagged and not flagged_codes:
        print("逆日歩ありの銘柄はありません。")

    return flagged_codes


def main() -> int:
    parser = argparse.ArgumentParser(description="保有銘柄の逆日歩(品貸料率)をチェックする")
    parser.add_argument("--config", default="stocks.json", help="設定ファイル(JSON)")
    parser.add_argument("--state", default=".nippo_state.json", help="状態ファイル(JSON)")
    parser.add_argument("--only-flagged", action="store_true", help="逆日歩あり銘柄のみ表示")
    parser.add_argument("--diff", action="store_true", help="前回から新規に逆日歩ありになった銘柄のみ表示")
    args = parser.parse_args()

    config_path = Path(args.config)
    state_path = Path(args.state)

    if not config_path.exists():
        print(f"設定ファイルが見つかりません: {config_path}", file=sys.stderr)
        return 1

    targets = load_targets(config_path)
    csv_text = fetch_csv_text(SHINA_CSV_URL)
    rows = parse_shina_csv(csv_text)
    results = make_result(rows, targets)

    flagged_codes = print_report(results, only_flagged=args.only_flagged, targets=targets)

    if args.diff:
        prev = set(load_state(state_path).get("flagged_codes", []))
        current = set(flagged_codes)
        new_hits = sorted(current - prev)
        print("=== 前回差分（新規に逆日歩あり）===")
        if not new_hits:
            print("新規該当なし")
        else:
            for code in new_hits:
                print(code)

    save_state(state_path, flagged_codes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
