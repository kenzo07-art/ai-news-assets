/**
 * AINewsDispatch v4 — 【AIニュースダイジェスト】の下書きを送信する。
 *
 * 毎朝の Routine は、その日のヘッダー画像を GitHub リポジトリ ai-news-assets の
 * daily/YYYY-MM-DD.jpg（日本時間の日付）に push し、メール本文には目印
 *   %%HEADER_IMAGE%%
 * だけを置く。このスクリプトが送信直前にその画像を取得し、本文の冒頭に埋め込んでから送る。
 *
 * なぜこの形か:
 *  - Gmailコネクターは HTML本文の <img> タグを削除するので、本文に画像を書けない
 *  - 本文にURLを書くと Gmail が勝手に <a> タグでリンク化して目印が壊れるので、
 *    URLは本文に書かせず、ここで日付から組み立てる
 *
 * 使い方: 既存の sendAINewsDrafts をこの内容で丸ごと置き換える。トリガー(15分おき)はそのまま。
 */

const SUBJECT_PREFIX = '【AIニュースダイジェスト】';
const HEADER_FILENAME = 'aidigest_header.jpg';
const HEADER_CID = 'aidigestheader';
const HEADER_TOKEN = '%%HEADER_IMAGE';
const IMAGE_BASE_URL = 'https://raw.githubusercontent.com/kenzo07-art/ai-news-assets/main/daily/';

function sendAINewsDrafts() {
  const drafts = GmailApp.getDrafts();
  let sent = 0;

  for (const draft of drafts) {
    const msg = draft.getMessage();
    const subject = msg.getSubject() || '';
    if (subject.indexOf(SUBJECT_PREFIX) !== 0) continue;

    const to = msg.getTo();
    if (!to) {
      Logger.log('skip: no recipient / subject=' + subject);
      continue;
    }

    let html = msg.getBody() || '';
    const plain = msg.getPlainBody() || '';

    // --- ヘッダー画像を用意する（1: 当日分のURL / 2: 添付ファイル） ---
    let headerBlob = fetchTodaysHeader_();

    const otherAttachments = [];
    const attachments = msg.getAttachments({ includeInlineImages: true, includeAttachments: true });
    for (const att of attachments) {
      if (att.getName() === HEADER_FILENAME) {
        if (!headerBlob) headerBlob = att.copyBlob().setName(HEADER_FILENAME);
      } else {
        otherAttachments.push(att);
      }
    }

    html = replaceHeaderToken_(html, headerBlob);

    const options = { htmlBody: html };
    if (msg.getCc()) options.cc = msg.getCc();
    if (msg.getBcc()) options.bcc = msg.getBcc();
    if (headerBlob) options.inlineImages = { [HEADER_CID]: headerBlob };
    if (otherAttachments.length) options.attachments = otherAttachments;

    GmailApp.sendEmail(to, subject, plain, options);
    draft.deleteDraft();
    sent++;
    Logger.log('sent: ' + subject + ' / header=' + (headerBlob ? 'yes' : 'no'));
  }

  Logger.log('done. sent=' + sent);
}

/** 当日分のヘッダー画像を GitHub から取得する。無ければ null。 */
function fetchTodaysHeader_() {
  const today = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd');
  const url = IMAGE_BASE_URL + today + '.jpg';

  // push直後はCDNに載っていないことがあるので数回だけ試す
  for (let i = 0; i < 3; i++) {
    try {
      const res = UrlFetchApp.fetch(url, { muteHttpExceptions: true, followRedirects: true });
      if (res.getResponseCode() === 200) {
        return res.getBlob().setName(HEADER_FILENAME);
      }
      Logger.log('header fetch HTTP ' + res.getResponseCode() + ' / ' + url);
    } catch (e) {
      Logger.log('header fetch failed: ' + e);
    }
    Utilities.sleep(3000);
  }
  return null;
}

/**
 * 本文の `%%HEADER_IMAGE%%` を含む <td> ごと画像に差し替える。
 * Gmail が目印の周りにタグを差し込んでいても壊れないよう、正規表現ではなく
 * 「目印を挟む <td> ... </td> の範囲」を位置で特定して置き換える。
 */
function replaceHeaderToken_(html, headerBlob) {
  const at = html.indexOf(HEADER_TOKEN);
  if (at < 0) return html;

  const tdStart = html.lastIndexOf('<td', at);
  const tdEnd = html.indexOf('</td>', at);
  if (tdStart < 0 || tdEnd < 0) return html;

  const replacement = headerBlob
    ? '<td style="padding:0;font-size:0;line-height:0;">' +
      '<img src="cid:' + HEADER_CID + '" width="600" alt="本日のAIニュース一覧" ' +
      'style="display:block;width:100%;max-width:600px;height:auto;border:0;outline:none;text-decoration:none;">' +
      '</td>'
    : '<td style="padding:0;font-size:0;line-height:0;">&nbsp;</td>';

  return html.slice(0, tdStart) + replacement + html.slice(tdEnd + 5);
}
