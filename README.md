# PDF 下载器（macOS / iPad / 手机通用）

一个**完整的、带图形界面的 PDF 搜索 / 下载工具**，基于本地 Flask Web 应用（浏览器即界面，零前端构建）。
已改造成**响应式 PWA**：在 iPad / iPhone 上体验接近原生 App，可「添加到主屏幕」离线缓存壳层。

> ⚠️ iPad / 手机本身不能运行 Python，因此需要一个「后端」跑着这个服务：
> - 方式 A（推荐，零成本）：服务跑在你的 **Mac** 上，iPad 连同一 WiFi 访问；
> - 方式 B（随处可用）：部署到 **Render** 等免费云平台，iPad 在任意网络下访问。
> 文件会保存在运行服务的那台机器/服务器上，再通过界面「打开 / 下载 / 分享」取回。

## 功能
- **ArXiv 检索下载**：按关键词 / 分类（如 `cs.LG`）/ 年份检索，勾选后批量下载 PDF
- **DOI 批量下载**：粘贴一个或多个 DOI / arXiv ID，自动解析开放获取全文
- **网页 PDF 抓取**：给定任意网页 URL，抓取该页所有 PDF 链接并下载
- **文件管理**：查看已下载文件，浏览器一键取回

## 在 macOS 上运行

### 方式一：直接运行（推荐）
1. 安装 Python 3.11+（推荐从 [python.org](https://www.python.org) 或 `brew install python`）
2. 打开「终端」，进入本目录：
   ```bash
   cd pdf-downloader-mac
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python app.py
   ```
3. 浏览器打开 **http://127.0.0.1:5000**（Safari / Chrome 均可）

> 下载目录默认是 `~/Downloads/PDF_Downloader`，可在界面顶部修改。

### 方式二：打包成原生 .app（双击即用）
用 [py2app](https://py2app.readthedocs.io) 把整个工具打成 `PDF Downloader.app`，
双击即可运行——会自动在后台启动服务、打开浏览器到界面，并弹出一个带「在浏览器打开 / 退出」的状态窗口。

**一键构建：**
```bash
bash build_app.sh
```
脚本会自动建虚拟环境、装依赖（含 `py2app`）、执行打包。产物位于 `dist/PDF Downloader.app`。

**或手动构建：**
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt py2app
rm -rf build dist
python setup.py py2app
```

**使用 .app：**
- 把 `dist/PDF Downloader.app` 拖进「应用程序」文件夹，双击运行；
- 首次运行若提示「无法验证开发者」，右键 → 打开，或到
  `系统设置 → 隐私与安全性` 点「仍要打开」；
- 运行时 Dock 会显示该 App，退出即停止本地服务。

**打包原理（`setup.py` 关键点）：**
- `APP = ["mac_app.py"]`：`.app` 入口是 `mac_app.py` 启动器（而非 `app.py`）；
- `DATA_FILES` 把 `templates/index.html` 打包进 `Contents/Resources/templates`，
  使 Flask 在打包后仍能找到页面模板；
- `mac_app.py` 用 `waitress` 在线程里跑服务、自动开浏览器，并用 Tkinter 显示状态窗口。

> 前提：打包机需为 macOS，并安装 [python.org](https://www.python.org) 版 Python 3.11+（自带 Tk，便于状态窗口；用 `brew` 装的 Python 也可，但请确认已装 `tcl-tk`）。py2app 不能跨平台构建，必须在 Mac 上打包。

## 在 iPad / 手机上使用

iPad 上没法直接跑 Python，所以要让服务先跑在某处（Mac 或云端），再用 Safari 打开界面。

### 方式一：iPad 连同一 WiFi，访问你 Mac 上的服务（零成本）

1. 在 **Mac** 上启动服务并允许局域网访问：
   ```bash
   cd pdf-downloader-mac
   source venv/bin/activate        # 若未建虚拟环境先 python3 -m venv venv && source venv/bin/activate
   python app.py --host 0.0.0.0
   ```
   启动后会打印类似：
   ```
   iPad/手机: http://192.168.1.20:5000/  (需与本机在同一 WiFi)
   ```
2. 在 **iPad** 的 Safari 地址栏输入上面那个 `http://192.168.1.x:5000/`，回车打开。
3. 点 Safari 底部的 **分享按钮 → 添加到主屏幕**，桌面就多了一个「PDF 下载器」图标，
   之后像普通 App 一样点开即用（全屏、无浏览器地址栏）。
4. 下载的 PDF 文件实际保存在 Mac 的 `~/Downloads/PDF_Downloader`，可在 iPad 上：
   - **打开**：Safari 内联预览 PDF；
   - **下载 / 分享**：长按或点「分享」，可存到「文件」App、图书，或 AirDrop 给其他设备。

> 用 `.app` 版也想给 iPad 用？双击 `.app` 时加 `--lan` 参数启动（或用终端 `python mac_app.py --lan`），
> 状态窗口会显示局域网地址，iPad 同样可访问。

### 方式二：部署到云端，iPad 在任意网络下访问（推荐 Render 免费版）

云端跑着服务，iPad 在任意 WiFi / 蜂窝网络下用 Safari 打开公网地址即可，体验与方式一一致。

**第 0 步：把代码推到 GitHub（只需做一次）**
```bash
cd pdf-downloader-mac
git init && git add -A && git commit -m "PDF 下载器"
# 在 github.com 新建一个空仓库，然后：
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git branch -M main
git push -u origin main
```

**部署（之后每次改代码重推即自动重新部署）**
1. 打开 [Render](https://render.com) → 注册/登录 → **New → Blueprint**；
2. 关联上面的 GitHub 仓库，Render 会自动读取本目录的 `render.yaml`；
3. 点 **Apply**，等待构建（约 1–2 分钟，自动 `pip install` 并启动 `python -u app.py --host 0.0.0.0`）；
4. 部署完成获得 `https://<服务名>.onrender.com` 公网 HTTPS 地址，iPad 用 Safari 打开；
5. 同样「分享 → 添加到主屏幕」获得 App 体验；HTTPS 下 Service Worker 还会缓存界面壳层，弱网也能打开。

> 说明：Render 免费版会休眠、磁盘为临时存储，适合临时检索/下载并把文件取回本地；
> 如需长期保存，请挂载持久磁盘，或改用方式一（Mac 本地）。云端模式下文件保存在 Render 实例磁盘上，刷新列表取回即可。

## 使用小贴士
- **ArXiv 分类**参考：计算机 `cs.LG`(机器学习) / `cs.CV`(视觉) / `cs.CL`(NLP)；数学 `math.PR`；物理 `physics.comp-ph` 等。
- **DOI 模式**优先走 Unpaywall 开放获取；若出版商要求机构权限，会提示失败——此时可用学校 VPN / 机构代理。
- 大量下载时 ArXiv 有速率限制，工具已内置重试与限速，请勿把数量调到极端值。

## 合规说明
本工具仅用于获取**开放获取 / 你有权访问**的文献。请勿用于批量抓取受版权保护、需付费的内容。
