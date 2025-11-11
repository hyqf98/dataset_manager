import os
import shutil
from enum import Enum
from typing import Optional
import os
import shutil
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFormLayout, QLineEdit, QFileDialog, QMessageBox, QDoubleSpinBox, QLabel, QProgressBar, QHBoxLayout, QCheckBox
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from ..logging_config import logger
import yaml


class DatasetSplitter:
    """
    数据集划分器（用于模型训练）
    """

    @staticmethod
    def split_dataset(dataset_path, output_path, train_ratio, val_ratio, test_ratio):
        """
        划分数据集

        Args:
            dataset_path (str): 数据集路径
            output_path (str): 输出路径
            train_ratio (float): 训练集比例
            val_ratio (float): 验证集比例
            test_ratio (float): 测试集比例

        Returns:
            bool: 是否成功
        """
        try:
            # 检查输入路径是否存在
            if not os.path.exists(dataset_path):
                raise FileNotFoundError(f"数据集路径不存在: {dataset_path}")

            # 检查比例是否有效
            total_ratio = train_ratio + val_ratio + test_ratio
            if abs(total_ratio - 1.0) > 1e-6:
                raise ValueError("训练集、验证集和测试集比例之和必须为1.0")

            # 使用数据集文件夹名称作为导出名称
            dataset_name = os.path.basename(os.path.normpath(dataset_path))
            output_path = os.path.join(output_path, dataset_name)

            # 创建输出目录结构
            train_dir = os.path.join(output_path, "train")
            val_dir = os.path.join(output_path, "val")
            test_dir = os.path.join(output_path, "test")

            for dir_path in [train_dir, val_dir, test_dir]:
                images_dir = os.path.join(dir_path, "images")
                labels_dir = os.path.join(dir_path, "labels")
                os.makedirs(images_dir, exist_ok=True)
                os.makedirs(labels_dir, exist_ok=True)

            # 获取所有图片文件（递归查找所有层级）
            image_files = []
            all_files = []
            for root, dirs, files in os.walk(dataset_path):
                for file in files:
                    all_files.append(os.path.join(root, file))

                for file in files:
                    if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                        image_files.append(os.path.join(root, file))

            if not image_files:
                raise ValueError("数据集中没有找到图片文件")

            # 打乱文件列表
            import random
            random.shuffle(image_files)

            # 计算各部分的数量
            total_files = len(image_files)
            train_count = int(total_files * train_ratio)
            val_count = int(total_files * val_ratio)
            test_count = total_files - train_count - val_count

            # 划分文件
            train_files = image_files[:train_count]
            val_files = image_files[train_count:train_count + val_count]
            test_files = image_files[train_count + val_count:]

            # 复制文件到对应目录
            for file_list, target_dir in [(train_files, train_dir), (val_files, val_dir), (test_files, test_dir)]:
                for image_file in file_list:
                    # 复制图片文件
                    image_name = os.path.basename(image_file)
                    target_image_path = os.path.join(target_dir, "images", image_name)
                    shutil.copy2(image_file, target_image_path)

                    # 复制对应的标签文件（如果存在）
                    # 递归查找所有层级中与图片同名的标注文件
                    image_base_name = os.path.splitext(image_name)[0]
                    label_file = None

                    # 在整个数据集目录中递归查找同名的标注文件
                    for root, dirs, files in os.walk(dataset_path):
                        for file in files:
                            if file == f"{image_base_name}.txt":
                                label_file = os.path.join(root, file)
                                break
                        if label_file:
                            break

                    if label_file and os.path.exists(label_file):
                        target_label_path = os.path.join(target_dir, "labels", f"{image_base_name}.txt")
                        shutil.copy2(label_file, target_label_path)

            # 生成类别名称列表
            class_names = DatasetSplitter._get_class_names(dataset_path)

            # 在每个labels目录下生成classes.txt文件
            DatasetSplitter._generate_classes_files(output_path, class_names)

            # 生成YOLO配置文件
            DatasetSplitter._generate_yaml_config(output_path, class_names)

            logger.info(f"数据集划分完成: 训练集{len(train_files)}张, 验证集{len(val_files)}张, 测试集{len(test_files)}张")
            return True
        except Exception as e:
            logger.error(f"数据集划分失败: {str(e)}")
            raise

    @staticmethod
    def _get_class_names(dataset_path):
        """
        从数据集中获取类别名称列表

        Args:
            dataset_path (str): 数据集路径

        Returns:
            list: 类别名称列表
        """
        class_names = []
        labels_dir = os.path.join(dataset_path, "labels")

        if not os.path.exists(labels_dir):
            logger.warning("未找到labels目录，将使用默认类别")
            return ["default"]

        # 遍历所有标签文件，提取类别ID
        # 递归查找整个数据集目录中的所有标注文件
        class_ids = set()
        for root, dirs, files in os.walk(dataset_path):
            for file in files:
                if file.endswith(".txt"):
                    with open(os.path.join(root, file), 'r') as f:
                        for line in f:
                            if line.strip():
                                try:
                                    class_id = int(line.split()[0])
                                    class_ids.add(class_id)
                                except (ValueError, IndexError):
                                    # 忽略无效的标注行
                                    continue

        # 尝试从classes.txt读取类别名称
        # 递归查找整个数据集目录中的classes.txt文件
        classes_file = None
        for root, dirs, files in os.walk(dataset_path):
            for file in files:
                if file == "classes.txt":
                    classes_file = os.path.join(root, file)
                    break
            if classes_file:
                break

        if classes_file and os.path.exists(classes_file):
            with open(classes_file, 'r') as f:
                class_names = [line.strip() for line in f.readlines() if line.strip()]
                # 确保类别数量与ID数量匹配
                if class_ids and len(class_names) <= max(class_ids):
                    logger.warning("classes.txt中的类别数量不足，将补充默认类别名称")
                    while len(class_names) <= max(class_ids):
                        class_names.append(f"class_{len(class_names)}")
        else:
            # 如果没有classes.txt，使用默认命名
            class_names = [f"class_{i}" for i in sorted(class_ids)] if class_ids else ["default"]

        return class_names

    @staticmethod
    def _generate_classes_files(output_path, class_names):
        """
        在每个数据集划分的labels目录下生成classes.txt文件

        Args:
            output_path (str): 输出路径
            class_names (list): 类别名称列表
        """
        # 在train, val, test的labels目录下都生成classes.txt
        for split in ["train", "val", "test"]:
            labels_dir = os.path.join(output_path, split, "labels")
            if os.path.exists(labels_dir):
                classes_file = os.path.join(labels_dir, "classes.txt")
                with open(classes_file, 'w', encoding='utf-8') as f:
                    for class_name in class_names:
                        f.write(f"{class_name}\n")
                logger.info(f"classes.txt文件已生成: {classes_file}")

    @staticmethod
    def _generate_yaml_config(output_path, class_names):
        """
        生成YOLO训练配置文件

        Args:
            output_path (str): 输出路径
            class_names (list): 类别名称列表
        """
        config = {
            'path': '.',  # 使用相对路径，数据集根目录就是当前目录
            'train': 'train/images',               # 训练集图片路径
            'val': 'val/images',                   # 验证集图片路径
            'test': 'test/images',                 # 测试集图片路径
            'nc': len(class_names),                # 类别数量
            'names': class_names                   # 类别名称列表
        }

        yaml_path = os.path.join(output_path, "train.yml")
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

        logger.info(f"YOLO配置文件已生成: {yaml_path}")

    @staticmethod
    def generate_train_script(output_path, train_params=""):
        """
        生成训练脚本

        Args:
            output_path (str): 输出路径
            train_params (str): 训练参数
        """
        # 确保输出路径存在
        if not os.path.exists(output_path):
            os.makedirs(output_path)

        # 生成train.py脚本
        train_script_content = f"""#!/usr/bin/env python3
# 训练脚本自动生成

import os
import sys
import subprocess
import argparse

# 添加ultralytics到路径
try:
    from ultralytics import YOLO
except ImportError:
    print("请安装ultralytics: pip install ultralytics")
    sys.exit(1)


def train_model():
    # 获取数据配置文件路径（使用相对路径）
    data_yaml = 'train.yml'
    
    # 检查配置文件是否存在
    if not os.path.exists(data_yaml):
        print(f"配置文件不存在: {{data_yaml}}")
        return
    
    # 创建模型实例
    model = YOLO('yolov8n.pt')  # 默认使用yolov8n，可根据需要修改
    
    # 训练参数
    train_args = {{
        'data': data_yaml,
        'epochs': 100,
        'batch': 16,
        'imgsz': 640,
    }}
    
    # 解析自定义参数
    if '{train_params}':
        # 解析参数字符串
        params_str = '{train_params}'
        # 按空格分割参数
        params_parts = params_str.split()
        i = 0
        while i < len(params_parts):
            if params_parts[i].startswith('--'):
                key = params_parts[i][2:]  # 移除--前缀
                if i + 1 < len(params_parts):
                    value = params_parts[i + 1]
                    # 尝试转换为数字
                    try:
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                    except ValueError:
                        pass  # 保持为字符串
                    train_args[key] = value
                    i += 2
                else:
                    i += 1
            else:
                i += 1
    
    print(f"开始训练模型，参数: {{train_args}}")
    
    # 开始训练
    try:
        model.train(**train_args)
        print("训练完成!")
    except Exception as e:
        print(f"训练过程中发生错误: {{e}}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    train_model()
"""

        # 写入训练脚本文件（与train.yml同一路径下）
        train_script_path = os.path.join(output_path, "train.py")
        with open(train_script_path, 'w', encoding='utf-8') as f:
            f.write(train_script_content)

        logger.info(f"训练脚本已生成: {train_script_path}")


class SplitWorker(QThread):
    """
    数据集划分工作线程（用于模型训练）
    """
    progress_updated = pyqtSignal(int, int)  # current, total
    split_finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, dataset_path, output_path, train_ratio, val_ratio, test_ratio, generate_script=False, train_params=""):
        super().__init__()
        self.dataset_path = dataset_path
        self.output_path = output_path
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.generate_script = generate_script
        self.train_params = train_params

    def run(self):
        """
        执行数据集划分
        """
        try:
            # 这里应该调用实际的划分逻辑
            # 为了简化，我们只是模拟进度更新
            splitter = DatasetSplitter()
            splitter.split_dataset(
                self.dataset_path,
                self.output_path,
                self.train_ratio,
                self.val_ratio,
                self.test_ratio
            )

            # 如果需要生成训练脚本
            if self.generate_script:
                dataset_name = os.path.basename(os.path.normpath(self.dataset_path))
                output_path = os.path.join(self.output_path, dataset_name)
                splitter.generate_train_script(output_path, self.train_params)

            self.split_finished.emit(True, "数据集划分完成" + ("并生成训练脚本" if self.generate_script else ""))
        except Exception as e:
            self.split_finished.emit(False, f"数据集划分失败: {str(e)}")


class DatasetSplitPanel(QWidget):
    """
    数据集划分面板类（用于模型训练）
    """

    def __init__(self):
        super().__init__()
        self.worker = None
        self.param_inputs = []  # 存储参数输入框的列表
        self.init_ui()

    def init_ui(self):
        """
        初始化界面
        """
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 添加标题
        title_layout = QHBoxLayout()
        title_label = QLabel("模型训练")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        # 添加说明文本
        description_label = QLabel("该工具将数据集划分为训练集、验证集和测试集，并生成符合YOLO格式的目录结构和配置文件，用于模型训练。")
        description_label.setWordWrap(True)
        description_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 12px;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(description_label)

        # 创建表单容器
        form_container = QWidget()
        form_container.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 20px;
            }
        """)

        form_layout = QFormLayout(form_container)
        form_layout.setHorizontalSpacing(20)
        form_layout.setVerticalSpacing(15)

        self.dataset_path_edit = QLineEdit()
        self.dataset_path_edit.setPlaceholderText("请选择数据集路径...")
        self.dataset_path_edit.setMinimumWidth(200)
        self.dataset_path_edit.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: white;
                selection-background-color: #4CAF50;
            }
            QLineEdit:focus {
                border-color: #4CAF50;
                outline: none;
            }
        """)

        self.dataset_path_button = QPushButton("选择路径")
        self.dataset_path_button.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """)

        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("请选择输出路径...")
        self.output_path_edit.setMinimumWidth(200)
        self.output_path_edit.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: white;
                selection-background-color: #4CAF50;
            }
            QLineEdit:focus {
                border-color: #4CAF50;
                outline: none;
            }
        """)

        self.output_path_button = QPushButton("选择路径")
        self.output_path_button.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """)

        self.train_ratio_spinbox = QDoubleSpinBox()
        self.train_ratio_spinbox.setRange(0.0, 1.0)
        self.train_ratio_spinbox.setSingleStep(0.05)
        self.train_ratio_spinbox.setValue(0.7)
        self.train_ratio_spinbox.setDecimals(2)
        self.train_ratio_spinbox.setStyleSheet("""
            QDoubleSpinBox {
                padding: 8px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: white;
            }
            QDoubleSpinBox:focus {
                border-color: #4CAF50;
                outline: none;
            }
        """)

        self.val_ratio_spinbox = QDoubleSpinBox()
        self.val_ratio_spinbox.setRange(0.0, 1.0)
        self.val_ratio_spinbox.setSingleStep(0.05)
        self.val_ratio_spinbox.setValue(0.2)
        self.val_ratio_spinbox.setDecimals(2)
        self.val_ratio_spinbox.setStyleSheet("""
            QDoubleSpinBox {
                padding: 8px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: white;
            }
            QDoubleSpinBox:focus {
                border-color: #4CAF50;
                outline: none;
            }
        """)

        self.test_ratio_spinbox = QDoubleSpinBox()
        self.test_ratio_spinbox.setRange(0.0, 1.0)
        self.test_ratio_spinbox.setSingleStep(0.05)
        self.test_ratio_spinbox.setValue(0.1)
        self.test_ratio_spinbox.setDecimals(2)
        self.test_ratio_spinbox.setStyleSheet("""
            QDoubleSpinBox {
                padding: 8px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: white;
            }
            QDoubleSpinBox:focus {
                border-color: #4CAF50;
                outline: none;
            }
        """)

        # 连接信号
        self.dataset_path_button.clicked.connect(self.select_dataset_path)
        self.output_path_button.clicked.connect(self.select_output_path)

        # 添加控件到表单布局
        form_layout.addRow("数据集路径:", self.dataset_path_edit)
        form_layout.addRow("", self.dataset_path_button)
        form_layout.addRow("输出路径:", self.output_path_edit)
        form_layout.addRow("", self.output_path_button)
        form_layout.addRow("训练集比例:", self.train_ratio_spinbox)
        form_layout.addRow("验证集比例:", self.val_ratio_spinbox)
        form_layout.addRow("测试集比例:", self.test_ratio_spinbox)

        # 创建按钮
        button_layout = QHBoxLayout()

        # 添加生成训练脚本复选框
        self.generate_train_script_checkbox = QCheckBox("生成训练脚本")
        self.generate_train_script_checkbox.setStyleSheet("""
            QCheckBox {
                font-weight: bold;
                color: #333;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #ced4da;
                background-color: white;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #007bff;
                background-color: #007bff;
                border-radius: 3px;
            }
        """)
        self.generate_train_script_checkbox.stateChanged.connect(self.on_generate_script_changed)

        # 添加参数输入区域（默认隐藏）
        self.params_widget = QWidget()
        self.params_widget.setVisible(False)
        params_layout = QVBoxLayout(self.params_widget)
        params_layout.setContentsMargins(0, 10, 0, 10)

        # 添加参数说明
        params_description = QLabel("使用yolo框架训练参数:")
        params_description.setStyleSheet("""
            QLabel {
                font-weight: bold;
                color: #555;
                margin-bottom: 5px;
            }
        """)
        params_layout.addWidget(params_description)

        # 参数输入容器
        self.params_container = QWidget()
        self.params_container_layout = QVBoxLayout(self.params_container)
        self.params_container_layout.setContentsMargins(0, 0, 0, 0)
        self.params_container_layout.setSpacing(5)
        params_layout.addWidget(self.params_container)

        # 添加参数按钮
        add_param_layout = QHBoxLayout()
        self.add_param_button = QPushButton("➕ 添加参数")
        self.add_param_button.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #138496;
            }
            QPushButton:pressed {
                background-color: #117a8b;
            }
        """)
        self.add_param_button.clicked.connect(self.add_parameter)
        add_param_layout.addStretch()
        add_param_layout.addWidget(self.add_param_button)
        params_layout.addLayout(add_param_layout)

        # 存储参数输入框的列表
        self.param_inputs = []

        self.split_btn = QPushButton("开始划分")
        self.split_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.split_btn.clicked.connect(self.start_split)

        # 添加控件到按钮布局
        button_layout.addWidget(self.generate_train_script_checkbox)
        button_layout.addWidget(self.params_widget)
        button_layout.addStretch()
        button_layout.addWidget(self.split_btn)

        # 创建进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(25)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
                background-color: #f0f0f0;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)

        # 添加控件到主布局
        layout.addWidget(form_container)
        layout.addLayout(button_layout)
        layout.addWidget(self.progress_bar)

        # 添加输出说明
        output_description = QLabel("输出格式: \n"
                                   "├── train/\n"
                                   "│   ├── images/\n"
                                   "│   └── labels/\n"
                                   "├── val/\n"
                                   "│   ├── images/\n"
                                   "│   └── labels/\n"
                                   "├── test/\n"
                                   "│   ├── images/\n"
                                   "│   └── labels/\n"
                                   "└── train.yml")
        output_description.setStyleSheet("""
            QLabel {
                font-family: monospace;
                font-size: 11px;
                color: #555555;
                background-color: #f8f8f8;
                padding: 10px;
                border-radius: 4px;
                margin-top: 10px;
            }
        """)
        layout.addWidget(output_description)

        layout.addStretch()

        self.setLayout(layout)

    def on_generate_script_changed(self, state):
        """
        处理生成训练脚本复选框状态变化
        """
        is_checked = state == Qt.CheckState.Checked
        self.params_widget.setVisible(is_checked)

        # 如果是选中状态且没有参数输入框，则添加一个默认的
        if is_checked and not self.param_inputs:
            self.add_parameter()

    def add_parameter(self):
        """
        添加参数输入框
        """
        # 创建参数输入行
        param_row = QWidget()
        row_layout = QHBoxLayout(param_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)

        # 参数键输入框
        key_edit = QLineEdit()
        key_edit.setPlaceholderText("参数名，例如: epochs")
        key_edit.setStyleSheet("""
            QLineEdit {
                padding: 6px;
                border: 1px solid #ced4da;
                border-radius: 3px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #007bff;
                outline: none;
            }
        """)

        # 参数值输入框
        value_edit = QLineEdit()
        value_edit.setPlaceholderText("参数值，例如: 100")
        value_edit.setStyleSheet("""
            QLineEdit {
                padding: 6px;
                border: 1px solid #ced4da;
                border-radius: 3px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #007bff;
                outline: none;
            }
        """)

        # 删除按钮
        remove_btn = QPushButton("❌")
        remove_btn.setFixedSize(25, 25)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:pressed {
                background-color: #bd2130;
            }
        """)

        # 存储引用以便后续操作
        param_data = {
            'widget': param_row,
            'key_edit': key_edit,
            'value_edit': value_edit,
            'remove_btn': remove_btn
        }

        # 连接删除按钮
        remove_btn.clicked.connect(lambda: self.remove_parameter(param_data))

        # 添加到布局
        row_layout.addWidget(QLabel("参数名:"))
        row_layout.addWidget(key_edit, 2)
        row_layout.addWidget(QLabel("参数值:"))
        row_layout.addWidget(value_edit, 3)
        row_layout.addWidget(remove_btn)

        # 添加到参数容器
        self.params_container_layout.addWidget(param_row)

        # 添加到参数输入列表
        self.param_inputs.append(param_data)

    def remove_parameter(self, param_data):
        """
        删除参数输入框

        Args:
            param_data (dict): 参数数据字典
        """
        # 从布局中移除
        self.params_container_layout.removeWidget(param_data['widget'])

        # 从参数输入列表中移除
        if param_data in self.param_inputs:
            self.param_inputs.remove(param_data)

        # 删除控件
        param_data['widget'].deleteLater()

        # 如果没有参数输入框了，添加一个默认的
        if not self.param_inputs:
            self.add_parameter()

    def select_dataset_path(self):
        """
        选择数据集路径
        """
        path = QFileDialog.getExistingDirectory(self, "选择数据集路径")
        if path:
            self.dataset_path_edit.setText(path)

    def select_output_path(self):
        """
        选择输出路径
        """
        path = QFileDialog.getExistingDirectory(self, "选择输出路径")
        if path:
            self.output_path_edit.setText(path)

    def start_split(self):
        """
        开始划分数据集
        """
        dataset_path = self.dataset_path_edit.text()
        output_path = self.output_path_edit.text()
        train_ratio = self.train_ratio_spinbox.value()
        val_ratio = self.val_ratio_spinbox.value()
        test_ratio = self.test_ratio_spinbox.value()

        # 获取训练脚本选项
        generate_script = self.generate_train_script_checkbox.isChecked()
        train_params = ""

        # 如果需要生成脚本，收集参数
        if generate_script:
            # 收集所有参数
            params_list = []
            for param_data in self.param_inputs:
                key = param_data['key_edit'].text().strip()
                value = param_data['value_edit'].text().strip()

                # 只有当键和值都不为空时才添加
                if key and value:
                    # 尝试转换数值类型
                    try:
                        # 尝试转换为整数
                        if '.' not in value:
                            value = int(value)
                        else:
                            # 尝试转换为浮点数
                            value = float(value)
                    except ValueError:
                        # 保持为字符串
                        pass

                    params_list.append(f"--{key} {value}")

            train_params = " ".join(params_list)

        # 验证输入
        if not dataset_path:
            QMessageBox.warning(self, "警告", "请选择数据集路径!")
            return

        if not output_path:
            QMessageBox.warning(self, "警告", "请选择输出路径!")
            return

        if not os.path.exists(dataset_path):
            QMessageBox.warning(self, "警告", "数据集路径不存在!")
            return

        # 检查比例之和是否为1
        total_ratio = train_ratio + val_ratio + test_ratio
        if abs(total_ratio - 1.0) > 1e-6:
            QMessageBox.warning(self, "警告", "训练集、验证集和测试集比例之和必须为1.0!")
            return

        # 禁用按钮，显示进度条
        self.split_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 设置为不确定模式

        # 创建并启动工作线程
        self.worker = SplitWorker(dataset_path, output_path, train_ratio, val_ratio, test_ratio, generate_script, train_params)
        self.worker.split_finished.connect(self.on_split_finished)
        self.worker.start()

    def on_split_finished(self, success, message):
        """
        数据集划分完成时的处理
        """
        # 启用按钮，隐藏进度条
        self.split_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        if success:
            QMessageBox.information(self, "成功", message)
            logger.info(message)
        else:
            QMessageBox.critical(self, "错误", message)
            logger.error(message)
