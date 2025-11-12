import os
import csv
import subprocess
from typing import Optional, Dict
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTreeWidget, QTreeWidgetItem, QMessageBox, QDialog,
                             QLabel, QHeaderView)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from ..logging_config import logger
from .training_task import TrainingTask, TrainingTaskManager, TrainingTaskStatus, TrainingTaskType
from .task_edit_dialog import TaskEditDialog
from .training_log_viewer import TrainingLogViewer
from ..remote_server.server_config import ServerConfigManager, ServerConfig
from ..remote_server.ssh_client import SSHClient





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
            self.task_tree.setColumnWidth(4, 320)  # 增加操作列宽度以容纳开始按钮
        
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
        
        # 开始按钮
        start_btn = QPushButton("开始")
        start_btn.setStyleSheet("""
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
        start_btn.setEnabled(task.status != TrainingTaskStatus.RUNNING)
        if task.task_id is not None:
            start_btn.clicked.connect(lambda: self.start_task(task.task_id))
        btn_layout.addWidget(start_btn)
        
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
            edit_btn.clicked.connect(lambda: self.edit_task(task.task_id))
        btn_layout.addWidget(edit_btn)
        
        # 删除按钮（运行中时显示为停止）
        delete_btn = QPushButton("删除" if task.status != TrainingTaskStatus.RUNNING else "停止")
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
            delete_btn.clicked.connect(lambda: self.delete_task(task.task_id))
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
            log_btn.clicked.connect(lambda: self.view_execution_log(task.task_id))
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
            train_log_btn.clicked.connect(lambda: self.view_training_log(task.task_id))
        btn_layout.addWidget(train_log_btn)
        
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
            else:
                self.start_remote_training(task)
            
            # 更新任务状态
            task.status = TrainingTaskStatus.RUNNING
            self.task_manager.update_task(task)
            self.update_task_widget_status(task_id, TrainingTaskStatus.RUNNING)
            
            QMessageBox.information(self, "成功", "训练任务已启动")
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
        train_script = os.path.join(task.dataset_path, "train.py")
        task.execution_log += f"[INFO] 生成训练脚本: {train_script}\n"
        
        # TODO: 这里应该从模板生成train.py脚本
        # 目前假设脚本已存在
        if not os.path.exists(train_script):
            task.execution_log += "[WARNING] 训练脚本不存在，尝试生成...\n"
            # 这里可以添加生成逻辑
            raise Exception(f"训练脚本不存在: {train_script}")
        
        # 检查conda环境
        if task.conda_env:
            task.execution_log += f"[INFO] 检查conda环境: {task.conda_env}\n"
            if not self.check_conda_environment(task.conda_env):
                error_msg = f"conda环境 '{task.conda_env}' 不存在，请先配置conda环境"
                task.execution_log += f"[ERROR] {error_msg}\n"
                raise Exception(error_msg)
            
            # 使用conda环境构建命令
            cmd = f"conda run -n {task.conda_env} python train.py train"
            task.execution_log += f"[INFO] 使用conda环境: {task.conda_env}\n"
        else:
            # 不使用conda环境
            cmd = f"python train.py train"
            task.execution_log += "[INFO] 不使用conda环境\n"
        
        task.execution_log += f"[INFO] 执行命令: {cmd}\n"
        
        # 启动进程
        try:
            process = subprocess.Popen(
                cmd,
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
            
            # 构建训练命令
            if task.conda_env:
                cmd = f"cd {remote_dataset_path} && conda run -n {task.conda_env} python train.py train"
                task.execution_log += f"[INFO] 使用conda环境: {task.conda_env}\n"
            else:
                cmd = f"cd {remote_dataset_path} && python train.py train"
            
            task.execution_log += f"[INFO] 执行命令: {cmd}\n"
            
            # 在后台运行训练命令
            nohup_cmd = f"nohup {cmd} > training.log 2>&1 &"
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
