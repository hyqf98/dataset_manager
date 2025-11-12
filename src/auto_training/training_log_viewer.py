import os
import csv
from typing import Optional
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                             QTabWidget, QWidget, QTextEdit, QMessageBox)
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QFont
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from .training_task import TrainingTask, TrainingTaskType
from ..remote_server.server_config import ServerConfigManager
from ..remote_server.ssh_client import SSHClient
from ..logging_config import logger


class TrainingLogViewer(QDialog):
    """训练日志查看器"""
    
    def __init__(self, task: TrainingTask, server_config_manager: ServerConfigManager, parent=None):
        super().__init__(parent)
        self.task = task
        self.server_config_manager = server_config_manager
        self.refresh_timer = None
        
        self.setWindowTitle(f"训练日志 - {task.name}")
        self.setMinimumSize(900, 700)
        self.init_ui()
        
        # 加载日志数据
        self.load_log_data()
        
        # 启动自动刷新（每5秒）
        self.start_auto_refresh()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 标题
        title_label = QLabel(f"训练日志 - {self.task.name}")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Tab控件
        self.tab_widget = QTabWidget()
        
        # 图表Tab
        chart_widget = QWidget()
        chart_layout = QVBoxLayout(chart_widget)
        
        # 创建matplotlib图表
        self.figure = Figure(figsize=(8, 6))
        self.canvas = FigureCanvas(self.figure)
        chart_layout.addWidget(self.canvas)
        
        self.tab_widget.addTab(chart_widget, "训练图表")
        
        # 文本日志Tab
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                font-family: monospace;
                font-size: 11px;
                background-color: #f8f9fa;
            }
        """)
        text_layout.addWidget(self.log_text)
        
        self.tab_widget.addTab(text_widget, "文本日志")
        
        layout.addWidget(self.tab_widget)
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        self.refresh_btn.clicked.connect(self.load_log_data)
        btn_layout.addWidget(self.refresh_btn)
        
        btn_layout.addStretch()
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
    
    def load_log_data(self):
        """加载日志数据"""
        try:
            if self.task.task_type == TrainingTaskType.LOCAL:
                self.load_local_log()
            else:
                self.load_remote_log()
        except Exception as e:
            logger.error(f"加载日志数据失败: {e}")
            QMessageBox.warning(self, "警告", f"加载日志数据失败: {str(e)}")
    
    def load_local_log(self):
        """加载本地日志"""
        # 查找results.csv文件
        results_file = self.find_results_file(self.task.dataset_path)
        
        if results_file and os.path.exists(results_file):
            self.parse_and_plot_results(results_file)
        else:
            self.log_text.setPlainText("未找到训练结果文件 results.csv")
    
    def load_remote_log(self):
        """加载远程日志"""
        if self.task.server_id is not None:
            server_config = self.server_config_manager.get_server_config_by_id(self.task.server_id)
        else:
            server_config = None
        if not server_config:
            self.log_text.setPlainText("服务器配置不存在")
            return
        
        ssh_client = SSHClient(server_config)
        if not ssh_client.connect_to_server():
            self.log_text.setPlainText("连接服务器失败")
            return
        
        try:
            # 查找远程results.csv文件
            remote_results_file = f"{self.task.remote_path}/runs/detect/train/results.csv"
            
            # 下载到临时文件
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
            temp_file.close()
            
            try:
                ssh_client.download_file(remote_results_file, temp_file.name)
                self.parse_and_plot_results(temp_file.name)
            except Exception as e:
                self.log_text.setPlainText(f"未找到远程训练结果文件: {str(e)}")
            finally:
                # 清理临时文件
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
        finally:
            ssh_client.disconnect_from_server()
    
    def find_results_file(self, base_path: str) -> Optional[str]:
        """查找results.csv文件"""
        # 通常在 runs/detect/train/results.csv
        possible_paths = [
            os.path.join(base_path, "runs", "detect", "train", "results.csv"),
            os.path.join(base_path, "runs", "detect", "train2", "results.csv"),
            os.path.join(base_path, "runs", "detect", "train3", "results.csv"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # 尝试查找最新的训练结果
        runs_dir = os.path.join(base_path, "runs", "detect")
        if os.path.exists(runs_dir):
            train_dirs = [d for d in os.listdir(runs_dir) if d.startswith("train")]
            if train_dirs:
                # 按修改时间排序，获取最新的
                train_dirs.sort(key=lambda x: os.path.getmtime(os.path.join(runs_dir, x)), reverse=True)
                latest_results = os.path.join(runs_dir, train_dirs[0], "results.csv")
                if os.path.exists(latest_results):
                    return latest_results
        
        return None
    
    def parse_and_plot_results(self, results_file: str):
        """解析并绘制results.csv数据"""
        try:
            # 读取CSV文件
            data = {
                'epoch': [],
                'train_loss': [],
                'val_loss': [],
                'metrics_precision': [],
                'metrics_recall': [],
                'metrics_mAP50': [],
                'metrics_mAP50-95': []
            }
            
            with open(results_file, 'r') as f:
                # 跳过空白行
                lines = [line for line in f if line.strip()]
                reader = csv.DictReader(lines)
                
                for row in reader:
                    # 读取数据
                    data['epoch'].append(float(row.get('epoch', 0)))
                    
                    # 训练损失
                    train_loss_keys = ['train/box_loss', 'train/cls_loss', 'train/dfl_loss']
                    train_loss = sum(float(row.get(k, 0)) for k in train_loss_keys if k in row)
                    data['train_loss'].append(train_loss)
                    
                    # 验证损失
                    val_loss_keys = ['val/box_loss', 'val/cls_loss', 'val/dfl_loss']
                    val_loss = sum(float(row.get(k, 0)) for k in val_loss_keys if k in row)
                    data['val_loss'].append(val_loss)
                    
                    # 评估指标
                    data['metrics_precision'].append(float(row.get('metrics/precision(B)', 0)))
                    data['metrics_recall'].append(float(row.get('metrics/recall(B)', 0)))
                    data['metrics_mAP50'].append(float(row.get('metrics/mAP50(B)', 0)))
                    data['metrics_mAP50-95'].append(float(row.get('metrics/mAP50-95(B)', 0)))
            
            # 绘制图表
            self.plot_training_metrics(data)
            
            # 更新文本日志
            log_text = f"训练结果文件: {results_file}\n\n"
            log_text += f"总轮次: {len(data['epoch'])}\n"
            if data['epoch']:
                log_text += f"最新轮次: {int(data['epoch'][-1])}\n"
                log_text += f"最新训练损失: {data['train_loss'][-1]:.4f}\n"
                log_text += f"最新验证损失: {data['val_loss'][-1]:.4f}\n"
                log_text += f"最新 mAP50: {data['metrics_mAP50'][-1]:.4f}\n"
                log_text += f"最新 mAP50-95: {data['metrics_mAP50-95'][-1]:.4f}\n"
            
            self.log_text.setPlainText(log_text)
            
        except Exception as e:
            logger.error(f"解析结果文件失败: {e}")
            self.log_text.setPlainText(f"解析结果文件失败: {str(e)}")
    
    def plot_training_metrics(self, data):
        """绘制训练指标图表"""
        self.figure.clear()
        
        # 创建2x2子图
        axes = self.figure.subplots(2, 2)
        
        # 损失曲线
        axes[0, 0].plot(data['epoch'], data['train_loss'], label='Train Loss', color='#1f77b4')
        axes[0, 0].plot(data['epoch'], data['val_loss'], label='Val Loss', color='#ff7f0e')
        axes[0, 0].set_title('Loss')
        axes[0, 0].set_xlabel('Epoch')
        axes[0, 0].set_ylabel('Loss')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # Precision & Recall
        axes[0, 1].plot(data['epoch'], data['metrics_precision'], label='Precision', color='#2ca02c')
        axes[0, 1].plot(data['epoch'], data['metrics_recall'], label='Recall', color='#d62728')
        axes[0, 1].set_title('Precision & Recall')
        axes[0, 1].set_xlabel('Epoch')
        axes[0, 1].set_ylabel('Score')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # mAP50
        axes[1, 0].plot(data['epoch'], data['metrics_mAP50'], label='mAP50', color='#9467bd')
        axes[1, 0].set_title('mAP50')
        axes[1, 0].set_xlabel('Epoch')
        axes[1, 0].set_ylabel('mAP')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # mAP50-95
        axes[1, 1].plot(data['epoch'], data['metrics_mAP50-95'], label='mAP50-95', color='#8c564b')
        axes[1, 1].set_title('mAP50-95')
        axes[1, 1].set_xlabel('Epoch')
        axes[1, 1].set_ylabel('mAP')
        axes[1, 1].legend()
        axes[1, 1].grid(True, alpha=0.3)
        
        self.figure.tight_layout()
        self.canvas.draw()
    
    def start_auto_refresh(self):
        """启动自动刷新"""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.load_log_data)
        self.refresh_timer.start(5000)  # 每5秒刷新
    
    def closeEvent(self, a0):
        """关闭事件"""
        if self.refresh_timer:
            self.refresh_timer.stop()
        super().closeEvent(a0)
