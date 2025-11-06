import os
import shutil
from enum import Enum
from typing import Optional
import os
import shutil
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFormLayout, QLineEdit, QFileDialog, QMessageBox, QDoubleSpinBox, QLabel, QProgressBar, QHBoxLayout
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from ..logging_config import logger
import yaml


class DatasetSplitter:
    """
    数据集划分器
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

            # 创建输出目录结构
            train_dir = os.path.join(output_path, "train")
            val_dir = os.path.join(output_path, "val")
            test_dir = os.path.join(output_path, "test")

            for dir_path in [train_dir, val_dir, test_dir]:
                images_dir = os.path.join(dir_path, "images")
                labels_dir = os.path.join(dir_path, "labels")
                os.makedirs(images_dir, exist_ok=True)
                os.makedirs(labels_dir, exist_ok=True)

            # 获取所有图片文件
            image_files = []
            for root, dirs, files in os.walk(dataset_path):
                # 跳过labels目录
                if "labels" in [os.path.basename(d) for d in dirs]:
                    dirs.remove("labels")
                    
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
                    image_base_name = os.path.splitext(image_name)[0]
                    label_file = os.path.join(dataset_path, "labels", f"{image_base_name}.txt")
                    if os.path.exists(label_file):
                        target_label_path = os.path.join(target_dir, "labels", f"{image_base_name}.txt")
                        shutil.copy2(label_file, target_label_path)

            # 生成类别名称列表
            class_names = DatasetSplitter._get_class_names(dataset_path)
            
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
        class_ids = set()
        for root, dirs, files in os.walk(labels_dir):
            for file in files:
                if file.endswith(".txt"):
                    with open(os.path.join(root, file), 'r') as f:
                        for line in f:
                            if line.strip():
                                class_id = int(line.split()[0])
                                class_ids.add(class_id)

        # 尝试从classes.txt读取类别名称
        classes_file = os.path.join(labels_dir, "classes.txt")
        if os.path.exists(classes_file):
            with open(classes_file, 'r') as f:
                class_names = [line.strip() for line in f.readlines() if line.strip()]
                # 确保类别数量与ID数量匹配
                if len(class_names) <= max(class_ids) if class_ids else 0:
                    logger.warning("classes.txt中的类别数量不足，将补充默认类别名称")
                    while len(class_names) <= max(class_ids):
                        class_names.append(f"class_{len(class_names)}")
        else:
            # 如果没有classes.txt，使用默认命名
            class_names = [f"class_{i}" for i in sorted(class_ids)] if class_ids else ["default"]
            
        return class_names

    @staticmethod
    def _generate_yaml_config(output_path, class_names):
        """
        生成YOLO训练配置文件

        Args:
            output_path (str): 输出路径
            class_names (list): 类别名称列表
        """
        config = {
            'path': os.path.abspath(output_path),  # 数据集根目录
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


class SplitWorker(QThread):
    """
    数据集划分工作线程
    """
    progress_updated = pyqtSignal(int, int)  # current, total
    split_finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, dataset_path, output_path, train_ratio, val_ratio, test_ratio):
        super().__init__()
        self.dataset_path = dataset_path
        self.output_path = output_path
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio

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
            self.split_finished.emit(True, "数据集划分完成")
        except Exception as e:
            self.split_finished.emit(False, f"数据集划分失败: {str(e)}")


class DatasetSplitPanel(QWidget):
    """
    数据集划分面板类
    """

    def __init__(self):
        super().__init__()
        self.worker = None
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
        title_label = QLabel("数据集划分")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        # 添加说明文本
        description_label = QLabel("该工具将数据集划分为训练集、验证集和测试集，并生成符合YOLO格式的目录结构和配置文件。")
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
                background-color: #f5f5f5;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        
        form_layout = QFormLayout(form_container)
        form_layout.setLabelAlignment(Qt.AlignRight)
        form_layout.setHorizontalSpacing(20)
        form_layout.setVerticalSpacing(15)
        
        self.dataset_path_edit = QLineEdit()
        self.dataset_path_edit.setPlaceholderText("请选择数据集路径...")
        self.dataset_path_edit.setMinimumWidth(200)
        self.dataset_path_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
        """)
        
        self.dataset_path_button = QPushButton("选择路径")
        self.dataset_path_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("请选择输出路径...")
        self.output_path_edit.setMinimumWidth(200)
        self.output_path_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
            }
        """)
        
        self.output_path_button = QPushButton("选择路径")
        self.output_path_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
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
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
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
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
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
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
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
        self.split_btn = QPushButton("开始划分")
        self.split_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
            QPushButton:disabled {
                background-color: #BBDEFB;
            }
        """)
        self.split_btn.clicked.connect(self.start_split)
        
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
        layout.addWidget(self.split_btn, alignment=Qt.AlignCenter)
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
        self.worker = SplitWorker(dataset_path, output_path, train_ratio, val_ratio, test_ratio)
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