import os
import sys
import json
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget, 
                             QTreeWidgetItem, QHeaderView, QMessageBox, QLabel, QComboBox,
                             QFileDialog, QSplitter, QTextEdit, QDialog, QDialogButtonBox,
                             QFormLayout, QLineEdit, QCheckBox, QSpinBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

# 将pandas和matplotlib相关导入放在try-except块中以避免导入错误
try:
    import pandas as pd
    import matplotlib.pyplot as plt
    try:
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    except ImportError:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
except ImportError as e:
    print(f"导入数据分析库时出错: {e}")
    pd = None
    plt = None
    FigureCanvas = None
    Figure = None

# 添加远程服务器相关导入
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ..remote_server.server_config import ServerConfig, ServerConfigManager
from ..remote_server.ssh_client import SSHClient
from ..remote_server.file_transfer_dialog import RemoteBrowserDialog
from ..logging_config import logger


class LogAnalysisConfig:
    """
    日志分析配置类
    """
    
    def __init__(self, name="", file_type="local", file_path="", server_name="", config_id=None):
        self.id = config_id
        self.name = name
        self.file_type = file_type  # "local" 或 "remote"
        self.file_path = file_path
        self.server_name = server_name  # 远程服务器名称
        
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'file_type': self.file_type,
            'file_path': self.file_path,
            'server_name': self.server_name
        }
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建对象"""
        return cls(
            name=data.get('name', ''),
            file_type=data.get('file_type', 'local'),
            file_path=data.get('file_path', ''),
            server_name=data.get('server_name', ''),
            config_id=data.get('id')
        )


class LogAnalysisConfigManager:
    """
    日志分析配置管理器
    """
    
    def __init__(self):
        # 配置文件路径设置为用户目录下的.dataset_m路径
        user_home = os.path.expanduser("~")
        dataset_manager_dir = os.path.join(user_home, ".dataset_m")
        os.makedirs(dataset_manager_dir, exist_ok=True)
        self.config_file = os.path.join(dataset_manager_dir, "log_analysis_configs.json")
        
        self.configs = []
        self.load_configs()
        
    def load_configs(self):
        """加载配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.configs = [LogAnalysisConfig.from_dict(item) for item in data]
                logger.info(f"加载了 {len(self.configs)} 个日志分析配置")
            else:
                self.configs = []
                logger.info("未找到日志分析配置文件，初始化空列表")
        except Exception as e:
            logger.error(f"加载日志分析配置时出错: {e}")
            self.configs = []
            
    def save_configs(self):
        """保存配置"""
        try:
            data = [config.to_dict() for config in self.configs]
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"保存了 {len(self.configs)} 个日志分析配置")
        except Exception as e:
            logger.error(f"保存日志分析配置时出错: {e}")
            QMessageBox.critical(None, "错误", f"保存配置时出错: {e}")
            
    def add_config(self, config):
        """添加配置"""
        if self.configs:
            config.id = max(c.id for c in self.configs if c.id) + 1
        else:
            config.id = 1
        self.configs.append(config)
        self.save_configs()
        logger.info(f"添加日志分析配置: {config.name}")
        
    def update_config(self, config):
        """更新配置"""
        for i, c in enumerate(self.configs):
            if c.id == config.id:
                self.configs[i] = config
                self.save_configs()
                logger.info(f"更新日志分析配置: {config.name}")
                return True
        return False
        
    def delete_config(self, config_id):
        """删除配置"""
        self.configs = [c for c in self.configs if c.id != config_id]
        self.save_configs()
        logger.info(f"删除日志分析配置 ID: {config_id}")
        
    def get_configs(self):
        """获取所有配置"""
        return self.configs


class LogAnalysisConfigDialog(QDialog):
    """
    日志分析配置对话框
    """
    
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config
        self.server_manager = ServerConfigManager()
        
        self.setWindowTitle("添加日志分析配置" if config is None else "编辑日志分析配置")
        self.setModal(True)
        self.resize(600, 400)
        self.init_ui()
        
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        # 表单布局
        form_layout = QFormLayout()
        
        # 配置名称
        self.name_edit = QLineEdit()
        if self.config:
            self.name_edit.setText(self.config.name)
        form_layout.addRow("配置名称:", self.name_edit)
        
        # 文件类型选择
        type_layout = QHBoxLayout()
        self.file_type_combo = QComboBox()
        self.file_type_combo.addItem("本地文件", "local")
        self.file_type_combo.addItem("远程文件", "remote")
        self.file_type_combo.currentIndexChanged.connect(self.on_file_type_changed)
        type_layout.addWidget(self.file_type_combo)
        form_layout.addRow("文件类型:", type_layout)
        
        # 本地文件选择
        self.local_widget = QWidget()
        local_layout = QHBoxLayout(self.local_widget)
        local_layout.setContentsMargins(0, 0, 0, 0)
        self.local_path_edit = QLineEdit()
        self.local_path_edit.setReadOnly(True)
        self.browse_local_btn = QPushButton("浏览...")
        self.browse_local_btn.clicked.connect(self.browse_local_file)
        local_layout.addWidget(self.local_path_edit)
        local_layout.addWidget(self.browse_local_btn)
        form_layout.addRow("文件路径:", self.local_widget)
        
        # 远程文件选择
        self.remote_widget = QWidget()
        self.remote_widget.setVisible(False)
        remote_layout = QVBoxLayout(self.remote_widget)
        remote_layout.setContentsMargins(0, 0, 0, 0)
        
        # 服务器选择
        server_layout = QHBoxLayout()
        self.server_combo = QComboBox()
        self.refresh_servers_btn = QPushButton("刷新")
        self.refresh_servers_btn.clicked.connect(self.load_servers)
        server_layout.addWidget(self.server_combo)
        server_layout.addWidget(self.refresh_servers_btn)
        remote_layout.addLayout(server_layout)
        
        # 远程文件路径
        remote_file_layout = QHBoxLayout()
        self.remote_path_edit = QLineEdit()
        self.remote_path_edit.setReadOnly(True)
        self.browse_remote_btn = QPushButton("浏览...")
        self.browse_remote_btn.clicked.connect(self.browse_remote_file)
        remote_file_layout.addWidget(self.remote_path_edit)
        remote_file_layout.addWidget(self.browse_remote_btn)
        remote_layout.addLayout(remote_file_layout)
        
        form_layout.addRow("远程配置:", self.remote_widget)
        
        layout.addLayout(form_layout)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # 加载服务器列表
        self.load_servers()
        
        # 如果是编辑模式，填充数据
        if self.config:
            if self.config.file_type == "local":
                self.file_type_combo.setCurrentIndex(0)
                self.local_path_edit.setText(self.config.file_path)
            else:
                self.file_type_combo.setCurrentIndex(1)
                self.remote_path_edit.setText(self.config.file_path)
                # 选择对应的服务器
                for i in range(self.server_combo.count()):
                    server = self.server_combo.itemData(i)
                    if isinstance(server, ServerConfig) and server.name == self.config.server_name:
                        self.server_combo.setCurrentIndex(i)
                        break
                        
    def load_servers(self):
        """加载服务器列表"""
        self.server_combo.clear()
        self.server_manager.load_server_configs()
        servers = self.server_manager.get_server_configs()
        
        if not servers:
            self.server_combo.addItem("（没有配置的服务器）")
            return
            
        for server in servers:
            self.server_combo.addItem(f"{server.name} ({server.host}:{server.port})", server)
            
    def on_file_type_changed(self, index):
        """文件类型变化"""
        file_type = self.file_type_combo.currentData()
        if file_type == "local":
            self.local_widget.setVisible(True)
            self.remote_widget.setVisible(False)
        else:
            self.local_widget.setVisible(False)
            self.remote_widget.setVisible(True)
            
    def browse_local_file(self):
        """浏览本地文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择CSV文件", "", "CSV文件 (*.csv);;所有文件 (*)"
        )
        if file_path:
            self.local_path_edit.setText(file_path)
            
    def browse_remote_file(self):
        """浏览远程文件"""
        server_config = self.server_combo.currentData()
        if not server_config or not isinstance(server_config, ServerConfig):
            QMessageBox.warning(self, "警告", "请先选择一个服务器")
            return
            
        try:
            dialog = RemoteBrowserDialog(server_config, self)
            if dialog.exec() == QDialog.Accepted:
                selected_path = dialog.get_selected_path()
                if not selected_path:
                    QMessageBox.warning(self, "警告", "请选择一个文件")
                    return
                if not selected_path.lower().endswith('.csv'):
                    QMessageBox.warning(self, "警告", "请选择CSV文件")
                    return
                self.remote_path_edit.setText(selected_path)
        except Exception as e:
            logger.error(f"浏览远程文件时发生错误: {str(e)}")
            QMessageBox.critical(self, "错误", f"浏览远程文件时发生错误：{str(e)}")
            
    def get_config(self):
        """获取配置"""
        if self.result() != QDialog.Accepted:
            return None
            
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "警告", "请输入配置名称")
            return None
            
        file_type = self.file_type_combo.currentData()
        
        if file_type == "local":
            file_path = self.local_path_edit.text().strip()
            server_name = ""
        else:
            file_path = self.remote_path_edit.text().strip()
            server_config = self.server_combo.currentData()
            if isinstance(server_config, ServerConfig):
                server_name = server_config.name
            else:
                server_name = ""
                
        if not file_path:
            QMessageBox.warning(self, "警告", "请选择文件路径")
            return None
            
        config = LogAnalysisConfig(
            name=name,
            file_type=file_type,
            file_path=file_path,
            server_name=server_name
        )
        
        if self.config:
            config.id = self.config.id
            
        return config


class YoloLossChartDialog(QDialog):
    """
    YOLO Loss图表对话框
    """
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.server_manager = ServerConfigManager()
        self.data_frame = None
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        
        self.setWindowTitle(f"YOLO Loss分析 - {config.name}")
        self.resize(1200, 800)
        self.init_ui()
        
        # 加载初始数据
        self.load_data()
        
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        # 刷新间隔设置
        toolbar.addWidget(QLabel("自动刷新间隔(秒):"))
        self.refresh_interval_spin = QSpinBox()
        self.refresh_interval_spin.setRange(1, 300)
        self.refresh_interval_spin.setValue(10)
        toolbar.addWidget(self.refresh_interval_spin)
        
        # 开始/停止刷新按钮
        self.refresh_btn = QPushButton("开始自动刷新")
        self.refresh_btn.setCheckable(True)
        self.refresh_btn.clicked.connect(self.toggle_refresh)
        toolbar.addWidget(self.refresh_btn)
        
        # 手动刷新按钮
        self.manual_refresh_btn = QPushButton("手动刷新")
        self.manual_refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(self.manual_refresh_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # 图表显示区域
        if Figure and FigureCanvas:
            self.figure = Figure(figsize=(12, 8), dpi=100)
            self.canvas = FigureCanvas(self.figure)
            self.canvas.setStyleSheet("background-color: white; border: 1px solid #ccc;")
            layout.addWidget(self.canvas)
        else:
            error_label = QLabel("缺少matplotlib库，无法显示图表")
            error_label.setStyleSheet("color: red; font-size: 14px;")
            layout.addWidget(error_label)
            
    def toggle_refresh(self):
        """切换自动刷新"""
        if self.refresh_btn.isChecked():
            interval = self.refresh_interval_spin.value() * 1000
            self.refresh_timer.start(interval)
            self.refresh_btn.setText("停止自动刷新")
            logger.info(f"启动自动刷新，间隔: {self.refresh_interval_spin.value()}秒")
        else:
            self.refresh_timer.stop()
            self.refresh_btn.setText("开始自动刷新")
            logger.info("停止自动刷新")
            
    def load_data(self):
        """加载数据"""
        if pd is None:
            QMessageBox.critical(self, "错误", "缺少pandas库，无法加载数据")
            return
            
        try:
            if self.config.file_type == "local":
                if not os.path.exists(self.config.file_path):
                    QMessageBox.warning(self, "警告", f"文件不存在: {self.config.file_path}")
                    return
                self.data_frame = pd.read_csv(self.config.file_path)
            else:
                # 远程文件
                self.data_frame = self.load_remote_csv()
                
            # 绘制图表
            self.plot_loss_chart()
            
        except Exception as e:
            logger.error(f"加载数据时出错: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"加载数据时出错: {e}")
            
    def load_remote_csv(self):
        """加载远程CSV文件"""
        import tempfile
        
        # 获取服务器配置
        self.server_manager.load_server_configs()
        servers = self.server_manager.get_server_configs()
        server_config = None
        
        for server in servers:
            if server.name == self.config.server_name:
                server_config = server
                break
                
        if not server_config:
            raise Exception(f"未找到服务器配置: {self.config.server_name}")
            
        # 连接服务器并下载文件
        ssh_client = SSHClient(server_config)
        if not ssh_client.connect_to_server():
            raise Exception("无法连接到服务器")
            
        try:
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.csv') as temp_file:
                temp_path = temp_file.name
                
            ssh_client.download_file(self.config.file_path, temp_path)
            df = pd.read_csv(temp_path)
            os.unlink(temp_path)
            
            return df
        finally:
            ssh_client.disconnect_from_server()
            
    def refresh_data(self):
        """刷新数据"""
        logger.info("刷新数据...")
        self.load_data()
        
    def plot_loss_chart(self):
        """绘制Loss图表"""
        if self.data_frame is None or Figure is None or plt is None:
            return
            
        try:
            self.figure.clear()
            
            # 创建子图 - 2x2布局
            axes = []
            axes.append(self.figure.add_subplot(2, 2, 1))
            axes.append(self.figure.add_subplot(2, 2, 2))
            axes.append(self.figure.add_subplot(2, 2, 3))
            axes.append(self.figure.add_subplot(2, 2, 4))
            
            # 获取数据列
            columns = self.data_frame.columns.tolist()
            
            # 常见的YOLO loss列名
            loss_columns = {
                'box_loss': 'Box Loss',
                'cls_loss': 'Class Loss',
                'dfl_loss': 'DFL Loss',
                'total_loss': 'Total Loss',
                'train/box_loss': 'Box Loss',
                'train/cls_loss': 'Class Loss',
                'train/dfl_loss': 'DFL Loss',
                'metrics/mAP50': 'mAP@50',
                'metrics/mAP50-95': 'mAP@50-95'
            }
            
            # 尝试找到epoch列
            epoch_col = None
            for col in ['epoch', 'Epoch', 'EPOCH']:
                if col in columns:
                    epoch_col = col
                    break
                    
            if epoch_col is None and len(self.data_frame) > 0:
                # 如果没有epoch列，使用索引
                x_data = self.data_frame.index
                x_label = 'Step'
            else:
                x_data = self.data_frame[epoch_col]
                x_label = 'Epoch'
                
            # 绘制各种loss
            plot_index = 0
            for col_key, col_label in loss_columns.items():
                if col_key in columns and plot_index < 4:
                    ax = axes[plot_index]
                    ax.plot(x_data, self.data_frame[col_key], marker='o', markersize=3, linewidth=1.5)
                    ax.set_title(col_label, fontsize=12, fontweight='bold')
                    ax.set_xlabel(x_label)
                    ax.set_ylabel('Loss' if 'loss' in col_key.lower() else 'Score')
                    ax.grid(True, alpha=0.3)
                    plot_index += 1
                    
            # 如果没有找到标准列名，尝试绘制所有数值列
            if plot_index == 0:
                numeric_cols = self.data_frame.select_dtypes(include=['float64', 'int64']).columns
                for i, col in enumerate(numeric_cols[:4]):
                    if col == epoch_col:
                        continue
                    ax = axes[i]
                    ax.plot(x_data, self.data_frame[col], marker='o', markersize=3, linewidth=1.5)
                    ax.set_title(col, fontsize=12, fontweight='bold')
                    ax.set_xlabel(x_label)
                    ax.set_ylabel('Value')
                    ax.grid(True, alpha=0.3)
                    
            self.figure.tight_layout()
            self.canvas.draw()
            
            logger.info(f"绘制图表完成，数据行数: {len(self.data_frame)}")
            
        except Exception as e:
            logger.error(f"绘制图表时出错: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"绘制图表时出错: {e}")
            
    def closeEvent(self, event):
        """关闭事件"""
        # 停止定时器
        if self.refresh_timer.isActive():
            self.refresh_timer.stop()
            logger.info("关闭窗口，停止自动刷新定时器")
        event.accept()


class LogAnalysisPanel(QWidget):
    """
    日志分析管理面板
    """
    
    def __init__(self):
        super().__init__()
        self.config_manager = LogAnalysisConfigManager()
        self.init_ui()
        
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 标题
        title_label = QLabel("训练日志分析管理")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 5px;
                border-bottom: 1px solid #ccc;
            }
        """)
        layout.addWidget(title_label)
        
        # 按钮栏
        button_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("➕ 添加配置")
        self.add_btn.clicked.connect(self.add_config)
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
        """)
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self.refresh_configs)
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
        """)
        
        button_layout.addWidget(self.add_btn)
        button_layout.addWidget(self.refresh_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # 配置列表
        self.config_tree = QTreeWidget()
        self.config_tree.setHeaderLabels(["配置名称", "文件类型", "文件路径", "服务器", "操作"])
        self.config_tree.setRootIsDecorated(False)
        self.config_tree.setAlternatingRowColors(True)
        self.config_tree.setStyleSheet("""
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
        
        header = self.config_tree.header()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(4, 300)
            
        layout.addWidget(self.config_tree)
        
        # 初始加载配置
        self.refresh_configs()
        
    def refresh_configs(self):
        """刷新配置列表"""
        self.config_manager.load_configs()
        self.config_tree.clear()
        
        for config in self.config_manager.get_configs():
            item = QTreeWidgetItem(self.config_tree)
            item.setText(0, config.name)
            item.setText(1, "本地文件" if config.file_type == "local" else "远程文件")
            item.setText(2, config.file_path)
            item.setText(3, config.server_name if config.file_type == "remote" else "-")
            item.setData(0, Qt.UserRole, config.id)
            
            # 创建操作按钮
            button_widget = QWidget()
            button_layout = QHBoxLayout(button_widget)
            button_layout.setContentsMargins(0, 0, 0, 0)
            button_layout.setSpacing(2)
            
            # 分析按钮
            analyze_btn = QPushButton("分析")
            analyze_btn.setStyleSheet("""
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
            analyze_btn.clicked.connect(lambda checked, c=config: self.analyze_config(c))
            
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
            edit_btn.clicked.connect(lambda checked, c=config: self.edit_config(c))
            
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
            delete_btn.clicked.connect(lambda checked, c=config: self.delete_config(c))
            
            button_layout.addWidget(analyze_btn)
            button_layout.addWidget(edit_btn)
            button_layout.addWidget(delete_btn)
            
            self.config_tree.setItemWidget(item, 4, button_widget)
            
        logger.info("刷新日志分析配置列表")
        
    def add_config(self):
        """添加配置"""
        dialog = LogAnalysisConfigDialog(self)
        if dialog.exec() == QDialog.Accepted:
            config = dialog.get_config()
            if config:
                self.config_manager.add_config(config)
                self.refresh_configs()
                
    def edit_config(self, config):
        """编辑配置"""
        dialog = LogAnalysisConfigDialog(self, config)
        if dialog.exec() == QDialog.Accepted:
            updated_config = dialog.get_config()
            if updated_config:
                self.config_manager.update_config(updated_config)
                self.refresh_configs()
                
    def delete_config(self, config):
        """删除配置"""
        reply = QMessageBox.question(
            self, "确认", 
            f"确定要删除配置 '{config.name}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.config_manager.delete_config(config.id)
            self.refresh_configs()
            
    def analyze_config(self, config):
        """分析配置"""
        try:
            dialog = YoloLossChartDialog(config, self)
            dialog.exec()
        except Exception as e:
            logger.error(f"打开分析对话框时出错: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"打开分析对话框时出错: {e}")
