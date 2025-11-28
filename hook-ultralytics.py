# PyInstaller hook for ultralytics
# 减少 ultralytics 打包体积的 hook

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 只收集必要的数据文件
datas = []

# 排除不需要的子模块以减小体积
excludedimports = [
    'torch.distributions',
    'torch.testing',
    'tensorboard',
    'wandb',
    'mlflow',
    'comet_ml',
]
