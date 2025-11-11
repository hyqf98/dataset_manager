import os
from typing import List
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget, \
    QTreeWidgetItem, QHeaderView, QFileDialog, QMessageBox, QProgressBar, QLabel, QInputDialog, \
    QAbstractItemView, QTreeView
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from .server_config import ServerConfig
from .ssh_client import SSHClient
from ..logging_config import logger


class FileTransferWorker(QThread):
    """
    文件传输工作线程
    """
    
    progress_updated = pyqtSignal(str, int)  # 文件名, 进度
    transfer_completed = pyqtSignal(str)  # 文件名
    transfer_error = pyqtSignal(str, str)  # 文件名, 错误信息
    all_completed = pyqtSignal()  # 所有传输完成
    
    def __init__(self, server_config: ServerConfig, transfer_type: str, 
                 local_paths: List[str], remote_path: str):
        super().__init__()
        self.server_config = server_config
        self.transfer_type = transfer_type  # "upload" 或 "download"
        self.local_paths = local_paths
        self.remote_path = remote_path
        self.ssh_client = None
        
    def run(self):
        """
        执行文件传输操作
        """
        try:
            # 创建SSH客户端并连接
            self.ssh_client = SSHClient(self.server_config)
            
            # 连接信号
            self.ssh_client.progress_updated.connect(self.progress_updated.emit)
            self.ssh_client.transfer_completed.connect(self.transfer_completed.emit)
            self.ssh_client.transfer_error.connect(self.transfer_error.emit)
            
            # 连接到服务器
            if not self.ssh_client.connect_to_server():
                return
                
            # 执行传输操作
            if self.transfer_type == "upload":
                self._upload_files()
            elif self.transfer_type == "download":
                self._download_files()
                
            # 发送完成信号
            self.all_completed.emit()
            
        except Exception as e:
            error_msg = f"文件传输过程中发生错误: {str(e)}"
            logger.error(error_msg)
            self.transfer_error.emit("传输", error_msg)
        finally:
            # 断开连接
            if self.ssh_client:
                self.ssh_client.disconnect_from_server()
    
    def _upload_files(self):
        """
        上传文件
        """
        for local_path in self.local_paths:
            try:
                if os.path.isfile(local_path):
                    # 上传单个文件
                    filename = os.path.basename(local_path)
                    remote_file_path = f"{self.remote_path}/{filename}"
                    if self.ssh_client:
                        self.ssh_client.upload_file(local_path, remote_file_path)
                elif os.path.isdir(local_path):
                    # 上传整个目录
                    dirname = os.path.basename(local_path)
                    remote_dir_path = f"{self.remote_path}/{dirname}"
                    if self.ssh_client:
                        self.ssh_client.upload_directory(local_path, remote_dir_path)
            except Exception as e:
                error_msg = f"上传 '{local_path}' 时发生错误: {str(e)}"
                logger.error(error_msg)
                self.transfer_error.emit(os.path.basename(local_path), error_msg)
    
    def _download_files(self):
        """
        下载文件
        """
        for remote_file in self.local_paths:  # local_paths在这里存储的是远程文件路径
            try:
                filename = os.path.basename(remote_file)
                local_file_path = f"{self.remote_path}/{filename}"  # remote_path在这里是本地路径
                
                # 检查远程路径是文件还是目录
                is_directory = False
                if self.ssh_client:
                    remote_items = self.ssh_client.list_remote_files(remote_file)
                    is_directory = any(item[0] == filename and item[3] for item in remote_items)
                
                if is_directory:
                    # 下载整个目录
                    local_dir_path = f"{self.remote_path}/{filename}"
                    if self.ssh_client:
                        self.ssh_client.download_directory(remote_file, local_dir_path)
                else:
                    # 下载单个文件
                    if self.ssh_client:
                        self.ssh_client.download_file(remote_file, local_file_path)
            except Exception as e:
                error_msg = f"下载 '{remote_file}' 时发生错误: {str(e)}"
                logger.error(error_msg)
                self.transfer_error.emit(os.path.basename(remote_file), error_msg)


class RemoteBrowserDialog(QDialog):
    """
    远程目录浏览器对话框
    """
    
    def __init__(self, server_config: ServerConfig, parent=None):
        super().__init__(parent)
        self.server_config = server_config
        self.ssh_client = None
        self.current_path = "/"
        self.selected_files = []
        
        self.setWindowTitle("远程目录浏览器")
        self.setModal(True)
        self.resize(600, 400)
        self.init_ui()
        self.connect_to_server()
        
    def init_ui(self):
        """
        初始化界面
        """
        layout = QVBoxLayout(self)
        
        # 标题和服务器信息
        title_label = QLabel(f"服务器: {self.server_config.name} ({self.server_config.host}:{self.server_config.port})")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # 路径显示
        path_layout = QHBoxLayout()
        self.path_label = QLabel("路径:")
        self.path_edit = QLabel(self.current_path)
        self.path_edit.setStyleSheet("background-color: #f0f0f0; padding: 5px; border-radius: 3px;")
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_directory)
        path_layout.addWidget(self.path_label)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.refresh_btn)
        layout.addLayout(path_layout)
        
        # 文件列表
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["名称", "修改时间", "大小", "类型"])
        self.file_tree.setRootIsDecorated(False)
        self.file_tree.setAlternatingRowColors(True)
        
        header = self.file_tree.header()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            
        # 连接双击信号
        self.file_tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        # 连接单击信号以启用选择按钮
        self.file_tree.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.file_tree)
        
        # 按钮
        button_layout = QHBoxLayout()
        self.up_btn = QPushButton("上级目录")
        self.up_btn.clicked.connect(self.go_up)
        self.select_btn = QPushButton("选择")
        self.select_btn.clicked.connect(self.accept)
        self.select_btn.setEnabled(False)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.up_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.select_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
        
    def connect_to_server(self):
        """
        连接到服务器并加载根目录
        """
        try:
            self.ssh_client = SSHClient(self.server_config)
            if self.ssh_client.connect_to_server():
                self.refresh_directory()
            else:
                QMessageBox.critical(self, "连接错误", "无法连接到服务器")
                self.reject()
        except Exception as e:
            QMessageBox.critical(self, "连接错误", f"连接服务器时发生错误：{str(e)}")
            self.reject()
            
    def refresh_directory(self):
        """
        刷新当前目录
        """
        try:
            if not self.ssh_client:
                return
                
            files = self.ssh_client.list_remote_files(self.current_path)
            self.file_tree.clear()
            
            # 添加上级目录项（如果不是根目录）
            if self.current_path != "/":
                up_item = QTreeWidgetItem(self.file_tree)
                up_item.setText(0, "..")
                up_item.setText(3, "目录")
                up_item.setData(0, Qt.ItemDataRole.UserRole, "..")
            
            # 添加文件和目录项
            for filename, mod_time, size, is_directory in files:
                item = QTreeWidgetItem(self.file_tree)
                item.setText(0, filename)
                item.setText(1, self.format_timestamp(mod_time))
                item.setText(2, self.format_file_size(size) if not is_directory else "")
                item.setText(3, "目录" if is_directory else "文件")
                item.setData(0, Qt.ItemDataRole.UserRole, is_directory)
                
            self.path_edit.setText(self.current_path)
        except Exception as e:
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
        filename = item.text(0)
        is_directory = item.data(0, Qt.ItemDataRole.UserRole)
        
        if filename == "..":
            self.go_up()
        elif is_directory:
            # 进入子目录
            if self.current_path == "/":
                self.current_path = f"/{filename}"
            else:
                self.current_path = f"{self.current_path}/{filename}"
            self.refresh_directory()
            
    def on_item_clicked(self, item, column):
        """
        处理项单击事件，用于启用选择按钮
        """
        # 启用选择按钮，因为用户已选择了一个项目
        self.select_btn.setEnabled(True)
            
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
            
    def get_selected_path(self):
        """
        获取选择的路径
        """
        # 检查是否有选中的项目
        selected_items = self.file_tree.selectedItems()
        if selected_items:
            item = selected_items[0]
            filename = item.text(0)
            is_directory = item.data(0, Qt.ItemDataRole.UserRole)
            
            # 如果选中的是目录，则返回该目录的完整路径
            if is_directory and filename != "..":
                if self.current_path == "/":
                    return f"/{filename}"
                else:
                    return f"{self.current_path}/{filename}"
        
        # 默认返回当前目录路径
        return self.current_path


class FileTransferDialog(QDialog):
    """
    文件传输对话框
    """
    
    def __init__(self, server_config: ServerConfig, transfer_type: str, parent=None):
        super().__init__(parent)
        self.server_config = server_config
        self.transfer_type = transfer_type  # "upload" 或 "下载"
        self.worker = None
        self.transfer_items = []  # 传输项目列表
        
        self.setWindowTitle("上传文件" if transfer_type == "upload" else "下载文件")
        self.setModal(True)
        self.resize(600, 400)
        self.init_ui()
        
    def set_server_config(self, server_config: ServerConfig):
        """
        设置服务器配置
        
        Args:
            server_config (ServerConfig): 服务器配置
        """
        self.server_config = server_config
        # 更新界面显示的服务器信息
        if hasattr(self, 'server_label'):
            server_info = f"服务器: {self.server_config.name} ({self.server_config.host}:{self.server_config.port})"
            self.server_label.setText(server_info)
        
    def init_ui(self):
        """
        初始化界面
        """
        layout = QVBoxLayout(self)
        
        # 标题
        title = "上传文件到服务器" if self.transfer_type == "upload" else "从服务器下载文件"
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # 服务器信息
        server_info = f"服务器: {self.server_config.name} ({self.server_config.host}:{self.server_config.port})"
        self.server_label = QLabel(server_info)
        self.server_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        
        # 服务器选择按钮
        self.select_server_btn = QPushButton("选择服务器...")
        self.select_server_btn.clicked.connect(self.select_server)
        
        # 服务器信息布局
        server_layout = QHBoxLayout()
        server_layout.addWidget(self.server_label)
        server_layout.addStretch()
        server_layout.addWidget(self.select_server_btn)
        layout.addLayout(server_layout)
        
        # 文件列表
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["文件名", "大小", "进度"])
        self.file_tree.setRootIsDecorated(False)
        self.file_tree.setAlternatingRowColors(True)
        # 启用多选模式，支持批量移除
        self.file_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        
        header = self.file_tree.header()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # type: ignore
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # type: ignore
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # type: ignore
            
        layout.addWidget(self.file_tree)
        
        # 路径选择区域
        path_layout = QHBoxLayout()
        
        if self.transfer_type == "upload":
            self.select_files_btn = QPushButton("选择文件...")
            self.select_files_btn.clicked.connect(self.select_files)
            self.select_folders_btn = QPushButton("选择文件夹...")
            self.select_folders_btn.clicked.connect(self.select_folders)
            self.remove_btn = QPushButton("移除选中")
            self.remove_btn.clicked.connect(self.remove_selected_items)
            self.remove_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    padding: 5px 10px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #d32f2f;
                }
                QPushButton:disabled {
                    background-color: #cccccc;
                }
            """)
            self.remote_path_label = QLabel("远程路径:")
            self.remote_path_edit = QLabel("/")  # 默认根路径
            self.browse_remote_btn = QPushButton("浏览远程目录...")
            self.browse_remote_btn.clicked.connect(self.browse_remote_directory)
            path_layout.addWidget(self.select_files_btn)
            path_layout.addWidget(self.select_folders_btn)
            path_layout.addWidget(self.remove_btn)
            path_layout.addWidget(self.remote_path_label)
            path_layout.addWidget(self.remote_path_edit)
            path_layout.addWidget(self.browse_remote_btn)
        else:
            self.remote_path_label = QLabel("远程路径:")
            self.remote_path_edit = QLabel("/")  # 默认根路径
            self.browse_remote_btn = QPushButton("浏览远程目录...")
            self.browse_remote_btn.clicked.connect(self.browse_remote_directory)
            path_layout.addWidget(self.remote_path_label)
            path_layout.addWidget(self.remote_path_edit)
            path_layout.addWidget(self.browse_remote_btn)
        
        layout.addLayout(path_layout)
        
        # 本地路径选择（仅下载时显示）
        if self.transfer_type == "download":
            local_path_layout = QHBoxLayout()
            self.local_path_label = QLabel("保存到:")
            self.local_path_edit = QLabel(os.path.expanduser("~"))  # 默认用户主目录
            self.browse_local_btn = QPushButton("选择本地目录...")
            self.browse_local_btn.clicked.connect(self.select_local_directory)
            local_path_layout.addWidget(self.local_path_label)
            local_path_layout.addWidget(self.local_path_edit)
            local_path_layout.addWidget(self.browse_local_btn)
            layout.addLayout(local_path_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel()
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)
        
        # 按钮
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始传输")
        self.start_btn.clicked.connect(self.start_transfer)
        self.start_btn.setEnabled(False)
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.reject)  # type: ignore
        button_layout.addWidget(self.start_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)
        
    def select_files(self):
        """
        选择要上传的文件或目录，支持同时选择文件和文件夹
        """
        # 创建自定义对话框，支持选择文件和文件夹
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        
        # 启用文件和文件夹同时选择
        file_view = dialog.findChild(QTreeView)
        if file_view:
            file_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        
        list_view = dialog.findChild(QAbstractItemView, "listView")
        if list_view:
            list_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        
        if dialog.exec() == QFileDialog.DialogCode.Accepted:
            selected_paths = dialog.selectedFiles()
            
            # 额外检查是否有选中的目录（通过目录选择对话框）
            directory = dialog.directory().absolutePath()
            if directory and os.path.isdir(directory):
                # 如果用户双击了文件夹，可能需要额外处理
                # 但由于ExistingFiles模式，双击会进入文件夹
                pass
            
            self.add_transfer_items(selected_paths)
    
    def select_folders(self):
        """
        专门选择文件夹的方法
        """
        folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder_path and os.path.exists(folder_path):
            self.add_transfer_items([folder_path])
    
    def add_transfer_items(self, paths):
        """
        添加传输项目到列表
        """
        self.transfer_items.extend(paths)
        self.update_file_list()
        self.start_btn.setEnabled(len(self.transfer_items) > 0)
    
    def update_file_list(self):
        """
        更新文件列表显示，如果是文件夹则计算大小
        """
        self.file_tree.clear()
        
        for path in self.transfer_items:
            item = QTreeWidgetItem(self.file_tree)
            item.setText(0, os.path.basename(path))
            # 将完整路径存储在item的data中，用于移除时识别
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            
            # 获取文件或文件夹大小
            try:
                if os.path.isfile(path):
                    size = os.path.getsize(path)
                    item.setText(1, self.format_file_size(size))
                elif os.path.isdir(path):
                    # 计算文件夹大小
                    folder_size = self._calculate_folder_size(path)
                    item.setText(1, self.format_file_size(folder_size))
                else:
                    item.setText(1, "未知")
            except Exception as e:
                logger.debug(f"获取文件大小失败: {path}, 错误: {e}")
                item.setText(1, "未知")
            
            # 进度列
            item.setText(2, "等待")
    
    def remove_selected_items(self):
        """
        移除选中的传输项
        """
        selected_items = self.file_tree.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择要移除的项目")
            return
        
        # 获取选中项的路径
        paths_to_remove = []
        for item in selected_items:
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path:
                paths_to_remove.append(path)
        
        # 从传输列表中移除
        for path in paths_to_remove:
            if path in self.transfer_items:
                self.transfer_items.remove(path)
        
        # 更新显示
        self.update_file_list()
        self.start_btn.setEnabled(len(self.transfer_items) > 0)
        
        logger.info(f"已移除 {len(paths_to_remove)} 个项目")
    
    def _calculate_folder_size(self, folder_path):
        """
        计算文件夹大小（字节）
        
        Args:
            folder_path (str): 文件夹路径
            
        Returns:
            int: 文件夹大小（字节）
        """
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(folder_path):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    try:
                        if os.path.exists(file_path):
                            total_size += os.path.getsize(file_path)
                    except (OSError, PermissionError) as e:
                        logger.debug(f"无法访问文件: {file_path}, 错误: {e}")
                        continue
            return total_size
        except Exception as e:
            logger.error(f"计算文件夹大小时发生异常: {str(e)}")
            return 0
            
    def format_file_size(self, size_bytes):
        """
        格式化文件大小显示
        """
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
            
        return f"{size_bytes:.1f} {size_names[i]}"
    
    def browse_remote_directory(self):
        """
        浏览远程目录（下载时使用）
        """
        try:
            dialog = RemoteBrowserDialog(self.server_config, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_path = dialog.get_selected_path()
                self.remote_path_edit.setText(selected_path)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"浏览远程目录时发生错误：{str(e)}")
    
    def select_server(self):
        """
        选择服务器
        """
        try:
            # 导入服务器配置管理器
            from .server_config import ServerConfigManager
            
            # 获取所有服务器配置
            server_manager = ServerConfigManager()
            server_configs = server_manager.get_server_configs()
            
            # 检查是否有配置的服务器
            if not server_configs:
                QMessageBox.warning(self, "警告", "请先配置远程服务器!")
                return
            
            # 如果只有一个服务器配置，直接使用
            if len(server_configs) == 1:
                self.set_server_config(server_configs[0])
            else:
                # 如果有多个服务器配置，让用户选择
                server_names = [sc.name for sc in server_configs]
                selected_name, ok = QInputDialog.getItem(
                    self, "选择服务器", "请选择要上传到的服务器:", server_names, 0, False
                )
                
                if ok and selected_name:
                    # 查找选中的服务器配置
                    selected_server = None
                    for sc in server_configs:
                        if sc.name == selected_name:
                            selected_server = sc
                            break
                    
                    if selected_server:
                        self.set_server_config(selected_server)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"选择服务器时发生异常: {str(e)}")
    
    def select_local_directory(self):
        """
        选择本地保存目录（下载时使用）
        """
        directory = QFileDialog.getExistingDirectory(self, "选择保存目录", self.local_path_edit.text())
        if directory:
            self.local_path_edit.setText(directory)
    
    def start_transfer(self):
        """
        开始文件传输
        """
        if not self.transfer_items:
            QMessageBox.warning(self, "警告", "请先选择要传输的文件或目录。")
            return
            
        # 确定远程路径和本地路径
        if self.transfer_type == "upload":
            remote_path = self.remote_path_edit.text()  # 远程路径
            local_paths = self.transfer_items
        else:
            remote_path = self.local_path_edit.text()  # 本地保存路径
            local_paths = self.transfer_items  # 远程文件路径
            
        # 创建并启动工作线程
        self.worker = FileTransferWorker(
            self.server_config, 
            self.transfer_type, 
            local_paths, 
            remote_path
        )
        
        # 连接信号
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.transfer_completed.connect(self.on_transfer_completed)
        self.worker.transfer_error.connect(self.on_transfer_error)
        self.worker.all_completed.connect(self.on_all_completed)
        
        # 禁用开始按钮，显示进度条
        self.start_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.status_label.setText("正在连接到服务器...")
        
        # 启动线程
        self.worker.start()
    
    def update_progress(self, filename, progress):
        """
        更新传输进度
        """
        # 在文件树中找到对应的项目并更新进度
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            if item and item.text(0) == filename:
                item.setText(2, f"{progress}%")
                break
                
        # 更新总体进度条
        self.progress_bar.setValue(progress)
    
    def on_transfer_completed(self, filename):
        """
        处理单个文件传输完成
        """
        # 更新文件状态
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            if item and item.text(0) == filename:
                item.setText(2, "完成")
                break
                
        self.status_label.setText(f"已完成: {filename}")
    
    def on_transfer_error(self, filename, error_msg):
        """
        处理传输错误
        """
        # 更新文件状态
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            if item and item.text(0) == filename:
                item.setText(2, "错误")
                break
                
        self.status_label.setText(f"错误: {error_msg}")
        QMessageBox.critical(self, "传输错误", f"文件 '{filename}' 传输失败:\n{error_msg}")
    
    def on_all_completed(self):
        """
        处理所有传输完成
        """
        self.status_label.setText("所有文件传输完成!")
        self.progress_bar.setValue(100)
        QMessageBox.information(self, "完成", "所有文件传输完成!")