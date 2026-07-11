# 北海道家族旅行ガイド

2026年7月31日から8月12日までの北海道家族旅行を、書店の旅行ガイドブック風PowerPointとして管理するリポジトリです。

## 成果物

- `output/hokkaido-family-travel-guide.pptx`
  - 16:9横長のPowerPoint
  - `python-pptx` で生成
  - 日本語フォント指定あり
- `output/hokkaido-family-travel-guide.pdf`
  - ローカルでは同じ旅程データから確認用PDFを生成
  - GitHub ActionsではLibreOfficeでPowerPointからPDFへ変換
- `itinerary/days/*.md`
  - 日別に編集できる旅程Markdown

## 初回に作成済みの日程

- `2026-07-31`: 仙台からフェリーで苫小牧へ
- `2026-08-05`: 札幌から層雲峡へ

## ディレクトリ構成

```text
README.md
AGENTS.md
requirements.txt
itinerary/
  days/
images/
maps/
scripts/
output/
.github/workflows/
```

## 画像の置き方

写真は `images/` フォルダに置きます。

ビルド時は、日付や場所名から以下のようなファイルを探します。

```text
images/2026-07-31.jpg
images/2026-07-31.png
images/仙台港.jpg
images/苫小牧港.png
```

画像が見つからない場合は、スライド上に場所名入りのプレースホルダーを表示します。

## ローカルでの生成方法

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/build_guide.py
```

生成後、以下を確認してください。

```text
output/hokkaido-family-travel-guide.pptx
output/hokkaido-family-travel-guide.pdf
```

## PDF生成について

ローカルの `scripts/build_guide.py` はPowerPointと同じ旅程データから確認用PDFを生成します。

GitHub Actionsでは、LibreOfficeを使って次の形式でPowerPointからPDFを生成します。

```bash
libreoffice --headless --convert-to pdf --outdir output output/hokkaido-family-travel-guide.pptx
```

## 日程の編集方法

日程は `itinerary/days/` 配下のMarkdownを編集します。

- `## Summary`: その日の概要
- `## Timeline`: 時刻ベースの予定
- `## Restaurants`: レストラン候補
- `## Notes`: 補足メモ

レイアウトや色、フォントを変えたい場合は `scripts/build_guide.py` を編集します。

## GitHub Actions

`.github/workflows/build.yml` に自動ビルドを用意しています。

pushまたはpull request時に以下を実行します。

1. Python依存関係のインストール
2. PowerPoint生成
3. LibreOfficeでPowerPointからPDF生成
4. `output/` をartifactとして保存

