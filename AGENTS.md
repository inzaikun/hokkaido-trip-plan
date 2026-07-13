# AGENTS.md

このリポジトリは、北海道家族旅行ガイドをPowerPoint/PDFとして生成するためのものです。

## 基本ルール

- 旅程内容とレイアウトコードを分けて管理する。
- 旅程は `itinerary/days/*.md` に日別で追加・編集する。
- PowerPointの見た目や生成ロジックは `scripts/build_guide.py` に集約する。
- GitHub Pages用の公開HTMLは `scripts/build_public_site.py` で `docs/index.html` に生成する。
- ガイドブック用の派生情報（Today's Route、Today's Theme、食事レコメンド、Tips、スポット情報）は `scripts/guidebook_common.py` で共通生成し、HTML/PowerPoint/PDFで同じ情報を使う。
- 写真は `images/` に置き、スクリプトから読み込む。
- 画像がない場合でもビルドが失敗しないよう、場所名入りプレースホルダーを出す。
- 生成物は `output/` に置く。
- 日本語が文字化けしないよう、PowerPointでは日本語フォントを明示する。

## PowerPointルール

- スライドサイズは必ず16:9横長にする。
- 1日あたり1〜2ページを目安にする。
- 各日には以下を含める。
  - Today's Route
  - Today's Theme
  - 時刻ベースの詳細スケジュール
  - 移動時間
  - 昼食
  - 夕食
  - 観光
  - 休憩
  - おすすめランチ・おすすめ夕食
  - Today's Tips
  - 観光スポット写真、駐車場、滞在時間、GoogleMapリンク
- 写真がある場合は大きく使い、書店の旅行ガイドブック風にする。
- 写真がない場合は、場所名がわかるプレースホルダーを表示する。

## Markdown編集ルール

- 日付ファイル名は `YYYY-MM-DD.md` にする。
- `## Timeline` はMarkdown表で管理する。
- 時刻は `HH:MM` または `HH:MM-HH:MM` 形式を基本にする。
- 移動時間は `移動` 行に明記する。
- レストラン候補は `## Restaurants` に表で記載する。

## ビルド確認

変更後は原則として以下を実行する。

```bash
python scripts/build_guide.py
python scripts/build_web_data.py
python scripts/build_public_site.py
```

確認対象:

- `output/hokkaido-family-travel-guide.pptx` が生成されること
- `output/hokkaido-family-travel-guide.pdf` が生成されること
- `docs/index.html` に全日程の時刻ベーススケジュールが生成されること
- PowerPointが開けること
- PDFが開けること

## PRルール

- 旅程変更とレイアウト変更は、できるだけ別コミットに分ける。
- レストラン・宿泊・交通の予約状況が変わった場合は、該当日のMarkdownも更新する。
- 生成物を更新した場合は、READMEや変更概要に反映する。
