from enum import Enum
from typing import Optional
import os
import json
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem, QDialog, QFormLayout, \
    QComboBox, QLineEdit, QMessageBox, QFileDialog, QDialogButtonBox, QHBoxLayout, QLabel
from PyQt5.QtCore import pyqtSignal, Qt
from ..logging_config import logger


class DataSourceType(Enum):
    """
    数据源类型枚举
    """
    LIVE_STREAM = "直播源"


class DataSource:
    """
    数据源类，表示一个数据源配置
    """

    def __init__(self, name: str, source_type: DataSourceType, stream_url: str, save_path: str, id: Optional[int] = None):
        self.id = id
        self.name = name
        self.source_type = source_type
        self.stream_url = stream_url
        self.save_path = save_path

    def to_dict(self):
        """
        将数据源对象转换为字典
        """
        return {
            'id': self.id,
            'name': self.name,
            'source_type': self.source_type.value,
            'stream_url': self.stream_url,
            'save_path': self.save_path
        }

    @classmethod
    def from_dict(cls, data):
        """
        从字典创建数据源对象
        """
        return cls(
            id=data['id'],
            name=data['name'],
            source_type=DataSourceType(data['source_type']),
            stream_url=data['stream_url'],
            save_path=data['save_path']
        )


class DataSourceManager:
    """
    数据源管理器，负责数据源的增删改查
    """

    def __init__(self, config_file=None):
        # 将配置文件路径设置为用户目录下的.dataset_m路径
        if config_file is None:
            user_home = os.path.expanduser("~")
            dataset_manager_dir = os.path.join(user_home, ".dataset_m")
            # 确保目录存在
            os.makedirs(dataset_manager_dir, exist_ok=True)
            self.config_file = os.path.join(dataset_manager_dir, "data_sources.json")
        else:
            self.config_file = config_file
            
        self.data_sources = []
        self.load_data_sources()

    def load_data_sources(self):
        """
        从配置文件加载数据源
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.data_sources = [DataSource.from_dict(item) for item in data]
                logger.info(f"加载了 {len(self.data_sources)} 个数据源")
            else:
                self.data_sources = []
                logger.info("未找到数据源配置文件，初始化空的数据源列表")
        except Exception as e:
            logger.error(f"加载数据源时出错: {e}")
            self.data_sources = []

    def save_data_sources(self):
        """
        保存数据源到配置文件
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            data = [ds.to_dict() for ds in self.data_sources]
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"保存了 {len(self.data_sources)} 个数据源到配置文件")
        except Exception as e:
            logger.error(f"保存数据源时出错: {e}")
            QMessageBox.critical(None, "错误", f"保存数据源时出错: {e}")

    def add_data_source(self, data_source: DataSource):
        """
        添加数据源
        """
        # 为新数据源分配ID
        if self.data_sources:
            data_source.id = max(ds.id for ds in self.data_sources) + 1
        else:
            data_source.id = 1

        self.data_sources.append(data_source)
        self.save_data_sources()
        logger.info(f"添加数据源: {data_source.name}")

    def update_data_source(self, data_source: DataSource):
        """
        更新数据源
        """
        for i, ds in enumerate(self.data_sources):
            if ds.id == data_source.id:
                self.data_sources[i] = data_source
                self.save_data_sources()
                logger.info(f"更新数据源: {data_source.name}")
                return True
        return False

    def delete_data_source(self, data_source_id: int):
        """
        删除数据源
        """
        self.data_sources = [ds for ds in self.data_sources if ds.id != data_source_id]
        self.save_data_sources()
        logger.info(f"删除数据源 ID: {data_source_id}")

    def get_data_sources(self):
        """
        获取所有数据源
        """
        return self.data_sources


class DataSourceForm(QDialog):
    """
    数据源表单对话框
    """

    def __init__(self, parent=None, data_source=None):
        super().__init__(parent)
        self.data_source = data_source
        self.setWindowTitle("添加数据源" if data_source is None else "编辑数据源")
        self.setModal(True)
        self.resize(400, 200)
        self.init_ui()

    def init_ui(self):
        """
        初始化界面
        """
        layout = QFormLayout(self)

        self.type_combo = QComboBox()
        for source_type in DataSourceType:
            self.type_combo.addItem(source_type.value, source_type)

        self.stream_url_edit = QLineEdit()
        self.save_path_edit = QLineEdit()
        self.save_path_button = QPushButton("选择路径")

        # 设置默认值（如果是编辑模式）
        if self.data_source:
            index = self.type_combo.findData(self.data_source.source_type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)
            self.stream_url_edit.setText(self.data_source.stream_url)
            self.save_path_edit.setText(self.data_source.save_path)

        # 连接信号
        self.save_path_button.clicked.connect(self.select_save_path)

        # 添加控件到布局
        layout.addRow("数据源类型:", self.type_combo)
        layout.addRow("直播源地址:", self.stream_url_edit)
        layout.addRow("文件保存地址:", self.save_path_edit)
        layout.addRow("", self.save_path_button)

        # 添加按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def select_save_path(self):
        """
        选择保存路径
        """
        path = QFileDialog.getExistingDirectory(self, "选择文件保存路径")
        if path:
            self.save_path_edit.setText(path)

    def get_data_source(self):
        """
        获取表单中的数据源对象
        """
        if self.result() == QDialog.Accepted:
            name = f"数据源_{self.type_combo.currentData().value}"
            return DataSource(
                name=name,
                source_type=self.type_combo.currentData(),
                stream_url=self.stream_url_edit.text(),
                save_path=self.save_path_edit.text()
            )
        return None


class DataSourcePanel(QWidget):
    """
    数据源面板类
    """

    # 定义播放信号，当用户点击播放按钮时发出
    play_requested = pyqtSignal(DataSource)

    def __init__(self):
        super().__init__()
        self.manager = DataSourceManager()
        self.init_ui()
        self.dialog_parent = None  # 添加对父对话框的引用

    def init_ui(self):
        """
        初始化界面
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)  # 设置边缘间距
        layout.setSpacing(10)  # 设置控件间距

        # 创建标题
        title_label = QLabel("数据源管理")
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
        self.add_btn = QPushButton("➕ 添加数据源")
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

        self.add_btn.clicked.connect(self.add_data_source)
        self.refresh_btn.clicked.connect(self.refresh_data_sources)

        button_layout.addWidget(self.add_btn)
        button_layout.addWidget(self.refresh_btn)
        button_layout.addStretch()

        # 创建数据源列表
        self.data_source_tree = QTreeWidget()
        self.data_source_tree.setHeaderLabels(["名称", "类型", "直播源地址", "保存路径"])
        self.data_source_tree.setRootIsDecorated(False)
        self.data_source_tree.setAlternatingRowColors(True)
        self.data_source_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.data_source_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.data_source_tree.setStyleSheet("""
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

        # 连接双击事件
        self.data_source_tree.itemDoubleClicked.connect(self.play_data_source)

        # 添加控件到布局
        layout.addWidget(title_label)
        layout.addLayout(button_layout)
        layout.addWidget(self.data_source_tree)

        # 初始加载数据源
        self.refresh_data_sources()

    def refresh_data_sources(self):
        """
        刷新数据源列表
        """
        self.manager.load_data_sources()
        self.data_source_tree.clear()

        for ds in self.manager.get_data_sources():
            item = QTreeWidgetItem(self.data_source_tree)
            item.setText(0, ds.name)
            item.setText(1, ds.source_type.value)
            item.setText(2, ds.stream_url)
            item.setText(3, ds.save_path)
            item.setData(0, Qt.UserRole, ds.id)

        logger.info("刷新数据源列表")

    def add_data_source(self):
        """
        添加数据源
        """
        form = DataSourceForm(self)
        if form.exec_() == QDialog.Accepted:
            data_source = form.get_data_source()
            if data_source:
                self.manager.add_data_source(data_source)
                self.refresh_data_sources()

    def update_data_source(self, data_source_id):
        """
        更新数据源
        """
        # 查找要更新的数据源
        data_source = None
        for ds in self.manager.get_data_sources():
            if ds.id == data_source_id:
                data_source = ds
                break

        if data_source:
            form = DataSourceForm(self, data_source)
            if form.exec_() == QDialog.Accepted:
                updated_data_source = form.get_data_source()
                if updated_data_source:
                    updated_data_source.id = data_source_id
                    self.manager.update_data_source(updated_data_source)
                    self.refresh_data_sources()

    def delete_data_source(self, data_source_id):
        """
        删除数据源
        """
        reply = QMessageBox.question(self, "确认", "确定要删除选中的数据源吗?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.manager.delete_data_source(data_source_id)
            self.refresh_data_sources()

    def show_context_menu(self, position):
        """
        显示右键菜单
        """
        item = self.data_source_tree.itemAt(position)
        if not item:
            return

        data_source_id = item.data(0, Qt.UserRole)

        from PyQt5.QtWidgets import QMenu, QAction
        menu = QMenu(self)

        # 添加播放操作（仅对直播源有效）
        play_action = QAction("▶ 播放", self)
        play_action.triggered.connect(lambda: self.play_data_source(item))
        menu.addAction(play_action)

        # 添加编辑操作
        edit_action = QAction("✏️ 编辑", self)
        edit_action.triggered.connect(lambda: self.update_data_source(data_source_id))
        menu.addAction(edit_action)

        # 添加删除操作
        delete_action = QAction("🗑️ 删除", self)
        delete_action.triggered.connect(lambda: self.delete_data_source(data_source_id))
        menu.addAction(delete_action)

        menu.exec_(self.data_source_tree.viewport().mapToGlobal(position))

    def play_data_source(self, item, column=None):
        """
        播放数据源
        """
        data_source_id = item.data(0, Qt.UserRole)

        # 查找对应的数据源
        for ds in self.manager.get_data_sources():
            if ds.id == data_source_id:
                # 发出播放信号
                self.play_requested.emit(ds)
                # 关闭数据源管理面板对话框
                if self.dialog_parent and isinstance(self.dialog_parent, QDialog):
                    self.dialog_parent.accept()
                break