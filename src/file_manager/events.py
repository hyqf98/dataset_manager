from PyQt5.QtCore import QObject, pyqtSignal
import os
import shutil
import json
from ..logging_config import logger


class FileManagerEvents(QObject):
    """
    文件管理器事件处理类
    处理文件操作相关的事件
    """
    
    # 定义信号
    file_selected = pyqtSignal(str)  # 文件选中信号
    file_deleted = pyqtSignal(str)   # 文件删除信号
    file_restored = pyqtSignal(str)  # 文件恢复信号
    
    def __init__(self):
        """
        初始化事件处理器
        """
        super().__init__()

    def on_file_selected(self, file_path):
        """
        处理文件选中事件
        
        Args:
            file_path (str): 选中的文件路径
        """
        if os.path.exists(file_path):
            self.file_selected.emit(file_path)
            logger.info(f"文件选中事件: {file_path}")

    def on_file_delete(self, file_path, recycle_bin_path):
        """
        处理文件删除事件（移动到回收站）
        
        Args:
            file_path (str): 要删除的文件路径
            recycle_bin_path (str): 回收站路径
        """
        try:
            if not os.path.exists(recycle_bin_path):
                os.makedirs(recycle_bin_path)
                logger.debug(f"创建回收站目录: {recycle_bin_path}")
                
            filename = os.path.basename(file_path)
            destination = os.path.join(recycle_bin_path, filename)
            
            # 处理重名情况
            counter = 1
            base_name, ext = os.path.splitext(filename)
            while os.path.exists(destination):
                new_filename = f"{base_name}_{counter}{ext}"
                destination = os.path.join(recycle_bin_path, new_filename)
                counter += 1
                
            shutil.move(file_path, destination)
            logger.info(f"文件移动到回收站: {file_path} -> {destination}")
            
            # 保存原始路径信息到统一的元数据文件
            self.update_metadata_file(recycle_bin_path, {os.path.basename(destination): file_path})
            
            # 检查回收站目录是否为空，如果为空则删除
            self.cleanup_empty_recycle_bin(recycle_bin_path)
                
            self.file_deleted.emit(destination)
        except Exception as e:
            logger.error(f"删除文件时出错: {e}", exc_info=True)

    def update_metadata_file(self, recycle_bin_path, metadata):
        """
        更新回收站的元数据文件
        
        Args:
            recycle_bin_path (str): 回收站路径
            metadata (dict): 要添加到元数据文件的信息
        """
        metadata_file = os.path.join(recycle_bin_path, ".meta.json")
        try:
            # 如果元数据文件已存在，读取现有数据
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r') as f:
                    existing_metadata = json.load(f)
                existing_metadata.update(metadata)
                logger.debug(f"更新现有元数据文件: {metadata_file}")
            else:
                existing_metadata = metadata
                logger.debug(f"创建新的元数据文件: {metadata_file}")
                
            # 写入更新后的元数据
            with open(metadata_file, 'w') as f:
                json.dump(existing_metadata, f, indent=2, ensure_ascii=False)
            logger.debug(f"元数据文件保存成功: {metadata_file}")
        except Exception as e:
            logger.error(f"更新元数据文件失败: {e}", exc_info=True)

    def on_file_restore(self, file_path, original_path):
        """
        处理文件恢复事件
        
        Args:
            file_path (str): 回收站中的文件路径
            original_path (str): 原始文件路径
        """
        try:
            # 确保原始路径的目录存在
            original_dir = os.path.dirname(original_path)
            if not os.path.exists(original_dir):
                os.makedirs(original_dir)
                logger.debug(f"创建目录以恢复文件: {original_dir}")
                
            shutil.move(file_path, original_path)
            logger.info(f"文件已恢复: {file_path} -> {original_path}")
            self.file_restored.emit(original_path)
        except Exception as e:
            logger.error(f"恢复文件时出错: {e}", exc_info=True)
            
    def cleanup_empty_recycle_bin(self, recycle_bin_path):
        """
        清理空的回收站目录
        
        Args:
            recycle_bin_path (str): 回收站路径
        """
        try:
            # 检查目录是否存在
            if not os.path.exists(recycle_bin_path):
                return
                
            # 检查是否是delete目录
            if not os.path.basename(recycle_bin_path) == "delete":
                return
                
            # 检查目录是否为空（忽略.meta.json文件）
            items = os.listdir(recycle_bin_path)
            # 过滤掉.meta.json文件
            items = [item for item in items if item != ".meta.json"]
            
            # 如果目录为空，则删除该目录和元数据文件
            if not items:
                # 删除元数据文件（如果存在）
                metadata_file = os.path.join(recycle_bin_path, ".meta.json")
                if os.path.exists(metadata_file):
                    os.remove(metadata_file)
                    logger.debug(f"删除空回收站的元数据文件: {metadata_file}")
                    
                # 删除空的回收站目录
                os.rmdir(recycle_bin_path)
                logger.info(f"删除空回收站目录: {recycle_bin_path}")
        except Exception as e:
            logger.error(f"清理空回收站目录时出错: {e}", exc_info=True)