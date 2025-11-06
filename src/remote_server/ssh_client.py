import paramiko
import os
from typing import List, Tuple, Optional
from PyQt5.QtCore import QObject, pyqtSignal
from .server_config import ServerConfig
from ..logging_config import logger


class SSHClient(QObject):
    """
    SSH客户端类，用于连接远程服务器并执行文件操作
    """
    
    # 信号定义
    progress_updated = pyqtSignal(str, int)  # (文件名, 进度百分比)
    transfer_completed = pyqtSignal(str)  # (文件名)
    transfer_error = pyqtSignal(str, str)  # (文件名, 错误信息)
    
    def __init__(self, server_config: ServerConfig):
        super().__init__()
        self.server_config = server_config
        self.ssh_client = None
        self.sftp_client = None
        
    def connect_to_server(self) -> bool:
        """
        连接到远程服务器
        
        Returns:
            bool: 连接是否成功
        """
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 准备连接参数
            connect_kwargs = {
                'hostname': self.server_config.host,
                'port': self.server_config.port,
                'username': self.server_config.username,
            }
            
            # 根据认证方式设置参数
            if self.server_config.private_key_path and os.path.exists(self.server_config.private_key_path):
                # 使用私钥认证
                private_key = paramiko.RSAKey.from_private_key_file(self.server_config.private_key_path)
                connect_kwargs['pkey'] = private_key
            elif self.server_config.password:
                # 使用密码认证
                connect_kwargs['password'] = self.server_config.password
            else:
                raise Exception("未提供有效的认证信息（密码或私钥）")
            
            # 连接服务器
            self.ssh_client.connect(**connect_kwargs)
            
            # 创建SFTP客户端
            self.sftp_client = self.ssh_client.open_sftp()
            
            logger.info(f"成功连接到服务器 {self.server_config.name} ({self.server_config.host})")
            return True
            
        except Exception as e:
            error_msg = f"连接服务器失败: {str(e)}"
            logger.error(error_msg)
            self.transfer_error.emit("连接", error_msg)
            return False
    
    def disconnect_from_server(self):
        """
        断开与远程服务器的连接
        """
        try:
            if self.sftp_client:
                self.sftp_client.close()
                self.sftp_client = None
                
            if self.ssh_client:
                self.ssh_client.close()
                self.ssh_client = None
                
            logger.info(f"已断开与服务器 {self.server_config.name} 的连接")
        except Exception as e:
            logger.error(f"断开连接时发生错误: {str(e)}")
    
    def list_remote_files(self, remote_path: str = ".") -> List[Tuple[str, str, int, bool]]:
        """
        列出远程服务器上的文件和目录
        
        Args:
            remote_path (str): 远程路径，默认为当前目录
            
        Returns:
            List[Tuple[str, str, int, bool]]: 文件信息列表，每个元素为(文件名, 修改时间, 大小, 是否为目录)
        """
        try:
            if not self.sftp_client:
                raise Exception("SFTP客户端未初始化")
                
            files = []
            for item in self.sftp_client.listdir_attr(remote_path):
                # 获取文件信息
                filename = item.filename
                # 跳过当前目录和父目录
                if filename in [".", ".."]:
                    continue
                    
                # 判断是否为目录
                is_directory = False
                if item.st_mode is not None:
                    is_directory = item.st_mode & 0o040000 != 0  # 检查是否为目录
                
                # 获取修改时间
                mod_time = item.st_mtime
                
                # 获取文件大小
                size = item.st_size if not is_directory else 0
                
                files.append((filename, mod_time, size, is_directory))
                
            logger.info(f"列出远程路径 '{remote_path}' 下的 {len(files)} 个项目")
            return files
            
        except Exception as e:
            error_msg = f"列出远程文件失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def upload_file(self, local_path: str, remote_path: str):
        """
        上传单个文件到远程服务器
        
        Args:
            local_path (str): 本地文件路径
            remote_path (str): 远程文件路径
        """
        try:
            if not self.sftp_client:
                raise Exception("SFTP客户端未初始化")
                
            filename = os.path.basename(local_path)
            
            # 获取本地文件大小用于进度计算
            local_size = os.path.getsize(local_path)
            
            # 定义进度回调函数
            def progress_callback(transferred, total):
                if total > 0:
                    progress = int((transferred / total) * 100)
                    self.progress_updated.emit(filename, progress)
            
            # 执行上传
            self.sftp_client.put(local_path, remote_path, callback=progress_callback)
            
            self.transfer_completed.emit(filename)
            logger.info(f"上传文件 '{local_path}' 到 '{remote_path}' 完成")
            
        except Exception as e:
            error_msg = f"上传文件失败: {str(e)}"
            logger.error(error_msg)
            self.transfer_error.emit(os.path.basename(local_path), error_msg)
            raise
    
    def upload_directory(self, local_dir: str, remote_dir: str):
        """
        上传整个目录到远程服务器
        
        Args:
            local_dir (str): 本地目录路径
            remote_dir (str): 远程目录路径
        """
        try:
            if not self.sftp_client:
                raise Exception("SFTP客户端未初始化")
                
            # 确保远程目录存在
            try:
                self.sftp_client.stat(remote_dir)
            except FileNotFoundError:
                self.sftp_client.mkdir(remote_dir)
            
            # 遍历本地目录
            for root, dirs, files in os.walk(local_dir):
                # 计算相对路径
                rel_path = os.path.relpath(root, local_dir)
                if rel_path == ".":
                    remote_root = remote_dir
                else:
                    remote_root = f"{remote_dir}/{rel_path.replace(os.sep, '/')}"
                
                # 确保远程子目录存在
                try:
                    self.sftp_client.stat(remote_root)
                except FileNotFoundError:
                    self.sftp_client.mkdir(remote_root)
                
                # 上传文件
                for file in files:
                    local_file_path = os.path.join(root, file)
                    remote_file_path = f"{remote_root}/{file}"
                    self.upload_file(local_file_path, remote_file_path)
                    
            logger.info(f"上传目录 '{local_dir}' 到 '{remote_dir}' 完成")
            
        except Exception as e:
            error_msg = f"上传目录失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def download_file(self, remote_path: str, local_path: str):
        """
        从远程服务器下载单个文件
        
        Args:
            remote_path (str): 远程文件路径
            local_path (str): 本地文件路径
        """
        try:
            if not self.sftp_client:
                raise Exception("SFTP客户端未初始化")
                
            filename = os.path.basename(remote_path)
            
            # 获取远程文件大小用于进度计算
            remote_stat = self.sftp_client.stat(remote_path)
            remote_size = remote_stat.st_size
            
            # 定义进度回调函数
            def progress_callback(transferred, total):
                if total > 0:
                    progress = int((transferred / total) * 100)
                    self.progress_updated.emit(filename, progress)
            
            # 执行下载
            self.sftp_client.get(remote_path, local_path, callback=progress_callback)
            
            self.transfer_completed.emit(filename)
            logger.info(f"下载文件 '{remote_path}' 到 '{local_path}' 完成")
            
        except Exception as e:
            error_msg = f"下载文件失败: {str(e)}"
            logger.error(error_msg)
            self.transfer_error.emit(os.path.basename(remote_path), error_msg)
            raise
    
    def download_directory(self, remote_dir: str, local_dir: str):
        """
        从远程服务器下载整个目录
        
        Args:
            remote_dir (str): 远程目录路径
            local_dir (str): 本地目录路径
        """
        try:
            if not self.sftp_client:
                raise Exception("SFTP客户端未初始化")
                
            # 确保本地目录存在
            os.makedirs(local_dir, exist_ok=True)
            
            # 列出远程目录内容
            items = self.list_remote_files(remote_dir)
            
            for filename, _, _, is_directory in items:
                remote_item_path = f"{remote_dir}/{filename}"
                local_item_path = os.path.join(local_dir, filename)
                
                if is_directory:
                    # 递归下载子目录
                    self.download_directory(remote_item_path, local_item_path)
                else:
                    # 下载文件
                    self.download_file(remote_item_path, local_item_path)
                    
            logger.info(f"下载目录 '{remote_dir}' 到 '{local_dir}' 完成")
            
        except Exception as e:
            error_msg = f"下载目录失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)