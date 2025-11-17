#!/usr/bin/env python3
"""
用于将数据集管理器打包成跨平台应用程序的脚本
支持 macOS 和 Windows 平台
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
import platform

def install_pyinstaller():
    """安装 PyInstaller"""
    try:
        import PyInstaller
        print("PyInstaller 已安装")
    except ImportError:
        print("正在安装 PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

def create_spec_file():
    """创建 PyInstaller spec 文件"""
    # 获取项目根目录（使用当前工作目录而不是 __file__）
    project_root = Path.cwd()
    
    spec_content = f'''
# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

# 获取项目根目录
project_root = Path(r"{project_root}")

# 分析项目结构，添加所有需要的模块
block_cipher = None

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
        'jinja2',
        'yaml',
        'pandas',
    ],
    hookspath=[],
    hooksconfig={{}},
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
    name='dataset_manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 设置为 False 以创建无控制台窗口的应用程序
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

'''
    
    # 根据平台添加相应的打包配置
    if platform.system() == "Darwin":  # macOS
        spec_content += f'''
app = BUNDLE(
    exe,
    name='dataset_manager.app',
    icon=None,
    bundle_identifier='com.dataset.manager',
)
'''
    elif platform.system() == "Windows":
        spec_content += '''
# Windows 不需要 BUNDLE，直接使用 EXE
pass
'''
    
    with open('dataset_manager.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    print("已创建 spec 文件: dataset_manager.spec")

def build_app():
    """使用 PyInstaller 构建应用程序"""
    print("开始构建应用程序...")
    
    # 确保在项目根目录
    project_root = Path(__file__).parent.resolve()
    os.chdir(project_root)
    
    # 创建 spec 文件
    create_spec_file()
    
    # 使用 PyInstaller 构建
    try:
        subprocess.check_call([
            sys.executable, "-m", "PyInstaller", 
            "--clean",  # 清理之前的构建
            "dataset_manager.spec"
        ])
        print("应用程序构建完成!")
        
        # 根据平台显示不同的输出路径
        if platform.system() == "Darwin":  # macOS
            print(f"应用程序位置: {project_root / 'dist' / 'dataset_manager.app'}")
        elif platform.system() == "Windows":
            print(f"应用程序位置: {project_root / 'dist' / 'dataset_manager.exe'}")
        else:
            print(f"应用程序位置: {project_root / 'dist'}")
            
    except subprocess.CalledProcessError as e:
        print(f"构建失败: {e}")
        sys.exit(1)

def main():
    """主函数"""
    print("数据集管理器打包脚本")
    print("=" * 30)
    print(f"当前平台: {platform.system()}")
    
    # 安装 PyInstaller
    install_pyinstaller()
    
    # 构建应用程序
    build_app()
    
    print("=" * 30)
    print("打包完成!")

if __name__ == "__main__":
    main()