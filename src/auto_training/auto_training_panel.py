import os
import csv
import subprocess
from typing import Optional, Dict
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTreeWidget, QTreeWidgetItem, QMessageBox, QDialog,
                             QLabel, QHeaderView, QTextEdit, QCheckBox, QSpinBox)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from ..logging_config import logger
from .training_task import TrainingTask, TrainingTaskManager, TrainingTaskStatus, TrainingTaskType
from .task_edit_dialog import TaskEditDialog
from .training_log_viewer import TrainingLogViewer
from .async_uploader import AsyncUploader
from ..remote_server.server_config import ServerConfigManager, ServerConfig
from ..remote_server.ssh_client import SSHClient
from PyQt5.QtWidgets import QTextEdit, QCheckBox, QSpinBox, QHBoxLayout, QWidget





class AutoTrainingPanel(QWidget):
    """自动训练管理面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.task_manager = TrainingTaskManager()
        self.server_config_manager = ServerConfigManager()
        self.running_processes: Dict[int, subprocess.Popen] = {}  # 存储运行中的进程
        self.init_ui()
        self.load_tasks()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 标题
        title_label = QLabel("自动训练管理")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 5px;
                border-bottom: 1px solid #ccc;
            }
        """)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        # 新增任务按钮
        add_btn = QPushButton("➕ 新增任务")
        add_btn.setStyleSheet("""
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
        add_btn.clicked.connect(self.add_task)
        button_layout.addWidget(add_btn)
        
        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setStyleSheet("""
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
        refresh_btn.clicked.connect(self.load_tasks)
        button_layout.addWidget(refresh_btn)
        
        button_layout.addStretch()
        
        # 任务列表
        self.task_tree = QTreeWidget()
        self.task_tree.setHeaderLabels(["任务名称", "类型", "状态", "详细信息", "操作"])
        self.task_tree.setRootIsDecorated(False)
        self.task_tree.setAlternatingRowColors(True)
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
        
        # 设置列宽
        header = self.task_tree.header()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # 任务名称
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)    # 类型
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)    # 状态
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # 详细信息
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)    # 操作
            self.task_tree.setColumnWidth(1, 100)
            self.task_tree.setColumnWidth(2, 80)
            self.task_tree.setColumnWidth(4, 400)  # 增加操作列宽度以容纳所有按钮
        
        # 添加控件到布局
        layout.addWidget(title_label)
        layout.addLayout(button_layout)
        layout.addWidget(self.task_tree)
    
    def load_tasks(self):
        """加载任务列表"""
        self.task_tree.clear()
        tasks = self.task_manager.get_tasks()
        
        for task in tasks:
            item = QTreeWidgetItem(self.task_tree)
            item.setText(0, task.name)
            item.setText(1, task.task_type.value)
            item.setText(2, task.status.value)
            
            # 详细信息
            if task.task_type == TrainingTaskType.LOCAL:
                detail = f"保存路径: {task.save_path}"
            else:
                server_name = "未知服务器"
                if task.server_id is not None:
                    server_config = self.server_config_manager.get_server_config_by_id(task.server_id)
                    if server_config:
                        server_name = server_config.name
                detail = f"服务器: {server_name} | 路径: {task.remote_path}"
            item.setText(3, detail)
            
            item.setData(0, Qt.ItemDataRole.UserRole, task.task_id)  # type: ignore
            
            # 添加操作按钮
            self.add_action_buttons(item, task)
    
    def add_task(self):
        """新增任务"""
        dialog = TaskEditDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            task = dialog.get_task()
            self.task_manager.add_task(task)
            self.load_tasks()
    
    def edit_task(self, task_id: int):
        """编辑任务"""
        task = self.task_manager.get_task_by_id(task_id)
        if task:
            dialog = TaskEditDialog(parent=self, task=task)
            if dialog.exec() == QDialog.Accepted:
                updated_task = dialog.get_task()
                self.task_manager.update_task(updated_task)
                self.load_tasks()
    
    def add_action_buttons(self, item: QTreeWidgetItem, task: TrainingTask):
        """添加操作按钮到树形项"""
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(2, 2, 2, 2)
        btn_layout.setSpacing(3)
        
        # 开始/停止按钮
        if task.status == TrainingTaskStatus.RUNNING or task.status == TrainingTaskStatus.UPLOADING:
            action_btn = QPushButton("停止")
            action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #dc3545;
                    color: white;
                    border: none;
                    padding: 2px 8px;
                    border-radius: 3px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #c82333;
                }
            """)
            if task.task_id is not None:
                action_btn.clicked.connect(lambda checked, tid=task.task_id: self.stop_task(tid))
        else:
            action_btn = QPushButton("开始")
            action_btn.setStyleSheet("""
                QPushButton {
                    background-color: #28a745;
                    color: white;
                    border: none;
                    padding: 2px 8px;
                    border-radius: 3px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #218838;
                }
                QPushButton:disabled {
                    background-color: #6c757d;
                }
            """)
            # 任务运行中时禁用开始按钮
            action_btn.setEnabled(task.status != TrainingTaskStatus.RUNNING and task.status != TrainingTaskStatus.UPLOADING)
            if task.task_id is not None:
                action_btn.clicked.connect(lambda checked, tid=task.task_id: self.start_task(tid))
        btn_layout.addWidget(action_btn)
        
        # 编辑按钮
        edit_btn = QPushButton("编辑")
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 2px 8px;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        # 任务运行中时禁用编辑按钮
        edit_btn.setEnabled(task.status != TrainingTaskStatus.RUNNING)
        if task.task_id is not None:
            edit_btn.clicked.connect(lambda checked, tid=task.task_id: self.edit_task(tid))
        btn_layout.addWidget(edit_btn)
        
        # 删除按钮
        delete_btn = QPushButton("删除")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 2px 8px;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        if task.task_id is not None:
            delete_btn.clicked.connect(lambda checked, tid=task.task_id: self.delete_task(tid))
        btn_layout.addWidget(delete_btn)
        
        # 日志按钮
        log_btn = QPushButton("日志")
        log_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 2px 8px;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        if task.task_id is not None:
            log_btn.clicked.connect(lambda checked, tid=task.task_id: self.view_execution_log(tid))
        btn_layout.addWidget(log_btn)
        
        # 训练日志按钮
        train_log_btn = QPushButton("训练日志")
        train_log_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                padding: 2px 8px;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        if task.task_id is not None:
            train_log_btn.clicked.connect(lambda checked, tid=task.task_id: self.view_training_log(tid))
        btn_layout.addWidget(train_log_btn)
        
        # 训练日志文件按钮
        train_log_file_btn = QPushButton("日志文件")
        train_log_file_btn.setStyleSheet("""
            QPushButton {
                background-color: #6f42c1;
                color: white;
                border: none;
                padding: 2px 8px;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #5a32a3;
            }
        """)
        if task.task_id is not None:
            train_log_file_btn.clicked.connect(lambda checked, tid=task.task_id: self.view_training_log_file(tid))
        btn_layout.addWidget(train_log_file_btn)
        
        self.task_tree.setItemWidget(item, 4, btn_widget)
    
    def delete_task(self, task_id: int):
        """删除任务（如果任务运行中则先停止）"""
        task = self.task_manager.get_task_by_id(task_id)
        if not task:
            return
        
        # 如果任务正在运行，先停止任务
        if task.status == TrainingTaskStatus.RUNNING:
            reply = QMessageBox.question(
                self, "确认停止", 
                "该任务正在运行中，是否停止任务？",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                try:
                    self.stop_task(task_id)
                except Exception as e:
                    logger.error(f"停止任务失败: {e}")
                    QMessageBox.critical(self, "错误", f"停止任务失败: {str(e)}")
            return
        
        # 任务未运行，确认删除
        reply = QMessageBox.question(
            self, "确认删除", 
            "确定要删除这个训练任务吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.task_manager.delete_task(task_id)
            self.load_tasks()
    
    def check_conda_environment(self, env_name: str) -> bool:
        """检查conda环境是否存在"""
        try:
            # 执行conda命令检查环境是否存在
            result = subprocess.run(
                ["conda", "env", "list"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # 检查输出中是否包含指定的环境名称
                return env_name in result.stdout
            else:
                logger.warning(f"检查conda环境失败: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            logger.error("检查conda环境超时")
            return False
        except FileNotFoundError:
            logger.error("未找到conda命令，请确保已安装conda")
            return False
        except Exception as e:
            logger.error(f"检查conda环境时发生异常: {str(e)}")
            return False
    
    def start_task(self, task_id: int):
        """开始训练任务（创建并启动）"""
        task = self.task_manager.get_task_by_id(task_id)
        if not task:
            return
        
        # 清空之前的执行日志
        task.execution_log = ""
        
        try:
            if task.task_type == TrainingTaskType.LOCAL:
                self.start_local_training(task)
                # 更新任务状态
                task.status = TrainingTaskStatus.RUNNING
                self.task_manager.update_task(task)
                self.update_task_widget_status(task_id, TrainingTaskStatus.RUNNING)
                QMessageBox.information(self, "成功", "训练任务已启动")
            else:
                # 远程训练使用异步上传
                self.start_remote_training_async(task)
        except Exception as e:
            error_msg = f"启动训练任务失败: {str(e)}"
            logger.error(error_msg)
            task.execution_log += f"\n[ERROR] {error_msg}\n"
            task.status = TrainingTaskStatus.ERROR
            self.task_manager.update_task(task)
            self.update_task_widget_status(task_id, TrainingTaskStatus.ERROR)
            QMessageBox.critical(self, "错误", error_msg)
    
    def start_local_training(self, task: TrainingTask):
        """启动本地训练"""
        task.execution_log += "[INFO] 开始本地训练任务...\n"
        
        # 检查数据集路径
        if not os.path.exists(task.dataset_path):
            raise Exception(f"数据集路径不存在: {task.dataset_path}")
        
        task.execution_log += f"[INFO] 数据集路径: {task.dataset_path}\n"
        
        # 生成训练脚本
        task.execution_log += "[INFO] 生成训练脚本\n"
        self.generate_train_script(task.dataset_path)
        train_script = os.path.join(task.dataset_path, "train.py")
        task.execution_log += f"[INFO] 训练脚本路径: {train_script}\n"
        
        # 检查conda环境
        if task.conda_env:
            task.execution_log += f"[INFO] 检查conda环境: {task.conda_env}\n"
            if not self.check_conda_environment(task.conda_env):
                error_msg = f"conda环境 '{task.conda_env}' 不存在，请先配置conda环境"
                task.execution_log += f"[ERROR] {error_msg}\n"
                raise Exception(error_msg)
        
        # 根据平台构建后台命令
        import platform
        system = platform.system().lower()
        
        if system == "linux" or system == "darwin":  # Linux or macOS
            # 使用nohup在后台运行，并将日志输出到train.log
            if task.conda_env:
                full_cmd = f"cd {task.dataset_path} && conda activate {task.conda_env} && nohup python train.py train > ./train.log 2>&1 &"
            else:
                full_cmd = f"cd {task.dataset_path} && nohup python train.py train > ./train.log 2>&1 &"
            task.execution_log += f"[INFO] 使用平台命令启动后台训练 (Linux/macOS): {full_cmd}\n"
        elif system == "windows":
            # Windows使用start命令
            if task.conda_env:
                full_cmd = f"cd /d {task.dataset_path} && conda activate {task.conda_env} && start /B python train.py train > train.log 2>&1"
            else:
                full_cmd = f"cd /d {task.dataset_path} && start /B python train.py train > train.log 2>&1"
            task.execution_log += f"[INFO] 使用平台命令启动后台训练 (Windows): {full_cmd}\n"
        else:
            # 其他平台使用默认方式
            if task.conda_env:
                full_cmd = f"conda run -n {task.conda_env} python train.py train"
            else:
                full_cmd = f"python train.py train"
            task.execution_log += f"[INFO] 使用默认方式启动训练: {full_cmd}\n"
        
        task.execution_log += f"[INFO] 执行命令: {full_cmd}\n"
        
        # 启动进程
        try:
            if system == "linux" or system == "darwin" or system == "windows":
                # 对于Linux/macOS/Windows，直接执行后台命令
                result = subprocess.run(full_cmd, shell=True, cwd=task.dataset_path, 
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                if result.returncode == 0:
                    task.execution_log += "[INFO] 后台训练任务启动成功\n"
                    if result.stdout:
                        task.execution_log += f"[OUTPUT] {result.stdout}\n"
                else:
                    task.execution_log += f"[WARNING] 后台命令执行可能存在问题: {result.stderr}\n"
                
                # 获取进程ID（对于nohup启动的进程，需要特殊处理）
                if system == "linux" or system == "darwin":
                    # 尝试获取最近启动的python进程ID
                    try:
                        ps_result = subprocess.run("ps aux | grep 'python.*train.py' | grep -v grep | head -1 | awk '{print $2}'", 
                                                 shell=True, cwd=task.dataset_path, 
                                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        if ps_result.stdout.strip():
                            task.process_id = int(ps_result.stdout.strip())
                            task.execution_log += f"[INFO] 获取到训练进程ID: {task.process_id}\n"
                    except Exception as e:
                        task.execution_log += f"[WARNING] 无法获取训练进程ID: {str(e)}\n"
                elif system == "windows":
                    # Windows下获取进程ID比较复杂，暂时留空
                    task.execution_log += "[INFO] Windows平台下进程ID获取暂不支持\n"
            else:
                # 其他平台使用原来的Popen方式
                process = subprocess.Popen(
                    full_cmd,
                    shell=True,
                    cwd=task.dataset_path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                if task.task_id is not None:
                    self.running_processes[task.task_id] = process
                task.process_id = process.pid
                
                task.execution_log += f"[INFO] 训练任务已启动: PID={process.pid}\n"
                logger.info(f"本地训练任务已启动: PID={process.pid}")
        except Exception as e:
            task.execution_log += f"[ERROR] 启动进程失败: {str(e)}\n"
            raise
    
    def start_remote_training(self, task: TrainingTask):
        """启动远程训练（连接服务器、上传数据、启动训练）"""
        task.execution_log += "[INFO] 开始远程训练任务...\n"
        
        # 获取服务器配置
        if task.server_id is None:
            raise Exception("服务器配置不存在")
        
        server_config = self.server_config_manager.get_server_config_by_id(task.server_id)
        if not server_config:
            raise Exception("服务器配置不存在")
        
        task.execution_log += f"[INFO] 连接服务器: {server_config.name} ({server_config.host})\n"
        
        # 连接服务器
        ssh_client = SSHClient(server_config)
        if not ssh_client.connect_to_server():
            task.execution_log += "[ERROR] 连接服务器失败\n"
            raise Exception("连接服务器失败")
        
        task.execution_log += "[INFO] 服务器连接成功\n"
        
        try:
            # 检查远程环境
            task.execution_log += "[INFO] 检查远程环境...\n"
            self.ensure_remote_environment(ssh_client, task)
            
            # 创建远程目录
            remote_dataset_path = task.remote_path
            task.execution_log += f"[INFO] 创建远程目录: {remote_dataset_path}\n"
            if ssh_client.ssh_client:
                ssh_client.ssh_client.exec_command(f"mkdir -p {remote_dataset_path}")
            
            # 上传数据集
            task.execution_log += f"[INFO] 上传数据集到远程服务器...\n"
            local_dataset_path = task.dataset_path
            
            if not os.path.exists(local_dataset_path):
                task.execution_log += f"[ERROR] 本地数据集路径不存在: {local_dataset_path}\n"
                raise Exception(f"本地数据集路径不存在: {local_dataset_path}")
            
            # 上传数据集文件（递归上传整个目录）
            self.upload_directory(ssh_client, local_dataset_path, remote_dataset_path, task)
            
            task.execution_log += "[INFO] 数据集上传完成\n"
            
            # 生成训练脚本
            task.execution_log += "[INFO] 生成远程训练脚本\n"
            self.generate_remote_train_script(ssh_client, remote_dataset_path)
            
            # 构建训练命令
            if task.conda_env:
                # 分步执行：先激活conda环境，再进入训练路径，最后执行训练命令
                task.execution_log += f"[INFO] 使用conda环境: {task.conda_env}\n"
                # 使用分步命令执行训练
                nohup_cmd = f"cd {remote_dataset_path} && conda activate {task.conda_env} && nohup python train.py train > ./train.log 2>&1 &"
            else:
                # 不使用conda环境
                nohup_cmd = f"cd {remote_dataset_path} && nohup python train.py train > ./train.log 2>&1 &"
            
            task.execution_log += f"[INFO] 执行命令: {nohup_cmd}\n"
            
            # 在后台运行训练命令
            if ssh_client.ssh_client:
                stdin, stdout, stderr = ssh_client.ssh_client.exec_command(nohup_cmd)
                # 读取输出
                output = stdout.read().decode()
                error = stderr.read().decode()
                if output:
                    task.execution_log += f"[OUTPUT] {output}\n"
                if error:
                    task.execution_log += f"[ERROR] {error}\n"
            
            task.execution_log += "[INFO] 远程训练任务已启动\n"
            logger.info(f"远程训练任务已启动")
        except Exception as e:
            task.execution_log += f"[ERROR] 远程训练失败: {str(e)}\n"
            raise
        finally:
            ssh_client.disconnect_from_server()
            task.execution_log += "[INFO] 已断开服务器连接\n"
    
    def ensure_remote_environment(self, ssh_client: SSHClient, task: TrainingTask):
        """确保远程环境配置正确"""
        if not ssh_client.ssh_client:
            return
            
        # 检查conda环境是否存在
        if task.conda_env:
            stdin, stdout, stderr = ssh_client.ssh_client.exec_command(f"conda env list | grep {task.conda_env}")
            env_exists = task.conda_env in stdout.read().decode()
            
            if not env_exists:
                # 创建conda环境
                logger.info(f"创建conda环境: {task.conda_env}")
                create_cmd = f"conda create -n {task.conda_env} python=3.9 -y"
                stdin, stdout, stderr = ssh_client.ssh_client.exec_command(create_cmd)
                stdout.channel.recv_exit_status()  # 等待命令完成
            
            # 检查ultralytics是否安装
            check_cmd = f"conda run -n {task.conda_env} python -c 'import ultralytics'"
            stdin, stdout, stderr = ssh_client.ssh_client.exec_command(check_cmd)
            if stdout.channel.recv_exit_status() != 0:
                # 安装ultralytics
                logger.info(f"安装ultralytics到环境: {task.conda_env}")
                install_cmd = f"conda run -n {task.conda_env} pip install ultralytics"
                stdin, stdout, stderr = ssh_client.ssh_client.exec_command(install_cmd)
                stdout.channel.recv_exit_status()  # 等待命令完成
    
    def upload_directory(self, ssh_client: SSHClient, local_path: str, remote_path: str, task: TrainingTask):
        """递归上传目录到远程服务器"""
        try:
            if not ssh_client.ssh_client:
                raise Exception("SSH客户端未连接")
            
            # 确保远程目录存在
            ssh_client.ssh_client.exec_command(f"mkdir -p {remote_path}")
            
            # 遍历本地目录
            for root, dirs, files in os.walk(local_path):
                # 计算相对路径
                rel_path = os.path.relpath(root, local_path)
                if rel_path == ".":
                    remote_root = remote_path
                else:
                    remote_root = os.path.join(remote_path, rel_path).replace("\\", "/")
                
                # 确保远程子目录存在
                ssh_client.ssh_client.exec_command(f"mkdir -p {remote_root}")
                
                # 上传文件
                for file in files:
                    local_file = os.path.join(root, file)
                    remote_file = os.path.join(remote_root, file).replace("\\", "/")
                    
                    try:
                        ssh_client.upload_file(local_file, remote_file)
                        task.execution_log += f"[INFO] 上传文件: {local_file} -> {remote_file}\n"
                    except Exception as e:
                        task.execution_log += f"[ERROR] 上传文件失败 {local_file}: {str(e)}\n"
                        raise Exception(f"上传文件失败 {local_file}: {str(e)}")
        except Exception as e:
            raise Exception(f"上传目录失败: {str(e)}")
    
    def start_remote_training_async(self, task: TrainingTask):
        """异步开始远程训练任务"""
        # 更新任务状态为上传中
        task.status = TrainingTaskStatus.UPLOADING
        self.task_manager.update_task(task)
        if task.task_id is not None:
            self.update_task_widget_status(task.task_id, TrainingTaskStatus.UPLOADING)
        
        # 获取服务器配置
        if task.server_id is None:
            raise Exception("服务器配置不存在")
        
        server_config = self.server_config_manager.get_server_config_by_id(task.server_id)
        if not server_config:
            raise Exception("服务器配置不存在")
        
        # 连接服务器
        ssh_client = SSHClient(server_config)
        if not ssh_client.connect_to_server():
            raise Exception("连接服务器失败")
        
        # 创建异步上传器
        uploader = AsyncUploader(ssh_client, task)
        
        # 连接信号
        if task.task_id is not None:
            tid = task.task_id
            uploader.upload_progress.connect(lambda uploaded, total: self.update_upload_progress(tid, uploaded, total))
        uploader.upload_completed.connect(lambda: self.on_upload_completed(task))
        uploader.upload_error.connect(lambda error: self.on_upload_error(task, error))
        uploader.upload_log.connect(lambda log: self.on_upload_log(task, log))
        
        # 开始上传
        uploader.start_upload()
    
    def update_upload_progress(self, task_id: int, uploaded: int, total: int):
        """更新上传进度"""
        # 这里可以更新UI显示上传进度
        if total > 0:
            progress = (uploaded / total) * 100
            logger.info(f"任务 {task_id} 上传进度: {uploaded}/{total} ({progress:.1f}%)")
    
    def on_upload_completed(self, task: TrainingTask):
        """上传完成回调"""
        try:
            # 上传完成，开始训练
            self.start_remote_training(task)
            # 更新任务状态
            task.status = TrainingTaskStatus.RUNNING
            self.task_manager.update_task(task)
            if task.task_id is not None:
                self.update_task_widget_status(task.task_id, TrainingTaskStatus.RUNNING)
            QMessageBox.information(self, "成功", "文件上传完成，训练任务已启动")
        except Exception as e:
            error_msg = f"启动远程训练失败: {str(e)}"
            logger.error(error_msg)
            task.execution_log += f"\n[ERROR] {error_msg}\n"
            task.status = TrainingTaskStatus.ERROR
            self.task_manager.update_task(task)
            if task.task_id is not None:
                self.update_task_widget_status(task.task_id, TrainingTaskStatus.ERROR)
            QMessageBox.critical(self, "错误", error_msg)
    
    def on_upload_error(self, task: TrainingTask, error: str):
        """上传错误回调"""
        error_msg = f"文件上传失败: {error}"
        logger.error(error_msg)
        task.execution_log += f"\n[ERROR] {error_msg}\n"
        task.status = TrainingTaskStatus.ERROR
        self.task_manager.update_task(task)
        if task.task_id is not None:
            self.update_task_widget_status(task.task_id, TrainingTaskStatus.ERROR)
        QMessageBox.critical(self, "错误", error_msg)
    
    def on_upload_log(self, task: TrainingTask, log: str):
        """上传日志回调"""
        task.execution_log += f"{log}\n"
        self.task_manager.update_task(task)
    
    def generate_train_script(self, dataset_path: str):
        """从模板生成训练脚本"""
        try:
            # 获取模板文件路径
            template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'train_template.py')
            
            # 检查模板文件是否存在
            if not os.path.exists(template_path):
                raise Exception(f"训练脚本模板不存在: {template_path}")
            
            # 读取模板内容
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            # 生成训练脚本路径
            train_script_path = os.path.join(dataset_path, "train.py")
            
            # 写入训练脚本
            with open(train_script_path, 'w', encoding='utf-8') as f:
                f.write(template_content)
            
            logger.info(f"训练脚本已生成: {train_script_path}")
        except Exception as e:
            logger.error(f"生成训练脚本失败: {str(e)}")
            raise Exception(f"生成训练脚本失败: {str(e)}")
    
    def generate_remote_train_script(self, ssh_client: SSHClient, remote_path: str):
        """在远程服务器上生成训练脚本"""
        try:
            if not ssh_client.ssh_client:
                raise Exception("SSH客户端未连接")
            
            # 获取模板文件路径
            template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'train_template.py')
            
            # 检查本地模板文件是否存在
            if not os.path.exists(template_path):
                raise Exception(f"训练脚本模板不存在: {template_path}")
            
            # 读取模板内容
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            # 生成远程训练脚本路径
            remote_train_script_path = os.path.join(remote_path, "train.py")
            
            # 写入远程训练脚本
            stdin, stdout, stderr = ssh_client.ssh_client.exec_command(f"cat > {remote_train_script_path}")
            stdin.write(template_content)
            stdin.flush()
            stdin.close()
            
            logger.info(f"远程训练脚本已生成: {remote_train_script_path}")
        except Exception as e:
            logger.error(f"生成远程训练脚本失败: {str(e)}")
            raise Exception(f"生成远程训练脚本失败: {str(e)}")
    
    def stop_task(self, task_id: int):
        """停止训练任务"""
        task = self.task_manager.get_task_by_id(task_id)
        if not task:
            return
        
        try:
            if task.task_type == TrainingTaskType.LOCAL:
                # 停止本地进程
                if task_id in self.running_processes:
                    process = self.running_processes[task_id]
                    process.terminate()
                    del self.running_processes[task_id]
            else:
                # 停止远程进程
                if task.server_id is not None:
                    server_config = self.server_config_manager.get_server_config_by_id(task.server_id)
                    if server_config:
                        ssh_client = SSHClient(server_config)
                        if ssh_client.connect_to_server() and ssh_client.ssh_client:
                            # 查找并杀死python训练进程
                            kill_cmd = f"pkill -f 'python.*train.py'"
                            ssh_client.ssh_client.exec_command(kill_cmd)
                            ssh_client.disconnect_from_server()
            
            # 更新任务状态
            task.status = TrainingTaskStatus.STOPPED
            task.process_id = None
            self.task_manager.update_task(task)
            self.update_task_widget_status(task_id, TrainingTaskStatus.STOPPED)
            
            QMessageBox.information(self, "成功", "训练任务已停止")
        except Exception as e:
            logger.error(f"停止训练任务失败: {e}")
            QMessageBox.critical(self, "错误", f"停止训练任务失败: {str(e)}")
    
    def view_execution_log(self, task_id: int):
        """查看执行日志（命令执行过程的日志）"""
        task = self.task_manager.get_task_by_id(task_id)
        if not task:
            return
        
        # 创建简单的日志对话框
        from PyQt5.QtWidgets import QTextEdit
        dialog = QDialog(self)
        dialog.setWindowTitle(f"执行日志 - {task.name}")
        dialog.setMinimumSize(700, 500)
        
        layout = QVBoxLayout(dialog)
        
        # 日志文本框
        log_text = QTextEdit()
        log_text.setReadOnly(True)
        log_text.setStyleSheet("""
            QTextEdit {
                font-family: monospace;
                font-size: 11px;
                background-color: #f8f9fa;
            }
        """)
        log_text.setPlainText(task.execution_log if task.execution_log else "暂无执行日志")
        layout.addWidget(log_text)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.reject)
        layout.addWidget(close_btn)
        
        dialog.exec()
    
    def view_training_log(self, task_id: int):
        """查看训练日志（results.csv的图表展示）"""
        task = self.task_manager.get_task_by_id(task_id)
        if not task:
            return
        
        # 打开训练日志查看器对话框
        dialog = TrainingLogViewer(task, self.server_config_manager, parent=self)
        dialog.exec()
    
    def view_training_log_file(self, task_id: int):
        """查看训练日志文件（train.log）并支持持续监听"""
        task = self.task_manager.get_task_by_id(task_id)
        if not task:
            return
        
        # 创建日志查看对话框
        dialog = QDialog(self)
        dialog.setWindowTitle(f"训练日志文件 - {task.name}")
        dialog.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(dialog)
        
        # 控制面板
        control_widget = QWidget()
        control_layout = QHBoxLayout(control_widget)
        
        # 实时监听复选框
        auto_refresh_checkbox = QCheckBox("实时监听")
        auto_refresh_checkbox.setChecked(True)
        control_layout.addWidget(auto_refresh_checkbox)
        
        # 显示行数
        lines_label = QLabel("显示行数:")
        control_layout.addWidget(lines_label)
        
        lines_spinbox = QSpinBox()
        lines_spinbox.setRange(10, 10000)
        lines_spinbox.setValue(100)
        lines_spinbox.setSingleStep(10)
        control_layout.addWidget(lines_spinbox)
        
        control_layout.addStretch()
        
        layout.addWidget(control_widget)
        
        # 日志文本框
        log_text = QTextEdit()
        log_text.setReadOnly(True)
        log_text.setStyleSheet("""
            QTextEdit {
                font-family: monospace;
                font-size: 11px;
                background-color: #f8f9fa;
            }
        """)
        layout.addWidget(log_text)
        
        # 定时器
        refresh_timer = QTimer()
        
        def load_log_content():
            """加载日志内容"""
            try:
                if task.task_type == TrainingTaskType.LOCAL:
                    # 本地训练日志
                    log_file = os.path.join(task.dataset_path, "train.log")
                    if os.path.exists(log_file):
                        with open(log_file, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            
                        # 获取显示行数
                        display_lines = lines_spinbox.value()
                        if len(lines) > display_lines:
                            lines = lines[-display_lines:]
                            
                        log_content = ''.join(lines)
                        log_text.setPlainText(log_content)
                        
                        # 滚动到底部
                        if auto_refresh_checkbox.isChecked():
                            log_text.moveCursor(log_text.textCursor().End)
                    else:
                        log_text.setPlainText("日志文件不存在")
                else:
                    # 远程训练日志
                    if task.server_id is not None:
                        server_config = self.server_config_manager.get_server_config_by_id(task.server_id)
                        if server_config:
                            ssh_client = SSHClient(server_config)
                            if ssh_client.connect_to_server() and ssh_client.ssh_client:
                                try:
                                    # 读取远程日志文件
                                    remote_log_file = os.path.join(task.remote_path, "train.log")
                                    stdin, stdout, stderr = ssh_client.ssh_client.exec_command(f"tail -n {lines_spinbox.value()} {remote_log_file}")
                                    log_content = stdout.read().decode('utf-8')
                                    log_text.setPlainText(log_content)
                                    
                                    # 滚动到底部
                                    if auto_refresh_checkbox.isChecked():
                                        log_text.moveCursor(log_text.textCursor().End)
                                except Exception as e:
                                    log_text.setPlainText(f"读取远程日志失败: {str(e)}")
                                finally:
                                    ssh_client.disconnect_from_server()
                            else:
                                log_text.setPlainText("连接服务器失败")
                        else:
                            log_text.setPlainText("服务器配置不存在")
                    else:
                        log_text.setPlainText("服务器配置不存在")
            except Exception as e:
                log_text.setPlainText(f"读取日志失败: {str(e)}")
        
        def on_refresh():
            """刷新日志"""
            if auto_refresh_checkbox.isChecked():
                load_log_content()
        
        # 连接信号
        refresh_timer.timeout.connect(on_refresh)
        lines_spinbox.valueChanged.connect(load_log_content)
        auto_refresh_checkbox.stateChanged.connect(lambda: refresh_timer.start(2000) if auto_refresh_checkbox.isChecked() else None)
        
        # 初始加载日志
        load_log_content()
        
        # 启动定时刷新（2秒）
        refresh_timer.start(2000)
        
        # 关闭事件处理
        def on_close():
            refresh_timer.stop()
            dialog.reject()
        
        # 按钮布局
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(load_log_content)
        btn_layout.addWidget(refresh_btn)
        
        btn_layout.addStretch()
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(on_close)
        btn_layout.addWidget(close_btn)
        
        layout.addWidget(btn_widget)
        
        # 对话框关闭事件
        dialog.finished.connect(on_close)
        
        dialog.exec()
    
    def view_models(self, task_id: int):
        """查看模型文件"""
        task = self.task_manager.get_task_by_id(task_id)
        if not task:
            return
        
        # 查找runs目录
        if task.task_type == TrainingTaskType.LOCAL:
            # 本地模式
            runs_dir = os.path.join(task.dataset_path, "runs", "detect")
            if os.path.exists(runs_dir):
                # 显示模型路径
                msg = f"训练输出目录: {runs_dir}\n\n"
                # 列出所有训练结果
                for item in os.listdir(runs_dir):
                    item_path = os.path.join(runs_dir, item)
                    if os.path.isdir(item_path):
                        weights_dir = os.path.join(item_path, "weights")
                        if os.path.exists(weights_dir):
                            msg += f"\n{item}:\n"
                            for weight_file in os.listdir(weights_dir):
                                msg += f"  - {os.path.join(weights_dir, weight_file)}\n"
                
                QMessageBox.information(self, "模型文件", msg)
            else:
                QMessageBox.warning(self, "提示", "未找到训练输出目录")
        else:
            # 远程模式 - 提供下载功能
            QMessageBox.information(self, "提示", 
                f"远程训练模式\n"
                f"模型路径: {task.remote_path}/runs/detect/\n\n"
                f"请使用远程文件浏览器下载模型文件")
    
    def update_task_widget_status(self, task_id: int, status: TrainingTaskStatus):
        """更新任务Widget的状态显示"""
        # 重新加载任务列表以刷新状态显示
        self.load_tasks()
