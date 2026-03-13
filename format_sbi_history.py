import argparse
import csv
from pathlib import Path
from typing import Iterable


HEADER_ROW = "約定日,銘柄,銘柄コード,市場,取引,期限,預り,課税,約定数量,約定単価,手数料/諸経費等,税額,受渡日,受渡金額/決済損益"
OUTPUT_FIELDS = ["日付", "code", "株数", "株価"]
EXCLUDED_CODE = "8918"
BUY_KEYWORDS = ("買", "現引")
SELL_KEYWORDS = ("売", "現渡")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SBI証券の約定履歴CSVから買い・売り履歴を抽出して整形します。"
    )
    parser.add_argument("input_csv", type=Path, help="SBI証券の約定履歴CSV")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="整形済みCSVの出力先ディレクトリ",
    )
    return parser.parse_args()


def load_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "cp932", "utf-8"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"failed to decode {path}")


def extract_rows(path: Path) -> list[dict[str, str]]:
    text = load_text(path)
    lines = text.splitlines()
    try:
        header_index = lines.index(HEADER_ROW)
    except ValueError as exc:
        raise ValueError("約定履歴のヘッダ行が見つかりませんでした。") from exc

    table_lines = [line for line in lines[header_index:] if line.strip()]
    reader = csv.DictReader(table_lines)
    return [dict(row) for row in reader]


def classify_trade(trade_type: str) -> str | None:
    if any(keyword in trade_type for keyword in BUY_KEYWORDS):
        return "buy"
    if any(keyword in trade_type for keyword in SELL_KEYWORDS):
        return "sell"
    return None


def normalize_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "日付": row["約定日"].replace("/", "-").strip(),
        "code": row["銘柄コード"].strip().strip('"'),
        "株数": row["約定数量"].strip(),
        "株価": row["約定単価"].strip(),
    }


def split_rows(
    rows: Iterable[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    buy_rows: list[dict[str, str]] = []
    sell_rows: list[dict[str, str]] = []

    for row in rows:
        normalized = normalize_row(row)
        if not normalized["code"] or normalized["code"] == EXCLUDED_CODE:
            continue

        trade_side = classify_trade(row["取引"])
        if trade_side == "buy":
            buy_rows.append(normalized)
        elif trade_side == "sell":
            sell_rows.append(normalized)

    return buy_rows, sell_rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def print_rows(title: str, rows: list[dict[str, str]]) -> None:
    print(title)
    print("\t".join(OUTPUT_FIELDS))
    for row in rows:
        print("\t".join(row[field] for field in OUTPUT_FIELDS))
    print()


def main() -> int:
    args = parse_args()
    rows = extract_rows(args.input_csv)
    buy_rows, sell_rows = split_rows(rows)
    merged_rows = buy_rows + sell_rows

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    merged_path = output_dir / "sbi_history_formatted.csv"
    write_csv(merged_path, merged_rows)

    print_rows("買い履歴", buy_rows)
    print_rows("売り履歴", sell_rows)
    print_rows("統合履歴", merged_rows)
    print(f"統合履歴CSV: {merged_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
