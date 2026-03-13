# 逆日歩チェック用スクリプト

## ファイル
- `check_nippo.py`: 日証金の品貸料率CSVを取得して、保有銘柄の逆日歩有無を判定
- `format_sbi_history.py`: SBI証券の約定履歴CSVから買い/売り履歴を抽出して整形
- `stocks.sample.json`: 設定ファイルサンプル

## 使い方
1. `stocks.sample.json` をコピーして `stocks.json` を作成
2. 保有銘柄コードを設定
3. 実行

```powershell
python .\check_nippo.py --config .\stocks.json --only-flagged --diff
```

## 設定例
```json
{
  "stocks": [
    {"code": "7203", "name": "トヨタ"},
    "8306",
    "9984.T"
  ]
}
```

## 補足
- 判定元は `https://www.taisyaku.jp/data/shina.csv`（日証金公式）
- `--diff` を付けると前回実行時から新規に逆日歩ありになったコードだけを追加表示
- 実行後に `.nippo_state.json` を更新

## SBI証券CSV整形
```powershell
python .\format_sbi_history.py C:\Users\mdown\Downloads\SaveFile_000001_000334.csv
```

- 買い履歴・売り履歴・統合履歴をそれぞれ `日付 / code / 株数 / 株価` で標準出力
- `sbi_history_formatted.csv` を出力
- `8918` の売買履歴は除外
- 今後このプロジェクト内でCSVを渡されたら、このスクリプトを実行して結果を表示する

## 毎日実行（Windows タスクスケジューラ例）
```powershell
schtasks /Create /SC DAILY /ST 19:00 /TN "CheckNippo" /TR "powershell -NoProfile -Command \"cd C:\Users\mdown\.codex; python .\check_nippo.py --config .\stocks.json --only-flagged --diff\""
```
