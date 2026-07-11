# 北海道家族旅行ガイド HTML版

`itinerary/days/*.md` から生成したデータを使って、旅行ガイドをWebページとして表示します。

## 更新方法

リポジトリルートで以下を実行します。

```bash
python scripts/build_web_data.py
```

その後、Webサイトをビルドします。

```bash
cd web
npm ci
npm run build
```

`web/app/page.tsx` と `web/app/globals.css` は表示レイアウト、`web/app/itinerary-data.ts` は自動生成データです。
