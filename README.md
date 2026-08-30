# ai-news-assets

毎朝7:00 JSTに配信している「AIニュースダイジェスト」メールの中身。

claude.ai の Routine「AI関連ニュースの毎朝配信」がこのリポジトリをクローンし、
`INSTRUCTIONS.md` の手順どおりにニュースを集めてGmail下書きを作る。
下書きは Google Apps Script（`apps_script_v2.gs`）が15分おきに拾って送信する。

## 中身

| ファイル | 役割 |
|---|---|
| `INSTRUCTIONS.md` | 毎朝クラウドが読む手順書。**配信内容を変えたい時はここを直す** |
| `compose_header.py` | メール冒頭の「本日の一覧」画像を作る。日本語はフォントで正確に描画する |
| `assets/bg_main.jpg` | 背景アート（OpenAI gpt-image-2 で生成） |
| `email_template.html` | メール本文の骨組み（Gmail / Outlook 両対応） |
| `email_parts.html` | 差し込むパーツ（要点・カテゴリ見出し・ニュースカード・該当なし） |
| `apps_script.gs` | 送信側。下書きの `%%HEADER_IMAGE:URL%%` を画像に差し替えてから送る |
| `daily/YYYY-MM-DD.jpg` | その日のヘッダー画像。毎朝クラウドが生成して push する |
| `preview_sample.html` | ダミーデータでの完成イメージ（ブラウザで開く） |

## 直し方

1. このリポジトリのファイルを直して push する
2. 翌朝の実行から自動で反映される（Routine側の設定変更は不要）

## 設計メモ（なぜこの構成か）

- クラウド実行環境は**外部インターネットに出られない**（egress proxy が拒否）。
  そのため画像生成AIを毎朝呼ぶことはできず、背景アートは事前生成してここに置く。
- クラウドには日本語フォント（IPAゴシック）と Python があるので、
  **その日の見出しだけは毎朝クラウドで正確に描画する**。
- Gmailコネクターは HTML本文の `<img>` タグを削除する。
  そのため本文には `%%HEADER_IMAGE:URL%%` の目印だけを置き、Apps Script が送信直前に画像へ差し替える。
- 画像をメール添付で渡す案は**失敗**した。base64（約7〜8万文字）をモデルが書き写す工程で
  実行が20分以上停滞するため。代わりにクラウドから `daily/` へ push し、
  Apps Script が raw.githubusercontent.com から取得する方式にした（環境に `GITHUB_TOKEN` があり push できる）。
- Outlook はメールを Word のエンジンで描画するため、
  角丸・影・グラデーション・flexbox は使わず、テーブルレイアウトで組む。
