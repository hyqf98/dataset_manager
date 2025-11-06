from typing import Optional
import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem, \
    QDialog, QFormLayout, QLineEdit, QMessageBox, QDialogButtonBox, QHBoxLayout, QLabel, \
    QSpinBox, QFileDialog, QMenu, QAction, QHeaderView
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QContextMenuEvent
from .server_config import ServerConfig, ServerConfigManager
from .ssh_client import SSHClient
from .file_transfer_dialog import FileTransferDialog, RemoteBrowserDialog
from ..logging_config import logger


class ServerConfigForm(QDialog):
    """
    服务器配置表单对话框
    """

    def __init__(self, parent=None, server_config=None):
        super().__init__(parent)
        self.server_config = server_config
        self.setWindowTitle("添加服务器配置" if server_config is None else "编辑服务器配置")
        self.setModal(True)
        self.resize(400, 350)
        self.init_ui()

    def init_ui(self):
        """
        初始化界面
        """
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.setLabelAlignment(Qt.AlignRight)  # type: ignore
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)  # type: ignore

        self.name_edit = QLineEdit()
        self.host_edit = QLineEdit()
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(22)
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.private_key_edit = QLineEdit()
        self.private_key_button = QPushButton("浏览...")

        # 设置默认值（如果是编辑模式）
        if self.server_config:
            self.name_edit.setText(self.server_config.name)
            self.host_edit.setText(self.server_config.host)
            self.port_spin.setValue(self.server_config.port)
            self.username_edit.setText(self.server_config.username)
            self.password_edit.setText(self.server_config.password)
            self.private_key_edit.setText(self.server_config.private_key_path)

        # 连接信号
        self.private_key_button.clicked.connect(self.select_private_key_file)

        # 添加控件到布局
        layout.addRow("服务器名称:", self.name_edit)
        layout.addRow("主机地址:", self.host_edit)
        layout.addRow("端口:", self.port_spin)
        layout.addRow("用户名:", self.username_edit)
        layout.addRow("密码:", self.password_edit)
        
        # 私钥文件选择布局
        private_key_layout = QHBoxLayout()
        private_key_layout.addWidget(self.private_key_edit)
        private_key_layout.addWidget(self.private_key_button)
        layout.addRow("私钥文件:", private_key_layout)

        # 添加按钮
        buttons = QDialogButtonBox()
        buttons.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)  # type: ignore
        
        # 添加测试连接按钮
        self.test_connection_button = QPushButton("测试连接")
        self.test_connection_button.clicked.connect(self.test_connection)
        buttons.addButton(self.test_connection_button, QDialogButtonBox.ActionRole)  # type: ignore
        
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def select_private_key_file(self):
        """
        选择私钥文件
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "选择私钥文件", 
            "", 
            "私钥文件 (*.pem *.key);;所有文件 (*)"
        )
        if file_path:
            self.private_key_edit.setText(file_path)

    def test_connection(self):
        """
        测试服务器连接
        """
        # 创建临时服务器配置对象用于测试
        temp_config = ServerConfig(
            name=self.name_edit.text() or "测试连接",
            host=self.host_edit.text(),
            port=self.port_spin.value(),
            username=self.username_edit.text(),
            password=self.password_edit.text(),
            private_key_path=self.private_key_edit.text()
        )
        
        # 验证必要字段
        if not temp_config.host:
            QMessageBox.warning(self, "警告", "请输入主机地址。")
            return
            
        if not temp_config.username:
            QMessageBox.warning(self, "警告", "请输入用户名。")
            return
            
        if not temp_config.password and not temp_config.private_key_path:
            QMessageBox.warning(self, "警告", "请输入密码或选择私钥文件。")
            return

        try:
            # 创建SSH客户端并测试连接
            ssh_client = SSHClient(temp_config)
            if ssh_client.connect_to_server():
                ssh_client.disconnect_from_server()
                QMessageBox.information(self, "连接成功", "服务器连接测试成功！")
            else:
                QMessageBox.critical(self, "连接失败", "无法连接到服务器，请检查配置信息。")
        except Exception as e:
            QMessageBox.critical(self, "连接错误", f"连接服务器时发生错误：{str(e)}")

    def get_server_config(self):
        """
        获取表单中的服务器配置对象
        """
        if self.result() == QDialog.Accepted:  # type: ignore
            return ServerConfig(
                name=self.name_edit.text(),
                host=self.host_edit.text(),
                port=self.port_spin.value(),
                username=self.username_edit.text(),
                password=self.password_edit.text(),
                private_key_path=self.private_key_edit.text()
            )
        return None


class ServerConfigPanel(QWidget):
    """
    服务器配置面板类
    """

    def __init__(self):
        super().__init__()
        self.manager = ServerConfigManager()
        self.init_ui()

    def init_ui(self):
        """
        初始化界面
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 创建标题
        title_label = QLabel("远程服务器配置管理")
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
        self.add_btn = QPushButton("➕ 添加服务器配置")
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

        self.add_btn.clicked.connect(self.add_server_config)
        self.refresh_btn.clicked.connect(self.refresh_server_configs)

        button_layout.addWidget(self.add_btn)
        button_layout.addWidget(self.refresh_btn)
        button_layout.addStretch()

        # 创建服务器配置列表
        self.server_config_tree = QTreeWidget()
        self.server_config_tree.setHeaderLabels(["服务器名称", "主机地址", "端口", "用户名", "操作"])
        self.server_config_tree.setRootIsDecorated(False)
        self.server_config_tree.setAlternatingRowColors(True)
        # 移除右键菜单
        self.server_config_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)  # type: ignore
        self.server_config_tree.setStyleSheet("""
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

        # 设置列宽
        header = self.server_config_tree.header()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # 服务器名称
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # 主机地址
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)    # 端口
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # 用户名
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)    # 操作
            self.server_config_tree.setColumnWidth(2, 80)  # 端口列宽度
            self.server_config_tree.setColumnWidth(4, 200)  # 操作列宽度

        # 添加控件到布局
        layout.addWidget(title_label)
        layout.addLayout(button_layout)
        layout.addWidget(self.server_config_tree)

        # 初始加载服务器配置
        self.refresh_server_configs()

    def refresh_server_configs(self):
        """
        刷新服务器配置列表
        """
        self.manager.load_server_configs()
        self.server_config_tree.clear()

        for sc in self.manager.get_server_configs():
            item = QTreeWidgetItem(self.server_config_tree)
            item.setText(0, sc.name)
            item.setText(1, sc.host)
            item.setText(2, str(sc.port))
            item.setText(3, sc.username)
            item.setData(0, Qt.ItemDataRole.UserRole, sc.id)  # type: ignore
            
            # 添加操作按钮
            self.add_action_buttons(item, sc.id)

        logger.info("刷新服务器配置列表")
        
    def add_action_buttons(self, item, server_config_id):
        """
        为指定项添加操作按钮
        
        Args:
            item: 树形控件项
            server_config_id: 服务器配置ID
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
        edit_btn.clicked.connect(lambda: self.update_server_config(server_config_id))
        
        # 测试连接按钮
        test_btn = QPushButton("测试")
        test_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 2px 8px;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        test_btn.clicked.connect(lambda: self.test_server_connection(server_config_id))
        
        # 上传文件按钮
        upload_btn = QPushButton("上传")
        upload_btn.setStyleSheet("""
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
        upload_btn.clicked.connect(lambda: self.upload_files_to_server(server_config_id))
        
        # 下载文件按钮
        download_btn = QPushButton("下载")
        download_btn.setStyleSheet("""
            QPushButton {
                background-color: #00BCD4;
                color: white;
                border: none;
                padding: 2px 8px;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0097A7;
            }
        """)
        download_btn.clicked.connect(lambda: self.download_files_from_server(server_config_id))
        
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
        delete_btn.clicked.connect(lambda: self.delete_server_config(server_config_id))
        
        # 添加按钮到布局
        button_layout.addWidget(edit_btn)
        button_layout.addWidget(test_btn)
        button_layout.addWidget(upload_btn)
        button_layout.addWidget(download_btn)
        button_layout.addWidget(delete_btn)
        
        # 将按钮容器设置为项的第五列（操作列）
        self.server_config_tree.setItemWidget(item, 4, button_widget)

    def add_server_config(self):
        """
        添加服务器配置
        """
        form = ServerConfigForm(self)
        if form.exec() == QDialog.Accepted:  # type: ignore
            server_config = form.get_server_config()
            if server_config:
                self.manager.add_server_config(server_config)
                self.refresh_server_configs()

    def update_server_config(self, server_config_id):
        """
        更新服务器配置
        """
        # 查找要更新的服务器配置
        server_config = self.manager.get_server_config_by_id(server_config_id)
        
        if server_config:
            form = ServerConfigForm(self, server_config)
            if form.exec() == QDialog.Accepted:  # type: ignore
                updated_server_config = form.get_server_config()
                if updated_server_config:
                    updated_server_config.id = server_config_id
                    self.manager.update_server_config(updated_server_config)
                    self.refresh_server_configs()

    def delete_server_config(self, server_config_id):
        """
        删除服务器配置
        """
        reply = QMessageBox.question(self, "确认", "确定要删除选中的服务器配置吗?",
                                     QMessageBox.Yes | QMessageBox.No)  # type: ignore
        if reply == QMessageBox.Yes:
            self.manager.delete_server_config(server_config_id)
            self.refresh_server_configs()

    def test_server_connection(self, server_config_id):
        """
        测试服务器连接
        """
        # 查找服务器配置
        server_config = self.manager.get_server_config_by_id(server_config_id)
        
        if server_config:
            try:
                # 创建SSH客户端并测试连接
                ssh_client = SSHClient(server_config)
                if ssh_client.connect_to_server():
                    ssh_client.disconnect_from_server()
                    QMessageBox.information(self, "连接成功", f"服务器 '{server_config.name}' 连接测试成功！")
                else:
                    QMessageBox.critical(self, "连接失败", f"无法连接到服务器 '{server_config.name}'，请检查配置信息。")
            except Exception as e:
                QMessageBox.critical(self, "连接错误", f"连接服务器 '{server_config.name}' 时发生错误：{str(e)}")

    def upload_files_to_server(self, server_config_id):
        """
        上传文件到指定服务器
        """
        # 查找服务器配置
        server_config = self.manager.get_server_config_by_id(server_config_id)
        
        if server_config:
            # 创建文件传输对话框
            dialog = FileTransferDialog(server_config, "upload", self)
            dialog.exec()

    def download_files_from_server(self, server_config_id):
        """
        从指定服务器下载文件
        """
        # 查找服务器配置
        server_config = self.manager.get_server_config_by_id(server_config_id)
        
        if server_config:
            # 创建文件传输对话框
            dialog = FileTransferDialog(server_config, "download", self)
            dialog.exec()