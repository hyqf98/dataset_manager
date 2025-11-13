import os
import threading
from typing import Optional
from PyQt5.QtCore import QObject, pyqtSignal
from ..remote_server.ssh_client import SSHClient
from ..logging_config import logger
from .training_task import TrainingTask


class AsyncUploader(QObject):
    """
    异步文件上传器，用于在后台上传文件到远程服务器
    """
    
    # 信号定义
    upload_progress = pyqtSignal(int, int)  # (已上传文件数, 总文件数)
    upload_completed = pyqtSignal()  # 上传完成
    upload_error = pyqtSignal(str)  # 上传错误 (错误信息)
    upload_log = pyqtSignal(str)  # 上传日志 (日志信息)
    
    def __init__(self, ssh_client: SSHClient, task: TrainingTask):
        super().__init__()
        self.ssh_client = ssh_client
        self.task = task
        self._stop_requested = False
        self._upload_thread: Optional[threading.Thread] = None
        self._uploaded_files = 0  # 添加已上传文件计数器
        
    def start_upload(self):
        """开始异步上传"""
        if self._upload_thread and self._upload_thread.is_alive():
            logger.warning("上传线程已在运行中")
            return
            
        self._stop_requested = False
        self._upload_thread = threading.Thread(target=self._upload_worker, daemon=True)
        self._upload_thread.start()
        
    def stop_upload(self):
        """停止上传"""
        self._stop_requested = True
        if self._upload_thread and self._upload_thread.is_alive():
            self._upload_thread.join(timeout=5)  # 等待最多5秒
            
    def _upload_worker(self):
        """上传工作线程"""
        try:
            self.upload_log.emit("[INFO] 开始异步上传文件...")
            
            # 计算总文件数
            total_files = self._count_files(self.task.dataset_path)
            self._uploaded_files = 0
            
            self.upload_progress.emit(self._uploaded_files, total_files)
            
            # 递归上传目录
            self._upload_directory_recursive(
                self.task.dataset_path, 
                self.task.remote_path,
                total_files,
                self._uploaded_files
            )
            
            if not self._stop_requested:
                self.upload_completed.emit()
                self.upload_log.emit("[INFO] 文件上传完成")
                
        except Exception as e:
            if not self._stop_requested:
                error_msg = f"[ERROR] 文件上传失败: {str(e)}"
                self.upload_log.emit(error_msg)
                self.upload_error.emit(str(e))
                
    def _count_files(self, local_path: str) -> int:
        """计算本地目录中的文件总数"""
        count = 0
        for root, dirs, files in os.walk(local_path):
            count += len(files)
        return count
        
    def _upload_directory_recursive(self, local_path: str, remote_path: str, total_files: int, uploaded_files: int):
        """递归上传目录"""
        if self._stop_requested:
            return
            
        try:
            # 确保远程目录存在
            if self.ssh_client.ssh_client:
                self.ssh_client.ssh_client.exec_command(f"mkdir -p {remote_path}")
            
            # 遍历本地目录
            for root, dirs, files in os.walk(local_path):
                if self._stop_requested:
                    return
                    
                # 计算相对路径
                rel_path = os.path.relpath(root, local_path)
                if rel_path == ".":
                    remote_root = remote_path
                else:
                    remote_root = os.path.join(remote_path, rel_path).replace("\\", "/")
                
                # 确保远程子目录存在
                if self.ssh_client.ssh_client:
                    self.ssh_client.ssh_client.exec_command(f"mkdir -p {remote_root}")
                
                # 上传文件
                for file in files:
                    if self._stop_requested:
                        return
                        
                    local_file = os.path.join(root, file)
                    remote_file = os.path.join(remote_root, file).replace("\\", "/")
                    
                    try:
                        self.ssh_client.upload_file(local_file, remote_file)
                        self._uploaded_files += 1
                        self.upload_progress.emit(self._uploaded_files, total_files)
                        self.upload_log.emit(f"[INFO] 上传文件: {local_file} -> {remote_file}")
                    except Exception as e:
                        self.upload_log.emit(f"[WARNING] 上传文件失败 {local_file}: {str(e)}")
                        # 即使上传失败也增加计数，以保持进度条的准确性
                        self._uploaded_files += 1
                        self.upload_progress.emit(self._uploaded_files, total_files)
                        
        except Exception as e:
            raise Exception(f"上传目录失败: {str(e)}")