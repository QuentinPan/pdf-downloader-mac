"""
py2app 打包配置 —— 把 PDF 下载器做成 macOS 原生 .app
用法：
    pip install py2app
    python setup.py py2app
产物：dist/PDF Downloader.app  （双击即运行，自动开浏览器）
"""
from setuptools import setup

APP = ["mac_app.py"]

# 把 templates/index.html 作为数据文件打进 .app 的 Contents/Resources/templates
DATA_FILES = [("templates", ["templates/index.html"])]

OPTIONS = {
    # 显式包含的依赖包，避免 py2app 自动分析遗漏
    "packages": ["flask", "arxiv", "requests", "bs4", "waitress", "feedparser"],
    "includes": ["waitress", "waitress.server", "waitress.channel", "waitress.task"],
    # 不需要 argv 事件模拟（我们自带窗口）
    "argv_emulation": False,
    # 打包时把需要的 dylib / 资源一并带上
    "strip": False,
    # 如需自定义图标，把 .icns 放到本目录并在下方填写 'iconfile': 'app_icon.icns'
    "plist": {
        "CFBundleName": "PDF Downloader",
        "CFBundleDisplayName": "PDF Downloader",
        "CFBundleIdentifier": "com.example.pdfdownloader",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "LSBackgroundOnly": False,
        "NSHighResolutionCapable": True,
        "NSPrincipalClass": "NSApplication",
    },
}

setup(
    app=APP,
    name="PDF Downloader",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
