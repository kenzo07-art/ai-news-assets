import base64, json, re, sys
ROOT = "/Users/ken/Claude/ai-news-assets"
tpl = open(f"{ROOT}/email_template.html", encoding="utf-8").read()
parts = open(f"{ROOT}/email_parts.html", encoding="utf-8").read()

def part(n):
    blocks = re.split(r"<!-- \(\d\)[^>]*?-->", parts)
    return blocks[n].strip()

SUMMARY_ROW, SECTION, CARD, EMPTY = part(1), part(2), part(3), part(4)

data = json.load(open(sys.argv[1], encoding="utf-8"))
summary = "".join(SUMMARY_ROW.replace("{{SUMMARY_TEXT}}", s) for s in data["summary"])

sections = []
for cat in data["categories"]:
    c = cat["mail_color"]
    sec = (SECTION.replace("{{CAT_COLOR}}", c)
                  .replace("{{CAT_NAME}}", cat["full_name"])
                  .replace("{{CAT_COUNT}}", str(len(cat["items"]))))
    body = ""
    if not cat["items"]:
        body = EMPTY
    for it in cat["items"]:
        stars = "★" * it["score"] + "☆" * (3 - it["score"])
        body += (CARD.replace("{{CAT_COLOR}}", c).replace("{{STARS}}", stars)
                     .replace("{{SOURCE}}", it["source"]).replace("{{PUB_DATE}}", it["date"])
                     .replace("{{TITLE}}", it["title"]).replace("{{SUMMARY}}", it["summary"])
                     .replace("{{IMPACT}}", it["impact"]).replace("{{URL}}", it["url"]))
    sections.append(sec + body)

img_b64 = base64.b64encode(open(sys.argv[2], "rb").read()).decode()
html = (tpl.replace("{{DATE_LABEL}}", data["date_label"])
           .replace("{{PERIOD}}", data["period"])
           .replace("{{SUMMARY_LI}}", summary)
           .replace("{{SECTIONS}}", "".join(sections))
           .replace("%%HEADER_IMAGE%%",
                     '<img src="data:image/jpeg;base64,' + img_b64 + '" width="600" '
                     'alt="本日のAIニュース一覧" style="display:block;width:100%;max-width:600px;'
                     'height:auto;border:0;">'))
open(sys.argv[3], "w", encoding="utf-8").write(html)
print("wrote", sys.argv[3], len(html), "chars")
