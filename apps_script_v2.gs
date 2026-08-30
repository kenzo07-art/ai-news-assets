/**
 * AINewsDispatch v2 — 【AIニュースダイジェスト】の下書きを送信する。
 *
 * v1 からの変更点:
 *   Routine が添付したヘッダー画像 (aidigest_header.jpg) を本文の冒頭に埋め込んでから送る。
 *   Gmail コネクターは HTML 本文の <img> タグを削除してしまうため、
 *   本文には目印 %%HEADER_IMAGE%% だけを置いておき、ここで <img> に差し替える。
 *
 * 使い方: 既存の sendAINewsDrafts をこの内容で置き換える。トリガー設定 (15分おき) はそのまま。
 */

const SUBJECT_PREFIX = '【AIニュースダイジェスト】';
const HEADER_FILENAME = 'aidigest_header.jpg';
const HEADER_TOKEN = '%%HEADER_IMAGE%%';
const HEADER_CID = 'aidigestheader';

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

    const inlineImages = {};
    const otherAttachments = [];
    const attachments = msg.getAttachments({
      includeInlineImages: true,
      includeAttachments: true
    });
    for (const att of attachments) {
      if (att.getName() === HEADER_FILENAME) {
        inlineImages[HEADER_CID] = att.copyBlob().setName(HEADER_FILENAME);
      } else {
        otherAttachments.push(att);
      }
    }

    const imgTag =
      '<td style="padding:0;font-size:0;line-height:0;">' +
      '<img src="cid:' + HEADER_CID + '" width="600" alt="本日のAIニュース一覧" ' +
      'style="display:block;width:100%;max-width:600px;height:auto;border:0;outline:none;text-decoration:none;">' +
      '</td>';

    if (inlineImages[HEADER_CID]) {
      const tdPattern = new RegExp('<td[^>]*>\\s*' + HEADER_TOKEN + '\\s*</td>', 'i');
      if (tdPattern.test(html)) {
        html = html.replace(tdPattern, imgTag);
      } else {
        // 目印が見つからない場合でも画像を落とさない
        html = html.split(HEADER_TOKEN).join('');
        html = imgTag.replace(/^<td[^>]*>/, '').replace(/<\/td>$/, '') + html;
      }
    } else {
      // 画像が無い日は目印だけ消す
      html = html.split(HEADER_TOKEN).join('');
    }

    const options = { htmlBody: html };
    if (msg.getCc()) options.cc = msg.getCc();
    if (msg.getBcc()) options.bcc = msg.getBcc();
    if (Object.keys(inlineImages).length) options.inlineImages = inlineImages;
    if (otherAttachments.length) options.attachments = otherAttachments;

    GmailApp.sendEmail(to, subject, plain, options);
    draft.deleteDraft();
    sent++;
    Logger.log('sent: ' + subject + ' / header=' + (inlineImages[HEADER_CID] ? 'yes' : 'no'));
  }

  Logger.log('done. sent=' + sent);
}
