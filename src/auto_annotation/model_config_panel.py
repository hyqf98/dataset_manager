from enum import Enum
from typing import Optional, List
import os
import json
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem, QDialog, QFormLayout, \
    QComboBox, QLineEdit, QMessageBox, QTextEdit, QCheckBox, QDialogButtonBox, QHBoxLayout, QLabel, QFileDialog, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt
from ..logging_config import logger


class AnnotationType(Enum):
    """
    标注类型枚举
    """
    YOLO = "yolo"
    OPENAI = "openai"


class ModelConfig:
    """
    模型配置类
    """

    def __init__(self, name: str, annotation_type: AnnotationType, id: Optional[int] = None, **kwargs):
        self.id = id
        self.name = name
        self.annotation_type = annotation_type
        # YOLO参数
        self.yolo_model_name = kwargs.get('yolo_model_name', '')
        self.yolo_classes = kwargs.get('yolo_classes', [])
        # OpenAI参数
        self.openai_api_url = kwargs.get('openai_api_url', '')
        self.openai_api_key = kwargs.get('openai_api_key', '')
        self.openai_model_name = kwargs.get('openai_model_name', '')
        self.openai_prompt = kwargs.get('openai_prompt', '')
        self.openai_classes = kwargs.get('openai_classes', [])

    def to_dict(self):
        """
        将模型配置对象转换为字典
        """
        return {
            'id': self.id,
            'name': self.name,
            'annotation_type': self.annotation_type.value,
            'yolo_model_name': self.yolo_model_name,
            'yolo_classes': self.yolo_classes,
            'openai_api_url': self.openai_api_url,
            'openai_api_key': self.openai_api_key,
            'openai_model_name': self.openai_model_name,
            'openai_prompt': self.openai_prompt,
            'openai_classes': self.openai_classes
        }

    @classmethod
    def from_dict(cls, data):
        """
        从字典创建模型配置对象
        """
        return cls(
            id=data['id'],
            name=data['name'],
            annotation_type=AnnotationType(data['annotation_type']),
            yolo_model_name=data.get('yolo_model_name', ''),
            yolo_classes=data.get('yolo_classes', []),
            openai_api_url=data.get('openai_api_url', ''),
            openai_api_key=data.get('openai_api_key', ''),
            openai_model_name=data.get('openai_model_name', ''),
            openai_prompt=data.get('openai_prompt', ''),
            openai_classes=data.get('openai_classes', [])
        )


class ModelConfigManager:
    """
    模型配置管理器
    """

    def __init__(self, config_file=None):
        # 将配置文件路径设置为用户目录下的.dataset_m路径
        if config_file is None:
            user_home = os.path.expanduser("~")
            dataset_manager_dir = os.path.join(user_home, ".dataset_m")
            # 确保目录存在
            os.makedirs(dataset_manager_dir, exist_ok=True)
            self.config_file = os.path.join(dataset_manager_dir, "model_configs.json")

            # 检查并移动旧的配置文件
            old_config_file = "model_configs.json"
            if os.path.exists(old_config_file) and not os.path.exists(self.config_file):
                try:
                    import shutil
                    shutil.move(old_config_file, self.config_file)
                    logger.info(f"已将旧的模型配置文件从 {old_config_file} 移动到 {self.config_file}")
                except Exception as e:
                    logger.error(f"移动旧的模型配置文件时出错: {e}")
        else:
            self.config_file = config_file
        self.model_configs = []
        self.load_model_configs()

    def load_model_configs(self):
        """
        从配置文件加载模型配置
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.model_configs = [ModelConfig.from_dict(item) for item in data]
                logger.info(f"加载了 {len(self.model_configs)} 个模型配置")
            else:
                self.model_configs = []
                logger.info("未找到模型配置文件，初始化空的模型配置列表")
        except Exception as e:
            logger.error(f"加载模型配置时出错: {e}")
            self.model_configs = []

    def save_model_configs(self):
        """
        保存模型配置到配置文件
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

            data = [mc.to_dict() for mc in self.model_configs]
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存模型配置时出错: {e}")
            QMessageBox.critical(None, "错误", f"保存模型配置时出错: {e}")

    def add_model_config(self, model_config: ModelConfig):
        """
        添加模型配置
        """
        # 为新模型配置分配ID
        if self.model_configs:
            model_config.id = max(mc.id for mc in self.model_configs) + 1
        else:
            model_config.id = 1

        self.model_configs.append(model_config)
        self.save_model_configs()
        logger.info(f"添加模型配置: {model_config.name}")

    def update_model_config(self, model_config: ModelConfig):
        """
        更新模型配置
        """
        for i, mc in enumerate(self.model_configs):
            if mc.id == model_config.id:
                self.model_configs[i] = model_config
                self.save_model_configs()
                logger.info(f"更新模型配置: {model_config.name}")
                return True
        return False

    def delete_model_config(self, model_config_id: int):
        """
        删除模型配置
        """
        self.model_configs = [mc for mc in self.model_configs if mc.id != model_config_id]
        self.save_model_configs()
        logger.info(f"删除模型配置 ID: {model_config_id}")

    def get_model_configs(self):
        """
        获取所有模型配置
        """
        return self.model_configs


class ModelConfigForm(QDialog):
    """
    模型配置表单对话框
    """

    def __init__(self, parent=None, model_config=None):
        super().__init__(parent)
        self.model_config = model_config
        self.setWindowTitle("添加模型配置" if model_config is None else "编辑模型配置")
        self.setModal(True)
        self.resize(500, 400)
        self.init_ui()

    def init_ui(self):
        """
        初始化界面
        """
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)  # type: ignore
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)  # type: ignore

        self.name_edit = QLineEdit()
        self.type_combo = QComboBox()
        for annotation_type in AnnotationType:
            self.type_combo.addItem(annotation_type.value, annotation_type)

        # YOLO相关控件
        self.yolo_group = QWidget()
        yolo_layout = QFormLayout(self.yolo_group)
        yolo_layout.setContentsMargins(0, 0, 0, 0)
        yolo_layout.setSpacing(10)
        yolo_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)  # type: ignore
        yolo_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)  # type: ignore

        # YOLO模型选择布局(包含浏览按钮)
        yolo_model_layout = QHBoxLayout()
        self.yolo_model_name_combo = QComboBox()
        # 从models.txt文件读取模型列表
        self.load_models_from_file()
        self.yolo_model_name_combo.setEditable(True)
        self.yolo_model_button = QPushButton("浏览...")
        self.yolo_model_button.clicked.connect(self.select_yolo_model_file)
        yolo_model_layout.addWidget(self.yolo_model_name_combo)
        yolo_model_layout.addWidget(self.yolo_model_button)

        self.yolo_classes_edit = QTextEdit()
        self.yolo_classes_edit.setMaximumHeight(100)
        self.yolo_classes_edit.setPlaceholderText("每行输入一个分类，例如：\nperson\ncar\ndog")
        yolo_layout.addRow("YOLO模型名称:", yolo_model_layout)
        yolo_layout.addRow("YOLO分类:", self.yolo_classes_edit)

        # OpenAI相关控件
        self.openai_group = QWidget()
        openai_layout = QFormLayout(self.openai_group)
        openai_layout.setContentsMargins(0, 0, 0, 0)
        openai_layout.setSpacing(10)
        openai_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)  # type: ignore
        openai_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)  # type: ignore

        self.openai_api_url_edit = QLineEdit()
        self.openai_api_key_edit = QLineEdit()
        self.openai_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_model_name_edit = QLineEdit()
        self.openai_prompt_edit = QTextEdit()
        self.openai_prompt_edit.setMaximumHeight(100)
        self.openai_classes_edit = QTextEdit()
        self.openai_classes_edit.setMaximumHeight(100)
        self.openai_classes_edit.setPlaceholderText("每行输入一个分类，例如：\nperson\ncar\ndog")
        openai_layout.addRow("OpenAI API地址:", self.openai_api_url_edit)
        openai_layout.addRow("OpenAI API Key:", self.openai_api_key_edit)
        openai_layout.addRow("OpenAI模型名称:", self.openai_model_name_edit)
        openai_layout.addRow("OpenAI提示词:", self.openai_prompt_edit)
        openai_layout.addRow("OpenAI分类:", self.openai_classes_edit)

        # 设置默认值(如果是编辑模式)
        if self.model_config:
            self.name_edit.setText(self.model_config.name)
            index = self.type_combo.findData(self.model_config.annotation_type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)

            # YOLO参数
            self.yolo_model_name_combo.setEditText(self.model_config.yolo_model_name)
            self.yolo_classes_edit.setPlainText("\n".join(self.model_config.yolo_classes))

            # OpenAI参数
            self.openai_api_url_edit.setText(self.model_config.openai_api_url)
            self.openai_api_key_edit.setText(self.model_config.openai_api_key)
            self.openai_model_name_edit.setText(self.model_config.openai_model_name)
            self.openai_prompt_edit.setPlainText(self.model_config.openai_prompt)
            # OpenAI分类信息
            if hasattr(self.model_config, 'openai_classes'):
                self.openai_classes_edit.setPlainText("\n".join(self.model_config.openai_classes))

        # 连接信号
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)

        # 添加控件到布局
        layout.addRow("模型名称:", self.name_edit)
        layout.addRow("标注类型:", self.type_combo)
        layout.addRow(self.yolo_group)
        layout.addRow(self.openai_group)

        # 添加按钮
        buttons = QDialogButtonBox()
        buttons.setStandardButtons(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)  # type: ignore
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        # 初始状态更新
        self.on_type_changed(self.type_combo.currentIndex())

    def get_model_persist_path(self):
        """
        获取模型文件持久化存储路径
        """
        # 使用用户目录下的.dataset_m文件夹作为持久化路径
        user_home = os.path.expanduser("~")
        dataset_manager_dir = os.path.join(user_home, ".dataset_m")
        # 确保目录存在
        os.makedirs(dataset_manager_dir, exist_ok=True)
        persist_path = os.path.join(dataset_manager_dir, "models")
        return persist_path

    def load_models_from_file(self):
        """
        从models.txt文件加载模型列表
        """
        try:
            # 获取项目根目录
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            models_file = os.path.join(project_root, "models.txt")

            # 如果文件存在，读取模型列表
            if os.path.exists(models_file):
                with open(models_file, 'r', encoding='utf-8') as f:
                    models = [line.strip() for line in f.readlines() if line.strip()]
                    self.yolo_model_name_combo.addItems(models)
            else:
                # 如果文件不存在，使用默认模型列表
                self.yolo_model_name_combo.addItems([
                    "yolov8n.pt",
                    "yolov8s.pt",
                    "yolov8m.pt",
                    "yolov8l.pt",
                    "yolov8x.pt",
                    "yolov8s-world.pt",
                    "yolov8s-worldv2.pt",
                    "yolov8m-world.pt",
                    "yolov8m-worldv2.pt"
                ])

        except Exception as e:
            logger.error(f"加载模型列表失败: {str(e)}")
            # 出现错误时使用默认模型列表
            self.yolo_model_name_combo.addItems([
                "yolov8n.pt",
                "yolov8s.pt",
                "yolov8m.pt",
                "yolov8l.pt",
                "yolov8x.pt",
                "yolov8s-world.pt",
                "yolov8s-worldv2.pt",
                "yolov8m-world.pt",
                "yolov8m-worldv2.pt"
            ])

    def select_yolo_model_file(self):
        """
        选择YOLO模型文件
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择YOLO模型文件",
            "",
            "模型文件 (*.pt *.pth *.h5 *.onnx);;所有文件 (*)"
        )
        if file_path:
            self.yolo_model_name_combo.setEditText(file_path)

    def on_type_changed(self, index):
        """
        标注类型改变时的处理函数
        """
        annotation_type = self.type_combo.itemData(index)

        # 根据类型显示/隐藏相关字段
        if annotation_type == AnnotationType.YOLO:
            self.yolo_group.setVisible(True)
            self.openai_group.setVisible(False)
        elif annotation_type == AnnotationType.OPENAI:
            self.yolo_group.setVisible(False)
            self.openai_group.setVisible(True)
        else:
            # 默认都隐藏
            self.yolo_group.setVisible(False)
            self.openai_group.setVisible(False)

    def get_model_config(self):
        """
        获取表单中的模型配置对象
        """
        if self.result() == QDialog.DialogCode.Accepted:
            annotation_type = self.type_combo.currentData()

            kwargs = {}
            if annotation_type == AnnotationType.YOLO:
                kwargs['yolo_model_name'] = self.yolo_model_name_combo.currentText()
                kwargs['yolo_classes'] = [cls.strip() for cls in self.yolo_classes_edit.toPlainText().split('\n') if cls.strip()]
            elif annotation_type == AnnotationType.OPENAI:
                kwargs['openai_api_url'] = self.openai_api_url_edit.text()
                kwargs['openai_api_key'] = self.openai_api_key_edit.text()
                kwargs['openai_model_name'] = self.openai_model_name_edit.text()
                kwargs['openai_prompt'] = self.openai_prompt_edit.toPlainText()
                kwargs['openai_classes'] = [cls.strip() for cls in self.openai_classes_edit.toPlainText().split('\n') if cls.strip()]

            return ModelConfig(
                name=self.name_edit.text(),
                annotation_type=annotation_type,
                **kwargs
            )
        return None


class ModelConfigPanel(QWidget):
    """
    模型配置面板类
    """

    def __init__(self):
        super().__init__()
        self.manager = ModelConfigManager()
        self.init_ui()

    def init_ui(self):
        """
        初始化界面
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)  # 设置边缘间距
        layout.setSpacing(10)  # 设置控件间距

        # 创建标题
        title_label = QLabel("模型配置管理")
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
        self.add_btn = QPushButton("➕ 添加模型配置")
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

        self.add_btn.clicked.connect(self.add_model_config)
        self.refresh_btn.clicked.connect(self.refresh_model_configs)

        button_layout.addWidget(self.add_btn)
        button_layout.addWidget(self.refresh_btn)
        button_layout.addStretch()

        # 创建模型配置列表
        self.model_config_tree = QTreeWidget()
        self.model_config_tree.setHeaderLabels(["模型名称", "标注类型", "详细信息", "操作"])
        self.model_config_tree.setRootIsDecorated(False)
        self.model_config_tree.setAlternatingRowColors(True)
        # 移除右键菜单和双击事件
        # self.model_config_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        # self.model_config_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.model_config_tree.setStyleSheet("""
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
        layout.addWidget(self.model_config_tree)

        # 初始加载模型配置
        self.refresh_model_configs()

    def refresh_model_configs(self):
        """
        刷新模型配置列表
        """
        self.manager.load_model_configs()
        self.model_config_tree.clear()

        for mc in self.manager.get_model_configs():
            item = QTreeWidgetItem(self.model_config_tree)
            item.setText(0, mc.name)
            item.setText(1, mc.annotation_type.value)

            # 显示详细信息
            if mc.annotation_type == AnnotationType.YOLO:
                detail = f"模型: {mc.yolo_model_name}, 分类: {', '.join(mc.yolo_classes[:3])}"
                if len(mc.yolo_classes) > 3:
                    detail += f"... (共{len(mc.yolo_classes)}个)"
            elif mc.annotation_type == AnnotationType.OPENAI:
                detail = f"API: {mc.openai_api_url}, 模型: {mc.openai_model_name}"
            else:
                detail = "无详细信息"

            item.setText(2, detail)
            item.setData(0, Qt.ItemDataRole.UserRole, mc.id)

            # 添加操作按钮
            self.add_action_buttons(item, mc.id)

        logger.info("刷新模型配置列表")

    def add_model_config(self):
        """
        添加模型配置
        """
        form = ModelConfigForm(self)
        if form.exec() == QDialog.DialogCode.Accepted:
            model_config = form.get_model_config()
            if model_config:
                self.manager.add_model_config(model_config)
                self.refresh_model_configs()

    def update_model_config(self, model_config_id):
        """
        更新模型配置
        """
        # 查找要更新的模型配置
        model_config = None
        for mc in self.manager.get_model_configs():
            if mc.id == model_config_id:
                model_config = mc
                break

        if model_config:
            form = ModelConfigForm(self, model_config)
            if form.exec() == QDialog.DialogCode.Accepted:
                updated_model_config = form.get_model_config()
                if updated_model_config:
                    updated_model_config.id = model_config_id
                    self.manager.update_model_config(updated_model_config)
                    self.refresh_model_configs()

    def delete_model_config(self, model_config_id):
        """
        删除模型配置
        """
        reply = QMessageBox.question(self, "确认", "确定要删除选中的模型配置吗?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.manager.delete_model_config(model_config_id)
            self.refresh_model_configs()

    def add_action_buttons(self, item, model_config_id):
        """
        为指定项添加操作按钮

        Args:
            item: 树形控件项
            model_config_id: 模型配置ID
        """
        # 创建按钮容器
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(2)

        # 编辑按钮
        edit_btn = QPushButton("编辑")
        edit_btn.setStyleSheet("""
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
        edit_btn.clicked.connect(lambda: self.update_model_config(model_config_id))

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
        delete_btn.clicked.connect(lambda: self.delete_model_config(model_config_id))

        button_layout.addWidget(edit_btn)
        button_layout.addWidget(delete_btn)

        # 将按钮容器设置为项的第4列(操作列)
        self.model_config_tree.setItemWidget(item, 3, button_widget)
