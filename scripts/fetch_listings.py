#!/usr/bin/env python3
"""청약홈(applyhome.co.kr) 분양정보를 수집해 data/listings.json 으로 저장한다.

수집 대상
  - APT 분양정보 (특별공급·1순위·2순위)
  - APT 무순위/잔여세대/계약취소/불법행위 재공급
  - 오피스텔/생활숙박시설/도시형생활주택/민간임대
외부 패키지 없이 표준 라이브러리만 사용한다.
"""
import html
import json
import os
import re
import sys
import time
import datetime as dt
import urllib.request
import urllib.parse

BASE = "https://www.applyhome.co.kr"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "listings.json")

LISTS = {
    "apt": {
        "list": "/ai/aia/selectAPTLttotPblancListView.do",
        "detail": "/ai/aia/selectAPTLttotPblancDetail.do",
        "apply": "/ap/aph/reqst/selectSubscrtReqstAptMainView.do",
        "cols": ["region", "house_kind", "sale_kind", "name", "builder", "phone", "notice_date", "apply_period", "announce_date"],
    },
    "remainder": {
        "list": "/ai/aia/selectAPTRemndrLttotPblancListView.do",
        "detail": "/ai/aia/selectAPTRemndrLttotPblancDetailView.do",
        "apply": "/ap/apr/reqst/selectSubscrtReqstAptMainView.do",
        "cols": ["region", "supply_kind", "name", "builder", "notice_date", "apply_period", "announce_date"],
    },
    "other": {
        "list": "/ai/aia/selectOtherLttotPblancListView.do",
        "detail": "/ai/aia/selectPRMOLttotPblancDetailView.do",
        "apply": "/ap/apb/reqst/selectSubscrtReqstUOMainView.do",
        "cols": ["region", "house_kind", "name", "builder", "phone", "notice_date", "apply_period", "announce_date"],
    },
}

CAPITAL = {"서울", "경기", "인천"}
METRO = {"부산", "대구", "대전", "광주", "울산", "세종"}


def get(url, params=None, retries=3):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"GET failed {url}: {last}")


def strip_tags(s):
    s = re.sub(r"<[^>]+>", " ", s)
    return html.unescape(re.sub(r"\s+", " ", s)).strip()


def parse_rows(page_html, cols):
    i = page_html.find("<tbody")
    j = page_html.find("</tbody>", i)
    if i < 0 or j < 0:
        return []
    rows = []
    for tr in re.findall(r"<tr[^>]*>.*?</tr>", page_html[i:j], re.S):
        attrs = dict(re.findall(r'data-(\w+)="([^"]*)"', tr[: tr.find(">")]))
        tds = [strip_tags(td) for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if "pbno" not in attrs or len(tds) < len(cols):
            continue
        row = {"pblancNo": attrs.get("pbno"), "houseManageNo": attrs.get("hmno"), "houseSecd": attrs.get("hsecd", "")}
        for k, v in zip(cols, tds):
            row[k] = v
        row["name"] = attrs.get("honm") or row.get("name", "")
        row["phone"] = re.sub(r"^☎\s*", "", row.get("phone", "")) if row.get("phone") else ""
        rows.append(row)
    return rows


def text_of(page_html):
    t = re.sub(r"<script.*?</script>", "", page_html, flags=re.S)
    t = re.sub(r"<style.*?</style>", "", t, flags=re.S)
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    return t


TYPE_RE = re.compile(r"^\d{2,3}\.\d{2,4}\s*[A-Za-z]?$")
AREA_RE = re.compile(r"^\d{2,3}\.\d{2,4}$")
MONEY_RE = re.compile(r"^\d{1,3}(,\d{3})+$")
INT_RE = re.compile(r"^\d{1,6}$")
MODEL_RE = re.compile(r"^\d{8,}\(\d+\)$")
MONTH_RE = re.compile(r"^\d{4}[.\-]\d{1,2}$")


def tables(page_html):
    out = []
    for tb in re.findall(r"<table[^>]*>.*?</table>", page_html, re.S):
        cap = re.search(r"<caption[^>]*>(.*?)</caption>", tb, re.S)
        cap = strip_tags(cap.group(1)) if cap else ""
        ths = [strip_tags(c) for c in re.findall(r"<th[^>]*>(.*?)</th>", tb, re.S)]
        body = tb[tb.find("<tbody"):] if "<tbody" in tb else tb
        rows = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
            cells = [strip_tags(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            if cells:
                rows.append(cells)
        out.append((cap, ths, rows))
    return out


def parse_detail(page_html, category):
    t = text_of(page_html)
    d = {"address": "", "total_units_text": "", "total_units": None, "contract_period": "",
         "homepage": "", "move_in": "", "schedule": [], "units": [], "prices": {}}
    units = {}
    order = []

    def unit(key):
        if key not in units:
            units[key] = {"type": key}
            order.append(key)
        return units[key]

    for cap, ths, rows in tables(t):
        if "주요정보" in cap:
            for r in rows:
                if len(r) >= 2 and r[0].startswith("공급위치"):
                    d["address"] = r[1]
                elif len(r) >= 2 and r[0].startswith("공급규모"):
                    d["total_units_text"] = r[1]
            continue
        if "청약일정" in cap:
            for r in rows:
                label = r[0]
                if label.startswith("모집공고일") or label == "청약접수" and len(r) > 2:
                    continue
                if label.startswith("당첨자"):
                    hm = re.search(r"https?://[^\s)]+", " ".join(r[1:]))
                    d["homepage"] = hm.group(0) if hm else ""
                    continue
                if label.startswith("계약일"):
                    d["contract_period"] = " ".join(r[1:]).strip()
                    continue
                dates = [c for c in r[1:] if re.search(r"\d{4}-\d{2}-\d{2}", c)]
                if dates:
                    d["schedule"].append({"label": label, "dates": dates})
            continue
        if "특별공급" in cap or "기타사항" in cap:
            continue
        # 주택형 단위 표 (공급대상 / 공급금액 / 주택형·세대수·분양가 통합표)
        type_col = ths.index("타입") if "타입" in ths else None
        is_price_table = ("공급금액" in cap) or any("공급금액" in h or "분양가" in h for h in ths)
        for r in rows:
            if not r or r[0] == "계":
                continue
            key = None
            if type_col is not None:
                # 2단 헤더가 아니므로 셀과 헤더가 정렬됨. rowspan 으로 앞 셀이 빠지면 오른쪽 정렬
                off = len(ths) - len(r)
                idx = type_col - off
                if 0 <= idx < len(r):
                    key = r[idx]
                    rest = r[idx + 1:]
            else:
                tp = next((c for c in r if TYPE_RE.match(c)), None)
                if tp:
                    key = tp.strip()
                    rest = r[r.index(tp) + 1:]
            if not key or key in ("-", "계"):
                continue
            u = unit(key)
            area = next((c for c in rest if AREA_RE.match(c)), None)
            if area and "area" not in u:
                u["area"] = float(area)
            moneys = [int(c.replace(",", "")) for c in rest if MONEY_RE.match(c)]
            ints = [int(c) for c in rest if INT_RE.match(c) and not MODEL_RE.match(c) and c != area]
            months = [c for c in rest if MONTH_RE.match(c)]
            if months and not d["move_in"]:
                d["move_in"] = months[0].replace("-", ".")
            if is_price_table:
                if moneys:
                    u["price"] = moneys[0]
                elif ints and ints[0] >= 1000:
                    u["price"] = ints[0]
                if any("공급세대수" in h for h in ths) and ints and "total" not in u:
                    u["total"] = ints[0]
                continue
            if moneys and "price" not in u:
                u["price"] = moneys[0]
            if category == "other":
                if ints:
                    u["total"] = ints[0]
            elif len(ints) >= 3:
                u["general"], u["special"], u["total"] = ints[0], ints[1], ints[2]
            elif ints:
                u["total"] = ints[0]
    m = re.search(r"입주예정월\s*[:：]?\s*([0-9]{4}[.\-][0-9]{1,2})", strip_tags(t))
    if m and not d["move_in"]:
        d["move_in"] = m.group(1).replace("-", ".")
    m = re.search(r"(\d[\d,]*)\s*세대", d["total_units_text"])
    d["total_units"] = int(m.group(1).replace(",", "")) if m else None
    for k in order:
        u = units[k]
        if "price" in u:
            d["prices"][k] = u["price"]
            m = re.match(r"(\d{2,3}\.\d+)", k)
            area = float(m.group(1)) if m else u.get("area")
            if area:
                u["price_per_pyeong"] = round(u["price"] / (area / 3.3058))
    d["units"] = [units[k] for k in order]
    pv = [u["price"] for u in d["units"] if "price" in u]
    d["price_min"] = min(pv) if pv else None
    d["price_max"] = max(pv) if pv else None
    if d["total_units"] is None and d["units"]:
        tot = sum(u.get("total", 0) or 0 for u in d["units"])
        d["total_units"] = tot or None
    return d


HGNN_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"


def clean_apt_name(name):
    n = re.sub(r"\(.*?\)", " ", name)
    n = re.sub(r"\b(\d+차|\d+회차|본청약|공공분양|조합원\s*취소분|신혼희망타운|분양주택|민간임대)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def resolve_hogangnono(item):
    """호갱노노 검색 API로 단지 id·좌표를 찾는다. 실패하면 조용히 빈 값."""
    name = clean_apt_name(item.get("name", ""))
    if not name:
        return {}
    url = "https://hogangnono.com/api/v2/searches/new?" + urllib.parse.urlencode({"query": name})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": HGNN_UA, "Accept": "application/json", "Referer": "https://hogangnono.com/"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:  # noqa
        return {}
    lst = (((data or {}).get("data") or {}).get("matched") or {}).get("apt", {}).get("list") or []
    if not lst:
        return {}
    addr = item.get("address") or ""
    # 주소의 동·지번이 맞는 후보 우선, 없으면 첫 후보
    key = re.search(r"([가-힣]+[동리가]\s*\d+[-\d]*)", addr)
    best = None
    if key:
        k = re.sub(r"\s+", "", key.group(1))
        for c in lst:
            if k in re.sub(r"\s+", "", c.get("address") or ""):
                best = c
                break
    if best is None:
        dong = re.search(r"([가-힣]+[동리가])\b", addr)
        if dong:
            for c in lst:
                if dong.group(1) in (c.get("address") or ""):
                    best = c
                    break
    if best is None:
        # 지역(시도)이라도 맞아야 채택
        sido = (addr.split() or [""])[0][:2]
        for c in lst:
            if sido and sido in (c.get("address") or ""):
                best = c
                break
    if best is None:
        return {}
    loc = best.get("location") or {}
    return {"hogangnono_id": best.get("id"), "hogangnono_name": best.get("name"), "lat": loc.get("lat"), "lon": loc.get("lon")}


def parse_period(s):
    m = re.findall(r"\d{4}-\d{2}-\d{2}", s or "")
    if not m:
        return None, None
    return m[0], m[-1]


def score(item):
    """투자 주목도 점수. 0~100. 근거 태그도 함께 돌려준다."""
    pts, tags = 0, []
    cat = item["category"]
    kind = (item.get("supply_kind") or "") + (item.get("sale_kind") or "") + (item.get("house_kind") or "")
    region = item.get("region", "")
    if cat == "remainder":
        pts += 30
        tags.append("무순위·잔여세대")
        if any(k in kind for k in ("계약취소", "불법행위")):
            pts += 10
            tags.append("최초 분양가 재공급")
    if region in CAPITAL:
        pts += 30 if region == "서울" else 20
        tags.append("수도권")
    elif region in METRO:
        pts += 10
    if cat == "apt" and "공공" in item.get("name", ""):
        pts += 10
        tags.append("공공분양")
    if "임대" in kind:
        pts -= 20
    units = item.get("units") or []
    gen = sum(u.get("general", u.get("total", 0)) or 0 for u in units)
    if cat == "remainder" and gen and gen <= 5:
        pts += 5
        tags.append("소량 공급")
    if cat == "other":
        pts -= 10
    return max(0, min(100, pts)), tags


def main():
    today = dt.date.today().isoformat()
    keep_after = (dt.date.today() - dt.timedelta(days=45)).isoformat()
    items = []
    for cat, cfg in LISTS.items():
        seen = set()
        for page in range(1, 15):
            page_html = get(BASE + cfg["list"], {"pageIndex": page})
            rows = parse_rows(page_html, cfg["cols"])
            rows = [r for r in rows if r["pblancNo"] not in seen]
            if not rows:
                break
            stop = False
            for r in rows:
                seen.add(r["pblancNo"])
                s, e = parse_period(r.get("apply_period"))
                r["apply_start"], r["apply_end"] = s, e
                if e and e < keep_after:
                    stop = True
                    continue
                r["category"] = cat
                params = {"houseManageNo": r["houseManageNo"], "pblancNo": r["pblancNo"]}
                if r.get("houseSecd"):
                    params["houseSecd"] = r["houseSecd"]
                r["detail_url"] = BASE + cfg["detail"] + "?" + urllib.parse.urlencode(params)
                r["apply_url"] = BASE + cfg["apply"]
                try:
                    r.update(parse_detail(get(r["detail_url"]), cat))
                except Exception as ex:  # noqa
                    print("detail failed", r["name"], ex, file=sys.stderr)
                items.append(r)
                time.sleep(0.3)
            if stop:
                break
            time.sleep(0.5)
        print(cat, len([i for i in items if i["category"] == cat]), file=sys.stderr)

    # 호갱노노 단지 id·좌표 (접수 중·예정 + 최근 마감분만, 이전 결과 재사용)
    prev = {}
    try:
        with open(OUT, encoding="utf-8") as f:
            for it in json.load(f).get("items", []):
                if it.get("hogangnono_id"):
                    prev[it["pblancNo"]] = {k: it.get(k) for k in ("hogangnono_id", "hogangnono_name", "lat", "lon")}
    except Exception:  # noqa
        pass
    resolved = 0
    for it in items:
        if it["pblancNo"] in prev:
            it.update(prev[it["pblancNo"]])
            continue
        r = resolve_hogangnono(it)
        if r:
            it.update(r)
            resolved += 1
        time.sleep(0.25)
    print("hogangnono resolved", resolved, "reused", len(prev), file=sys.stderr)

    for it in items:
        it["score"], it["tags"] = score(it)
        s, e = it.get("apply_start"), it.get("apply_end")
        if e and e < today:
            it["status"] = "closed"
        elif s and s <= today <= (e or s):
            it["status"] = "open"
        else:
            it["status"] = "upcoming"
    items.sort(key=lambda x: (x.get("apply_start") or "9999", -x["score"]))
    out = {
        "updated_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST"),
        "source": "한국부동산원 청약홈 (applyhome.co.kr)",
        "count": len(items),
        "items": items,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("wrote", OUT, len(items), file=sys.stderr)


if __name__ == "__main__":
    main()
