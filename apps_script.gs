/**
 * AINewsDispatch v3 — 【AIニュースダイジェスト】の下書きを送信する。
 *
 * 毎朝の Routine は、その日のヘッダー画像を GitHub リポジトリ ai-news-assets の
 * daily/YYYY-MM-DD.jpg に push し、メール本文には目印だけを置く:
 *
 *   %%HEADER_IMAGE:https://raw.githubusercontent.com/.../daily/2026-08-31.jpg%%
 *
 * このスクリプトが送信直前にその画像を取得し、本文の冒頭に埋め込んでから送る。
 * （Gmailコネクターは HTML本文の <img> タグを削除してしまうため、この方式が必要）
 *
 * 使い方: 既存の sendAINewsDrafts をこの内容で丸ごと置き換える。トリガー(15分おき)はそのまま。
 */

const SUBJECT_PREFIX = '【AIニュースダイジェスト】';
const HEADER_FILENAME = 'aidigest_header.jpg';
const HEADER_CID = 'aidigestheader';
// 安全のため、画像を取りに行ってよいURLはこのリポジトリ配下だけに限定する
const ALLOWED_URL_PREFIX = 'https://raw.githubusercontent.com/kenzo07-art/ai-news-assets/';
// <td>...%%HEADER_IMAGE%%...</td> または <td>...%%HEADER_IMAGE:URL%%...</td>
const TOKEN_TD_RE = /<td[^>]*>\s*%%HEADER_IMAGE(?::([^%\s"'<>]+))?%%\s*<\/td>/i;
const TOKEN_BARE_RE = /%%HEADER_IMAGE(?::([^%\s"'<>]+))?%%/gi;

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

    // --- ヘッダー画像を用意する（1: 本文のURL / 2: 添付ファイル） ---
    let headerBlob = null;
    const m = html.match(TOKEN_TD_RE) || html.match(/%%HEADER_IMAGE:([^%\s"'<>]+)%%/i);
    const url = m ? m[1] : null;
    if (url && url.indexOf(ALLOWED_URL_PREFIX) === 0) {
      try {
        const res = UrlFetchApp.fetch(url, { muteHttpExceptions: true, followRedirects: true });
        if (res.getResponseCode() === 200) {
          headerBlob = res.getBlob().setName(HEADER_FILENAME);
        } else {
          Logger.log('header fetch HTTP ' + res.getResponseCode() + ' / ' + url);
        }
      } catch (e) {
        Logger.log('header fetch failed: ' + e);
      }
    }

    const otherAttachments = [];
    const attachments = msg.getAttachments({ includeInlineImages: true, includeAttachments: true });
    for (const att of attachments) {
      if (att.getName() === HEADER_FILENAME) {
        if (!headerBlob) headerBlob = att.copyBlob().setName(HEADER_FILENAME);
      } else {
        otherAttachments.push(att);
      }
    }

    // --- 目印を画像に差し替える ---
    if (headerBlob) {
      const imgTd =
        '<td style="padding:0;font-size:0;line-height:0;">' +
        '<img src="cid:' + HEADER_CID + '" width="600" alt="本日のAIニュース一覧" ' +
        'style="display:block;width:100%;max-width:600px;height:auto;border:0;outline:none;text-decoration:none;">' +
        '</td>';
      if (TOKEN_TD_RE.test(html)) {
        html = html.replace(TOKEN_TD_RE, imgTd);
      } else {
        html = html.replace(TOKEN_BARE_RE, '');
        html = imgTd.replace(/^<td[^>]*>/, '').replace(/<\/td>$/, '') + html;
      }
    } else {
      html = html.replace(TOKEN_BARE_RE, '');
    }

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
