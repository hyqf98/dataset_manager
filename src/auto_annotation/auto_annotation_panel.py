import os
import time

import cv2
import json
from enum import Enum
from typing import Optional
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem, QDialog, QFormLayout, \
    QComboBox, QLineEdit, QMessageBox, QTextEdit, QCheckBox, QFileDialog, QProgressBar, QLabel, QDialogButtonBox, QHBoxLayout
from PyQt6.QtCore import pyqtSignal, QThread, pyqtSlot, Qt
from ..logging_config import logger
from .model_config_panel import ModelConfigManager, AnnotationType


class AnnotationTask:
    """
    自动标注任务类
    """

    def __init__(self, id: int, model_config_id: int, dataset_path: str,
                 status: str = "未开始", progress: int = 0, total_files: int = 0, processed_files: int = 0,
                 error_message: str = ""):
        self.id = id
        self.model_config_id = model_config_id
        self.dataset_path = dataset_path
        self.status = status  # 未开始, 进行中, 已完成, 已停止, 错误
        self.progress = progress
        self.total_files = total_files
        self.processed_files = processed_files
        self.error_message = error_message  # 添加异常信息字段


class AnnotationTaskManager:
    """
    标注任务管理器
    """

    def __init__(self, tasks_file=None):
        # 将配置文件路径设置为用户目录下的.dataset_m路径
        if tasks_file is None:
            user_home = os.path.expanduser("~")
            dataset_manager_dir = os.path.join(user_home, ".dataset_m")
            # 确保目录存在
            os.makedirs(dataset_manager_dir, exist_ok=True)
            self.tasks_file = os.path.join(dataset_manager_dir, "annotation_tasks.json")

            # 检查并移动旧的配置文件
            old_tasks_file = "annotation_tasks.json"
            if os.path.exists(old_tasks_file) and not os.path.exists(self.tasks_file):
                try:
                    import shutil
                    shutil.move(old_tasks_file, self.tasks_file)
                    logger.info(f"已将旧的标注任务文件从 {old_tasks_file} 移动到 {self.tasks_file}")
                except Exception as e:
                    logger.error(f"移动旧的标注任务文件时出错: {e}")
        else:
            self.tasks_file = tasks_file
        self.tasks = []
        self.load_tasks()

    def load_tasks(self):
        """
        从配置文件加载标注任务
        """
        try:
            if os.path.exists(self.tasks_file):
                with open(self.tasks_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 使用字典解包创建任务对象，确保所有字段都被正确处理
                    self.tasks = []
                    for item in data:
                        # 确保必需的字段存在
                        if all(key in item for key in ['id', 'model_config_id', 'dataset_path']):
                            task = AnnotationTask(
                                id=item['id'],
                                model_config_id=item['model_config_id'],
                                dataset_path=item['dataset_path'],
                                status=item.get('status', '未开始'),
                                progress=item.get('progress', 0),
                                total_files=item.get('total_files', 0),
                                processed_files=item.get('processed_files', 0),
                                error_message=item.get('error_message', '')  # 加载异常信息
                            )
                            self.tasks.append(task)
                        else:
                            logger.warning(f"跳过无效的任务数据: {item}")
                logger.info(f"加载了 {len(self.tasks)} 个标注任务")
            else:
                self.tasks = []
                logger.info("未找到标注任务文件，初始化空的标注任务列表")
        except Exception as e:
            logger.error(f"加载标注任务时出错: {e}")
            self.tasks = []

    def save_tasks(self):
        """
        保存标注任务到配置文件
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.tasks_file), exist_ok=True)

            data = []
            for task in self.tasks:
                task_data = {
                    'id': task.id,
                    'model_config_id': task.model_config_id,
                    'dataset_path': task.dataset_path,
                    'status': task.status,
                    'progress': task.progress,
                    'total_files': task.total_files,
                    'processed_files': task.processed_files,
                    'error_message': getattr(task, 'error_message', '')  # 保存异常信息
                }
                data.append(task_data)

            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存标注任务时出错: {e}")
            QMessageBox.critical(None, "错误", f"保存标注任务时出错: {e}")

    def add_task(self, task: AnnotationTask):
        """
        添加标注任务
        """
        self.tasks.append(task)
        self.save_tasks()
        logger.info(f"添加标注任务: {task.id}")

    def update_task(self, task: AnnotationTask):
        """
        更新标注任务
        """
        for i, t in enumerate(self.tasks):
            if t.id == task.id:
                self.tasks[i] = task
                self.save_tasks()
                logger.info(f"更新标注任务: {task.id}")
                return True
        return False

    def delete_task(self, task_id: int):
        """
        删除标注任务
        """
        self.tasks = [t for t in self.tasks if t.id != task_id]
        self.save_tasks()
        logger.info(f"删除标注任务 ID: {task_id}")

    def get_tasks(self):
        """
        获取所有标注任务
        """
        return self.tasks


class AnnotationTaskForm(QDialog):
    """
    标注任务表单对话框
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model_config_manager = ModelConfigManager()
        self.setWindowTitle("添加自动标注任务")
        self.setModal(True)
        self.resize(500, 200)
        self.init_ui()

    def init_ui(self):
        """
        初始化界面
        """
        layout = QFormLayout(self)

        self.model_combo = QComboBox()
        self.dataset_path_edit = QLineEdit()
        self.dataset_path_button = QPushButton("选择路径")

        # 填充模型配置下拉框
        for model_config in self.model_config_manager.get_model_configs():
            self.model_combo.addItem(model_config.name, model_config.id)

        # 连接信号
        self.dataset_path_button.clicked.connect(self.select_dataset_path)

        # 添加控件到布局
        layout.addRow("模型:", self.model_combo)
        layout.addRow("数据集路径:", self.dataset_path_edit)
        layout.addRow("", self.dataset_path_button)

        # 添加按钮
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def select_dataset_path(self):
        """
        选择数据集路径
        """
        path = QFileDialog.getExistingDirectory(self, "选择数据集路径")
        if path:
            self.dataset_path_edit.setText(path)

    def get_task(self):
        """
        获取表单中的任务对象
        """
        if self.result() == QDialog.DialogCode.Accepted:
            model_config_id = self.model_combo.currentData()
            dataset_path = self.dataset_path_edit.text()

            if not model_config_id or not dataset_path:
                QMessageBox.warning(self, "警告", "请填写所有必填字段!")
                return None

            return AnnotationTask(
                id=int(round(time.time() * 1000)),  # 使用时间戳作为ID
                model_config_id=model_config_id,
                dataset_path=dataset_path
            )
        return None


class AnnotationWorker(QThread):
    """
    标注工作线程
    """
    progress_updated = pyqtSignal(int, int, int)  # processed, total, task_id
    task_finished = pyqtSignal(int, str)  # task_id, status
    log_message = pyqtSignal(str)  # log message
    task_error = pyqtSignal(int, str)  # task_id, error_message
    task_data_updated = pyqtSignal(int, int, int)  # task_id, processed_files, total_files

    def __init__(self, task: AnnotationTask, model_config):
        super().__init__()
        self.task = task
        self.model_config = model_config
        self.is_running = True

    def run(self):
        """
        执行标注任务
        """
        try:
            self.log_message.emit(f"开始标注任务 {self.task.id}")
            self.task.status = "进行中"

            # 获取数据集中的所有图片文件
            image_files = self.get_image_files(self.task.dataset_path)
            self.task.total_files = len(image_files)
            self.task.processed_files = 0

            # 发送任务数据更新信号
            self.task_data_updated.emit(self.task.id, self.task.processed_files, self.task.total_files)

            self.log_message.emit(f"找到 {self.task.total_files} 个图片文件")

            # 创廿labels目录
            labels_dir = os.path.join(self.task.dataset_path, "labels")
            if not os.path.exists(labels_dir):
                os.makedirs(labels_dir)

            # 处理每个图片文件
            for i, image_file in enumerate(image_files):
                if not self.is_running:
                    self.task.status = "已停止"
                    break

                self.process_image(image_file, labels_dir)
                self.task.processed_files = i + 1
                # 发送任务数据更新信号
                self.task_data_updated.emit(self.task.id, self.task.processed_files, self.task.total_files)
                self.progress_updated.emit(self.task.processed_files, self.task.total_files, self.task.id)

            if self.is_running:
                self.task.status = "已完成"
                self.task_finished.emit(self.task.id, "已完成")
                self.log_message.emit(f"标注任务 {self.task.id} 完成")
        except Exception as e:
            self.task.status = "错误"
            error_msg = f"标注任务 {self.task.id} 出错: {str(e)}"
            self.task_error.emit(self.task.id, error_msg)  # 发送错误信号
            self.task_finished.emit(self.task.id, "错误")
            self.log_message.emit(error_msg)
            logger.error(f"标注任务 {self.task.id} 出错: {str(e)}")

    def get_image_files(self, dataset_path):
        """
        获取数据集中的所有图片文件(问题4修复：过滤delete文件夹)
        """
        image_files = []
        for root, dirs, files in os.walk(dataset_path):
            # 问题4修复：过滤delete文件夹
            if "delete" in dirs:
                dirs.remove("delete")
            # 过滤labels目录
            if "labels" in dirs:
                dirs.remove("labels")

            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    image_files.append(os.path.join(root, file))
        return image_files

    def process_image(self, image_file, labels_dir):
        """
        处理单个图片文件
        """
        try:
            # 根据模型类型选择处理方法
            if self.model_config.annotation_type == AnnotationType.YOLO:
                self.process_image_with_yolo(image_file, labels_dir)
            elif self.model_config.annotation_type == AnnotationType.OPENAI:
                self.process_image_with_openai(image_file, labels_dir)
        except Exception as e:
            self.log_message.emit(f"处理图片 {image_file} 时出错: {str(e)}")
            logger.error(f"处理图片 {image_file} 时出错: {str(e)}")

    def process_image_with_yolo(self, image_file, labels_dir):
        """
        使用YOLO模型处理图片
        """
        try:
            # 导入YOLO相关库
            try:
                from ultralytics import YOLO, YOLOWorld
            except ImportError:
                self.log_message.emit(f"未安装ultralytics库，无法使用YOLO模型处理图片: {image_file}")
                return

            # 获取模型路径
            model_path = self.model_config.yolo_model_name

            # 如果模型路径是预定义的模型名称，则使用缓存路径
            predefined_models = ["yolov8n.pt", "yolov8s.pt", "yolov8m.pt", "yolov8l.pt", "yolov8x.pt",
                               "yolov8s-world.pt", "yolov8s-worldv2.pt", "yolov8m-world.pt", "yolov8m-worldv2.pt"]

            if model_path in predefined_models:
                # 使用用户目录下的.dataset_m/models路径
                user_home = os.path.expanduser("~")
                model_cache_dir = os.path.join(user_home, ".dataset_m", "models")
                os.makedirs(model_cache_dir, exist_ok=True)
                model_path = os.path.join(model_cache_dir, model_path)
                # ultralytics会自动下载模型到指定路径

            # 检查模型文件是否存在，如果不存在则让ultralytics自动下载
            if not os.path.exists(model_path):
                self.log_message.emit(f"模型文件不存在，将自动下载: {model_path}")

            # 检查是否是YOLO-World模型(文件名包含world)
            if "world" in os.path.basename(model_path).lower():
                # 使用YOLO-World模型
                model = YOLOWorld(model_path)

                # 获取配置的分类列表
                configured_classes = self.model_config.yolo_classes

                # 如果配置了分类，设置要检测的类别
                if configured_classes:
                    model.set_classes(configured_classes)

                # 进行推理
                results = model(image_file)
            else:
                # 使用普通YOLO模型
                model = YOLO(model_path)

                # 获取配置的分类列表
                configured_classes = self.model_config.yolo_classes

                # 进行推理
                if configured_classes:
                    # 如果配置了分类，使用classes参数进行过滤
                    # 需要将类别名称转换为索引
                    class_indices = []
                    if hasattr(model, 'names'):
                        for class_name in configured_classes:
                            for idx, name in model.names.items():
                                if name == class_name:
                                    class_indices.append(idx)
                                    break

                    if class_indices:
                        results = model(image_file, classes=class_indices)
                    else:
                        results = model(image_file)
                else:
                    # 如果没有配置分类，检测所有类别
                    results = model(image_file)

            # 生成标注文件
            image_name = os.path.splitext(os.path.basename(image_file))[0]
            label_file = os.path.join(labels_dir, f"{image_name}.txt")

            # 获取图片尺寸
            import cv2
            img = cv2.imread(image_file)
            if img is None:
                self.log_message.emit(f"无法读取图片文件: {image_file}")
                return

            img_height, img_width = img.shape[:2]

            # 写入YOLO格式的标注
            with open(label_file, 'w') as f:
                for result in results:
                    boxes = result.boxes
                    if boxes is not None:
                        for box in boxes:
                            # 获取类别ID
                            class_id = int(box.cls)

                            # 获取类别名称
                            if hasattr(result, 'names') and class_id < len(result.names):
                                class_name = result.names[class_id]
                            else:
                                class_name = str(class_id)

                            # 获取边界框坐标
                            x1, y1, x2, y2 = box.xyxy[0].tolist()

                            # 转换为YOLO格式 (中心点x, 中心点y, 宽度, 高度，都是归一化值)
                            x_center = ((x1 + x2) / 2) / img_width
                            y_center = ((y1 + y2) / 2) / img_height
                            width = (x2 - x1) / img_width
                            height = (y2 - y1) / img_height

                            # 写入YOLO格式: class_id x_center y_center width height
                            f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")

            # 生成classes.txt文件(如果配置了分类)
            classes_to_write = []
            if hasattr(self.model_config, 'yolo_classes') and self.model_config.yolo_classes:
                classes_to_write = self.model_config.yolo_classes
            elif hasattr(self.model_config, 'openai_classes') and self.model_config.openai_classes:
                classes_to_write = self.model_config.openai_classes

            if classes_to_write:
                classes_file = os.path.join(labels_dir, 'classes.txt')
                with open(classes_file, 'w') as f:
                    for class_name in classes_to_write:
                        f.write(f"{class_name}\n")

            self.log_message.emit(f"使用YOLO处理图片完成: {image_file}")
        except Exception as e:
            self.log_message.emit(f"使用YOLO处理图片 {image_file} 时出错: {str(e)}")
            logger.error(f"使用YOLO处理图片 {image_file} 时出错: {str(e)}")

    def process_image_with_openai(self, image_file, labels_dir):
        """
        使用OpenAI模型处理图片
        """
        try:
            # 导入OpenAI相关库
            try:
                import openai
                import base64
            except ImportError:
                self.log_message.emit(f"未安装openai库，无法使用OpenAI模型处理图片: {image_file}")
                return

            # 检查必要的配置参数
            api_url = self.model_config.openai_api_url
            api_key = self.model_config.openai_api_key
            model_name = self.model_config.openai_model_name

            if not api_key:
                self.log_message.emit(f"OpenAI API Key未配置")
                return

            if not model_name:
                model_name = "gpt-4-vision-preview"  # 默认模型

            # 设置OpenAI客户端
            client = openai.OpenAI(
                base_url=api_url if api_url else None,
                api_key=api_key
            )

            # 读取并编码图片
            with open(image_file, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')

            # 构建系统提示词，确保输出为YOLO格式
            system_prompt = """你是一个图像识别专家。请分析图像并以YOLO格式输出检测结果。
要求：
1. 只输出YOLO格式的标注，每行一个对象
2. 格式为: <class_id> <x_center> <y_center> <width> <height>
3. 所有坐标值必须是0-1之间的浮点数，表示相对于图像宽度和高度的比例
4. 不要输出任何其他文本，只输出标注数据
5. 如果没有检测到对象，不要输出任何内容"""

            # 添加分类信息到系统提示词
            if hasattr(self.model_config, 'openai_classes') and self.model_config.openai_classes:
                system_prompt += "\n\n可识别的分类包括：\n"
                for i, class_name in enumerate(self.model_config.openai_classes):
                    system_prompt += f"{i}: {class_name}\n"
                system_prompt += "\n请严格按照上述分类编号输出，不要使用其他编号。"

            # 获取用户提示词
            user_prompt = self.model_config.openai_prompt
            if not user_prompt:
                user_prompt = "请检测图像中的常见对象并标注"

            # 发送请求到OpenAI
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500
            )

            # 解析响应
            content = response.choices[0].message.content

            # 生成标注文件
            image_name = os.path.splitext(os.path.basename(image_file))[0]
            label_file = os.path.join(labels_dir, f"{image_name}.txt")

            # 写入标注结果
            with open(label_file, 'w') as f:
                if content:
                    # 验证内容是否为有效的YOLO格式
                    lines = content.strip().split('\n')
                    for line in lines:
                        parts = line.strip().split()
                        if len(parts) == 5:
                            try:
                                # 验证是否为数字
                                class_id = int(float(parts[0]))
                                x_center = float(parts[1])
                                y_center = float(parts[2])
                                width = float(parts[3])
                                height = float(parts[4])

                                # 验证数值范围
                                if 0 <= x_center <= 1 and 0 <= y_center <= 1 and \
                                   0 <= width <= 1 and 0 <= height <= 1:
                                    f.write(f"{line.strip()}\n")
                            except ValueError:
                                # 跳过无效行
                                continue

            # 生成classes.txt文件(如果配置了分类)
            if self.model_config.yolo_classes:
                classes_file = os.path.join(labels_dir, 'classes.txt')
                with open(classes_file, 'w') as f:
                    for class_name in self.model_config.yolo_classes:
                        f.write(f"{class_name}\n")

            self.log_message.emit(f"使用OpenAI处理图片完成: {image_file}")
        except Exception as e:
            self.log_message.emit(f"使用OpenAI处理图片 {image_file} 时出错: {str(e)}")
            logger.error(f"使用OpenAI处理图片 {image_file} 时出错: {str(e)}")

    def stop(self):
        """
        停止标注任务
        """
        self.is_running = False


class AutoAnnotationPanel(QWidget):
    """
    自动标注面板类
    """

    def __init__(self):
        super().__init__()
        self.manager = AnnotationTaskManager()
        self.model_config_manager = ModelConfigManager()
        self.workers = {}  # 存储正在进行的标注任务线程
        self.init_ui()
        # 初始化时不自动加载任务，只在需要时加载

    def init_ui(self):
        """
        初始化界面
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)  # 设置边缘间距
        layout.setSpacing(10)  # 设置控件间距

        # 创建标题
        title_label = QLabel("自动标注任务管理")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 5px;
                border-bottom: 1px solid #ccc;
            }
        """)

        # 创建按钮布局
        button_layout = QHBoxLayout()
        self.add_btn = QPushButton("➕ 添加标注任务")
        self.add_btn.setStyleSheet("""
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

        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
        """)

        self.add_btn.clicked.connect(self.add_task)
        self.refresh_btn.clicked.connect(self.refresh_tasks)

        button_layout.addWidget(self.add_btn)
        button_layout.addWidget(self.refresh_btn)
        button_layout.addStretch()

        # 创建任务列表
        self.task_tree = QTreeWidget()
        # 更新表头，添加操作列
        self.task_tree.setHeaderLabels(["任务ID", "模型", "数据集路径", "状态", "进度", "处理数据", "异常信息", "操作"])
        self.task_tree.setRootIsDecorated(False)
        self.task_tree.setAlternatingRowColors(True)
        # 移除右键菜单
        # self.task_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        # self.task_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.task_tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
                alternate-background-color: #f9f9f9;
            }
            QTreeWidget::item {
                padding: 5px;
            }
            QTreeWidget::item:selected {
                background-color: #e3f2fd;
                color: black;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 5px;
                border: 1px solid #ddd;
                font-weight: bold;
            }
        """)

        # 添加控件到布局
        layout.addWidget(title_label)
        layout.addLayout(button_layout)
        layout.addWidget(self.task_tree)

        # 初始加载任务
        self.refresh_tasks()

    def refresh_tasks(self):
        """
        刷新任务列表
        """
        # 不再自动加载任务，只显示当前内存中的任务
        self.task_tree.clear()

        model_configs = {mc.id: mc for mc in self.model_config_manager.get_model_configs()}

        for task in self.manager.get_tasks():
            item = QTreeWidgetItem(self.task_tree)
            item.setText(0, str(task.id))
            item.setText(1, model_configs.get(task.model_config_id, "未知模型").name if task.model_config_id in model_configs else "未知模型")
            item.setText(2, task.dataset_path)
            item.setText(3, task.status)

            # 显示进度
            if task.total_files > 0:
                progress_text = f"{task.processed_files}/{task.total_files} ({int(task.processed_files/task.total_files*100)}%)"
            else:
                progress_text = "0%"
            item.setText(4, progress_text)

            # 显示处理数据
            process_data_text = f"{task.processed_files}/{task.total_files}"
            item.setText(5, process_data_text)

            # 显示异常信息
            item.setText(6, getattr(task, 'error_message', ''))

            item.setData(0, Qt.ItemDataRole.UserRole, task.id)

            # 添加操作按钮
            self.add_action_buttons(item, task.id, task.status)

        logger.info("刷新自动标注任务列表")

    def add_task(self):
        """
        添加标注任务
        """
        # 检查是否有模型配置
        if not self.model_config_manager.get_model_configs():
            QMessageBox.warning(self, "警告", "请先添加模型配置!")
            return

        form = AnnotationTaskForm(self)
        if form.exec() == QDialog.DialogCode.Accepted:
            task = form.get_task()
            if task:
                self.manager.add_task(task)
                self.refresh_tasks()

    def start_task(self, task_id):
        """
        开始标注任务
        """
        # 查找任务
        task = None
        for t in self.manager.get_tasks():
            if t.id == task_id:
                task = t
                break

        if not task:
            QMessageBox.warning(self, "警告", "未找到指定的任务!")
            return

        # 获取模型配置
        model_config = None
        for mc in self.model_config_manager.get_model_configs():
            if mc.id == task.model_config_id:
                model_config = mc
                break

        if not model_config:
            QMessageBox.warning(self, "警告", "未找到对应的模型配置!")
            return

        # 检查数据集路径
        if not os.path.exists(task.dataset_path):
            QMessageBox.warning(self, "警告", "数据集路径不存在!")
            return

        # 在开始任务前加载数据集信息
        try:
            image_files = self.get_image_files(task.dataset_path)
            task.total_files = len(image_files)
            task.processed_files = 0
            # 清除之前的错误信息
            if hasattr(task, 'error_message'):
                task.error_message = ""
        except Exception as e:
            task.status = "错误"
            task.error_message = f"无法访问数据集: {str(e)}"
            self.manager.update_task(task)
            self.refresh_tasks()
            QMessageBox.critical(self, "错误", f"无法访问数据集: {str(e)}")
            return

        # 创建并启动工作线程
        worker = AnnotationWorker(task, model_config)
        worker.progress_updated.connect(self.update_task_progress)
        worker.task_finished.connect(self.on_task_finished)
        worker.log_message.connect(self.on_log_message)
        worker.task_error.connect(self.on_task_error)  # 连接错误信号
        worker.task_data_updated.connect(self.update_task_data)  # 连接任务数据更新信号

        self.workers[task_id] = worker
        worker.start()

        # 更新任务状态
        task.status = "进行中"
        self.manager.update_task(task)
        self.refresh_tasks()

        logger.info(f"开始标注任务: {task_id}")

    def get_image_files(self, dataset_path):
        """
        获取数据集中的所有图片文件
        """
        image_files = []
        for root, dirs, files in os.walk(dataset_path):
            # 跳过labels目录
            if "labels" in dirs:
                dirs.remove("labels")

            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    image_files.append(os.path.join(root, file))
        return image_files

    def stop_task(self, task_id):
        """
        停止标注任务
        """
        if task_id in self.workers:
            worker = self.workers[task_id]
            worker.stop()
            worker.quit()
            worker.wait()
            del self.workers[task_id]

            # 更新任务状态
            for task in self.manager.get_tasks():
                if task.id == task_id:
                    task.status = "已停止"
                    self.manager.update_task(task)  # 持久化更新
                    break

            self.refresh_tasks()
            logger.info(f"停止标注任务: {task_id}")

    def delete_task(self, task_id):
        """
        删除标注任务
        """
        reply = QMessageBox.question(self, "确认", "确定要删除选中的标注任务吗?\n注意：这不会删除已生成的标注文件。",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            # 停止任务(如果正在进行)
            if task_id in self.workers:
                self.stop_task(task_id)

            self.manager.delete_task(task_id)
            self.refresh_tasks()

    def update_task_data(self, task_id, processed_files, total_files):
        """
        更新任务数据(由Worker线程调用)
        """
        # 更新内存中的任务数据
        for task in self.manager.get_tasks():
            if task.id == task_id:
                task.processed_files = processed_files
                task.total_files = total_files
                self.manager.update_task(task)  # 持久化更新
                break

    def update_task_progress(self, processed, total, task_id):
        """
        更新任务进度
        """
        # 更新内存中的任务数据
        for task in self.manager.get_tasks():
            if task.id == task_id:
                task.processed_files = processed
                task.total_files = total
                self.manager.update_task(task)  # 持久化更新
                break

        # 更新UI中的进度显示
        for i in range(self.task_tree.topLevelItemCount()):
            item = self.task_tree.topLevelItem(i)
            if int(item.text(0)) == task_id:
                if total > 0:
                    progress_text = f"{processed}/{total} ({int(processed/total*100)}%)"
                else:
                    progress_text = "0%"
                item.setText(4, progress_text)
                # 更新处理数据列
                process_data_text = f"{processed}/{total}"
                item.setText(5, process_data_text)
                break

    def on_task_finished(self, task_id, status):
        """
        任务完成时的处理
        """
        # 更新任务状态
        for task in self.manager.get_tasks():
            if task.id == task_id:
                task.status = status
                task.progress = 100 if status == "已完成" else task.progress
                self.manager.update_task(task)  # 持久化更新
                break

        # 移除工作线程
        if task_id in self.workers:
            worker = self.workers[task_id]
            worker.quit()
            worker.wait()
            del self.workers[task_id]

        self.refresh_tasks()
        logger.info(f"标注任务 {task_id} 已完成，状态: {status}")

    def on_task_error(self, task_id, error_message):
        """
        处理任务错误
        """
        # 更新任务的错误信息
        for task in self.manager.get_tasks():
            if task.id == task_id:
                task.status = "错误"
                task.error_message = error_message
                self.manager.update_task(task)  # 持久化更新
                break

        # 停止并清理工作线程
        if task_id in self.workers:
            worker = self.workers[task_id]
            worker.quit()
            worker.wait()
            del self.workers[task_id]

        self.refresh_tasks()
        logger.info(f"标注任务 {task_id} 出错: {error_message}")

    def on_log_message(self, message):
        """
        处理日志消息
        """
        logger.info(f"[自动标注] {message}")

        # 如果日志消息包含错误信息，更新任务的错误信息显示
        if "出错:" in message or "错误:" in message:
            # 提取任务ID和错误信息
            # 格例: [自动标注] 标注任务 12345 出错: Some error message
            # 或者: [自动标注] 处理图片 /path/to/image.jpg 时出错: Some error message
            try:
                # 尝试从消息中提取任务ID
                import re
                task_id_match = re.search(r'任务 (\d+)', message)
                if task_id_match:
                    task_id = int(task_id_match.group(1))
                    # 更新对应任务的错误信息
                    for task in self.manager.get_tasks():
                        if task.id == task_id:
                            task.error_message = message
                            self.manager.update_task(task)
                            break
                self.refresh_tasks()
            except Exception as e:
                logger.error(f"处理错误日志消息时出错: {e}")

    def add_action_buttons(self, item, task_id, task_status):
        """
        为指定项添加操作按钮

        Args:
            item: 树形控件项
            task_id: 任务ID
            task_status: 任务状态
        """
        # 创建按钮容器
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(2)

        # 根据任务状态添加开始/停止按钮
        if task_status in ["未开始", "已停止", "错误"]:
            # 开始按钮
            start_btn = QPushButton("开始")
            start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 2px 8px;
                    border-radius: 3px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            start_btn.clicked.connect(lambda: self.start_task(task_id))
            button_layout.addWidget(start_btn)
        elif task_status == "进行中":
            # 停止按钮
            stop_btn = QPushButton("停止")
            stop_btn.setStyleSheet("""
                QPushButton {
                    background-color: #FF9800;
                    color: white;
                    border: none;
                    padding: 2px 8px;
                    border-radius: 3px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #F57C00;
                }
            """)
            stop_btn.clicked.connect(lambda: self.stop_task(task_id))
            button_layout.addWidget(stop_btn)

        # 删除按钮
        delete_btn = QPushButton("删除")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                border: none;
                padding: 2px 8px;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
        """)
        delete_btn.clicked.connect(lambda: self.delete_task(task_id))
        button_layout.addWidget(delete_btn)

        # 将按钮容器设置为项的第8列(操作列)
        self.task_tree.setItemWidget(item, 7, button_widget)
