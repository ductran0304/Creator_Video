"""Đăng hàng loạt nhiều video của một thương hiệu lên YouTube / Facebook / TikTok và báo cáo tình trạng.

  make_video.py social report [--brand kttg]                         bảng tình trạng từng video trên 3 nền tảng
  make_video.py social upload [--platforms yt,fb,tt] [--from 1 --to 30] [--publish]
                                                                     tải phần còn thiếu (bỏ qua mục đã có trong posted.json);
                                                                     --publish: công khai luôn mục đã tải (cần approve)
  make_video.py social publish [--platforms yt,fb] [--from 1 --to 30] [--pace 150]
                                                                     công khai mục đã tải, cách nhau --pace giây trên Facebook

Danh sách video lấy từ brands/<brand>/topics.md (dòng "[x] V<n> ... → projects/<slug>").
Giới hạn thực tế đã gặp (26/09/2026):
- YouTube: hết lượt tải video trong ngày sau ~80 lần tải (429 "Video Uploads"); hạn mức reset 14h giờ VN.
- Facebook: ~200 lệnh gọi/giờ cho app (code 4) và chặn chống spam khi đăng dày (code 368) — gặp 368 thì DỪNG, đợi
  vài giờ tới 1 ngày, làm tiếp chậm (--pace 150).
- TikTok: hộp thư nháp tối đa 5 video chờ trong 24 giờ (spam_risk_too_many_pending_share).
Gặp giới hạn ở nền tảng nào thì dừng riêng nền tảng đó, các nền tảng khác chạy tiếp.
"""
import json
import os
import re
import time

from . import facebook as fb
from . import tiktok as tt
from . import youtube as yt

LIMITS = {"yt": ("quotaExceeded", "uploadLimitExceeded", "rateLimitExceeded", "quota"),
          "fb": ("code 4)", "code 17)", "code 32)", "code 368)"),
          "tt": ("spam_risk", "too_many", "rate_limit")}


def video_list(base_dir, brand, lo=1, hi=10 ** 6):
    out = set()
    p = os.path.join(base_dir, "brands", brand, "topics.md")
    for line in open(p, encoding="utf-8"):
        m = re.search(r"\[x\] V(\d+) .*?projects/([a-z0-9_]+)", line)
        if m and lo <= int(m.group(1)) <= hi:
            out.add((int(m.group(1)), m.group(2)))
    return sorted(out)


def _hit_limit(plat, msg):
    return any(k in msg for k in LIMITS[plat])


def report(base_dir, brand):
    rows = []
    for v, slug in video_list(base_dir, brand):
        d = os.path.join(base_dir, "projects", slug)
        pp = os.path.join(d, "publish", "publish.json")
        if not os.path.exists(pp):
            rows.append({"v": v, "slug": slug, "missing": True})
            continue
        pub = json.load(open(pp, encoding="utf-8"))
        n = 1 + len(pub.get("shorts", []))
        p = yt.load_posted(d)
        Y, F, T = p.get("youtube", {}), p.get("facebook", {}), p.get("tiktok", {})
        rows.append({"v": v, "slug": slug, "need": n, "need_tt": n - 1,
                     "yt": len(Y), "yt_pub": sum(1 for r in Y.values() if r.get("privacy") == "public"),
                     "fb": len(F), "fb_pub": sum(1 for r in F.values() if r.get("state") == "PUBLISHED"),
                     "tt": len(T), "tt_posted": sum(1 for r in T.values() if r.get("state") == "PUBLISH_COMPLETE"),
                     "approved": yt.is_approved(d)})
    return rows


def upload(base_dir, brand, platforms=("yt", "fb", "tt"), lo=1, hi=10 ** 6, publish=False, log=print):
    import make_video
    stopped = {}
    for v, slug in video_list(base_dir, brand, lo, hi):
        d, project, _ = make_video.load(slug)
        steps = {"yt": lambda: yt.upload(base_dir, brand, project, d, which="all",
                                         privacy="public" if publish else "private"),
                 "fb": lambda: fb.upload(base_dir, brand, d, which="all", publish=publish),
                 "tt": lambda: tt.upload(base_dir, brand, d, which="all")}
        for plat in platforms:
            if plat in stopped:
                continue
            try:
                res = steps[plat]()
                if res:
                    log(f"V{v} {plat}: +{len(res)}")
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                log(f"V{v} {plat} LỖI: {msg[:160]}")
                if _hit_limit(plat, msg):
                    stopped[plat] = f"V{v}: {msg[:160]}"
        if len(stopped) == len(platforms):
            break
    return stopped


def publish(base_dir, brand, platforms=("yt", "fb"), lo=1, hi=10 ** 6, pace=150, log=print):
    stopped = {}
    for v, slug in video_list(base_dir, brand, lo, hi):
        d = os.path.join(base_dir, "projects", slug)
        for plat in platforms:
            if plat in stopped:
                continue
            try:
                done = (yt.publish if plat == "yt" else fb.publish)(base_dir, brand, d, log=lambda *a: None)
                if done:
                    log(f"V{v} {plat}: công khai {len(done)}")
                    if plat == "fb" and pace:
                        time.sleep(pace)
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                log(f"V{v} {plat} LỖI: {msg[:160]}")
                if _hit_limit(plat, msg):
                    stopped[plat] = f"V{v}: {msg[:160]}"
        if len(stopped) == len(platforms):
            break
    return stopped
