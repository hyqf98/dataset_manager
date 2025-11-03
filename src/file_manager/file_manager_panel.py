from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeView, QFileSystemModel, QLineEdit, QLabel, QMenu, \
    QAbstractItemView, QStyle, QDialog, QTreeWidget, QTreeWidgetItem, QMessageBox, QInputDialog, QShortcut, QFileDialog, QAction
from PyQt5.QtCore import QDir, Qt, pyqtSignal, QStandardPaths, QSortFilterProxyModel, QModelIndex, QObject, QFileInfo
from PyQt5.QtGui import QContextMenuEvent, QDragEnterEvent, QDropEvent, QKeySequence
import os
import shutil
import json
import traceback
from ..logging_config import logger


class FileManagerProxyModel(QSortFilterProxyModel):
    """
    文件管理器代理模型，用于过滤显示的文件和文件夹
    """

    def __init__(self, parent=None):
        try:
            super().__init__(parent)
            self.root_paths = []
        except Exception as e:
            logger.error(f"FileManagerProxyModel初始化时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            raise

    def set_root_paths(self, paths):
        """
        设置根路径列表

        Args:
            paths (list): 根路径列表
        """
        try:
            self.root_paths = list(paths)
            self.invalidateFilter()
        except Exception as e:
            logger.error(f"设置根路径列表时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            raise

    def filterAcceptsRow(self, source_row, source_parent):
        """
        过滤函数，决定哪些行应该显示

        Args:
            source_row (int): 源行
            source_parent (QModelIndex): 源父级索引

        Returns:
            bool: 是否接受该行
        """
        try:
            # 获取源模型
            source_model = self.sourceModel()
            if not source_model:
                return True

            # 获取当前索引
            source_index = source_model.index(source_row, 0, source_parent)
            if not source_index.isValid():
                return True

            # 获取当前节点的路径
            current_path = source_model.filePath(source_index)

            # 如果没有设置根路径，显示所有内容
            if not self.root_paths:
                return True

            # 检查当前路径是否属于任何一个根路径
            for root_path in self.root_paths:
                if current_path == root_path or current_path.startswith(root_path + os.sep) or root_path.startswith(current_path + os.sep):
                    return True

            return False
        except Exception as e:
            logger.error(f"过滤行时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return True

    def lessThan(self, left, right):
        """
        自定义排序规则，按照文件系统默认顺序排序

        Args:
            left (QModelIndex): 左侧索引
            right (QModelIndex): 右侧索引

        Returns:
            bool: 排序比较结果
        """
        try:
            # 获取源模型
            source_model = self.sourceModel()
            if not source_model:
                return super().lessThan(left, right)

            # 按照文件系统默认顺序排序（即不进行特殊排序）
            # 直接比较行号，保持文件系统中的默认顺序
            return left.row() < right.row()
        except Exception as e:
            logger.error(f"排序比较时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return False


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


class FileManagerUI(QWidget):
    """
    文件管理器UI类
    负责文件管理器的界面布局和样式
    """

    # 定义右键菜单请求信号
    context_menu_requested = pyqtSignal(str, object)  # 文件路径, 位置
    # 定义拖拽操作信号
    file_dropped = pyqtSignal(str, str)  # 源文件路径, 目标文件夹路径

    def __init__(self):
        """
        初始化文件管理器UI
        """
        try:
            super().__init__()
            self.tree_view = None
            self.model = None
            self.proxy_model = None  # 代理模型
            self.root_path_label = None  # 显示当前根路径的标签
            self.context_menu = None  # 右键菜单
            self.init_ui()
            self.loaded_files = {}  # 存储已加载的文件信息
            self.batch_size = 100   # 每次加载的文件数量
            self.dataset_manager_dir = self.get_dataset_manager_dir()  # 获取数据管理器目录
        except Exception as e:
            logger.error(f"FileManagerUI初始化时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            raise

    def init_ui(self):
        """
        初始化文件管理器用户界面
        """
        try:
            # 创建主布局
            main_layout = QVBoxLayout(self)
            self.setAcceptDrops(True)  # 允许接收拖拽事件

            # 创建顶部按钮布局
            button_layout = QHBoxLayout()

            # 创建按钮
            self.import_btn = QPushButton("📁 选择文件夹")
            self.remove_btn = QPushButton("🗑️ 移除文件夹")
            self.recycle_bin_btn = QPushButton("🗑️ 回收站")
            self.refresh_btn = QPushButton("🔄 刷新")

            # 设置按钮样式
            self.import_btn.setStyleSheet(self.get_button_style())
            self.remove_btn.setStyleSheet(self.get_button_style())
            self.recycle_bin_btn.setStyleSheet(self.get_button_style())
            self.refresh_btn.setStyleSheet(self.get_button_style())

            # 添加按钮到布局
            button_layout.addWidget(self.import_btn)
            button_layout.addWidget(self.remove_btn)
            button_layout.addWidget(self.recycle_bin_btn)
            button_layout.addWidget(self.refresh_btn)
            button_layout.addStretch()

            # 创建显示当前根路径的标签
            self.root_path_label = QLabel("未选择文件夹")
            self.root_path_label.setStyleSheet("""
                QLabel {
                    padding: 5px;
                    background-color: #f0f0f0;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    font-weight: bold;
                }
            """)

            # 创建搜索框
            self.search_box = QLineEdit()
            self.search_box.setPlaceholderText("🔍 搜索文件...")
            self.search_box.setStyleSheet("""
                QLineEdit {
                    padding: 5px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                }
            """)

            # 创建文件树视图
            self.tree_view = QTreeView()
            self.model = QFileSystemModel()  # 使用标准的QFileSystemModel
            self.proxy_model = FileManagerProxyModel()
            self.proxy_model.setSourceModel(self.model)

            # 设置模型
            self.tree_view.setModel(self.proxy_model)

            # 设置初始状态为空
            self.clear_view()

            # 设置树视图属性
            self.tree_view.setRootIsDecorated(True)
            self.tree_view.setIndentation(20)
            self.tree_view.setSortingEnabled(False)  # 默认不启用排序
            self.tree_view.setHeaderHidden(False)
            self.tree_view.setAlternatingRowColors(True)

            # 启用拖拽功能
            self.tree_view.setDragEnabled(True)
            self.tree_view.setAcceptDrops(True)
            self.tree_view.setDropIndicatorShown(True)
            self.tree_view.setDefaultDropAction(Qt.MoveAction)

            # 启用右键菜单
            self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
            self.tree_view.customContextMenuRequested.connect(self.show_context_menu)

            # 连接拖拽事件
            self.tree_view.dragEnterEvent = self.handle_drag_enter
            self.tree_view.dragMoveEvent = self.handle_drag_move
            self.tree_view.dropEvent = self.handle_drop

            # 设置列宽
            self.tree_view.setColumnWidth(0, 150)  # 名称列
            self.tree_view.setColumnWidth(1, 100)  # 大小列
            self.tree_view.setColumnWidth(2, 50)  # 类型列
            self.tree_view.setColumnWidth(3, 150)  # 修改时间列

            # 增加整体最小尺寸
            self.tree_view.setMinimumWidth(400)
            self.tree_view.setMinimumHeight(500)

            # 添加控件到主布局
            main_layout.addLayout(button_layout)
            main_layout.addWidget(self.root_path_label)
            main_layout.addWidget(self.search_box)
            main_layout.addWidget(self.tree_view)

            self.setLayout(main_layout)

            # 设置面板的最小尺寸
            self.setMinimumWidth(400)
            self.setMinimumHeight(500)
        except Exception as e:
            logger.error(f"初始化UI时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            raise

    def get_button_style(self):
        """
        获取按钮样式

        Returns:
            str: CSS样式字符串
        """
        try:
            return """
                QPushButton {
                    padding: 6px 12px;
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                QPushButton:pressed {
                    background-color: #3d8b40;
                }
            """
        except Exception as e:
            logger.error(f"获取按钮样式时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return ""

    def set_root_paths(self, paths):
        """
        设置文件树的根路径列表，并更新显示

        Args:
            paths (list): 根路径列表
        """
        try:
            # 设置代理模型的根路径列表
            self.proxy_model.set_root_paths(paths)

            # 更新根路径显示
            if paths:
                self.root_path_label.setText(f"已导入 {len(paths)} 个文件夹")

                # 设置模型的根路径为所有根路径的公共父目录
                # 找到所有路径的公共父目录
                if len(paths) == 1:
                    common_parent = os.path.dirname(paths[0])
                else:
                    # 找到公共父目录
                    common_parent = os.path.commonpath(paths)

                self.model.setRootPath(common_parent)

                # 设置视图的根索引
                root_index = self.model.index(common_parent)
                proxy_root_index = self.proxy_model.mapFromSource(root_index)
                self.tree_view.setRootIndex(proxy_root_index)
            else:
                self.root_path_label.setText("未选择文件夹")
                self.clear_view()

            # 重置已加载文件记录
            self.loaded_files = {}

            # 保存导入的路径到持久化存储
            for path in paths:
                self.save_imported_path(path)
            logger.info(f"设置根路径列表: {paths}")
        except Exception as e:
            logger.error(f"设置根路径列表时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            raise

    def clear_view(self):
        """
        清空文件视图，恢复到初始状态
        """
        try:
            # 设置空的根索引以确保初始状态为空
            invalid_index = self.proxy_model.index(-1, -1)
            self.tree_view.setRootIndex(invalid_index)
            # 重置根路径标签
            self.root_path_label.setText("未选择文件夹")
            logger.debug("清空文件视图")
        except Exception as e:
            logger.error(f"清空视图时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def get_selected_path(self):
        """
        获取当前选中的路径

        Returns:
            str: 选中的文件路径
        """
        try:
            index = self.tree_view.currentIndex()
            if index.isValid():
                # 需要将代理模型的索引映射回源模型的索引
                source_index = self.proxy_model.mapToSource(index)
                return self.model.filePath(source_index)
            return None
        except Exception as e:
            logger.error(f"获取选中路径时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return None

    def load_files_in_batches(self, folder_path):
        """
        分批加载文件夹中的文件

        Args:
            folder_path (str): 文件夹路径
        """
        try:
            # 获取文件夹中的所有文件
            all_files = []
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    all_files.append(os.path.join(root, file))
                # 限制遍历的目录数量以提高性能
                if len(all_files) > 10000:  # 如果文件太多，只处理前10000个
                    break

            # 分批处理文件
            total_files = len(all_files)
            batches = (total_files + self.batch_size - 1) // self.batch_size  # 计算总批次数

            logger.info(f"总共找到 {total_files} 个文件，分为 {batches} 批处理")

            # 这里可以实现具体的分批加载逻辑
            # 当前实现是简化版本，一次性加载所有文件
            # 在实际应用中，可以实现"加载更多"按钮来分批显示文件

        except Exception as e:
            logger.error(f"加载文件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def show_context_menu(self, position):
        """
        显示右键菜单

        Args:
            position: 菜单显示位置
        """
        try:
            # 获取右键点击的项
            index = self.tree_view.indexAt(position)
            if not index.isValid():
                logger.debug("右键点击位置无效")
                return

            # 需要将代理模型的索引映射回源模型的索引
            source_index = self.proxy_model.mapToSource(index)
            # 发射右键菜单信号，让panel处理具体逻辑
            file_path = self.model.filePath(source_index)
            self.context_menu_requested.emit(file_path, position)
            logger.debug(f"显示上下文菜单: {file_path}")
        except Exception as e:
            logger.error(f"显示上下文菜单时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def handle_drag_enter(self, event):
        """
        处理拖拽进入事件

        Args:
            event: 拖拽事件
        """
        try:
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
                logger.debug("接受拖拽进入事件")
        except Exception as e:
            logger.error(f"处理拖拽进入事件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def handle_drag_move(self, event):
        """
        处理拖拽移动事件

        Args:
            event: 拖拽事件
        """
        try:
            if event.mimeData().hasUrls():
                # 获取当前位置的索引
                index = self.tree_view.indexAt(event.pos())
                if index.isValid():
                    # 需要将代理模型的索引映射回源模型的索引
                    source_index = self.proxy_model.mapToSource(index)
                    path = self.model.filePath(source_index)
                    # 只允许拖拽到文件夹上
                    if os.path.isdir(path):
                        event.acceptProposedAction()
                        logger.debug(f"接受拖拽移动事件到文件夹: {path}")
                        return
            event.ignore()
            logger.debug("忽略拖拽移动事件")
        except Exception as e:
            logger.error(f"处理拖拽移动事件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def handle_drop(self, event):
        """
        处理拖拽放置事件

        Args:
            event: 拖拽事件
        """
        try:
            if event.mimeData().hasUrls():
                # 获取放置位置的索引
                index = self.tree_view.indexAt(event.pos())
                if index.isValid():
                    # 需要将代理模型的索引映射回源模型的索引
                    source_index = self.proxy_model.mapToSource(index)
                    target_path = self.model.filePath(source_index)
                    # 如果目标不是文件夹，使用其所在的文件夹
                    if not os.path.isdir(target_path):
                        target_path = os.path.dirname(target_path)

                    # 发射文件放置信号
                    for url in event.mimeData().urls():
                        source_path = url.toLocalFile()
                        self.file_dropped.emit(source_path, target_path)
                        logger.debug(f"处理拖拽放置事件: {source_path} -> {target_path}")
                event.acceptProposedAction()
        except Exception as e:
            logger.error(f"处理拖拽放置事件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def get_dataset_manager_dir(self):
        """
        获取数据管理器的配置目录路径

        Returns:
            str: 配置目录路径
        """
        try:
            # 获取用户主目录
            home_dir = QStandardPaths.writableLocation(QStandardPaths.HomeLocation)
            # 构造.dataset_m目录路径
            dataset_manager_dir = os.path.join(home_dir, ".dataset_m")

            # 如果目录不存在则创建
            if not os.path.exists(dataset_manager_dir):
                os.makedirs(dataset_manager_dir)
                logger.debug(f"创建数据管理器目录: {dataset_manager_dir}")

            return dataset_manager_dir
        except Exception as e:
            logger.error(f"获取数据管理器目录时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return "."

    def save_imported_path(self, path):
        """
        保存导入的路径到持久化存储

        Args:
            path (str): 导入的路径
        """
        try:
            # 获取配置文件路径
            config_file = os.path.join(self.dataset_manager_dir, "imported_paths.json")

            # 如果配置文件已存在，读取现有数据
            imported_paths = []
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    imported_paths = json.load(f)

            # 如果路径不在列表中，则添加
            if path not in imported_paths:
                imported_paths.append(path)

                # 保存到文件
                with open(config_file, 'w') as f:
                    json.dump(imported_paths, f, indent=2, ensure_ascii=False)
                logger.debug(f"保存导入路径到配置文件: {path}")
        except Exception as e:
            logger.error(f"保存导入路径时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def load_imported_paths(self):
        """
        从持久化存储加载导入的路径

        Returns:
            list: 导入的路径列表
        """
        try:
            # 获取配置文件路径
            config_file = os.path.join(self.dataset_manager_dir, "imported_paths.json")

            # 如果配置文件存在，读取数据
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    imported_paths = json.load(f)
                logger.debug(f"从配置文件加载导入路径: {imported_paths}")
                return imported_paths
        except Exception as e:
            logger.error(f"加载导入路径时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

        return []

    def remove_imported_path(self, path):
        """
        从持久化存储中移除导入的路径

        Args:
            path (str): 要移除的路径
        """
        try:
            # 获取配置文件路径
            config_file = os.path.join(self.dataset_manager_dir, "imported_paths.json")

            # 如果配置文件存在，读取现有数据
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    imported_paths = json.load(f)

                # 移除指定路径
                if path in imported_paths:
                    imported_paths.remove(path)

                    # 保存更新后的数据
                    with open(config_file, 'w') as f:
                        json.dump(imported_paths, f, indent=2, ensure_ascii=False)
                    logger.debug(f"从配置文件移除导入路径: {path}")
        except Exception as e:
            logger.error(f"移除导入路径时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")


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
            reply = QMessageBox.question(self, "确认",
                                         f"确定要从管理中移除 '{file_path}' 吗?\n(注意：这只是从软件中移除管理，不会删除文件系统中的文件)",
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

                    # 添加重命名文件夹选项
                    rename_action = QAction("重命名", self)
                    rename_action.triggered.connect(lambda: self.rename_file_or_folder(file_path))
                    context_menu.addAction(rename_action)

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
            return f"/{self.delete_folder}/" in file_path or file_path.endswith(
                f"/{self.delete_folder}") or f"\\{self.delete_folder}\\" in file_path or file_path.endswith(f"\\{self.delete_folder}")
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
            recycle_bin_root = '/'.join(parts[:delete_index + 1])
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

                prev_index = None
                prev_proxy_index = None

                # 循环查找前一个有效的文件
                search_row = row - 1
                while search_row >= 0:
                    # 同一级别中的上一个文件
                    prev_index = source_model.index(search_row, 0, parent)
                    if prev_index.isValid():
                        # 检查是否是文件且支持预览
                        file_path = source_model.filePath(prev_index)
                        if os.path.isfile(file_path) and self.is_supported_file(file_path):
                            # 映射回代理模型
                            prev_proxy_index = proxy_model.mapFromSource(prev_index)
                            if prev_proxy_index.isValid():
                                break
                    search_row -= 1

                # 如果没找到，检查父级是否有上一个兄弟节点
                if not (prev_proxy_index and prev_proxy_index.isValid()):
                    parent_row = parent.row()
                    if parent_row > 0:
                        parent_parent = parent.parent()
                        prev_parent_index = source_model.index(parent_row - 1, 0, parent_parent)
                        # 获取该父节点的最后一个子节点
                        prev_parent_row_count = source_model.rowCount(prev_parent_index)
                        if prev_parent_row_count > 0:
                            # 从最后一个子节点开始向前查找
                            search_row = prev_parent_row_count - 1
                            while search_row >= 0:
                                prev_index = source_model.index(search_row, 0, prev_parent_index)
                                if prev_index.isValid():
                                    file_path = source_model.filePath(prev_index)
                                    if os.path.isfile(file_path) and self.is_supported_file(file_path):
                                        prev_proxy_index = proxy_model.mapFromSource(prev_index)
                                        if prev_proxy_index.isValid():
                                            break
                                search_row -= 1
                        elif os.path.isfile(source_model.filePath(prev_parent_index)) and self.is_supported_file(
                                source_model.filePath(prev_parent_index)):
                            # 父节点本身是文件
                            prev_proxy_index = proxy_model.mapFromSource(prev_parent_index)

                if prev_proxy_index and prev_proxy_index.isValid():
                    # 选中该索引
                    self.ui.tree_view.setCurrentIndex(prev_proxy_index)
                    # 触发点击事件
                    self.on_item_clicked(prev_proxy_index)
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

                next_index = None
                next_proxy_index = None

                # 循环查找后一个有效的文件
                search_row = row + 1
                while search_row < row_count:
                    # 同一级别中的下一个文件
                    next_index = source_model.index(search_row, 0, parent)
                    if next_index.isValid():
                        # 检查是否是文件且支持预览
                        file_path = source_model.filePath(next_index)
                        if os.path.isfile(file_path) and self.is_supported_file(file_path):
                            # 映射回代理模型
                            next_proxy_index = proxy_model.mapFromSource(next_index)
                            if next_proxy_index.isValid():
                                break
                    search_row += 1

                # 如果没找到，检查父级是否有下一个兄弟节点
                if not (next_proxy_index and next_proxy_index.isValid()):
                    parent_row = parent.row()
                    parent_row_count = source_model.rowCount(parent.parent())
                    if parent_row < parent_row_count - 1:
                        parent_parent = parent.parent()
                        next_parent_index = source_model.index(parent_row + 1, 0, parent_parent)
                        # 获取该父节点的第一个子节点
                        if source_model.hasChildren(next_parent_index):
                            # 从第一个子节点开始向后查找
                            search_row = 0
                            child_row_count = source_model.rowCount(next_parent_index)
                            while search_row < child_row_count:
                                next_index = source_model.index(search_row, 0, next_parent_index)
                                if next_index.isValid():
                                    file_path = source_model.filePath(next_index)
                                    if os.path.isfile(file_path) and self.is_supported_file(file_path):
                                        next_proxy_index = proxy_model.mapFromSource(next_index)
                                        if next_proxy_index.isValid():
                                            break
                                search_row += 1
                        elif os.path.isfile(source_model.filePath(next_parent_index)) and self.is_supported_file(
                                source_model.filePath(next_parent_index)):
                            # 父节点本身是文件
                            next_proxy_index = proxy_model.mapFromSource(next_parent_index)

                if next_proxy_index and next_proxy_index.isValid():
                    # 选中该索引
                    self.ui.tree_view.setCurrentIndex(next_proxy_index)
                    # 触发点击事件
                    self.on_item_clicked(next_proxy_index)
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

    def is_supported_file(self, file_path):
        """
        检查文件是否支持预览

        Args:
            file_path (str): 文件路径

        Returns:
            bool: 如果文件支持预览返回True，否则返回False
        """
        try:
            if not os.path.isfile(file_path):
                return False

            # 获取文件扩展名
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()

            # 支持的文件格式列表
            supported_formats = [
                '.jpg', '.jpeg', '.png', '.bmp', '.gif',  # 图片格式
                '.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv'  # 视频格式
            ]

            return ext in supported_formats
        except Exception as e:
            logger.error(f"检查文件是否支持预览时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return False

    def rename_file_or_folder(self, file_path):
        """
        重命名文件或文件夹

        Args:
            file_path (str): 要重命名的文件或文件夹路径
        """
        try:
            # 弹出输入对话框获取新名称
            old_name = os.path.basename(file_path)
            new_name, ok = QInputDialog.getText(self, "重命名", "请输入新名称:", text=old_name)
            if not ok or not new_name:
                logger.debug("取消重命名操作")
                return

            # 检查名称是否有效
            new_name = new_name.strip()
            if not new_name:
                QMessageBox.warning(self, "警告", "名称不能为空!")
                logger.warning("重命名名称为空")
                return

            # 检查是否包含非法字符
            illegal_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
            if any(char in new_name for char in illegal_chars):
                QMessageBox.warning(self, "警告", "名称包含非法字符!\n非法字符包括: / \\ : * ? \" < > |")
                logger.warning(f"重命名名称包含非法字符: {new_name}")
                return

            # 检查新名称是否与旧名称相同
            if new_name == old_name:
                logger.debug("新名称与旧名称相同，无需重命名")
                return

            # 构造新路径
            parent_dir = os.path.dirname(file_path)
            new_path = os.path.join(parent_dir, new_name)

            # 检查目标是否已存在
            if os.path.exists(new_path):
                QMessageBox.warning(self, "警告", f"名称 '{new_name}' 已存在!")
                logger.warning(f"重命名目标已存在: {new_path}")
                return

            try:
                # 执行重命名操作
                os.rename(file_path, new_path)
                logger.info(f"重命名: {file_path} -> {new_path}")

                # 刷新视图
                self.refresh_view()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"重命名失败: {str(e)}")
                logger.error(f"重命名失败: {str(e)}", exc_info=True)
        except Exception as e:
            logger.error(f"重命名文件或文件夹时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"重命名文件或文件夹时发生异常: {str(e)}")
