#!/bin/bash
# 一键把 PDF 下载器打包成 macOS .app
# 用法：  bash build_app.sh
set -e
cd "$(dirname "$0")"

echo "==> 创建虚拟环境（推荐，避免污染系统 Python）"
python3 -m venv venv 2>/dev/null || true
# shellcheck disable=SC1091
source venv/bin/activate

echo "==> 安装依赖 + py2app"
pip install --upgrade pip
pip install -r requirements.txt
pip install py2app

echo "==> 清理旧构建"
rm -rf build dist

echo "==> 开始打包（首次较慢，需下载/分析依赖）"
python setup.py py2app

echo ""
echo "✅ 完成！.app 位于："
echo "   $(pwd)/dist/PDF Downloader.app"
echo "双击即可运行，会自动打开浏览器到本地界面。"
