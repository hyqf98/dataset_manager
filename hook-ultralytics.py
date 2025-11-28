# PyInstaller hook for ultralytics and torch
# 大幅减少打包体积的激进 hook

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os

# 只收集最小必要的数据文件
datas = []

# 排除所有不需要的子模块
excludedimports = [
    # PyTorch 大型模块
    'torch.distributions',
    'torch.testing',
    'torch._dynamo',
    'torch.autograd.profiler',
    'torch.profiler',
    'torch.utils.tensorboard',
    'torch.utils.bottleneck',
    'torch.distributed',
    'torch.quantization',
    'torch._inductor',
    'torch.fx',
    'torch.jit',
    'torch.onnx',
    
    # 追踪和实验工具
    'tensorboard',
    'wandb',
    'mlflow',
    'comet_ml',
    'neptune',
    'clearml',
    'aim',
    
    # CUDA/GPU
    'nvidia',
    'cuda',
    'cudnn',
    'tensorrt',
    'triton',
    
    # 开发工具
    'pytest',
    'IPython',
    'jupyter',
]

# 排除大型二进制文件的模式
# 这会阻止某些大型 .so/.dll 文件被包含
def filter_binaries(binaries):
    """
    过滤掉不需要的大型二进制文件
    """
    excluded_patterns = [
        'libcudnn',
        'libcublas',
        'libcufft',
        'libnvrtc',
        'libnvToolsExt',
    ]
    
    filtered = []
    for name, path in binaries:
        should_exclude = False
        for pattern in excluded_patterns:
            if pattern in name or pattern in path:
                should_exclude = True
                break
        if not should_exclude:
            filtered.append((name, path))
    
    return filtered
