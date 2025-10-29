from PyQt5.QtWidgets import QWidget, QVBoxLayout, QMessageBox, QInputDialog, QShortcut, QFileDialog, QMenu, QAction
from PyQt5.QtCore import QDir, Qt, QFileInfo, QPoint
from PyQt5.QtGui import QKeySequence
from ..file_manager.ui import FileManagerUI
from ..file_manager.events import FileManagerEvents
from ..file_manager.recycle_bin import RecycleBinDialog
from ..logging_config import logger
import os
import shutil
import traceback


class FileManagerPanel(QWidget):
    """
    文件管理面板类，负责显示文件树和管理文件操作
    """

    def __init__(self):
        """
        初始化文件管理面板
        """
        super().__init__()
        try:
            self.events = FileManagerEvents()
            self.delete_folder = "delete"  # 回收站文件夹名
            self.imported_root_paths = []  # 保存导入的根路径列表
            self.drag_source_path = None  # 保存拖拽源路径
            self.init_ui()
            # 自动加载持久化路径，确保用户重启后能看到上次导入的文件夹内容
            self.load_persistent_paths()
        except Exception as e:
            logger.error(f"FileManagerPanel初始化时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            raise

    def init_ui(self):
        """
        初始化文件管理面板的用户界面
        """
        try:
            layout = QVBoxLayout(self)
            
            # 使用专门的UI类
            self.ui = FileManagerUI()
            
            # 连接按钮事件
            self.ui.import_btn.clicked.connect(self.import_folders)
            self.ui.remove_btn.clicked.connect(self.remove_folder)
            self.ui.recycle_bin_btn.clicked.connect(self.open_recycle_bin)
            self.ui.refresh_btn.clicked.connect(self.refresh_view)
            
            # 连接树形视图的点击事件，用于处理文件和文件夹点击
            self.ui.tree_view.clicked.connect(self.on_item_clicked)
            
            # 连接右键菜单事件
            self.ui.context_menu_requested.connect(self.show_context_menu)
            
            # 连接拖拽事件
            self.ui.file_dropped.connect(self.handle_file_drop)
            
            # 连接事件处理器
            self.events.file_selected.connect(self.on_file_selected)
            self.events.file_deleted.connect(self.on_file_deleted)
            
            # 添加控件到布局
            layout.addWidget(self.ui)
            self.setLayout(layout)
            
            # 创建Delete键快捷方式，但只在文件管理器有焦点时生效
            self.delete_shortcut = QShortcut(QKeySequence("Delete"), self)
            self.delete_shortcut.setContext(Qt.WidgetWithChildrenShortcut)  # 只在当前widget或其子widget有焦点时激活
            self.delete_shortcut.activated.connect(self.delete_selected_file)
        except Exception as e:
            logger.error(f"FileManagerPanel初始化UI时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            raise

    def import_folders(self):
        """
        导入多个文件夹功能，使用文件系统选择对话框
        """
        try:
            # 打开文件夹选择对话框，允许选择多个文件夹
            folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹")
            if folder_path and os.path.exists(folder_path):
                if folder_path not in self.imported_root_paths:
                    self.imported_root_paths.append(folder_path)
                    self.ui.set_root_paths(self.imported_root_paths)
                    logger.info(f"导入文件夹: {folder_path}")
            elif folder_path:
                QMessageBox.warning(self, "错误", "文件夹路径不存在!")
                logger.warning(f"尝试导入不存在的文件夹: {folder_path}")
        except Exception as e:
            logger.error(f"导入文件夹时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"导入文件夹时发生异常: {str(e)}")

    def load_persistent_paths(self):
        """
        加载持久化的文件夹路径并在UI中显示
        """
        try:
            # 从持久化存储加载导入的路径
            imported_paths = self.ui.load_imported_paths()
            valid_paths = [path for path in imported_paths if os.path.exists(path)]
            if valid_paths:
                self.imported_root_paths = valid_paths
                self.ui.set_root_paths(valid_paths)
                logger.info(f"自动加载持久化路径: {valid_paths}")
        except Exception as e:
            logger.error(f"加载持久化路径时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def remove_folder(self):
        """
        移除文件夹功能（从软件管理中移除，不删除文件系统中的文件夹）
        """
        try:
            file_path = self.ui.get_selected_path()
            if not file_path or not os.path.exists(file_path):
                QMessageBox.warning(self, "警告", "请选择一个有效的文件或文件夹!")
                logger.warning("尝试移除无效的文件或文件夹")
                return
                
            # 确认操作
            reply = QMessageBox.question(self, "确认", f"确定要从管理中移除 '{file_path}' 吗?\n(注意：这只是从软件中移除管理，不会删除文件系统中的文件)",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                # 从持久化存储中移除该路径
                self.ui.remove_imported_path(file_path)
                
                # 从导入的路径列表中移除
                if file_path in self.imported_root_paths:
                    self.imported_root_paths.remove(file_path)
                
                # 更新UI显示
                if not self.imported_root_paths:
                    # 没有其他管理的文件夹了，清空视图
                    self.ui.clear_view()
                else:
                    # 还有其他管理的文件夹，更新显示
                    self.ui.set_root_paths(self.imported_root_paths)
                
                # 通过信号通知主窗口清空预览面板
                # 查找主窗口中的预览面板并清空
                main_window = self.window()
                if main_window and hasattr(main_window, 'preview_panel'):
                    main_window.preview_panel.show_message("请选择文件进行预览")
                logger.info(f"从管理中移除文件夹: {file_path}")
        except Exception as e:
            logger.error(f"移除文件夹时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"移除文件夹时发生异常: {str(e)}")

    def open_recycle_bin(self):
        """
        打开回收站对话框
        """
        try:
            # 如果没有导入的根路径，使用当前目录
            if self.imported_root_paths:
                root_path = self.imported_root_paths[0]  # 使用第一个导入的路径作为基础
            else:
                root_path = QDir.currentPath()
            
            # 构造回收站路径
            recycle_bin_path = os.path.join(root_path, self.delete_folder)
            
            # 如果回收站不存在则创建
            if not os.path.exists(recycle_bin_path):
                os.makedirs(recycle_bin_path)
                logger.debug(f"创建回收站目录: {recycle_bin_path}")
                
            # 打开回收站对话框
            dialog = RecycleBinDialog(recycle_bin_path, self)
            dialog.exec_()
            logger.debug("打开回收站对话框")
        except Exception as e:
            logger.error(f"打开回收站时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"打开回收站时发生异常: {str(e)}")

    def move_to_recycle_bin(self, file_path):
        """
        将文件或文件夹移动到回收站
        
        Args:
            file_path (str): 要移动的文件或文件夹路径
        """
        try:
            # 如果没有导入的根路径，使用当前目录
            if self.imported_root_paths:
                root_path = self.imported_root_paths[0]  # 使用第一个导入的路径作为基础
            else:
                root_path = QDir.currentPath()
            
            # 构造回收站路径
            recycle_bin_path = os.path.join(root_path, self.delete_folder)
            
            # 移动文件到回收站
            self.events.on_file_delete(file_path, recycle_bin_path)
        except Exception as e:
            logger.error(f"移动文件到回收站时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"移动文件到回收站时发生异常: {str(e)}")

    def refresh_view(self):
        """
        刷新视图
        """
        try:
            if self.imported_root_paths:
                valid_paths = [path for path in self.imported_root_paths if os.path.exists(path)]
                self.ui.set_root_paths(valid_paths)
                logger.debug(f"刷新视图，根路径: {valid_paths}")
            else:
                # 如果没有导入的根路径，则清空视图
                self.ui.clear_view()
                logger.debug("清空视图")
        except Exception as e:
            logger.error(f"刷新视图时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"刷新视图时发生异常: {str(e)}")

    def on_item_clicked(self, index):
        """
        处理树形视图项目点击事件
        
        Args:
            index: 被点击的项目索引
        """
        try:
            if index.isValid():
                # 需要将代理模型的索引映射回源模型的索引
                source_index = self.ui.proxy_model.mapToSource(index)
                file_path = self.ui.model.filePath(source_index)
                file_info = QFileInfo(file_path)
                
                # 检查是否是文件夹
                if file_info.isDir():
                    # 如果是文件夹，展开或折叠文件夹，而不是下钻
                    if self.ui.tree_view.isExpanded(index):
                        self.ui.tree_view.collapse(index)
                    else:
                        self.ui.tree_view.expand(index)
                    logger.debug(f"文件夹点击: {file_path}")
                else:
                    # 如果是文件，发送信号在预览面板中显示
                    self.events.file_selected.emit(file_path)
                    logger.debug(f"文件点击: {file_path}")
        except Exception as e:
            logger.error(f"处理项目点击事件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"处理项目点击事件时发生异常: {str(e)}")

    def on_file_selected(self, file_path):
        """
        处理文件选中事件
        
        Args:
            file_path (str): 选中的文件路径
        """
        try:
            # 这里可以添加处理文件选中的逻辑
            logger.debug(f"处理文件选中事件: {file_path}")
        except Exception as e:
            logger.error(f"处理文件选中事件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def on_file_deleted(self, file_path):
        """
        处理文件删除事件
        
        Args:
            file_path (str): 已删除的文件路径
        """
        try:
            # 刷新视图以反映删除操作
            self.refresh_view()
            
            # 通过信号通知主窗口清空预览面板
            # 查找主窗口中的预览面板并清空
            main_window = self.window()
            if main_window and hasattr(main_window, 'preview_panel'):
                try:
                    main_window.preview_panel.show_message("请选择文件进行预览")
                except RuntimeError as e:
                    logger.error(f"预览面板已被删除: {str(e)}")
            logger.info(f"处理文件删除事件: {file_path}")
        except Exception as e:
            logger.error(f"处理文件删除事件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def delete_selected_file(self):
        """
        删除选中的文件（通过Delete键）
        """
        try:
            file_path = self.ui.get_selected_path()
            if not file_path or not os.path.exists(file_path):
                QMessageBox.warning(self, "警告", "请选择一个有效的文件或文件夹!")
                logger.warning("尝试删除无效的文件或文件夹")
                return
                
            # 确认操作
            reply = QMessageBox.question(self, "确认", f"确定要删除 '{file_path}' 吗?\n(文件将被移动到回收站)",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.move_to_recycle_bin(file_path)
                logger.info(f"删除文件: {file_path}")
        except Exception as e:
            logger.error(f"删除文件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"删除文件时发生异常: {str(e)}")

    def show_context_menu(self, file_path, position):
        """
        显示右键菜单
        
        Args:
            file_path (str): 选中的文件路径
            position (QPoint): 菜单位置
        """
        try:
            if not file_path or not os.path.exists(file_path):
                logger.warning(f"尝试对无效文件显示上下文菜单: {file_path}")
                return
                
            # 创建右键菜单
            context_menu = QMenu(self)
            
            # 判断当前是否在回收站目录中
            in_recycle_bin = self.is_in_recycle_bin(file_path)
            
            if in_recycle_bin:
                # 在回收站中，添加还原选项
                restore_action = QAction("还原", self)
                restore_action.triggered.connect(lambda: self.restore_file(file_path))
                context_menu.addAction(restore_action)
            else:
                # 不在回收站中，根据选中项类型添加不同操作
                if os.path.isdir(file_path):
                    # 选中的是文件夹，添加新建文件夹和删除选项
                    new_folder_action = QAction("新建文件夹", self)
                    new_folder_action.triggered.connect(lambda: self.create_new_folder(file_path))
                    context_menu.addAction(new_folder_action)
                    context_menu.addSeparator()
                    
                # 添加删除选项（适用于文件和文件夹）
                delete_action = QAction("删除", self)
                delete_action.triggered.connect(lambda: self.delete_file(file_path))
                context_menu.addAction(delete_action)
            
            # 在鼠标位置显示菜单
            context_menu.exec_(self.ui.tree_view.viewport().mapToGlobal(position))
            logger.debug(f"显示上下文菜单: {file_path}")
        except Exception as e:
            logger.error(f"显示上下文菜单时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"显示上下文菜单时发生异常: {str(e)}")

    def is_in_recycle_bin(self, file_path):
        """
        判断文件是否在回收站中
        
        Args:
            file_path (str): 文件路径
            
        Returns:
            bool: 是否在回收站中
        """
        try:
            if not self.imported_root_paths:
                return False
                
            # 检查文件路径是否包含delete文件夹
            return f"/{self.delete_folder}/" in file_path or file_path.endswith(f"/{self.delete_folder}") or f"\\{self.delete_folder}\\" in file_path or file_path.endswith(f"\\{self.delete_folder}")
        except Exception as e:
            logger.error(f"判断文件是否在回收站中时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return False

    def delete_file(self, file_path):
        """
        删除文件（移动到回收站）
        
        Args:
            file_path (str): 要删除的文件路径
        """
        try:
            if not file_path or not os.path.exists(file_path):
                QMessageBox.warning(self, "警告", "请选择一个有效的文件或文件夹!")
                logger.warning("尝试删除无效的文件或文件夹")
                return
                
            # 确认操作
            reply = QMessageBox.question(self, "确认", f"确定要删除 '{file_path}' 吗?\n(文件将被移动到回收站)",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.move_to_recycle_bin(file_path)
                logger.info(f"删除文件: {file_path}")
        except Exception as e:
            logger.error(f"删除文件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"删除文件时发生异常: {str(e)}")

    def restore_file(self, file_path):
        """
        还原回收站中的文件
        
        Args:
            file_path (str): 回收站中的文件路径
        """
        try:
            if not file_path or not os.path.exists(file_path):
                QMessageBox.warning(self, "警告", "请选择一个有效的文件!")
                logger.warning("尝试还原无效的文件")
                return
                
            # 获取回收站根路径
            recycle_bin_root = self.get_recycle_bin_root(file_path)
            if not recycle_bin_root:
                QMessageBox.warning(self, "错误", "无法确定回收站根路径!")
                logger.error("无法确定回收站根路径")
                return
                
            # 创建回收站对话框实例以使用其还原功能
            recycle_bin_dialog = RecycleBinDialog(recycle_bin_root, self)
            
            # 执行还原
            if recycle_bin_dialog.restore_file(file_path, recycle_bin_root):
                # 刷新视图
                self.refresh_view()
                logger.info(f"还原文件: {file_path}")
        except Exception as e:
            logger.error(f"还原文件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"还原文件时发生异常: {str(e)}")

    def get_recycle_bin_root(self, file_path):
        """
        获取回收站的根路径
        
        Args:
            file_path (str): 回收站中的文件路径
            
        Returns:
            str: 回收站根路径
        """
        try:
            # 查找路径中delete文件夹的位置
            parts = file_path.replace('\\', '/').split('/')
            delete_index = -1
            for i, part in enumerate(parts):
                if part == self.delete_folder:
                    delete_index = i
                    break
                    
            if delete_index == -1:
                return None
                
            # 构造回收站根路径
            recycle_bin_root = '/'.join(parts[:delete_index+1])
            return recycle_bin_root
        except Exception as e:
            logger.error(f"获取回收站根路径时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return None

    def handle_file_drop(self, source_path, target_path):
        """
        处理文件拖拽放置事件
        
        Args:
            source_path (str): 源文件路径
            target_path (str): 目标文件夹路径
        """
        try:
            # 检查源和目标是否有效
            if not os.path.exists(source_path):
                QMessageBox.warning(self, "错误", "源文件不存在!")
                logger.warning(f"源文件不存在: {source_path}")
                return
                
            if not os.path.exists(target_path):
                QMessageBox.warning(self, "错误", "目标文件夹不存在!")
                logger.warning(f"目标文件夹不存在: {target_path}")
                return
                
            # 检查目标是否是文件夹
            if not os.path.isdir(target_path):
                target_path = os.path.dirname(target_path)
                
            # 检查是否是同一个位置
            if os.path.dirname(source_path) == target_path:
                logger.debug("源文件和目标位置相同，无需移动")
                return  # 相同目录，无需移动
                
            # 检查目标是否是源的子目录（避免移动到自己的子目录中）
            source_abs = os.path.abspath(source_path)
            target_abs = os.path.abspath(target_path)
            try:
                common_path = os.path.commonpath([source_abs, target_abs])
                if common_path == source_abs and source_path != target_path:
                    QMessageBox.warning(self, "错误", "不能将文件夹移动到自己的子目录中!")
                    logger.warning("不能将文件夹移动到自己的子目录中")
                    return
            except ValueError:
                # 在不同的驱动器上，可以继续
                pass
                
            # 确认操作
            source_name = os.path.basename(source_path)
            target_display_name = os.path.basename(target_path) if target_path not in self.imported_root_paths else "根目录"
            reply = QMessageBox.question(self, "确认", f"确定要将 '{source_name}' 移动到 '{target_display_name}' 吗?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                try:
                    # 执行移动操作
                    destination = os.path.join(target_path, source_name)
                    
                    # 处理重名情况
                    counter = 1
                    base_name, ext = os.path.splitext(source_name)
                    while os.path.exists(destination):
                        new_name = f"{base_name}_{counter}{ext}"
                        destination = os.path.join(target_path, new_name)
                        counter += 1
                        
                    shutil.move(source_path, destination)
                    logger.info(f"移动文件: {source_path} -> {destination}")
                    
                    # 刷新视图
                    self.refresh_view()
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"移动文件失败: {str(e)}")
                    logger.error(f"移动文件失败: {str(e)}", exc_info=True)
        except Exception as e:
            logger.error(f"处理文件拖拽放置事件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"处理文件拖拽放置事件时发生异常: {str(e)}")

    def create_new_folder(self, parent_path):
        """
        在指定路径下创建新文件夹
        
        Args:
            parent_path (str): 父文件夹路径
        """
        try:
            # 弹出输入对话框获取新文件夹名称
            folder_name, ok = QInputDialog.getText(self, "新建文件夹", "请输入文件夹名称:")
            if not ok or not folder_name:
                logger.debug("取消创建新文件夹")
                return
                
            # 检查文件夹名称是否有效
            folder_name = folder_name.strip()
            if not folder_name:
                QMessageBox.warning(self, "警告", "文件夹名称不能为空!")
                logger.warning("文件夹名称为空")
                return
                
            # 检查是否包含非法字符
            illegal_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
            if any(char in folder_name for char in illegal_chars):
                QMessageBox.warning(self, "警告", "文件夹名称包含非法字符!\n非法字符包括: / \\ : * ? \" < > |")
                logger.warning(f"文件夹名称包含非法字符: {folder_name}")
                return
                
            # 构造新文件夹路径
            new_folder_path = os.path.join(parent_path, folder_name)
            
            # 检查文件夹是否已存在
            if os.path.exists(new_folder_path):
                QMessageBox.warning(self, "警告", f"文件夹 '{folder_name}' 已存在!")
                logger.warning(f"文件夹已存在: {new_folder_path}")
                return
                
            try:
                # 创建新文件夹
                os.makedirs(new_folder_path)
                logger.info(f"创建新文件夹: {new_folder_path}")
                
                # 刷新视图
                self.refresh_view()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建文件夹失败: {str(e)}")
                logger.error(f"创建文件夹失败: {str(e)}", exc_info=True)
        except Exception as e:
            logger.error(f"创建新文件夹时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"创建新文件夹时发生异常: {str(e)}")

    def select_previous_file(self):
        """
        选择前一个文件
        """
        try:
            logger.info("选择前一个文件")
            # 获取当前选中的索引
            current_index = self.ui.tree_view.currentIndex()
            if current_index.isValid():
                # 获取代理模型
                proxy_model = self.ui.proxy_model
                # 获取源模型
                source_model = self.ui.model
                
                # 将代理索引映射到源索引
                source_index = proxy_model.mapToSource(current_index)
                
                # 获取上一个索引
                parent = source_index.parent()
                row = source_index.row()
                
                if row > 0:
                    # 同一级别中的上一个文件
                    prev_index = source_model.index(row - 1, 0, parent)
                else:
                    # 需要检查父级是否有上一个兄弟节点
                    parent_row = parent.row()
                    if parent_row > 0:
                        parent_parent = parent.parent()
                        prev_parent_index = source_model.index(parent_row - 1, 0, parent_parent)
                        # 获取该父节点的最后一个子节点
                        prev_parent_row_count = source_model.rowCount(prev_parent_index)
                        if prev_parent_row_count > 0:
                            prev_index = source_model.index(prev_parent_row_count - 1, 0, prev_parent_index)
                        else:
                            prev_index = prev_parent_index
                    else:
                        # 没有上一个节点
                        prev_index = None
                
                if prev_index and prev_index.isValid():
                    # 映射回代理模型
                    proxy_index = proxy_model.mapFromSource(prev_index)
                    if proxy_index.isValid():
                        # 选中该索引
                        self.ui.tree_view.setCurrentIndex(proxy_index)
                        # 触发点击事件
                        self.on_item_clicked(proxy_index)
        except Exception as e:
            logger.error(f"选择前一个文件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def select_next_file(self):
        """
        选择后一个文件
        """
        try:
            logger.info("选择后一个文件")
            # 获取当前选中的索引
            current_index = self.ui.tree_view.currentIndex()
            if current_index.isValid():
                # 获取代理模型
                proxy_model = self.ui.proxy_model
                # 获取源模型
                source_model = self.ui.model
                
                # 将代理索引映射到源索引
                source_index = proxy_model.mapToSource(current_index)
                
                # 获取下一个索引
                parent = source_index.parent()
                row = source_index.row()
                row_count = source_model.rowCount(parent)
                
                if row < row_count - 1:
                    # 同一级别中的下一个文件
                    next_index = source_model.index(row + 1, 0, parent)
                else:
                    # 需要检查父级是否有下一个兄弟节点
                    parent_row = parent.row()
                    parent_row_count = source_model.rowCount(parent.parent())
                    if parent_row < parent_row_count - 1:
                        parent_parent = parent.parent()
                        next_parent_index = source_model.index(parent_row + 1, 0, parent_parent)
                        # 获取该父节点的第一个子节点
                        if source_model.hasChildren(next_parent_index):
                            next_index = source_model.index(0, 0, next_parent_index)
                        else:
                            next_index = next_parent_index
                    else:
                        # 没有下一个节点
                        next_index = None
                
                if next_index and next_index.isValid():
                    # 映射回代理模型
                    proxy_index = proxy_model.mapFromSource(next_index)
                    if proxy_index.isValid():
                        # 选中该索引
                        self.ui.tree_view.setCurrentIndex(proxy_index)
                        # 触发点击事件
                        self.on_item_clicked(proxy_index)
        except Exception as e:
            logger.error(f"选择后一个文件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def keyPressEvent(self, event):
        """
        处理键盘按键事件
        
        Args:
            event: 键盘事件
        """
        try:
            # 检查是否是回车键
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                # 如果有确认对话框打开，则模拟点击"是"按钮
                focused_widget = self.focusWidget()
                if isinstance(focused_widget, QMessageBox):
                    yes_button = focused_widget.button(QMessageBox.Yes)
                    if yes_button and yes_button.isEnabled():
                        yes_button.click()
                        return
                        
            # 检查是否是ESC键
            elif event.key() == Qt.Key_Escape:
                # 如果有确认对话框打开，则模拟点击"否"按钮
                focused_widget = self.focusWidget()
                if isinstance(focused_widget, QMessageBox):
                    no_button = focused_widget.button(QMessageBox.No)
                    if no_button and no_button.isEnabled():
                        no_button.click()
                        return
                        
            # 调用父类的处理方法
            super().keyPressEvent(event)
        except Exception as e:
            logger.error(f"处理键盘按键事件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
