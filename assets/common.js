/* 공용 도우미 */
const DAYS = ["일", "월", "화", "수", "목", "금", "토"];
function todayISO() {
  const d = new Date(); const k = new Date(d.getTime() + (9 * 60 + d.getTimezoneOffset()) * 60000);
  return k.toISOString().slice(0, 10);
}
function fmtMan(m) {
  if (m == null || isNaN(m)) return "-";
  const eok = Math.floor(m / 10000), rest = m % 10000;
  return (eok ? eok + "억 " : "") + (rest ? rest.toLocaleString("ko-KR") + "만" : "") + "원";
}
function fmtDate(iso, withYear) {
  if (!iso) return "-";
  const [y, mo, d] = iso.split("-").map(Number);
  const dt = new Date(y, mo - 1, d);
  return (withYear ? y + "년 " : "") + mo + "월 " + d + "일(" + DAYS[dt.getDay()] + ")";
}
function fmtRange(s, e) {
  if (!s) return "-";
  if (!e || s === e) return fmtDate(s);
  const sameMonth = s.slice(0, 7) === e.slice(0, 7);
  return fmtDate(s) + " ~ " + (sameMonth ? fmtDate(e).replace(/^\d+월 /, "") : fmtDate(e));
}
function daysUntil(iso) {
  if (!iso) return null;
  const a = new Date(todayISO()), b = new Date(iso);
  return Math.round((b - a) / 86400000);
}
function esc(s) { return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function pyeong(m2) { return (m2 / 3.3058).toFixed(1); }
async function loadJSON(path) {
  const r = await fetch(path + "?t=" + Math.floor(Date.now() / 600000), { cache: "no-cache" });
  if (!r.ok) throw new Error(path + " " + r.status);
  return r.json();
}
function store(k, v) { try { if (v === undefined) return JSON.parse(localStorage.getItem(k)); localStorage.setItem(k, JSON.stringify(v)); } catch (e) { return null; } }
