from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem, QMessageBox
from PyQt5.QtCore import Qt, QDir
import os
import shutil
import json
from ..logging_config import logger


class RecycleBinDialog(QDialog):
    """
    回收站对话框类，用于管理和操作回收站中的文件
    """

    def __init__(self, recycle_bin_path, parent=None):
        """
        初始化回收站对话框
        
        Args:
            recycle_bin_path (str): 回收站路径
            parent: 父级窗口
        """
        super().__init__(parent)
        self.recycle_bin_path = recycle_bin_path
        self.init_ui()
        self.load_recycle_bin_contents()
        logger.debug(f"初始化回收站对话框: {recycle_bin_path}")

    def init_ui(self):
        """
        初始化回收站对话框界面
        """
        self.setWindowTitle("回收站")
        self.setGeometry(200, 200, 600, 400)

        # 创建主布局
        layout = QVBoxLayout(self)

        # 创建文件树
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["文件名", "原始路径", "大小", "删除时间"])
        self.file_tree.setRootIsDecorated(False)
        self.file_tree.setAlternatingRowColors(True)

        # 创建按钮
        button_layout = QHBoxLayout()
        
        self.restore_btn = QPushButton("还原选中文件")
        self.restore_all_btn = QPushButton("还原全部文件")
        self.delete_btn = QPushButton("彻底删除选中文件")
        self.delete_all_btn = QPushButton("清空回收站")
        self.close_btn = QPushButton("关闭")
        
        # 连接按钮事件
        self.restore_btn.clicked.connect(self.restore_selected)
        self.restore_all_btn.clicked.connect(self.restore_all)
        self.delete_btn.clicked.connect(self.delete_selected)
        self.delete_all_btn.clicked.connect(self.delete_all)
        self.close_btn.clicked.connect(self.accept)
        
        # 添加按钮到布局
        button_layout.addWidget(self.restore_btn)
        button_layout.addWidget(self.restore_all_btn)
        button_layout.addWidget(self.delete_btn)
        button_layout.addWidget(self.delete_all_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)
        
        # 添加控件到主布局
        layout.addWidget(self.file_tree)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)

    def load_recycle_bin_contents(self):
        """
        加载回收站中的文件列表
        """
        self.file_tree.clear()
        
        if not os.path.exists(self.recycle_bin_path):
            logger.debug(f"回收站路径不存在: {self.recycle_bin_path}")
            return
            
        try:
            # 递归查找所有delete文件夹
            self.find_and_load_recycle_bins(self.recycle_bin_path)
            logger.debug(f"加载回收站内容: {self.recycle_bin_path}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载回收站内容失败: {str(e)}")
            logger.error(f"加载回收站内容失败: {str(e)}", exc_info=True)

    def find_and_load_recycle_bins(self, root_path):
        """
        递归查找并加载所有回收站文件
        
        Args:
            root_path (str): 根路径
        """
        try:
            # 先加载当前回收站目录的文件
            for item_name in os.listdir(root_path):
                item_path = os.path.join(root_path, item_name)
                if os.path.isfile(item_path) or os.path.isdir(item_path):
                    # 检查是否是元数据文件，如果是则跳过
                    if item_name.endswith('.metadata'):
                        continue
                        
                    # 创建树形项目
                    tree_item = QTreeWidgetItem(self.file_tree)
                    tree_item.setText(0, item_name)
                    
                    # 获取文件信息
                    stat = os.stat(item_path)
                    size = stat.st_size
                    mtime = stat.st_mtime
                    
                    # 尝试从文件名中提取原始路径信息
                    original_path = self.extract_original_path(item_name)
                    tree_item.setText(1, original_path if original_path else "未知")
                    tree_item.setText(2, self.format_size(size))
                    tree_item.setText(3, self.format_time(mtime))
                    
                    # 保存完整路径作为数据
                    tree_item.setData(0, Qt.UserRole, item_path)
                    
                    # 保存所在回收站路径，用于还原操作
                    tree_item.setData(0, Qt.UserRole + 1, root_path)
            
            # 递归查找子目录中的delete文件夹
            for root, dirs, files in os.walk(root_path):
                for dir_name in dirs:
                    if dir_name == "delete":
                        delete_path = os.path.join(root, dir_name)
                        # 确保不是当前根目录下的delete文件夹（已经处理过了）
                        if delete_path != self.recycle_bin_path:
                            # 为子回收站创建一个分组项
                            group_item = QTreeWidgetItem(self.file_tree)
                            group_item.setText(0, f"回收站 ({delete_path})")
                            group_item.setExpanded(True)
                            
                            # 加载该回收站中的文件
                            for item_name in os.listdir(delete_path):
                                item_path = os.path.join(delete_path, item_name)
                                if os.path.isfile(item_path) or os.path.isdir(item_path):
                                    # 检查是否是元数据文件，如果是则跳过
                                    if item_name.endswith('.metadata'):
                                        continue
                                        
                                    # 创建树形项目作为分组项的子项
                                    tree_item = QTreeWidgetItem(group_item)
                                    tree_item.setText(0, item_name)
                                    
                                    # 获取文件信息
                                    stat = os.stat(item_path)
                                    size = stat.st_size
                                    mtime = stat.st_mtime
                                    
                                    # 尝试从文件名中提取原始路径信息
                                    original_path = self.extract_original_path(item_name)
                                    tree_item.setText(1, original_path if original_path else "未知")
                                    tree_item.setText(2, self.format_size(size))
                                    tree_item.setText(3, self.format_time(mtime))
                                    
                                    # 保存完整路径作为数据
                                    tree_item.setData(0, Qt.UserRole, item_path)
                                    
                                    # 保存所在回收站路径，用于还原操作
                                    tree_item.setData(0, Qt.UserRole + 1, delete_path)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"查找回收站内容失败: {str(e)}")
            logger.error(f"查找回收站内容失败: {str(e)}", exc_info=True)

    def extract_original_path(self, filename):
        """
        从文件名中提取原始路径信息
        
        Args:
            filename (str): 回收站中的文件名
            
        Returns:
            str: 原始路径，如果无法提取则返回None
        """
        # 检查统一的元数据文件
        metadata_file = os.path.join(self.recycle_bin_path, ".meta.json")
        
        # 首先在当前回收站路径查找元数据文件
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    if filename in metadata:
                        return metadata[filename]
            except:
                pass
        
        # 如果在当前回收站路径找不到，尝试在其他可能的回收站路径查找
        # 遍历所有可能的回收站路径
        try:
            for root, dirs, files in os.walk(os.path.dirname(self.recycle_bin_path)):
                for dir_name in dirs:
                    if dir_name == "delete":
                        possible_recycle_bin = os.path.join(root, dir_name)
                        possible_metadata = os.path.join(possible_recycle_bin, ".meta.json")
                        if os.path.exists(possible_metadata):
                            try:
                                with open(possible_metadata, 'r') as f:
                                    metadata = json.load(f)
                                    if filename in metadata:
                                        return metadata[filename]
                            except:
                                pass
        except:
            pass
            
        return None

    def restore_selected(self):
        """
        还原选中的文件
        """
        selected_items = self.file_tree.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择要还原的文件!")
            logger.debug("未选择要还原的文件")
            return
            
        restored_count = 0
        for item in selected_items:
            file_path = item.data(0, Qt.UserRole)
            # 获取该文件所在的回收站路径
            recycle_bin_path = item.data(0, Qt.UserRole + 1) or self.recycle_bin_path
            if self.restore_file(file_path, recycle_bin_path):
                # 从列表中移除
                index = self.file_tree.indexOfTopLevelItem(item)
                if index >= 0:
                    self.file_tree.takeTopLevelItem(index)
                else:
                    # 如果是子项，从父项中移除
                    parent = item.parent()
                    if parent:
                        parent.removeChild(item)
                restored_count += 1
                
        logger.info(f"还原 {restored_count} 个文件")

    def restore_all(self):
        """
        还原所有文件
        """
        root = self.file_tree.invisibleRootItem()
        count = root.childCount()
        
        if count == 0:
            QMessageBox.information(self, "提示", "回收站是空的!")
            logger.debug("回收站是空的")
            return
            
        reply = QMessageBox.question(self, "确认", f"确定要还原全部 {count} 个文件吗?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            restored_count = 0
            # 从后往前删除避免索引变化问题
            for i in range(count - 1, -1, -1):
                item = root.child(i)
                file_path = item.data(0, Qt.UserRole)
                # 获取该文件所在的回收站路径
                recycle_bin_path = item.data(0, Qt.UserRole + 1) or self.recycle_bin_path
                if self.restore_file(file_path, recycle_bin_path):
                    self.file_tree.takeTopLevelItem(i)
                    restored_count += 1
                    
            logger.info(f"还原全部 {restored_count} 个文件")

    def restore_file(self, file_path, recycle_bin_path=None):
        """
        还原单个文件到原始位置
        
        Args:
            file_path (str): 要还原的文件路径
            recycle_bin_path (str): 文件所在的回收站路径
            
        Returns:
            bool: 是否还原成功
        """
        try:
            filename = os.path.basename(file_path)
            
            # 如果未提供回收站路径，则使用默认路径
            if recycle_bin_path is None:
                recycle_bin_path = self.recycle_bin_path
                
            # 尝试获取原始路径
            original_path = self.extract_original_path(filename)
            
            # 如果没有原始路径信息，则使用默认还原路径（回收站的上级目录）
            if not original_path:
                parent_dir = os.path.dirname(recycle_bin_path)  # 回收站的上级目录
                original_path = os.path.join(parent_dir, filename)
            
            # 处理重名情况
            destination = original_path
            counter = 1
            base_name, ext = os.path.splitext(os.path.basename(original_path))
            dir_name = os.path.dirname(original_path)
            while os.path.exists(destination):
                new_filename = f"{base_name}_{counter}{ext}"
                destination = os.path.join(dir_name, new_filename)
                counter += 1
                
            # 确保目标路径的目录存在
            destination_dir = os.path.dirname(destination)
            if not os.path.exists(destination_dir):
                os.makedirs(destination_dir)
                
            shutil.move(file_path, destination)
            logger.info(f"还原文件: {file_path} -> {destination}")
            
            # 从元数据文件中移除该文件的记录
            self.remove_from_metadata(recycle_bin_path, filename)
            
            # 检查回收站目录是否为空，如果为空则删除
            self.cleanup_empty_recycle_bin(recycle_bin_path)
                
            return True
        except Exception as e:
            QMessageBox.critical(self, "错误", f"还原文件失败: {str(e)}")
            logger.error(f"还原文件失败: {str(e)}", exc_info=True)
            return False

    def remove_from_metadata(self, recycle_bin_path, filename):
        """
        从元数据文件中移除指定文件的记录
        
        Args:
            recycle_bin_path (str): 回收站路径
            filename (str): 文件名
        """
        metadata_file = os.path.join(recycle_bin_path, ".meta.json")
        try:
            # 如果元数据文件存在，读取现有数据
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    
                # 移除指定文件的记录
                if filename in metadata:
                    del metadata[filename]
                    
                # 如果还有其他记录，写回文件
                if metadata:
                    with open(metadata_file, 'w') as f:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)
                    logger.debug(f"从元数据文件中移除记录: {filename}")
                else:
                    # 如果没有记录了，删除元数据文件
                    os.remove(metadata_file)
                    logger.debug(f"删除空的元数据文件: {metadata_file}")
        except Exception as e:
            logger.error(f"从元数据文件中移除记录失败: {e}", exc_info=True)

    def delete_selected(self):
        """
        彻底删除选中的文件
        """
        selected_items = self.file_tree.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "提示", "请先选择要删除的文件!")
            logger.debug("未选择要删除的文件")
            return
            
        reply = QMessageBox.question(self, "确认", f"确定要彻底删除选中的 {len(selected_items)} 个文件吗?\n此操作不可恢复!",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            deleted_count = 0
            for item in selected_items:
                file_path = item.data(0, Qt.UserRole)
                recycle_bin_path = item.data(0, Qt.UserRole + 1) or self.recycle_bin_path
                if self.delete_file(file_path):
                    # 从列表中移除
                    index = self.file_tree.indexOfTopLevelItem(item)
                    if index >= 0:
                        self.file_tree.takeTopLevelItem(index)
                    else:
                        # 如果是子项，从父项中移除
                        parent = item.parent()
                        if parent:
                            parent.removeChild(item)
                    deleted_count += 1
                    
            logger.info(f"彻底删除 {deleted_count} 个文件")

    def delete_all(self):
        """
        清空回收站（删除所有delete文件夹）
        """
        reply = QMessageBox.question(self, "确认", "确定要清空回收站吗?\n此操作不可恢复!",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                # 删除所有delete文件夹
                if os.path.exists(self.recycle_bin_path):
                    shutil.rmtree(self.recycle_bin_path)
                    logger.info(f"删除回收站目录: {self.recycle_bin_path}")
                    
                # 递归查找并删除所有子目录中的delete文件夹
                root_dir = os.path.dirname(self.recycle_bin_path)
                for root, dirs, files in os.walk(root_dir):
                    for dir_name in dirs:
                        if dir_name == "delete":
                            delete_path = os.path.join(root, dir_name)
                            if os.path.exists(delete_path):
                                shutil.rmtree(delete_path)
                                logger.info(f"删除子回收站目录: {delete_path}")
                                
                self.file_tree.clear()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"清空回收站失败: {str(e)}")
                logger.error(f"清空回收站失败: {str(e)}", exc_info=True)

    def delete_file(self, file_path):
        """
        彻底删除单个文件
        
        Args:
            file_path (str): 要删除的文件路径
            
        Returns:
            bool: 是否删除成功
        """
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
                
            # 检查文件所在的回收站目录是否为空，如果为空则删除该目录
            self.cleanup_empty_recycle_bin(os.path.dirname(file_path))
            logger.info(f"彻底删除文件: {file_path}")
                
            return True
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除文件失败: {str(e)}")
            logger.error(f"删除文件失败: {str(e)}", exc_info=True)
            return False

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

    def format_size(self, size):
        """
        格式化文件大小显示
        
        Args:
            size (int): 文件大小（字节）
            
        Returns:
            str: 格式化后的大小字符串
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def format_time(self, timestamp):
        """
        格式化时间显示
        
        Args:
            timestamp (float): 时间戳
            
        Returns:
            str: 格式化后的时间字符串
        """
        from datetime import datetime
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")