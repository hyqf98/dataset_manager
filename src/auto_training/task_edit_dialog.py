"""训练任务编辑对话框"""
import os
import subprocess
from typing import Optional
from PyQt5.QtWidgets import (QDialog, QFormLayout, QVBoxLayout, QHBoxLayout, QLineEdit, 
                              QComboBox, QPushButton, QMessageBox, QFileDialog, QWidget, QLabel, QDialogButtonBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from .training_task import TrainingTask, TrainingTaskType, TrainingTaskStatus
from ..remote_server.server_config import ServerConfigManager
from ..remote_server.file_transfer_dialog import RemoteBrowserDialog
from ..logging_config import logger


class TaskEditDialog(QDialog):
    """任务编辑对话框"""
    
    def __init__(self, parent=None, task: Optional[TrainingTask] = None):
        super().__init__(parent)
        self.task = task
        self.is_edit_mode = task is not None
        self.server_config_manager = ServerConfigManager()
        
        self.setWindowTitle("添加训练任务" if self.is_edit_mode else "新增训练任务")
        self.setModal(True)
        self.resize(400, 350)
        
        self.init_ui()
        
        # 如果是编辑模式,加载任务数据
        if self.is_edit_mode and task:
            self.load_task_data(task)
    
    def init_ui(self):
        """初始化UI"""
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        layout.setLabelAlignment(Qt.AlignRight)  # type: ignore
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)  # type: ignore
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入任务名称...")
        layout.addRow("任务名称:", self.name_edit)
        
        self.type_combo = QComboBox()
        self.type_combo.addItem(TrainingTaskType.LOCAL.value, TrainingTaskType.LOCAL)
        self.type_combo.addItem(TrainingTaskType.REMOTE.value, TrainingTaskType.REMOTE)
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        layout.addRow("任务类型:", self.type_combo)
        
        # 数据集路径
        dataset_layout = QHBoxLayout()
        self.dataset_path_edit = QLineEdit()
        self.dataset_path_edit.setPlaceholderText("选择数据集路径...")
        dataset_layout.addWidget(self.dataset_path_edit, 1)
        
        self.dataset_path_btn = QPushButton("浏览")
        self.dataset_path_btn.clicked.connect(self.select_dataset_path)
        dataset_layout.addWidget(self.dataset_path_btn)
        layout.addRow("训练集路径:", dataset_layout)
        
        # 任务保存路径(根据任务类型动态显示)
        self.save_path_widget = QWidget()
        save_path_layout = QHBoxLayout(self.save_path_widget)
        self.save_path_edit = QLineEdit()
        self.save_path_edit.setPlaceholderText("选择任务保存路径...")
        save_path_layout.addWidget(self.save_path_edit, 1)
        
        self.save_path_btn = QPushButton("浏览")
        self.save_path_btn.clicked.connect(self.select_save_path)
        save_path_layout.addWidget(self.save_path_btn)
        layout.addRow("任务保存路径:", self.save_path_widget)
        
        # 远程服务器(远程训练) - 创建一个包装widget来包含整行
        self.server_row_widget = QWidget()
        server_row_layout = QHBoxLayout(self.server_row_widget)
        server_row_layout.setContentsMargins(0, 0, 0, 0)
        self.server_widget = QWidget()
        server_layout = QHBoxLayout(self.server_widget)
        server_layout.setContentsMargins(0, 0, 0, 0)
        self.server_combo = QComboBox()
        server_layout.addWidget(self.server_combo)
        server_row_layout.addWidget(QLabel("远程服务器:"), 0)
        server_row_layout.addWidget(self.server_widget, 1)
        layout.addRow(self.server_row_widget)
        
        # 加载服务器列表
        self.load_servers()
        
        # 环境框架(下拉选择)
        self.framework_combo = QComboBox()
        self.framework_combo.addItem("conda", "conda")
        self.framework_combo.setCurrentIndex(0)  # 默认选择conda
        layout.addRow("环境框架:", self.framework_combo)
        
        # Conda环境(下拉框选择)
        conda_env_layout = QHBoxLayout()
        self.conda_env_combo = QComboBox()
        self.conda_env_combo.setEditable(True)  # 允许手动输入
        self.conda_env_combo.setPlaceholderText("选择或输入conda环境名称")
        conda_env_layout.addWidget(self.conda_env_combo, 1)
        
        refresh_conda_btn = QPushButton("刷新")
        refresh_conda_btn.clicked.connect(self.refresh_conda_envs)
        refresh_conda_btn.setMaximumWidth(60)
        conda_env_layout.addWidget(refresh_conda_btn)
        
        layout.addRow("环境:", conda_env_layout)
        
        # 按钮
        buttons = QDialogButtonBox()
        buttons.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)  # type: ignore
        buttons.accepted.connect(self.save_task)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        # 初始显示/隐藏控件
        self.on_type_changed(0)
    
    def load_servers(self):
        """加载服务器列表"""
        self.server_combo.clear()
        servers = self.server_config_manager.get_server_configs()
        for server in servers:
            self.server_combo.addItem(server.name, server.id)
        
        # 连接服务器切换信号
        self.server_combo.currentIndexChanged.connect(self.on_server_changed)
    
    def on_type_changed(self, index):
        """任务类型改变时的处理"""
        task_type = self.type_combo.itemData(index)
        
        # 根据类型显示/隐藏相关控件
        is_local = task_type == TrainingTaskType.LOCAL
        
        # 服务器控件(仅远程训练时显示)
        self.server_row_widget.setVisible(not is_local)
        
        # 更新保存路径按钮文本
        if is_local:
            self.save_path_btn.setText("浏览")
        else:
            self.save_path_btn.setText("远程浏览")
        
        # 不再自动刷新环境列表，只在点击刷新按钮时刷新
    
    def on_server_changed(self, index):
        """服务器切换时不再自动刷新环境列表"""
        # 不再自动刷新，用户需要手动点击刷新按钮
        pass
    
    def select_dataset_path(self):
        """选择数据集路径"""
        # 使用文件对话框选择数据集路径(与数据集划分模块保持一致)
        path = QFileDialog.getExistingDirectory(self, "选择数据集路径")
        if path:
            # 检查是否为已划分的数据集(包含train.yml文件)
            train_yml = os.path.join(path, "train.yml")
            if os.path.exists(train_yml):
                self.dataset_path_edit.setText(path)
            else:
                # 如果不是已划分的数据集,提示用户
                reply = QMessageBox.question(
                    self, "确认", 
                    "该目录不包含train.yml配置文件,可能不是已划分的数据集。\n"
                    "请确保选择的是通过'数据集划分'功能生成的数据集目录。\n\n"
                    "是否仍然使用这个路径?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.dataset_path_edit.setText(path)
    
    def select_save_path(self):
        """选择保存路径"""
        task_type = self.type_combo.currentData()
        
        if task_type == TrainingTaskType.LOCAL:
            # 本地训练:选择本地路径
            path = QFileDialog.getExistingDirectory(self, "选择保存路径")
            if path:
                self.save_path_edit.setText(path)
        else:
            # 远程训练:选择远程路径
            # 检查是否选择了服务器
            if self.server_combo.count() == 0:
                QMessageBox.warning(self, "警告", "请先在服务器管理中配置远程服务器")
                return
            
            server_id = self.server_combo.currentData()
            if server_id is None:
                QMessageBox.warning(self, "警告", "请先选择一个服务器")
                return
            
            # 获取服务器配置
            server_config = self.server_config_manager.get_server_config_by_id(server_id)
            if not server_config:
                QMessageBox.warning(self, "警告", "服务器配置不存在")
                return
            
            # 打开远程文件浏览器对话框
            dialog = RemoteBrowserDialog(server_config, parent=self)
            if dialog.exec() == QDialog.Accepted:
                selected_path = dialog.get_selected_path()
                if selected_path:
                    self.save_path_edit.setText(selected_path)
    
    def select_remote_path(self):
        """选择远程路径"""
        # 此方法已不再需要，因为保存路径选择已合并
        pass
    
    def refresh_conda_envs(self):
        """刷新conda环境列表"""
        self.conda_env_combo.clear()
        
        # 获取当前任务类型
        task_type = self.type_combo.currentData()
        
        if task_type == TrainingTaskType.LOCAL:
            # 本地模式:获取本地conda环境
            envs = self.get_local_conda_envs()
            if envs:
                self.conda_env_combo.addItems(envs)
                self.conda_env_combo.setPlaceholderText("选择或输入环境名称")
            else:
                self.conda_env_combo.setPlaceholderText("未找到环境(可手动输入创建)")
        else:
            # 远程模式:获取远程conda环境
            server_id = self.server_combo.currentData()
            if server_id is not None:
                envs = self.get_remote_conda_envs(server_id)
                if envs:
                    self.conda_env_combo.addItems(envs)
                    self.conda_env_combo.setPlaceholderText("选择或输入环境名称")
                else:
                    self.conda_env_combo.setPlaceholderText("未找到环境(可手动输入创建)")
            else:
                self.conda_env_combo.setPlaceholderText("请先选择服务器")
    
    def get_local_conda_envs(self):
        """获取本地conda环境列表"""
        try:
            # 执行conda env list命令
            result = subprocess.run(
                ['conda', 'env', 'list'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                envs = []
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    # 跳过注释行和空行
                    if line and not line.startswith('#'):
                        # 提取环境名称(第一列)
                        parts = line.split()
                        if parts:
                            env_name = parts[0]
                            # 跳过base环境的路径行
                            if not env_name.startswith('/'):
                                envs.append(env_name)
                return envs
            else:
                logger.warning(f"获取本地conda环境列表失败: {result.stderr}")
                return []
        except FileNotFoundError:
            logger.warning("未找到conda命令,请确保已安装conda")
            return []
        except subprocess.TimeoutExpired:
            logger.warning("获取本地conda环境列表超时")
            return []
        except Exception as e:
            logger.error(f"获取本地conda环境列表时发生错误: {e}")
            return []
    
    def get_remote_conda_envs(self, server_id: int):
        """获取远程conda环境列表"""
        try:
            from ..remote_server.ssh_client import SSHClient
            
            # 获取服务器配置
            server_config = self.server_config_manager.get_server_config_by_id(server_id)
            if not server_config:
                logger.warning(f"服务器配置不存在: {server_id}")
                return []
            
            # 连接服务器
            ssh_client = SSHClient(server_config)
            if not ssh_client.connect_to_server():
                logger.warning(f"无法连接到服务器: {server_config.name}")
                return []
            
            try:
                # 尝试多种方式执行conda env list命令
                commands = [
                    'conda env list',
                    'source ~/.bashrc && conda env list',
                    'source ~/.bash_profile && conda env list',
                    '/opt/conda/bin/conda env list',
                    '~/anaconda3/bin/conda env list',
                    '~/miniconda3/bin/conda env list'
                ]
                
                output = ""
                error_output = ""
                success = False
                
                for cmd in commands:
                    try:
                        logger.info(f"尝试执行命令: {cmd}")
                        if ssh_client.ssh_client:
                            stdin, stdout, stderr = ssh_client.ssh_client.exec_command(cmd)
                            output = stdout.read().decode('utf-8')
                            error_output = stderr.read().decode('utf-8')
                            
                            # 检查是否有有效输出
                            if output and not error_output:
                                success = True
                                logger.info(f"命令执行成功: {cmd}")
                                break
                            elif error_output:
                                logger.warning(f"命令执行失败: {cmd}, 错误: {error_output}")
                    except Exception as e:
                        logger.warning(f"执行命令 {cmd} 时发生异常: {e}")
                        continue
                
                if not success:
                    logger.error(f"所有conda命令都执行失败")
                    return []
                
                # 添加调试信息
                logger.info(f"远程conda env list命令输出: {output}")
                if error_output:
                    logger.warning(f"远程conda env list命令错误输出: {error_output}")
                
                envs = []
                lines = output.split('\n')
                logger.info(f"远程conda env list命令输出行数: {len(lines)}")
                for i, line in enumerate(lines):
                    line = line.strip()
                    logger.info(f"第{i}行内容: '{line}'")
                    # 跳过注释行和空行
                    if line and not line.startswith('#'):
                        # 提取环境名称(第一列)
                        parts = line.split()
                        if parts:
                            env_name = parts[0]
                            logger.info(f"解析到环境名称: '{env_name}'")
                            # 跳过路径行
                            if not env_name.startswith('/') and env_name != 'base':
                                envs.append(env_name)
                            elif env_name == 'base':
                                # 特殊处理base环境
                                envs.append(env_name)
                                logger.info(f"添加base环境: '{env_name}'")
                            else:
                                logger.info(f"跳过路径行: '{env_name}'")
                        else:
                            logger.info(f"空行被跳过: '{line}'")
                    else:
                        logger.info(f"注释行或空行被跳过: '{line}'")
                
                logger.info(f"从服务器 {server_config.name} 获取到 {len(envs)} 个conda环境: {envs}")
                return envs
            finally:
                ssh_client.disconnect_from_server()
                
        except Exception as e:
            logger.error(f"获取远程conda环境列表时发生错误: {e}")
            return []
    
    def load_task_data(self, task: TrainingTask):
        """加载任务数据到表单"""
        self.name_edit.setText(task.name)
        
        # 设置任务类型
        index = self.type_combo.findData(task.task_type)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
        
        # 根据任务类型显示/隐藏服务器行
        is_local = task.task_type == TrainingTaskType.LOCAL
        self.server_row_widget.setVisible(not is_local)
        
        # 更新保存路径按钮文本
        if is_local:
            self.save_path_btn.setText("浏览")
        else:
            self.save_path_btn.setText("远程浏览")
        
        self.dataset_path_edit.setText(task.dataset_path)
        
        # 设置保存路径(本地或远程)
        if task.task_type == TrainingTaskType.LOCAL:
            self.save_path_edit.setText(task.save_path)
        else:
            self.save_path_edit.setText(task.remote_path)
        
        # 如果是远程任务,设置服务器
        if task.task_type == TrainingTaskType.REMOTE and task.server_id:
            server_index = self.server_combo.findData(task.server_id)
            if server_index >= 0:
                self.server_combo.setCurrentIndex(server_index)
        
        # 设置conda环境
        if task.conda_env:
            self.conda_env_combo.setCurrentText(task.conda_env)
    
    def save_task(self):
        """保存任务"""
        # 验证输入
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "警告", "请输入任务名称")
            return
        
        dataset_path = self.dataset_path_edit.text().strip()
        if not dataset_path:
            QMessageBox.warning(self, "警告", "请选择数据集路径")
            return
        
        task_type = self.type_combo.currentData()
        
        # 初始化变量
        save_path = ""
        server_id = None
        
        if task_type == TrainingTaskType.LOCAL:
            save_path = self.save_path_edit.text().strip()
            if not save_path:
                QMessageBox.warning(self, "警告", "请选择保存路径")
                return
        else:
            server_id = self.server_combo.currentData()
            if server_id is None:
                QMessageBox.warning(self, "警告", "请选择远程服务器")
                return
            
            save_path = self.save_path_edit.text().strip()
            if not save_path:
                QMessageBox.warning(self, "警告", "请输入远程路径")
                return
        
        conda_env = self.conda_env_combo.currentText().strip()
        if not conda_env:
            QMessageBox.warning(self, "警告", "请选择或输入conda环境名称")
            return
        
        # 创建或更新任务
        if self.task is None:
            self.task = TrainingTask(
                task_id=None,
                name=name,
                task_type=task_type,
                dataset_path=dataset_path,
                save_path=save_path,
                server_id=server_id,
                remote_path=save_path if task_type == TrainingTaskType.REMOTE else "",
                conda_env=conda_env,
                status=TrainingTaskStatus.STOPPED,
                process_id=None,
                results_path=""
            )
        else:
            self.task.name = name
            self.task.task_type = task_type
            self.task.dataset_path = dataset_path
            self.task.save_path = save_path
            self.task.server_id = server_id
            self.task.remote_path = save_path if task_type == TrainingTaskType.REMOTE else ""
            self.task.conda_env = conda_env
        
        self.accept()
    
    def get_task(self) -> TrainingTask:
        """获取任务对象"""
        if self.task is None:
            # 返回一个空任务而不是None
            return TrainingTask(
                task_id=None,
                name="",
                task_type=TrainingTaskType.LOCAL,
                dataset_path="",
                save_path="",
                server_id=None,
                remote_path="",
                conda_env="",
                status=TrainingTaskStatus.STOPPED,
                process_id=None,
                results_path=""
            )
        return self.task