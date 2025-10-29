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

## 环境要求

- Python >= 3.9
- opencv-python
- PyQt5

## 安装依赖

```bash
pip install -r requirements.txt
```

或者使用 uv:

```bash
uv sync
```

## 运行应用

```bash
python main.py
```

## 使用说明

1. 点击"选择文件夹"按钮通过文件选择对话框选择要管理的数据集文件夹
2. 选中的文件夹会作为根路径显示在左侧文件管理区域
3. 在左侧文件树中双击图片文件进行预览
4. 使用 Ctrl+滚轮 对图片进行缩放
5. 使用 Shift+滚轮 对图片进行水平滚动
6. 使用"移除文件夹"将文件移动到回收站
7. 点击"回收站"管理已删除的文件

## 项目结构

```
dataset_manager/
├── main.py                           # 程序入口
├── src/                              # 源代码目录
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