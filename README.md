# 破綻ねこ

破綻ねこは、Stable Diffusion などで生成した画像の破綻候補を見つけ、ローカルで素早く仕分けるための Windows 向け検品アプリです。

初期版では高度な AI 判定ではなく、画像ビューア、OK / Fix / NG / Deleted への仕分け、安全な退避、Undo、読み込みエラー・解像度違い・縦横比違い・単色画像・完全重複の簡易スキャンを実装しています。検出結果は最終判断ではなく、確認補助として扱います。

## 起動

```powershell
python -m pip install -r requirements.txt
python -m hateneko.main
```

## 主な操作

- フォルダ選択: 画像フォルダを読み込みます。
- 前へ / 次へ: 画像を移動します。
- OK / Fix / NG / Delete: 選択画像を各フォルダへ移動します。
- Undo: 直前の移動を戻します。
- スキャン開始: 表示中の一覧を簡易スキャンします。

## ショートカット

- `←` または `A`: 前の画像
- `→` または `D`: 次の画像
- `1`: OK
- `2`: Fix
- `3`: NG
- `Delete`: Deleted
- `Ctrl+Z`: Undo
- `Space`: 全体表示 / 等倍表示
- `F5`: フォルダ再読み込み

## 生成されるフォルダ

選択した画像フォルダの直下に以下を作成します。

- `_hateneko_ok`
- `_hateneko_fix`
- `_hateneko_ng`
- `_hateneko_deleted`
- `_hateneko_logs`

Delete の初期設定は完全削除ではなく `_hateneko_deleted` への退避です。設定で Windows ゴミ箱送りにも変更できますが、その場合は Undo 対象外です。

## 設定

`settings.json` に保存します。基準解像度、縦横比許容誤差、Delete の扱い、スキャン重複チェックなどを変更できます。

## ログ

仕分けとスキャンのログは、選択フォルダ内の `_hateneko_logs/action_log.jsonl` に追記します。

## 拡張

検出器は `hateneko/detectors/` 配下に疎結合で追加できます。新しい検出器は `BaseDetector` を継承し、`Issue` のリストを返します。

