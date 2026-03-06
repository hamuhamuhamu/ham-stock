# 逆日歩チェック用スクリプト

## ファイル
- `check_nippo.py`: 日証金の品貸料率CSVを取得して、保有銘柄の逆日歩有無を判定
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

## 毎日実行（Windows タスクスケジューラ例）
```powershell
schtasks /Create /SC DAILY /ST 19:00 /TN "CheckNippo" /TR "powershell -NoProfile -Command \"cd C:\Users\mdown\.codex; python .\check_nippo.py --config .\stocks.json --only-flagged --diff\""
```
