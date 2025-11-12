import os
import tempfile
from typing import Optional
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget, 
                              QTreeWidgetItem, QHeaderView, QMessageBox, QLabel, QComboBox,
                              QTextEdit, QDialog, QDialogButtonBox, QSplitter, QMenu, QAction,
                              QInputDialog, QFileDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QContextMenuEvent
from .server_config import ServerConfig, ServerConfigManager
from .ssh_client import SSHClient
from ..logging_config import logger


class RemoteFileLoadWorker(QThread):
    """
    远程文件加载工作线程
    """
    
    file_loaded = pyqtSignal(str)  # 文件内容
    load_error = pyqtSignal(str)  # 错误信息
    
    def __init__(self, ssh_client: SSHClient, remote_path: str):
        super().__init__()
        self.ssh_client = ssh_client
        self.remote_path = remote_path
        
    def run(self):
        """
        执行文件加载操作
        """
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8') as temp_file:
                temp_path = temp_file.name
                
            # 下载文件到临时位置
            self.ssh_client.download_file(self.remote_path, temp_path)
            
            # 读取文件内容
            with open(temp_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 删除临时文件
            os.unlink(temp_path)
            
            # 发送成功信号
            self.file_loaded.emit(content)
            
        except Exception as e:
            error_msg = f"加载文件失败: {str(e)}"
            logger.error(error_msg)
            self.load_error.emit(error_msg)


class RemoteFileSaveWorker(QThread):
    """
    远程文件保存工作线程
    """
    
    file_saved = pyqtSignal()  # 保存成功
    save_error = pyqtSignal(str)  # 错误信息
    
    def __init__(self, ssh_client: SSHClient, remote_path: str, content: str):
        super().__init__()
        self.ssh_client = ssh_client
        self.remote_path = remote_path
        self.content = content
        
    def run(self):
        """
        执行文件保存操作
        """
        try:
            # 创建临时文件并写入内容
            with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as temp_file:
                temp_path = temp_file.name
                temp_file.write(self.content)
                
            # 上传文件到远程服务器（强制覆盖，不检查文件是否存在）
            self.ssh_client.upload_file(temp_path, self.remote_path, check_exists=False)
            
            # 删除临时文件
            os.unlink(temp_path)
            
            # 发送成功信号
            self.file_saved.emit()
            
        except Exception as e:
            error_msg = f"保存文件失败: {str(e)}"
            logger.error(error_msg)
            self.save_error.emit(error_msg)


class RemoteFileEditorDialog(QDialog):
    """
    远程文件编辑器对话框
    """
    # 定义文件保存成功信号
    file_saved = pyqtSignal()
    
    def __init__(self, ssh_client: SSHClient, remote_path: str, parent=None):
        super().__init__(parent)
        self.ssh_client = ssh_client
        self.remote_path = remote_path
        self.original_content = ""
        self.is_modified = False
        
        self.setWindowTitle(f"编辑远程文件 - {os.path.basename(remote_path)}")
        self.setModal(True)
        self.resize(800, 600)
        self.init_ui()
        self.load_file()
        
    def init_ui(self):
        """
        初始化界面
        """
        layout = QVBoxLayout(self)
        
        # 文件路径显示
        path_label = QLabel(f"文件路径: {self.remote_path}")
        path_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(path_label)
        
        # 文本编辑器
        self.text_edit = QTextEdit()
        self.text_edit.setStyleSheet("""
            QTextEdit {
                font-family: 'Courier New', monospace;
                font-size: 12px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
        """)
        self.text_edit.textChanged.connect(self.on_text_changed)
        layout.addWidget(self.text_edit)
        
        # 状态标签
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.status_label)
        
        # 按钮
        button_box = QDialogButtonBox()
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.save_file)
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet("""
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
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close_editor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        
        button_box.addButton(self.save_btn, QDialogButtonBox.ButtonRole.ActionRole)
        button_box.addButton(self.close_btn, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(button_box)
        
    def load_file(self):
        """
        加载远程文件内容
        """
        self.status_label.setText("正在加载文件...")
        self.text_edit.setEnabled(False)
        
        # 创建并启动加载线程
        self.load_worker = RemoteFileLoadWorker(self.ssh_client, self.remote_path)
        self.load_worker.file_loaded.connect(self.on_file_loaded)
        self.load_worker.load_error.connect(self.on_load_error)
        self.load_worker.start()
        
    def on_file_loaded(self, content: str):
        """
        文件加载完成
        """
        self.original_content = content
        self.text_edit.setPlainText(content)
        self.text_edit.setEnabled(True)
        self.status_label.setText("文件加载成功")
        self.is_modified = False
        
    def on_load_error(self, error_msg: str):
        """
        文件加载错误
        """
        self.status_label.setText(f"错误: {error_msg}")
        QMessageBox.critical(self, "错误", error_msg)
        self.reject()
        
    def on_text_changed(self):
        """
        文本内容变化
        """
        current_content = self.text_edit.toPlainText()
        self.is_modified = current_content != self.original_content
        self.save_btn.setEnabled(self.is_modified)
        
        if self.is_modified:
            self.status_label.setText("文件已修改（未保存）")
        else:
            self.status_label.setText("")
            
    def save_file(self):
        """
        保存文件到远程服务器
        """
        content = self.text_edit.toPlainText()
        self.status_label.setText("正在保存文件...")
        self.save_btn.setEnabled(False)
        self.text_edit.setEnabled(False)
        
        # 创建并启动保存线程
        self.save_worker = RemoteFileSaveWorker(self.ssh_client, self.remote_path, content)
        self.save_worker.file_saved.connect(self.on_file_saved)
        self.save_worker.save_error.connect(self.on_save_error)
        self.save_worker.start()
        
    def on_file_saved(self):
        """
        文件保存成功
        """
        self.original_content = self.text_edit.toPlainText()
        self.is_modified = False
        self.text_edit.setEnabled(True)
        self.status_label.setText("文件保存成功")
        QMessageBox.information(self, "成功", "文件保存成功!")
        
        # 发出文件保存成功信号
        self.file_saved.emit()
        
    def on_save_error(self, error_msg: str):
        """
        文件保存错误
        """
        self.text_edit.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.status_label.setText(f"保存失败: {error_msg}")
        QMessageBox.critical(self, "错误", error_msg)
        
    def close_editor(self):
        """
        关闭编辑器
        """
        if self.is_modified:
            reply = QMessageBox.question(
                self, 
                "确认", 
                "文件已修改但未保存，确定要关闭吗？",
                QMessageBox.Yes | QMessageBox.No  # type: ignore
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.reject()
        else:
            self.reject()


class RemoteFileBrowserPanel(QWidget):
    """
    远程文件浏览器面板
    """
    
    def __init__(self):
        super().__init__()
        self.server_manager = ServerConfigManager()
        self.ssh_client = None
        self.current_server = None
        self.current_path = "/"
        self.init_ui()
        self.load_servers()
        
    def init_ui(self):
        """
        初始化界面
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 标题
        title_label = QLabel("远程文件浏览器")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 5px;
                border-bottom: 1px solid #ccc;
            }
        """)
        layout.addWidget(title_label)
        
        # 服务器选择区域
        server_layout = QHBoxLayout()
        server_label = QLabel("选择服务器:")
        self.server_combo = QComboBox()
        self.server_combo.currentIndexChanged.connect(self.on_server_changed)
        
        self.connect_btn = QPushButton("连接")
        self.connect_btn.clicked.connect(self.connect_to_server)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.connect_btn.setEnabled(False)
        
        self.disconnect_btn = QPushButton("断开")
        self.disconnect_btn.clicked.connect(self.disconnect_from_server)
        self.disconnect_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.disconnect_btn.setEnabled(False)
        
        server_layout.addWidget(server_label)
        server_layout.addWidget(self.server_combo, 1)
        server_layout.addWidget(self.connect_btn)
        server_layout.addWidget(self.disconnect_btn)
        layout.addLayout(server_layout)
        
        # 路径导航区域
        path_layout = QHBoxLayout()
        path_label = QLabel("当前路径:")
        self.path_edit = QLabel("/")
        self.path_edit.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                padding: 5px;
                border-radius: 3px;
                border: 1px solid #ccc;
            }
        """)
        
        self.up_btn = QPushButton("⬆ 上级目录")
        self.up_btn.clicked.connect(self.go_up)
        self.up_btn.setEnabled(False)
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self.refresh_directory)
        self.refresh_btn.setEnabled(False)
        
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_edit, 1)
        path_layout.addWidget(self.up_btn)
        path_layout.addWidget(self.refresh_btn)
        layout.addLayout(path_layout)
        
        # 文件列表
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["名称", "修改时间", "大小", "类型"])
        self.file_tree.setRootIsDecorated(False)
        self.file_tree.setAlternatingRowColors(True)
        self.file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.file_tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.file_tree.setStyleSheet("""
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
        
        header = self.file_tree.header()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            
        layout.addWidget(self.file_tree)
        
        # 状态栏
        self.status_label = QLabel("请选择服务器并连接")
        self.status_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.status_label)
        
    def load_servers(self):
        """
        加载服务器列表
        """
        self.server_combo.clear()
        self.server_manager.load_server_configs()
        servers = self.server_manager.get_server_configs()
        
        if not servers:
            self.server_combo.addItem("（没有配置的服务器）")
            self.connect_btn.setEnabled(False)
            return
            
        for server in servers:
            self.server_combo.addItem(f"{server.name} ({server.host}:{server.port})", server)
            
        self.connect_btn.setEnabled(True)
        
    def on_server_changed(self, index):
        """
        服务器选择变化
        """
        if self.ssh_client:
            reply = QMessageBox.question(
                self,
                "确认",
                "切换服务器将断开当前连接，是否继续？",
                QMessageBox.Yes | QMessageBox.No  # type: ignore
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.disconnect_from_server()
            else:
                # 恢复之前的选择
                for i in range(self.server_combo.count()):
                    if self.server_combo.itemData(i) == self.current_server:
                        self.server_combo.setCurrentIndex(i)
                        break
                        
    def connect_to_server(self):
        """
        连接到选中的服务器
        """
        server_config = self.server_combo.currentData()
        if not server_config:
            QMessageBox.warning(self, "警告", "请先选择一个服务器")
            return
            
        try:
            self.status_label.setText("正在连接到服务器...")
            self.ssh_client = SSHClient(server_config)
            
            if self.ssh_client.connect_to_server():
                self.current_server = server_config
                self.current_path = "/"
                self.connect_btn.setEnabled(False)
                self.disconnect_btn.setEnabled(True)
                self.up_btn.setEnabled(True)
                self.refresh_btn.setEnabled(True)
                self.server_combo.setEnabled(False)
                self.status_label.setText(f"已连接到 {server_config.name}")
                self.refresh_directory()
            else:
                self.status_label.setText("连接失败")
                QMessageBox.critical(self, "错误", "无法连接到服务器")
                self.ssh_client = None
        except Exception as e:
            self.status_label.setText("连接失败")
            QMessageBox.critical(self, "错误", f"连接服务器时发生错误：{str(e)}")
            self.ssh_client = None
            
    def disconnect_from_server(self):
        """
        断开服务器连接
        """
        if self.ssh_client:
            self.ssh_client.disconnect_from_server()
            self.ssh_client = None
            
        self.current_server = None
        self.current_path = "/"
        self.file_tree.clear()
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.up_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.server_combo.setEnabled(True)
        self.status_label.setText("已断开连接")
        
    def refresh_directory(self):
        """
        刷新当前目录
        """
        if not self.ssh_client:
            return
            
        try:
            self.status_label.setText("正在加载目录...")
            files = self.ssh_client.list_remote_files(self.current_path)
            self.file_tree.clear()
            
            # 添加文件和目录项
            for filename, mod_time, size, is_directory in files:
                item = QTreeWidgetItem(self.file_tree)
                item.setText(0, filename)
                item.setText(1, self.format_timestamp(mod_time))
                item.setText(2, self.format_file_size(size) if not is_directory else "")
                item.setText(3, "目录" if is_directory else "文件")
                item.setData(0, Qt.ItemDataRole.UserRole, {
                    'is_directory': is_directory,
                    'path': f"{self.current_path}/{filename}".replace("//", "/")
                })
                
            self.path_edit.setText(self.current_path)
            self.status_label.setText(f"已加载 {len(files)} 个项目")
        except Exception as e:
            self.status_label.setText("加载失败")
            QMessageBox.critical(self, "错误", f"读取目录时发生错误：{str(e)}")
            
    def format_timestamp(self, timestamp):
        """
        格式化时间戳
        """
        from datetime import datetime
        try:
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return ""
            
    def format_file_size(self, size_bytes):
        """
        格式化文件大小
        """
        if size_bytes == 0:
            return "0 B"
            
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
            
        return f"{size_bytes:.1f} {size_names[i]}"
        
    def on_item_double_clicked(self, item, column):
        """
        处理项双击事件
        """
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
            
        if data['is_directory']:
            # 进入子目录
            self.current_path = data['path']
            self.refresh_directory()
        else:
            # 打开文件编辑器
            self.edit_file(data['path'])
            
    def go_up(self):
        """
        返回上级目录
        """
        if self.current_path != "/":
            # 移除最后一个路径部分
            parts = self.current_path.strip("/").split("/")
            if len(parts) > 1:
                self.current_path = "/" + "/".join(parts[:-1])
            else:
                self.current_path = "/"
            self.refresh_directory()
            
    def show_context_menu(self, position):
        """
        显示右键菜单
        """
        item = self.file_tree.itemAt(position)
        menu = QMenu(self)
        
        if item:
            # 选中了文件或目录
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                if data['is_directory']:
                    # 目录菜单
                    enter_action = QAction("进入目录", self)
                    enter_action.triggered.connect(lambda: self.enter_directory(data['path']))
                    menu.addAction(enter_action)
                    
                    menu.addSeparator()
                    
                    # 新建文件/文件夹
                    new_file_action = QAction("新建文件", self)
                    new_file_action.triggered.connect(lambda: self.create_new_file(data['path']))
                    menu.addAction(new_file_action)
                    
                    new_folder_action = QAction("新建文件夹", self)
                    new_folder_action.triggered.connect(lambda: self.create_new_folder(data['path']))
                    menu.addAction(new_folder_action)
                    
                    menu.addSeparator()
                    
                    # 重命名
                    rename_action = QAction("重命名", self)
                    rename_action.triggered.connect(lambda: self.rename_item(data['path'], True))
                    menu.addAction(rename_action)
                    
                    # 删除
                    delete_action = QAction("删除目录", self)
                    delete_action.triggered.connect(lambda: self.delete_item(data['path'], True))
                    menu.addAction(delete_action)
                    
                    menu.addSeparator()
                    
                    download_action = QAction("下载目录", self)
                    download_action.triggered.connect(lambda: self.download_directory(data['path']))
                    menu.addAction(download_action)
                else:
                    # 文件菜单
                    edit_action = QAction("编辑文件", self)
                    edit_action.triggered.connect(lambda: self.edit_file(data['path']))
                    menu.addAction(edit_action)
                    
                    menu.addSeparator()
                    
                    # 重命名
                    rename_action = QAction("重命名", self)
                    rename_action.triggered.connect(lambda: self.rename_item(data['path'], False))
                    menu.addAction(rename_action)
                    
                    # 删除
                    delete_action = QAction("删除文件", self)
                    delete_action.triggered.connect(lambda: self.delete_item(data['path'], False))
                    menu.addAction(delete_action)
                    
                    menu.addSeparator()
                    
                    download_action = QAction("下载文件", self)
                    download_action.triggered.connect(lambda: self.download_file(data['path']))
                    menu.addAction(download_action)
        else:
            # 未选中任何项，显示当前目录操作
            new_file_action = QAction("新建文件", self)
            new_file_action.triggered.connect(lambda: self.create_new_file(self.current_path))
            menu.addAction(new_file_action)
            
            new_folder_action = QAction("新建文件夹", self)
            new_folder_action.triggered.connect(lambda: self.create_new_folder(self.current_path))
            menu.addAction(new_folder_action)
            
        viewport = self.file_tree.viewport()
        if viewport:
            menu.exec(viewport.mapToGlobal(position))
        
    def enter_directory(self, path):
        """
        进入目录
        """
        self.current_path = path
        self.refresh_directory()
        
    def edit_file(self, remote_path):
        """
        编辑远程文件
        """
        if not self.ssh_client:
            QMessageBox.warning(self, "警告", "请先连接到服务器")
            return
            
        try:
            editor = RemoteFileEditorDialog(self.ssh_client, remote_path, self)
            # 连接文件保存成功信号，保存后刷新目录
            editor.file_saved.connect(self.refresh_directory)
            editor.exec()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开文件编辑器时发生错误：{str(e)}")
            
    def download_file(self, remote_path):
        """
        下载文件到本地
        """
        if not self.ssh_client:
            QMessageBox.warning(self, "警告", "请先连接到服务器")
            return
            
        try:
            # 选择保存位置
            filename = os.path.basename(remote_path)
            local_path, _ = QFileDialog.getSaveFileName(
                self,
                "保存文件",
                filename,
                "所有文件 (*)"
            )
            
            if not local_path:
                return
                
            self.status_label.setText(f"正在下载 {filename}...")
            self.ssh_client.download_file(remote_path, local_path)
            self.status_label.setText(f"文件下载成功: {filename}")
            QMessageBox.information(self, "成功", f"文件已保存到:\n{local_path}")
        except Exception as e:
            self.status_label.setText("下载失败")
            QMessageBox.critical(self, "错误", f"下载文件时发生错误：{str(e)}")
            
    def download_directory(self, remote_path):
        """
        下载目录到本地
        """
        if not self.ssh_client:
            QMessageBox.warning(self, "警告", "请先连接到服务器")
            return
            
        try:
            # 选择保存位置
            dirname = os.path.basename(remote_path)
            local_path = QFileDialog.getExistingDirectory(
                self,
                "选择保存目录",
                os.path.expanduser("~")
            )
            
            if not local_path:
                return
                
            full_local_path = os.path.join(local_path, dirname)
            self.status_label.setText(f"正在下载目录 {dirname}...")
            self.ssh_client.download_directory(remote_path, full_local_path)
            self.status_label.setText(f"目录下载成功: {dirname}")
            QMessageBox.information(self, "成功", f"目录已保存到:\n{full_local_path}")
        except Exception as e:
            self.status_label.setText("下载失败")
            QMessageBox.critical(self, "错误", f"下载目录时发生错误：{str(e)}")
    
    def create_new_file(self, parent_path):
        """
        在远程目录创建新文件
        """
        if not self.ssh_client:
            QMessageBox.warning(self, "警告", "请先连接到服务器")
            return
            
        # 输入文件名
        filename, ok = QInputDialog.getText(self, "新建文件", "请输入文件名:")
        if not ok or not filename:
            return
            
        try:
            # 构建完整路径
            remote_file_path = f"{parent_path}/{filename}".replace("//", "/")
            
            # 检查文件是否已存在
            if self.ssh_client.check_remote_file_exists(remote_file_path):
                QMessageBox.warning(self, "警告", f"文件 '{filename}' 已存在！")
                return
                
            self.status_label.setText(f"正在创建文件 {filename}...")
            self.ssh_client.create_remote_file(remote_file_path)
            self.status_label.setText(f"文件创建成功: {filename}")
            
            # 刷新目录
            self.refresh_directory()
            QMessageBox.information(self, "成功", f"文件 '{filename}' 创建成功！")
        except Exception as e:
            self.status_label.setText("创建失败")
            QMessageBox.critical(self, "错误", f"创建文件时发生错误：{str(e)}")
    
    def create_new_folder(self, parent_path):
        """
        在远程目录创建新文件夹
        """
        if not self.ssh_client:
            QMessageBox.warning(self, "警告", "请先连接到服务器")
            return
            
        # 输入文件夹名
        foldername, ok = QInputDialog.getText(self, "新建文件夹", "请输入文件夹名:")
        if not ok or not foldername:
            return
            
        try:
            # 构建完整路径
            remote_folder_path = f"{parent_path}/{foldername}".replace("//", "/")
            
            # 检查文件夹是否已存在
            if self.ssh_client.check_remote_file_exists(remote_folder_path):
                QMessageBox.warning(self, "警告", f"文件夹 '{foldername}' 已存在！")
                return
                
            self.status_label.setText(f"正在创建文件夹 {foldername}...")
            self.ssh_client.create_remote_directory(remote_folder_path)
            self.status_label.setText(f"文件夹创建成功: {foldername}")
            
            # 刷新目录
            self.refresh_directory()
            QMessageBox.information(self, "成功", f"文件夹 '{foldername}' 创建成功！")
        except Exception as e:
            self.status_label.setText("创建失败")
            QMessageBox.critical(self, "错误", f"创建文件夹时发生错误：{str(e)}")
    
    def rename_item(self, old_path, is_directory):
        """
        重命名远程文件或目录
        """
        if not self.ssh_client:
            QMessageBox.warning(self, "警告", "请先连接到服务器")
            return
            
        old_name = os.path.basename(old_path)
        item_type = "目录" if is_directory else "文件"
        
        # 输入新名称
        new_name, ok = QInputDialog.getText(
            self, 
            f"重命名{item_type}", 
            f"请输入新的{item_type}名:",
            text=old_name
        )
        if not ok or not new_name or new_name == old_name:
            return
            
        try:
            # 构建新路径
            parent_path = os.path.dirname(old_path)
            new_path = f"{parent_path}/{new_name}".replace("//", "/")
            
            # 检查新名称是否已存在
            if self.ssh_client.check_remote_file_exists(new_path):
                QMessageBox.warning(self, "警告", f"{item_type} '{new_name}' 已存在！")
                return
                
            self.status_label.setText(f"正在重命名 {old_name}...")
            self.ssh_client.rename_remote_file(old_path, new_path)
            self.status_label.setText(f"重命名成功: {old_name} -> {new_name}")
            
            # 刷新目录
            self.refresh_directory()
            QMessageBox.information(self, "成功", f"{item_type} '{old_name}' 已重命名为 '{new_name}'！")
        except Exception as e:
            self.status_label.setText("重命名失败")
            QMessageBox.critical(self, "错误", f"重命名{item_type}时发生错误：{str(e)}")
    
    def delete_item(self, remote_path, is_directory):
        """
        删除远程文件或目录
        """
        if not self.ssh_client:
            QMessageBox.warning(self, "警告", "请先连接到服务器")
            return
            
        item_name = os.path.basename(remote_path)
        item_type = "目录" if is_directory else "文件"
        
        # 确认删除
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除{item_type} '{item_name}' 吗？\n\n此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No  # type: ignore
        )
        
        if reply != QMessageBox.Yes:
            return
            
        try:
            self.status_label.setText(f"正在删除 {item_name}...")
            
            if is_directory:
                self.ssh_client.delete_remote_directory(remote_path)
            else:
                self.ssh_client.delete_remote_file(remote_path)
                
            self.status_label.setText(f"删除成功: {item_name}")
            
            # 刷新目录
            self.refresh_directory()
            QMessageBox.information(self, "成功", f"{item_type} '{item_name}' 已删除！")
        except Exception as e:
            self.status_label.setText("删除失败")
            QMessageBox.critical(self, "错误", f"删除{item_type}时发生错误：{str(e)}")
