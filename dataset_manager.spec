
# -*- mode: python ; coding: utf-8 -*-
# Cross-platform spec file for Dataset Manager
# Works on both macOS and Windows

import os
import sys
import platform
from pathlib import Path

# 获取项目根目录（支持跨平台）
project_root = Path(os.path.dirname(os.path.abspath(SPEC)))

# 分析项目结构，添加所有需要的模块
block_cipher = None

# 平台检测
is_mac = platform.system() == 'Darwin'
is_windows = platform.system() == 'Windows'
is_linux = platform.system() == 'Linux'

a = Analysis(
    [str(project_root / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # 添加资源文件
        (str(project_root / 'train_template.py.jinja'), '.'),
        (str(project_root / 'models.txt'), '.'),
        # 如果有图标文件，也添加进来
        # (str(project_root / 'icon.icns'), '.'),  # macOS
        # (str(project_root / 'icon.ico'), '.'),   # Windows
    ],
    hiddenimports=[
        # 确保所有必要的模块都被包含
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtMultimedia',
        'PyQt6.QtMultimediaWidgets',
        'cv2',
        'ultralytics',
        'openai',
        'paramiko',
        'matplotlib',
        'matplotlib.backends.backend_agg',
        'jinja2',
        'yaml',
        'pandas',
        'numpy',
        'PIL',
        'torch',
        'torchvision',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DatasetManager',  # 使用统一的名称
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 无控制台窗口（GUI应用）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'icon.icns') if is_mac and (project_root / 'icon.icns').exists() else
         (str(project_root / 'icon.ico') if is_windows and (project_root / 'icon.ico').exists() else None),
)

# macOS: 创建 .app 包
if is_mac:
    app = BUNDLE(
        exe,
        name='DatasetManager.app',
        icon=str(project_root / 'icon.icns') if (project_root / 'icon.icns').exists() else None,
        bundle_identifier='com.dataset.manager',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': 'True',
            'CFBundleName': 'Dataset Manager',
            'CFBundleDisplayName': 'Dataset Manager',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
        },
    )

# Windows 和 Linux: 直接使用 EXE
# EXE 已经在上面定义，不需要额外配置
