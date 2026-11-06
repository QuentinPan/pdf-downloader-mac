"""
PDF Downloader for macOS  —  一个完整的 PDF 搜索/下载交互工具
============================================================
功能：
  1. ArXiv 检索下载   —— 按关键词 / 分类 / 年份检索，勾选后批量下载 PDF
  2. DOI 批量下载     —— 粘贴一个或多个 DOI / arXiv ID，自动解析并下载全文
  3. 网页 PDF 抓取    —— 给定一个网页 URL，抓取该页所有 PDF 链接并下载
  4. 文件管理         —— 查看已下载文件，浏览器直接取回

运行（macOS）：
  python3 -m venv venv && source venv/bin/activate
  pip install -r requirements.txt
  python app.py
  浏览器打开 http://127.0.0.1:5000
"""

import os
import re
import io
import sys
import uuid
import socket
import argparse
import threading

import arxiv
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory

# 模板目录用绝对路径，保证「源码直接运行」和「py2app 打包后」都能找到
_HERE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(_HERE, "templates"))

# 默认下载目录：macOS 上放在「下载」文件夹下，可用界面覆盖
DEFAULT_OUT = os.path.expanduser("~/Downloads/PDF_Downloader")

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36 PDFDownloader/1.0"
    )
}

# 简单的线程锁，避免并发写同一目录出问题
_lock = threading.Lock()


# ----------------------------- 工具函数 -----------------------------
def sanitize(name: str) -> str:
    """清理文件名，去掉 macOS/文件系统不友好的字符。"""
    name = name.strip().replace("\n", " ")
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = re.sub(r"\s+", " ", name)
    return name[:120] or "document"


def resolve_out_dir(out_dir: str) -> str:
    """解析下载目录，支持 ~ 扩展；为空则用默认。"""
    out_dir = (out_dir or "").strip()
    if not out_dir:
        out_dir = DEFAULT_OUT
    out_dir = os.path.expanduser(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def stream_download(url: str, out_path: str, timeout: int = 90) -> bool:
    """流式下载，判断 Content-Type 是否为 PDF，成功返回 True。"""
    try:
        with requests.get(
            url, headers=UA, stream=True, timeout=timeout, allow_redirects=True
        ) as r:
            ctype = r.headers.get("Content-Type", "").lower()
            if r.status_code != 200 or "pdf" not in ctype:
                # 有些服务器不返回正确类型，仍尝试按内容保存后再由前端校验
                if r.status_code != 200:
                    return False
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        # 校验文件头是否为 %PDF
        with open(out_path, "rb") as f:
            head = f.read(5)
        if head != b"%PDF-":
            os.remove(out_path)
            return False
        return True
    except Exception:
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except Exception:
                pass
        return False


def save_pdf_bytes(content: bytes, out_path: str) -> bool:
    if content[:5] != b"%PDF-":
        return False
    with open(out_path, "wb") as f:
        f.write(content)
    return True


# ----------------------------- 页面 -----------------------------
@app.route("/")
def index():
    return render_template("index.html", default_out=DEFAULT_OUT)


@app.route("/sw.js")
def sw_js():
    """以根路径提供 Service Worker，使其作用域覆盖整个应用（PWA 离线缓存用）。"""
    return send_from_directory(
        os.path.join(_HERE, "static"), "sw.js",
        mimetype="application/javascript",
    )


# ----------------------------- 1. ArXiv 检索 -----------------------------
@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.get_json(force=True, silent=True) or {}
    query = (data.get("query") or "").strip()
    category = (data.get("category") or "").strip()
    year = (data.get("year") or "").strip()
    try:
        max_results = min(int(data.get("max_results") or 10), 50)
    except Exception:
        max_results = 10

    q = []
    if category:
        q.append(f"cat:{category}")
    if query:
        q.append(f"({query})")
    if year and re.fullmatch(r"\d{4}", year):
        q.append(
            f"submittedDate:[{year}01010000 TO {year}12312359]"
        )
    search_query = " AND ".join(q) if q else "all:electron"

    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=search_query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        results = []
        for r in client.results(search):
            results.append(
                {
                    "id": r.get_short_id(),
                    "title": r.title.strip(),
                    "authors": ", ".join(a.name for a in r.authors[:5]),
                    "summary": (r.summary or "").strip()[:400],
                    "pdf_url": r.pdf_url,
                    "published": str(r.published.date()) if r.published else "",
                }
            )
        return jsonify({"ok": True, "count": len(results), "results": results})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/download_arxiv", methods=["POST"])
def api_download_arxiv():
    data = request.get_json(force=True, silent=True) or {}
    items = data.get("items") or []  # [{pdf_url, title, id}]
    out_dir = resolve_out_dir(data.get("out_dir") or "")
    downloaded, failed = [], []
    with _lock:
        for it in items:
            url = it.get("pdf_url")
            aid = it.get("id") or ""
            title = it.get("title") or aid
            fname = f"{aid or sanitize(title)}.pdf"
            fpath = os.path.join(out_dir, fname)
            if stream_download(url, fpath):
                downloaded.append({"file": fname, "title": title})
            else:
                failed.append({"title": title, "url": url})
    return jsonify(
        {
            "ok": True,
            "out_dir": out_dir,
            "downloaded": downloaded,
            "failed": failed,
        }
    )


# ----------------------------- 2. DOI 批量下载 -----------------------------
ARXIV_ID_RE = re.compile(r"^(?:arXiv:)?(\d{4}\.\d{4,5}(?:v\d+)?)$", re.I)
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:a-zA-Z0-9]+")


@app.route("/api/doi", methods=["POST"])
def api_doi():
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("dois") or "").strip()
    out_dir = resolve_out_dir(data.get("out_dir") or "")
    items = re.split(r"[\s,;]+", text)
    downloaded, failed = [], []

    with _lock:
        for raw in items:
            raw = raw.strip()
            if not raw:
                continue
            fname = None
            url = None
            # 情况 A：arXiv ID
            m = ARXIV_ID_RE.match(raw)
            if m:
                aid = m.group(1)
                url = f"https://arxiv.org/pdf/{aid}"
                fname = f"{aid}.pdf"
            else:
                # 情况 B：普通 DOI —— 通过 doi.org 重定向尝试获取 OA 全文
                doi = raw if raw.lower().startswith("10.") else None
                if not doi:
                    failed.append({"id": raw, "reason": "无法识别为 arXiv ID 或 DOI"})
                    continue
                fname = f"{doi.replace('/', '_')}.pdf"
                try:
                    # 优先尝试 Unpaywall 开放获取位置
                    up = requests.get(
                        f"https://api.unpaywall.org/v2/{doi}",
                        params={"email": "pdfdownloader@example.com"},
                        headers=UA,
                        timeout=30,
                    ).json()
                    oa = up.get("best_oa_location") or {}
                    url = oa.get("url_for_pdf") or oa.get("url")
                    if not url:
                        # 退回到 doi.org 重定向
                        red = requests.get(
                            f"https://doi.org/{doi}",
                            headers={**UA, "Accept": "application/pdf"},
                            allow_redirects=True,
                            stream=True,
                            timeout=30,
                        )
                        if red.status_code == 200 and "pdf" in red.headers.get(
                            "Content-Type", ""
                        ).lower():
                            fpath = os.path.join(out_dir, fname)
                            ok = stream_download(red.url, fpath)
                            (downloaded if ok else failed).append(
                                {"id": doi, "file": fname if ok else None}
                            )
                            continue
                except Exception as e:
                    failed.append({"id": raw, "reason": str(e)})
                    continue

            if url and fname:
                fpath = os.path.join(out_dir, fname)
                if stream_download(url, fpath):
                    downloaded.append({"id": raw, "file": fname})
                else:
                    failed.append({"id": raw, "reason": "未能获取 PDF（可能需机构权限）"})
    return jsonify(
        {"ok": True, "out_dir": out_dir, "downloaded": downloaded, "failed": failed}
    )


# ----------------------------- 3. 网页 PDF 抓取 -----------------------------
@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    data = request.get_json(force=True, silent=True) or {}
    url = (data.get("url") or "").strip()
    out_dir = resolve_out_dir(data.get("out_dir") or "")
    try:
        max_dl = int(data.get("max_downloads") or 50)
    except Exception:
        max_dl = 50
    if not url:
        return jsonify({"ok": False, "error": "URL 不能为空"}), 400

    try:
        resp = requests.get(url, headers=UA, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        return jsonify({"ok": False, "error": f"无法访问网页：{e}"}), 400

    soup = BeautifulSoup(resp.text, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        h = a["href"]
        hl = h.lower()
        if hl.endswith(".pdf") or "/pdf/" in hl:
            links.add(_abs(h, url))
    for tag in soup.find_all(src=True):
        h = tag["src"]
        hl = h.lower()
        if hl.endswith(".pdf") or "/pdf/" in hl:
            links.add(_abs(h, url))

    downloaded, failed = [], []
    with _lock:
        for link in sorted(links)[:max_dl]:
            fname = _pdf_name(link)
            fpath = os.path.join(out_dir, fname)
            if stream_download(link, fpath):
                downloaded.append({"file": fname, "url": link})
            else:
                failed.append({"url": link})
    if len(links) > max_dl:
        failed.extend([{"url": u} for u in sorted(links)[max_dl:]])
    return jsonify(
        {
            "ok": True,
            "out_dir": out_dir,
            "found": sorted(links),
            "downloaded": downloaded,
            "failed": failed,
        }
    )


def _abs(href: str, base: str) -> str:
    from urllib.parse import urljoin

    return urljoin(base, href)


def _pdf_name(link: str) -> str:
    from urllib.parse import urlparse

    path = urlparse(link).path
    base = os.path.basename(path.split("?")[0])
    if not base.endswith(".pdf"):
        base = (base or "doc") + ".pdf"
    return sanitize(base)


# ----------------------------- 4. 文件管理 -----------------------------
@app.route("/api/files", methods=["POST"])
def api_files():
    data = request.get_json(force=True, silent=True) or {}
    out_dir = resolve_out_dir(data.get("out_dir") or "")
    files = []
    if os.path.isdir(out_dir):
        for f in sorted(os.listdir(out_dir)):
            fp = os.path.join(out_dir, f)
            if os.path.isfile(fp) and f.lower().endswith(".pdf"):
                files.append(
                    {
                        "name": f,
                        "size_kb": round(os.path.getsize(fp) / 1024, 1),
                    }
                )
    return jsonify({"ok": True, "out_dir": out_dir, "files": files})


@app.route("/api/file/<path:name>")
def api_file(name):
    data = request.args.get("out_dir") or ""
    out_dir = resolve_out_dir(data)
    # 防目录穿越
    safe = os.path.basename(name)
    fpath = os.path.join(out_dir, safe)
    if not os.path.isfile(fpath):
        return jsonify({"ok": False, "error": "文件不存在"}), 404
    # iPad 上 inline=1 时在 Safari 内联预览（可长按存储到「文件」），否则强制下载
    inline = request.args.get("inline") == "1"
    return send_file(
        fpath,
        mimetype="application/pdf",
        as_attachment=not inline,
        download_name=safe,
    )


def lan_ip() -> str:
    """获取本机局域网 IP（用于 iPad / 同 WiFi 设备访问提示）。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF 下载器 Web 服务")
    parser.add_argument("--host", default="127.0.0.1",
                        help="监听地址：127.0.0.1(仅本机) 或 0.0.0.0(允许同 WiFi 的 iPad 访问)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5000)),
                        help="监听端口（云端部署时读取 $PORT 环境变量）")
    args = parser.parse_args()

    os.makedirs(DEFAULT_OUT, exist_ok=True)

    print("=" * 56)
    print("  PDF 下载器已启动")
    print("  本机访问 : http://127.0.0.1:%d/" % args.port)
    if args.host in ("0.0.0.0", "0.0.0.0"):
        print("  iPad/手机: http://%s:%d/  (需与本机在同一 WiFi)" % (lan_ip(), args.port))
        print("  提示：在 iPad Safari 打开后，点「分享 → 添加到主屏幕」即可像 App 使用")
    print("  下载目录 : %s" % DEFAULT_OUT)
    print("=" * 56)

    # 生产/局域网场景（绑定 0.0.0.0 或云端 $PORT 已设置）使用 waitress 生产级服务；
    # 本地 127.0.0.1 调试时仍用 Flask 开发服务器（错误信息更友好）。
    if args.host == "0.0.0.0" or os.environ.get("PORT") is not None:
        try:
            import waitress

            print("  服务模式 : waitress (生产级，支持并发)")
            waitress.serve(app, host=args.host, port=args.port, _quiet=True)
            sys.exit(0)
        except Exception as e:
            print("  waitress 不可用，回退 Flask 开发服务器：", e)

    # host 支持并发请求；0.0.0.0 时允许局域网内设备（如 iPad）访问
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
