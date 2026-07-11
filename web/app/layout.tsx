import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "北海道家族旅行ガイド",
  description: "2026年7月31日から8月12日までの北海道家族旅行を時刻ベースで確認できるHTMLガイドです。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
