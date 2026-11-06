"""
mac_app.py  —  PDF 下载器的 macOS .app 启动器
============================================
双击打包好的「PDF Downloader.app」时执行：
  1. 在后台线程用 waitress 启动 Flask 服务（127.0.0.1，自动避开被占用的端口）
  2. 自动打开默认浏览器到本地界面
  3. 弹出一个轻量状态窗口，提供「在浏览器打开」和「退出」按钮
     （若系统无 Tk / 显示环境，则退化为无界面后台运行）

开发调试时也可直接运行：  python mac_app.py
"""

import os
import sys
import time
import socket
import threading
import webbrowser

import waitress
from app import app  # app.py 与本文件同目录（打包后同在 Contents/Resources）


def find_free_port(start: int = 5000, host: str = "127.0.0.1") -> int:
    """从 start 开始找一个未被占用的端口。"""
    p = start
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, p)) != 0:
                return p
        p += 1
        if p > start + 100:
            return start  # 极端情况兜底


def open_browser(url: str, delay: float = 1.5):
    time.sleep(delay)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def run_server(host: str, port: int):
    waitress.serve(app, host=host, port=port, _quiet=True)


def main():
    # 支持 --lan：绑定 0.0.0.0，允许同一 WiFi 下的 iPad / 手机访问
    lan = "--lan" in sys.argv
    host = "0.0.0.0" if lan else "127.0.0.1"
    port = find_free_port(5000, host)
    local_url = f"http://127.0.0.1:{port}/"
    lan_addr = ""
    if lan:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            lan_addr = f"http://{s.getsockname()[0]}:{port}/"
            s.close()
        except Exception:
            pass

    # 后台启动 Web 服务
    t = threading.Thread(target=run_server, args=(host, port), daemon=True)
    t.start()

    # 稍后自动打开本机浏览器
    threading.Thread(target=open_browser, args=(local_url,), daemon=True).start()

    # 尝试弹出 Tkinter 状态窗口；失败则无界面后台运行
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.title("PDF Downloader")
        root.resizable(False, False)
        try:
            root.tk.call("tk", "windowingsystem")
        except Exception:
            pass

        info = tk.Label(
            root,
            text=(
                "PDF 下载器已启动\n\n"
                f"本机界面：{local_url}\n"
                + (f"局域网（iPad）：{lan_addr}\n" if lan_addr else "")
                + "下载目录：~/Downloads/PDF_Downloader"
            ),
            justify="left",
            padx=18,
            pady=14,
            font=("-apple-system", 12),
        )
        info.pack()

        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=(0, 12))

        def on_open():
            try:
                webbrowser.open(url)
            except Exception:
                pass

        def on_quit():
            try:
                root.destroy()
            finally:
                os._exit(0)

        tk.Button(btn_frame, text="在浏览器打开", command=on_open, width=14).pack(
            side="left", padx=6
        )
        tk.Button(
            btn_frame, text="退出", command=on_quit, width=14,
            fg="white", bg="#c0392b",
        ).pack(side="left", padx=6)

        # 关掉窗口红叉也退出
        root.protocol("WM_DELETE_WINDOW", on_quit)
        root.mainloop()
    except Exception:
        # 无界面兜底：保持进程存活，直到用户从 Dock 退出
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            os._exit(0)


if __name__ == "__main__":
    main()
