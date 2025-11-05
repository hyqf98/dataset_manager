# 数据集管理器

一个基于 PyQt5 的数据集管理工具，支持图片和视频文件的浏览、预览和管理。

## 功能特性

1. 三栏布局界面（文件管理、预览、详情），默认比例为2:6:2
2. 文件夹导入和树形结构展示（通过文件选择对话框）
3. 图片预览支持：
   - 原始分辨率显示
   - Ctrl+滚轮缩放
   - Shift+滚轮水平滚动
4. 视频预览（基础支持）
5. 回收站功能：
   - 文件删除到回收站
   - 回收站文件还原
   - 彻底删除文件
6. 自动标注功能：
   - 支持YOLO模型自动标注
   - 支持OpenAI视觉模型自动标注
   - 生成YOLO格式标注文件

## 环境要求

- Python >= 3.9
- opencv-python
- PyQt5
- ultralytics (用于YOLO模型)
- openai (用于OpenAI模型)

## 安装依赖

### 推荐使用 uv（更快的包管理器）
```bash
# 首次安装依赖
uv sync

# 如果遇到平台兼容性问题
uv sync --python-platform win32
```

### 传统方式安装
```bash
pip install -r requirements.txt
```

### 不同操作系统的安装说明

#### Windows
使用 uv 安装（推荐）：
```bash
uv sync
```

如果遇到 PyQt5 兼容性问题，可以尝试：
```bash
uv sync --python-platform win32
```

传统 pip 安装：
```bash
pip install -r requirements.txt
```

注意：在某些Windows系统上，可能需要安装Microsoft C++ Build Tools

#### macOS
如果遇到 PyQt5 安装问题，可以尝试：
```bash
brew install pyqt5
```
或者使用 conda:
```bash
conda install pyqt
```

#### Linux
在运行 pip install 之前，建议先安装系统依赖：

Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install python3-pyqt5 libgl1-mesa-glx libglib2.0-0 python3-dev
```

CentOS/RHEL/Fedora:
```bash
sudo yum install python3-qt5 mesa-libGL glib2-devel python3-devel
# Fedora 用户可使用 dnf 替代 yum
```

如果遇到 opencv-python 安装问题，可以尝试：
```bash
sudo apt-get install python3-opencv
```

## 运行应用

### 使用 uv 运行（推荐）
```bash
uv run main.py
```

### 使用 Python 直接运行
```bash
python main.py
```

如果使用 uv 时遇到平台兼容性问题，可以尝试指定平台：
```bash
uv run --python-platform win32 main.py
```

## 使用说明

1. 点击"选择文件夹"按钮通过文件选择对话框选择要管理的数据集文件夹
2. 选中的文件夹会作为根路径显示在左侧文件管理区域
3. 在左侧文件树中双击图片文件进行预览
4. 使用 Ctrl+滚轮 对图片进行缩放
5. 使用 Shift+滚轮 对图片进行水平滚动
6. 使用"移除文件夹"将文件移动到回收站
7. 点击"回收站"管理已删除的文件
8. 配置自动标注模型：
   - 在"模型配置"中添加YOLO或OpenAI模型配置
   - YOLO模型需要指定模型文件路径和分类列表
   - OpenAI模型需要指定API密钥、模型名称和提示词
9. 使用自动标注功能：
   - 在"自动标注"中添加标注任务
   - 选择配置好的模型和数据集路径
   - 开始标注任务
   - 标注结果将保存在数据集目录下的labels文件夹中

## 项目结构

```
dataset_manager/
├── main.py                           # 程序入口
├── src/                              # 源代码目录
│   ├── auto_annotation/              # 自动标注模块
│   │   ├── auto_annotation_panel.py  # 自动标注面板
│   │   └── model_config_panel.py     # 模型配置面板
│   ├── file_manager/                 # 文件管理模块
│   │   ├── __init__.py
│   │   ├── panel.py                  # 文件管理面板
│   │   ├── ui.py                     # 文件管理UI
│   │   ├── events.py                 # 文件管理事件
│   │   └── recycle_bin.py            # 回收站对话框
│   ├── preview/                      # 预览模块
│   │   ├── __init__.py
│   │   ├── panel.py                  # 预览面板
│   │   ├── strategies.py             # 预览策略
│   │   └── player.py                 # 视频播放器
│   ├── ui/                           # 界面模块
│   │   ├── __init__.py
│   │   ├── main_window.py            # 主窗口
│   │   └── details_panel.py          # 详情面板
│   └── __init__.py
├── requirements.txt                  # 依赖列表
└── README.md                         # 说明文档
```