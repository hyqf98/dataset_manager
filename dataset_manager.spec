
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
        # 只添加必要的资源文件
        (str(project_root / 'train_template.py.jinja'), '.'),
        (str(project_root / 'models.txt'), '.'),
    ],
    hiddenimports=[
        # 只包含必要的模块
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtMultimedia',
        'PyQt6.QtMultimediaWidgets',
    ],
    hookspath=[str(project_root)],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # ===== 开发和测试工具 =====
        'test', 'tests', 'testing', 'unittest', 'pytest', '_pytest',
        'setuptools', 'pip', 'wheel', 'pkg_resources',
        'distutils', 'packaging',
        
        # ===== Jupyter/IPython =====
        'IPython', 'ipykernel', 'jupyter', 'jupyter_client', 'jupyter_core',
        'notebook', 'nbconvert', 'nbformat',
        
        # ===== PyTorch 大型模块 =====
        'torch.distributions', 'torch.testing', 'torch._dynamo',
        'torch.autograd.profiler', 'torch.profiler',
        'torch.utils.tensorboard', 'torch.utils.bottleneck',
        'torch.distributed', 'torch.distributed.rpc',
        'torch.distributed.elastic', 'torch.distributed.pipeline',
        'torch.distributed.fsdp', 'torch.distributed.optim',
        'torch.distributed._shard', 'torch.distributed._tensor',
        'torch.quantization', 'torch._inductor',
        'torch.fx', 'torch.jit', 'torch.onnx',
        
        # ===== TensorBoard 和可视化 =====
        'tensorboard', 'tensorboardX', 'tb_plugin',
        
        # ===== MLflow, Wandb 等追踪工具 =====
        'wandb', 'mlflow', 'comet_ml', 'neptune',
        'clearml', 'aim',
        
        # ===== Matplotlib 后端和工具 =====
        'matplotlib.tests', 'matplotlib.testing',
        'matplotlib.backends.backend_qt5agg',
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends.backend_gtk3',
        'matplotlib.backends.backend_gtk4',
        'matplotlib.backends.backend_wx',
        'matplotlib.backends.backend_macosx',
        'tkinter', 'Tkinter', '_tkinter',
        
        # ===== SciPy 大型模块 =====
        'scipy.stats', 'scipy.sparse', 'scipy.signal',
        'scipy.spatial', 'scipy.optimize', 'scipy.integrate',
        'scipy.interpolate', 'scipy.ndimage',
        
        # ===== CUDA/GPU 相关 =====
        'nvidia', 'nvidia.cuda_runtime', 'nvidia.cudnn',
        'nvidia.cublas', 'nvidia.cufft', 'nvidia.curand',
        'nvidia.cusolver', 'nvidia.cusparse', 'nvidia.nccl',
        'cuda', 'cudnn', 'tensorrt', 'pycuda',
        
        # ===== Triton (PyTorch 编译器) =====
        'triton', 'triton.language', 'triton.compiler',
        
        # ===== PIL/Pillow 不需要的格式 =====
        'PIL.IcnsImagePlugin', 'PIL.MicImagePlugin',
        'PIL.FpxImagePlugin', 'PIL.PsdImagePlugin',
        
        # ===== 文档和示例 =====
        'sphinx', 'docutils', 'alabaster',
        'cv2.data',  # OpenCV 示例数据
        
        # ===== 其他大型库 =====
        'xmlrpc', 'pydoc', 'pydoc_data',
        'multiprocessing.dummy',
    ],
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
    name='DatasetManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # 启用 strip 以移除调试符号
    upx=True,  # 启用 UPX 压缩
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
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
