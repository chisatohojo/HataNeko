# 破綻ねこ

破綻ねこは、Stable Diffusion などで生成した画像の破綻候補を見つけ、ローカルで素早く仕分けるための Windows 向け検品アプリです。

初期版では高度な AI 判定ではなく、画像ビューア、OK / Fix / NG / Deleted への仕分け、安全な退避、Undo、読み込みエラー・解像度違い・縦横比違い・単色画像・完全重複・近似重複・顔数の簡易スキャンを実装しています。検出結果は最終判断ではなく、確認補助として扱います。

## 起動

```powershell
python -m pip install -r requirements.txt
python -m hateneko.main
```

## exeビルド

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-build.txt
.\build_exe.ps1
```

ビルド後の実行ファイルは `dist\HataNeko\HataNeko.exe` です。配布用には `dist\HataNeko-windows.zip` を使えます。exe実行時の設定とMediaPipeモデルは、exe横の `HataNekoData` に保存されます。

## 主な操作

- フォルダ選択: 画像フォルダを読み込みます。
- 前へ / 次へ: 画像を移動します。
- OK / Fix / NG / Delete: 選択画像を各フォルダへ移動します。
- Undo: 直前の移動を戻します。
- スキャン開始: 表示中の一覧を簡易スキャンします。
- CSV出力 / JSON出力: 検品結果の一覧レポートを `_hateneko_logs` に保存します。
- 顔数チェック: OpenCV の簡易検出で、想定人数より顔候補が多い画像を要確認にします。
- 近似重複: `imagehash` の pHash で似ている画像を要確認にします。
- 姿勢/腕チェック: MediaPipe Pose で腕の極端な角度や長さ比を要確認にします。
- 手・指チェック: MediaPipe Hand Landmarker で手数、指先の密集、手首位置のずれを要確認にします。
- 高速スキャン: CPUワーカーを並列投入して、複数画像を同時に検査します。

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

高速スキャンでは `scan_worker_count` を `0` にするとCPUコア数に応じて自動設定します。MediaPipe は `mediapipe_delegate` を `GPU` に変更できますが、環境側でGPU delegateが使えない場合は検出器エラーとして表示されます。

## ログ

仕分けとスキャンのログは、選択フォルダ内の `_hateneko_logs/action_log.jsonl` に追記します。

スキャン結果は `_hateneko_logs/scan_results.json` に保存され、同じフォルダを開いたときに復元されます。

検品結果の一覧レポートは、画面下部の CSV出力 / JSON出力から `_hateneko_logs/scan_report.csv` と `_hateneko_logs/scan_report.json` に保存できます。

## 拡張

検出器は `hateneko/detectors/` 配下に疎結合で追加できます。新しい検出器は `BaseDetector` を継承し、`Issue` のリストを返します。

MediaPipe の手・姿勢チェックを有効にすると、初回スキャン時に Google の公式モデルファイルを `hateneko/assets/models/` へ自動取得します。モデルファイルは大きいため Git 管理には含めていません。
