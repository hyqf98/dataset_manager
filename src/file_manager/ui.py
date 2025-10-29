from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeView, QFileSystemModel, QLineEdit, QLabel, QMenu, QAbstractItemView, QStyle
from PyQt5.QtCore import QDir, Qt, pyqtSignal, QStandardPaths, QSortFilterProxyModel, QModelIndex
from PyQt5.QtGui import QContextMenuEvent, QDragEnterEvent, QDropEvent
import os
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
            self.tree_view.setColumnWidth(0, 200)  # 名称列
            self.tree_view.setColumnWidth(1, 100)  # 大小列
            self.tree_view.setColumnWidth(2, 100)  # 类型列
            self.tree_view.setColumnWidth(3, 150)  # 修改时间列

            # 添加控件到主布局
            main_layout.addLayout(button_layout)
            main_layout.addWidget(self.root_path_label)
            main_layout.addWidget(self.search_box)
            main_layout.addWidget(self.tree_view)

            self.setLayout(main_layout)
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