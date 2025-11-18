from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTreeView, QLineEdit, QLabel, QMenu, \
    QAbstractItemView, QStyle, QDialog, QTreeWidget, QTreeWidgetItem, QMessageBox, QInputDialog, QFileDialog
from PyQt6.QtCore import QDir, Qt, pyqtSignal, QStandardPaths, QSortFilterProxyModel, QModelIndex, QObject, QFileInfo, QFileSystemWatcher
from PyQt6.QtGui import QContextMenuEvent, QDragEnterEvent, QDropEvent, QKeySequence, QStandardItemModel, QStandardItem, QIcon, QShortcut, QAction, QFileSystemModel
import os
import shutil
import json
import traceback
from ..logging_config import logger


class CustomFileSystemModel(QStandardItemModel):
    """
    自定义文件系统模型，直接显示导入的文件夹为根节点
    不显示中间的父目录层级
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.root_paths = []  # 导入的根路径列表
        self.file_system_model = QFileSystemModel()  # 用于获取文件信息
        self.setHorizontalHeaderLabels(["名称", "大小", "类型", "修改日期"])

    def set_root_paths(self, paths):
        """
        设置根路径列表，重建树结构

        Args:
            paths (list): 根路径列表
        """
        try:
            self.root_paths = list(paths)
            self.rebuild_tree()
        except Exception as e:
            logger.error(f"设置根路径时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def rebuild_tree(self):
        """
        重建树结构，将导入的文件夹直接显示为根节点
        """
        try:
            # 清空现有内容
            self.removeRows(0, self.rowCount())

            # 为每个导入的路径创建根节点
            for root_path in self.root_paths:
                if os.path.exists(root_path):
                    self.add_path_as_root(root_path)

        except Exception as e:
            logger.error(f"重建树结构时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def add_path_as_root(self, path):
        """
        将指定路径添加为根节点

        Args:
            path (str): 文件夹路径
        """
        try:
            # 创建根节点项
            root_item = self.create_item_for_path(path)
            self.appendRow(root_item)

            # 延迟加载：只添加一个占位子项，展开时再加载实际内容
            if os.path.isdir(path):
                # 添加占位子项，表示可以展开
                placeholder = QStandardItem("加载中...")
                root_item[0].appendRow(placeholder)

        except Exception as e:
            logger.error(f"添加根路径时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def create_item_for_path(self, path):
        """
        为指定路径创建标准项

        Args:
            path (str): 文件或文件夹路径

        Returns:
            list: 包含四列的 QStandardItem 列表
        """
        try:
            file_info = QFileInfo(path)

            # 名称列
            name_item = QStandardItem(file_info.fileName() or os.path.basename(path))
            name_item.setData(path, Qt.ItemDataRole.UserRole)  # 存储完整路径

            # 设置图标
            if file_info.isDir():
                name_item.setIcon(self.file_system_model.fileIcon(self.file_system_model.index(path)))
            else:
                # 根据文件扩展名设置图标
                name_item.setIcon(self.file_system_model.fileIcon(self.file_system_model.index(path)))

            # 大小列
            size_item = QStandardItem()
            if file_info.isFile():
                size = file_info.size()
                size_item.setText(self.format_size(size))
            else:
                size_item.setText("")

            # 类型列
            type_item = QStandardItem()
            if file_info.isDir():
                type_item.setText("文件夹")
            else:
                suffix = file_info.suffix()
                type_item.setText(f"{suffix} 文件" if suffix else "文件")

            # 修改日期列
            date_item = QStandardItem()
            date_item.setText(file_info.lastModified().toString("yyyy-MM-dd HH:mm:ss"))

            return [name_item, size_item, type_item, date_item]

        except Exception as e:
            logger.error(f"创建项时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return [QStandardItem("错误"), QStandardItem(""), QStandardItem(""), QStandardItem("")]

    def format_size(self, size):
        """
        格式化文件大小

        Args:
            size (int): 字节数

        Returns:
            str: 格式化后的大小字符串
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    def load_children(self, parent_item):
        """
        加载指定项的子内容

        Args:
            parent_item (QStandardItem): 父项
        """
        try:
            # 获取父路径
            parent_path = parent_item.data(Qt.ItemDataRole.UserRole)
            if not parent_path or not os.path.isdir(parent_path):
                return

            # 移除占位项
            if parent_item.rowCount() > 0:
                first_child = parent_item.child(0)
                if first_child and first_child.text() == "加载中...":
                    parent_item.removeRow(0)

            # 加载实际子项
            try:
                entries = os.listdir(parent_path)
                entries.sort()  # 按字母顺序排序

                for entry in entries:
                    entry_path = os.path.join(parent_path, entry)
                    # 跳过隐藏文件和回收站
                    if entry.startswith('.') or entry == 'delete':
                        continue

                    # 创建子项
                    child_items = self.create_item_for_path(entry_path)
                    parent_item.appendRow(child_items)

                    # 如果是文件夹，添加占位子项
                    if os.path.isdir(entry_path):
                        placeholder = QStandardItem("加载中...")
                        child_items[0].appendRow(placeholder)

            except PermissionError:
                logger.warning(f"无权限访问目录: {parent_path}")
            except Exception as e:
                logger.error(f"加载子内容时发生异常: {str(e)}")

        except Exception as e:
            logger.error(f"加载子项时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def get_file_path(self, index):
        """
        获取索引对应的文件路径

        Args:
            index (QModelIndex): 模型索引

        Returns:
            str: 文件路径
        """
        if not index.isValid():
            return ""
        item = self.itemFromIndex(index)
        if not item:
            # 如果不是第一列，获取同一行的第一列
            item = self.item(index.row(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else ""


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

    def on_file_delete(self, file_path, recycle_bin_path):
        """
        处理文件删除事件(移动到回收站)

        Args:
            file_path (str): 要删除的文件路径
            recycle_bin_path (str): 回收站路径
        """
        try:
            if not os.path.exists(recycle_bin_path):
                os.makedirs(recycle_bin_path)

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

            # 检查目录是否为空(忽略.meta.json文件)
            items = os.listdir(recycle_bin_path)
            # 过滤掉.meta.json文件
            items = [item for item in items if item != ".meta.json"]

            # 如果目录为空，则删除该目录和元数据文件
            if not items:
                # 删除元数据文件(如果存在)
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

    def __init__(self, width=None, height=None):
        """
        初始化文件管理器UI

        Args:
            width (int, optional): 面板宽度
            height (int, optional): 面板高度
        """
        try:
            super().__init__()
            self.panel_width = width
            self.panel_height = height
            self.tree_view = None
            self.model = None
            self.proxy_model = None  # 代理模型
            self.root_path_label = None  # 显示当前根路径的标签
            self.context_menu = None  # 右键菜单
            self.search_box = None  # 搜索框
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
        初始化文件管理器UI
        """
        try:
            main_layout = QVBoxLayout(self)

            # 创建按钮布局
            button_layout = QHBoxLayout()

            # 创建导入文件夹按钮
            self.import_btn = QPushButton("📁 导入文件夹")
            self.import_btn.setStyleSheet(self.get_button_style())

            # 创建移除文件夹按钮
            self.remove_btn = QPushButton("🗑️ 移除文件夹")
            self.remove_btn.setStyleSheet(self.get_button_style())

            # 创建回收站按钮
            self.recycle_bin_btn = QPushButton("🗑️ 回收站")
            self.recycle_bin_btn.setStyleSheet(self.get_button_style())

            # 创建刷新按钮
            self.refresh_btn = QPushButton("🔄 刷新")
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
            # 使用自定义模型替代 QFileSystemModel
            self.model = CustomFileSystemModel()

            # 设置模型
            self.tree_view.setModel(self.model)

            # 连接展开事件，延迟加载子内容
            self.tree_view.expanded.connect(self.on_item_expanded)

            # 设置初始状态为空
            self.clear_view()

            # 设置树视图属性
            self.tree_view.setRootIsDecorated(True)
            self.tree_view.setIndentation(20)
            self.tree_view.setSortingEnabled(False)  # 默认不启用排序
            self.tree_view.setHeaderHidden(False)
            self.tree_view.setAlternatingRowColors(True)
            # 问题2修复：启用多选模式以支持批量拖动
            self.tree_view.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
            # 禁用双击编辑功能
            self.tree_view.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)

            # 问题1修复：确保滚动条始终可见(上下和左右)
            self.tree_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
            self.tree_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            # 设置TreeView的大小策略，确保可以滚动
            from PyQt6.QtWidgets import QSizePolicy
            self.tree_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            # 应用滚动条样式和选中样式，使其更加明显(使用QTreeView选择器确保样式不被覆盖)
            scrollbar_style = self.get_scrollbar_style()
            selection_style = self.get_selection_style()
            # 添加QTreeView前缀确保样式只应用到当前TreeView
            tree_view_style = f"QTreeView {{ border: none; }} {selection_style} {scrollbar_style}"
            self.tree_view.setStyleSheet(tree_view_style)

            # 强制设置滚动条的最小尺寸，确保滚动条可见
            # 获取垂直滚动条并设置其属性
            v_scrollbar = self.tree_view.verticalScrollBar()
            if v_scrollbar:
                v_scrollbar.setMinimumWidth(15)
                v_scrollbar.setMaximumWidth(15)
                # 强制显示
                v_scrollbar.setVisible(True)
                # 设置范围，确保滚动条激活
                v_scrollbar.setRange(0, 1000)  # 设置一个足够大的范围
                logger.info(f"垂直滚动条设置完成: 宽度=15px, 可见={v_scrollbar.isVisible()}")
            else:
                logger.warning("无法获取垂直滚动条")

            # 获取水平滚动条并设置其属性(比垂直滚动条更细)
            h_scrollbar = self.tree_view.horizontalScrollBar()
            if h_scrollbar:
                h_scrollbar.setMinimumHeight(12)
                h_scrollbar.setMaximumHeight(12)
                # 设置范围，确保滚动条激活
                h_scrollbar.setRange(0, 1000)  # 设置一个足够大的范围
                logger.info(f"水平滚动条设置完成: 高度=12px, 可见={h_scrollbar.isVisible()}")
            else:
                logger.warning("无法获取水平滚动条")

            # 问题1修复：启用拖拽功能，支持内部和外部拖动
            self.tree_view.setDragEnabled(True)
            self.tree_view.setAcceptDrops(True)
            self.tree_view.setDropIndicatorShown(True)
            self.tree_view.setDefaultDropAction(Qt.DropAction.MoveAction)
            # 设置拖动模式为内部移动，支持批量拖动
            self.tree_view.setDragDropMode(QTreeView.DragDropMode.DragDrop)

            # 启用右键菜单
            self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.tree_view.customContextMenuRequested.connect(self.show_context_menu)

            # 连接拖拽事件
            self.tree_view.dragEnterEvent = self.handle_drag_enter
            self.tree_view.dragMoveEvent = self.handle_drag_move
            self.tree_view.dropEvent = self.handle_drop

            # 如果有尺寸参数，则设置面板尺寸
            if self.panel_width is not None and self.panel_height is not None:
                # 设置面板的最小尺寸和固定尺寸
                self.setMinimumWidth(self.panel_width)
                self.setMinimumHeight(self.panel_height)
                self.resize(self.panel_width, self.panel_height)

                # 设置树视图的最小尺寸
                self.tree_view.setMinimumWidth(self.panel_width)
                self.tree_view.setMinimumHeight(self.panel_height - 150)  # 为按钮和搜索框留出空间

                # 根据面板宽度设置文件树列宽
                if self.panel_width > 0:
                    # 计算各列的宽度比例
                    name_column_width = int(self.panel_width * 0.4)   # 名称列占40%
                    size_column_width = int(self.panel_width * 0.2)   # 大小列占20%
                    type_column_width = int(self.panel_width * 0.15)  # 类型列占15%
                    date_column_width = int(self.panel_width * 0.25)  # 修改时间列占25%

                    # 设置列宽
                    self.tree_view.setColumnWidth(0, name_column_width)   # 名称列
                    self.tree_view.setColumnWidth(1, size_column_width)   # 大小列
                    self.tree_view.setColumnWidth(2, type_column_width)   # 类型列
                    self.tree_view.setColumnWidth(3, date_column_width)   # 修改时间列

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

    def on_item_expanded(self, index):
        """
        处理项目展开事件，延迟加载子内容

        Args:
            index (QModelIndex): 被展开的项目索引
        """
        try:
            if not index.isValid():
                return

            # 获取对应的标准项
            item = self.model.itemFromIndex(index)
            if not item:
                return

            # 检查是否有占位子项，如果有，则加载实际内容
            if item.rowCount() > 0:
                first_child = item.child(0)
                if first_child and first_child.text() == "加载中...":
                    # 延迟加载子内容
                    self.model.load_children(item)

        except Exception as e:
            logger.error(f"处理项目展开事件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

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

    def get_scrollbar_style(self):
        """
        获取滚动条样式，使其更加明显易见
        上下和左右滚动条都使用相同的细尺寸

        Returns:
            str: CSS样式字符串
        """
        try:
            return """
                QScrollBar:vertical {
                    border: 1px solid #999999;
                    background: #f0f0f0;
                    width: 15px;
                    margin: 0px 0px 0px 0px;
                }
                QScrollBar::handle:vertical {
                    background: #4CAF50;
                    min-height: 30px;
                    border-radius: 7px;
                    border: 1px solid #45a049;
                }
                QScrollBar::handle:vertical:hover {
                    background: #45a049;
                }
                QScrollBar::handle:vertical:pressed {
                    background: #3d8b40;
                }
                QScrollBar::add-line:vertical {
                    border: none;
                    background: none;
                    height: 0px;
                }
                QScrollBar::sub-line:vertical {
                    border: none;
                    background: none;
                    height: 0px;
                }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                    background: #e0e0e0;
                }
                
                QScrollBar:horizontal {
                    border: 1px solid #999999;
                    background: #f0f0f0;
                    height: 12px;
                    margin: 0px 0px 0px 0px;
                }
                QScrollBar::handle:horizontal {
                    background: #4CAF50;
                    min-width: 30px;
                    border-radius: 7px;
                    border: 1px solid #45a049;
                }
                QScrollBar::handle:horizontal:hover {
                    background: #45a049;
                }
                QScrollBar::handle:horizontal:pressed {
                    background: #3d8b40;
                }
                QScrollBar::add-line:horizontal {
                    border: none;
                    background: none;
                    width: 0px;
                }
                QScrollBar::sub-line:horizontal {
                    border: none;
                    background: none;
                    width: 0px;
                }
                QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                    background: #e0e0e0;
                }
            """
        except Exception as e:
            logger.error(f"获取滚动条样式时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return ""

    def get_selection_style(self):
        """
        获取选中样式，确保无论焦点在哪里都能看到选中高亮

        Returns:
            str: CSS样式字符串
        """
        try:
            return """
                /* 选中项的样式，当TreeView有焦点时 */
                QTreeView::item:selected:active {
                    background-color: #3daee9;
                    color: white;
                }
                
                /* 选中项的样式，当TreeView没有焦点时（关键！） */
                QTreeView::item:selected:!active {
                    background-color: #3daee9;
                    color: white;
                }
                
                /* 鼠标悬停时的样式 */
                QTreeView::item:hover {
                    background-color: #e0f2f7;
                }
            """
        except Exception as e:
            logger.error(f"获取选中样式时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return ""

    def set_root_paths(self, paths):
        """
        设置文件树的根路径列表，并更新显示
        每个导入的文件夹都作为独立的根节点显示，不显示父级目录结构

        Args:
            paths (list): 根路径列表
        """
        try:
            # 更新根路径显示
            if paths:
                if self.root_path_label:
                    self.root_path_label.setText(f"已导入 {len(paths)} 个文件夹")

                # 设置自定义模型的根路径列表
                if self.model:
                    self.model.set_root_paths(paths)
            else:
                if self.root_path_label:
                    self.root_path_label.setText("未选择文件夹")
                self.clear_view()

            # 重置已加载文件记录
            self.loaded_files = {}

            # 保存导入的路径到持久化存储
            for path in paths:
                self.save_imported_path(path)
        except Exception as e:
            logger.error(f"设置根路径列表时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            raise

    def clear_view(self):
        """
        清空文件视图，恢复到初始状态
        """
        try:
            # 清空模型
            if self.model:
                self.model.removeRows(0, self.model.rowCount())
            # 重置根路径标签
            if self.root_path_label:
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
            index = self.tree_view.currentIndex() if self.tree_view else None
            if index and index.isValid():
                # 使用自定义模型的 get_file_path 方法
                if self.model:
                    return self.model.get_file_path(index)
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
            index = self.tree_view.indexAt(position) if self.tree_view else None
            if not index or not index.isValid():
                logger.debug("右键点击位置无效")
                return

            # 使用自定义模型的 get_file_path 方法
            file_path = self.model.get_file_path(index) if self.model else ""
            self.context_menu_requested.emit(file_path, position)
            logger.debug(f"显示上下文菜单: {file_path}")
        except Exception as e:
            logger.error(f"显示上下文菜单时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def handle_drag_enter(self, e):
        """
        处理拖拽进入事件

        Args:
            e: 拖拽事件
        """
        try:
            if e.mimeData().hasUrls():
                e.acceptProposedAction()
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
                index = self.tree_view.indexAt(event.pos()) if self.tree_view else None
                if index and index.isValid():
                    # 使用自定义模型的 get_file_path 方法
                    path = self.model.get_file_path(index) if self.model else ""
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

    def handle_drop(self, e):
        """
        问题2修复：处理拖拽放置事件，支持批量拖动

        Args:
            e: 拖拽事件
        """
        try:
            # 获取放置位置的索引
            index = self.tree_view.indexAt(e.pos()) if self.tree_view else None
            if not index or not index.isValid():
                e.ignore()
                return

            # 使用自定义模型的 get_file_path 方法
            target_path = self.model.get_file_path(index) if self.model else ""

            # 如枟目标不是文件夹，使用其所在的文件夹
            if target_path and not os.path.isdir(target_path):
                target_path = os.path.dirname(target_path)

            if not target_path:
                e.ignore()
                return

            # 问题2修复：处理内部拖动(批量选中)
            if e.source() == self.tree_view:
                # 获取所有选中的项目
                selected_indexes = self.tree_view.selectedIndexes()
                # 去重，只保留第0列的索引
                unique_indexes = [idx for idx in selected_indexes if idx.column() == 0]

                if unique_indexes:
                    for idx in unique_indexes:
                        source_path = self.model.get_file_path(idx) if self.model else ""
                        if source_path:
                            self.file_dropped.emit(source_path, target_path)
                            logger.debug(f"处理内部拖动: {source_path} -> {target_path}")

                    # 批量移动后统一刷新视图
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(300, lambda: self.refresh_view_keep_expanded())

                    e.acceptProposedAction()
                    return

            # 处理外部文件拖动
            if e.mimeData().hasUrls():
                # 发射文件放置信号，支持批量拖动
                for url in e.mimeData().urls():
                    source_path = url.toLocalFile()
                    self.file_dropped.emit(source_path, target_path)
                    logger.debug(f"处理外部拖动: {source_path} -> {target_path}")

                # 批量移动后统一刷新视图
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(300, lambda: self.refresh_view_keep_expanded())

                e.acceptProposedAction()
            else:
                e.ignore()

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
            home_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.HomeLocation)
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

    def __init__(self, recycle_bin_paths, parent=None):
        """
        问题3修复：初始化回收站对话框，支持多个回收站路径

        Args:
            recycle_bin_paths (list or str): 回收站路径列表或单个路径
            parent: 父级窗口
        """
        super().__init__(parent)
        # 支持传入列表或单个路径字符串
        if isinstance(recycle_bin_paths, list):
            self.recycle_bin_paths = recycle_bin_paths
        else:
            self.recycle_bin_paths = [recycle_bin_paths]
        self.init_ui()
        self.load_recycle_bin_contents()
        logger.debug(f"初始化回收站对话框: {self.recycle_bin_paths}")

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
        问题3修复：加载回收站中的文件列表(支持多个回收站路径)
        """
        self.file_tree.clear()

        # 遍历所有回收站路径
        for recycle_bin_path in self.recycle_bin_paths:
            if not os.path.exists(recycle_bin_path):
                logger.debug(f"回收站路径不存在: {recycle_bin_path}")
                continue

            try:
                # 递归查找所有delete文件夹
                self.find_and_load_recycle_bins(recycle_bin_path)
                logger.debug(f"加载回收站内容: {recycle_bin_path}")
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
                    # 问题1修复：跳过.meta.json和.metadata文件
                    if item_name == '.meta.json' or item_name.endswith('.metadata'):
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
                    tree_item.setData(0, Qt.ItemDataRole.UserRole, item_path)

                    # 保存所在回收站路径，用于还原操作
                    tree_item.setData(0, Qt.ItemDataRole.UserRole + 1, root_path)

            # 递归查找子目录中的delete文件夹
            for root, dirs, files in os.walk(root_path):
                for dir_name in dirs:
                    if dir_name == "delete":
                        delete_path = os.path.join(root, dir_name)
                        # 确保不是当前根目录下的delete文件夹(已经处理过了)
                        if delete_path != self.recycle_bin_path:
                            # 为子回收站创建一个分组项
                            group_item = QTreeWidgetItem(self.file_tree)
                            group_item.setText(0, f"回收站 ({delete_path})")
                            group_item.setExpanded(True)

                            # 加载该回收站中的文件
                            for item_name in os.listdir(delete_path):
                                item_path = os.path.join(delete_path, item_name)
                                if os.path.isfile(item_path) or os.path.isdir(item_path):
                                    # 问题1修复：跳过.meta.json和.metadata文件
                                    if item_name == '.meta.json' or item_name.endswith('.metadata'):
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
                                    tree_item.setData(0, Qt.ItemDataRole.UserRole, item_path)

                                    # 保存所在回收站路径，用于还原操作
                                    tree_item.setData(0, Qt.ItemDataRole.UserRole + 1, delete_path)
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
        # 问题3修复：在所有回收站路径中查找元数据
        for recycle_bin_path in self.recycle_bin_paths:
            # 检查统一的元数据文件
            metadata_file = os.path.join(recycle_bin_path, ".meta.json")

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
                for root, dirs, files in os.walk(os.path.dirname(recycle_bin_path)):
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
            except Exception as e:
                logger.error(f"查找元数据文件时发生异常: {str(e)}")

        # 如果找不到元数据，尝试从文件名中提取(假设文件名包含路径信息)
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
            file_path = item.data(0, Qt.ItemDataRole.UserRole)
            # 获取该文件所在的回收站路径
            recycle_bin_path = item.data(0, Qt.ItemDataRole.UserRole + 1) or self.recycle_bin_path
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
        root = self.file_tree.invisibleRootItem() if self.file_tree else None
        count = root.childCount() if root else 0

        if count == 0:
            QMessageBox.information(self, "提示", "回收站是空的!")
            logger.debug("回收站是空的")
            return

        reply = QMessageBox.question(self, "确认", f"确定要还原全部 {count} 个文件吗?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            restored_count = 0
            # 从后往前删除避免索引变化问题
            for i in range(count - 1, -1, -1):
                item = root.child(i) if root else None
                file_path = item.data(0, Qt.ItemDataRole.UserRole) if item else ""
                # 获取该文件所在的回收站路径
                recycle_bin_path = (item.data(0, Qt.ItemDataRole.UserRole + 1) if item else "") or self.recycle_bin_path
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

            # 如果没有原始路径信息，则使用默认还原路径(回收站的上级目录)
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
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = 0
            for item in selected_items:
                file_path = item.data(0, Qt.ItemDataRole.UserRole)
                recycle_bin_path = item.data(0, Qt.ItemDataRole.UserRole + 1) or self.recycle_bin_path
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
        清空回收站(删除所有delete文件夹)
        """
        reply = QMessageBox.question(self, "确认", "确定要清空回收站吗?\n此操作不可恢复!",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
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

            # 检查目录是否为空(忽略.meta.json文件)
            items = os.listdir(recycle_bin_path)
            # 过滤掉.meta.json文件
            items = [item for item in items if item != ".meta.json"]

            # 如果目录为空，则删除该目录和元数据文件
            if not items:
                # 删除元数据文件(如果存在)
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
            size (int): 文件大小(字节)

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

    def __init__(self, width=None, height=None):
        """
        初始化文件管理面板

        Args:
            width (int, optional): 面板宽度
            height (int, optional): 面板高度
        """
        super().__init__()
        # 存储尺寸参数作为内部属性
        self.panel_width = width
        self.panel_height = height

        self.events = FileManagerEvents()
        self.delete_folder = "delete"  # 回收站文件夹名
        self.imported_root_paths = []  # 保存导入的根路径列表
        self.drag_source_path = None  # 保存拖拽源路径
        self.is_searching = False  # 标记是否正在搜索，用于阻止搜索时触发预览

        # 问题4修复：初始化文件系统监听器
        self.file_watcher = QFileSystemWatcher()
        self.file_watcher.directoryChanged.connect(self.on_directory_changed)
        self.file_watcher.fileChanged.connect(self.on_file_changed)

        self.init_ui()

        # 自动加载持久化路径，确保用户重启后能看到上次导入的文件夹内容
        self.load_persistent_paths()

    def init_ui(self):
        """
        初始化文件管理面板的用户界面
        """
        try:
            layout = QVBoxLayout(self)

            # 使用专门的UI类，传递尺寸参数
            self.ui = FileManagerUI(width=self.panel_width, height=self.panel_height)

            # 连接按钮事件
            self.ui.import_btn.clicked.connect(self.import_folders)
            self.ui.remove_btn.clicked.connect(self.remove_folder)
            self.ui.recycle_bin_btn.clicked.connect(self.open_recycle_bin)
            self.ui.refresh_btn.clicked.connect(self.refresh_view)

            # 连接搜索框事件
            if self.ui.search_box:
                self.ui.search_box.textChanged.connect(self.on_search_text_changed)

            # 连接树形视图的点击事件，用于处理文件和文件夹点击
            if self.ui and self.ui.tree_view:
                self.ui.tree_view.clicked.connect(self.on_item_clicked)
                # 问题4修复：连接选择变化信号，以支持键盘导航时更新标题
                selection_model = self.ui.tree_view.selectionModel()
                if selection_model:
                    selection_model.currentChanged.connect(self.on_selection_changed)

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

            # 创建Delete键快捷方式，支持单个和批量删除
            self.delete_shortcut = QShortcut(QKeySequence("Delete"), self)
            self.delete_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)  # 只在当前widget或其子widget有焦点时激活
            self.delete_shortcut.activated.connect(self.delete_selected_file)
        except Exception as e:
            logger.error(f"FileManagerPanel初始化UI时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            raise

    def on_search_text_changed(self, text):
        """
        处理搜索框文本变化事件

        Args:
            text (str): 搜索框中的文本
        """
        try:
            # 如果搜索文本为空，则不做特殊处理，保持原有显示
            if not text:
                return

            # 在文件树中查找匹配的文件
            self.find_and_select_file(text)
        except Exception as e:
            logger.error(f"处理搜索文本变化时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def find_and_select_file(self, search_text):
        """
        在文件树中查找并选中匹配的文件(不触发预览)

        Args:
            search_text (str): 要搜索的文本
        """
        try:
            if not self.ui or not self.ui.tree_view or not self.ui.model:
                return

            # 设置搜索标志，阻止预览
            self.is_searching = True

            # 从模型根节点开始递归查找
            matched_index = self._find_file_in_model(self.ui.model.invisibleRootItem(), search_text.lower())

            if matched_index and matched_index.isValid():
                # 选中找到的文件(不触发预览)
                self.ui.tree_view.setCurrentIndex(matched_index)
                # 展开到该文件的路径
                parent = matched_index.parent()
                while parent.isValid():
                    self.ui.tree_view.expand(parent)
                    parent = parent.parent()
                # 滚动到该文件可见
                self.ui.tree_view.scrollTo(matched_index)

            # 重置搜索标志
            self.is_searching = False
        except Exception as e:
            logger.error(f"查找并选中文件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            # 确保重置搜索标志
            self.is_searching = False

    def _find_file_in_model(self, parent_item, search_text):
        """
        问题2修复：只在已展开的文件夹中查找匹配的文件，不触发延迟加载

        Args:
            parent_item (QStandardItem): 父项
            search_text (str): 要搜索的文本(小写)

        Returns:
            QModelIndex: 匹配的索引，如果未找到则返回None
        """
        try:
            if not parent_item:
                return None

            # 遍历所有子项
            for row in range(parent_item.rowCount()):
                child_item = parent_item.child(row, 0)
                if not child_item:
                    continue

                # 检查文件名是否匹配
                file_name = child_item.text()
                if search_text in file_name.lower():
                    # 检查是否是文件
                    file_path = child_item.data(Qt.ItemDataRole.UserRole)
                    if file_path and os.path.isfile(file_path):
                        return child_item.index()

                # 问题2修复：只在已展开的文件夹中递归搜索
                # 检查该项是否已展开
                if child_item.rowCount() > 0:
                    child_index = child_item.index()
                    if self.ui.tree_view.isExpanded(child_index):
                        # 只有在文件夹已展开的情况下才继续搜索
                        # 检查是否是占位项，如果是则跳过(说明还未真正展开)
                        first_grandchild = child_item.child(0)
                        if first_grandchild and first_grandchild.text() == "加载中...":
                            # 跳过未加载的文件夹
                            continue

                        result = self._find_file_in_model(child_item, search_text)
                        if result and result.isValid():
                            return result

            return None
        except Exception as e:
            logger.error(f"在模型中递归查找文件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return None

    def import_folders(self):
        """
        导入多个文件夹功能，使用文件系统选择对话框，显示文件夹大小
        """
        try:
            # 打开文件夹选择对话框，允许选择多个文件夹
            folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹")
            if folder_path and os.path.exists(folder_path):
                # 计算文件夹大小
                folder_size_mb = self._calculate_folder_size(folder_path)

                # 显示确认对话框，显示文件夹大小
                folder_name = os.path.basename(folder_path)
                reply = QMessageBox.question(
                    self,
                    "确认导入",
                    f"文件夹: {folder_name}\n大小: {folder_size_mb:.2f} MB\n\n确定要导入此文件夹吗？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.Yes:
                    if folder_path not in self.imported_root_paths:
                        self.imported_root_paths.append(folder_path)
                        self.ui.set_root_paths(self.imported_root_paths)

                        # 问题4修复：添加文件监听
                        self.add_path_to_watcher(folder_path)

                        logger.info(f"导入文件夹: {folder_path}, 大小: {folder_size_mb:.2f} MB")
                        QMessageBox.information(self, "成功", f"文件夹已导入\n大小: {folder_size_mb:.2f} MB")
                    else:
                        QMessageBox.information(self, "提示", "此文件夹已经导入！")
            elif folder_path:
                QMessageBox.warning(self, "错误", "文件夹路径不存在!")
                logger.warning(f"尝试导入不存在的文件夹: {folder_path}")
        except Exception as e:
            logger.error(f"导入文件夹时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"导入文件夹时发生异常: {str(e)}")

    def import_folder(self, folder_path):
        """
        Bug修复：自动导入指定文件夹(用于数据集划分后自动导入)

        Args:
            folder_path (str): 要导入的文件夹路径
        """
        try:
            if not folder_path or not os.path.exists(folder_path):
                logger.warning(f"导入文件夹失败，路径不存在: {folder_path}")
                return

            # 检查是否已经导入
            if folder_path not in self.imported_root_paths:
                self.imported_root_paths.append(folder_path)
                self.ui.set_root_paths(self.imported_root_paths)

                # 添加文件监听
                self.add_path_to_watcher(folder_path)

                logger.info(f"自动导入文件夹: {folder_path}")
            else:
                logger.info(f"文件夹已存在于导入列表: {folder_path}")
        except Exception as e:
            logger.error(f"自动导入文件夹时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def _calculate_folder_size(self, folder_path):
        """
        计算文件夹大小，以MB为单位

        Args:
            folder_path (str): 文件夹路径

        Returns:
            float: 文件夹大小(MB)
        """
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(folder_path):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    try:
                        if os.path.exists(file_path):
                            total_size += os.path.getsize(file_path)
                    except (OSError, PermissionError) as e:
                        logger.debug(f"无法访问文件: {file_path}, 错误: {e}")
                        continue

            # 转换为MB
            size_mb = total_size / (1024 * 1024)
            return size_mb
        except Exception as e:
            logger.error(f"计算文件夹大小时发生异常: {str(e)}")
            return 0.0

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

                # 问题4修复：为所有导入的路径添加监听
                for path in valid_paths:
                    self.add_path_to_watcher(path)

                logger.info(f"自动加载持久化路径: {valid_paths}")
        except Exception as e:
            logger.error(f"加载持久化路径时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def remove_folder(self):
        """
        移除文件夹功能(从软件管理中移除，不删除文件系统中的文件夹)
        """
        try:
            file_path = self.ui.get_selected_path()
            if not file_path or not os.path.exists(file_path):
                QMessageBox.warning(self, "警告", "请选择一个有效的文件或文件夹!")
                logger.warning("尝试移除无效的文件或文件夹")
                return

            # 修复bug2: 简化并改进路径匹配逻辑
            root_to_remove = None
            for root_path in self.imported_root_paths:
                # 标准化路径以便比较
                normalized_file_path = os.path.normpath(file_path)
                normalized_root_path = os.path.normpath(root_path)

                # 完全匹配
                if normalized_file_path == normalized_root_path:
                    root_to_remove = root_path
                    break

                # 检查file_path是否是root_path的子目录或者root_path是否是file_path的子目录
                # 这样可以处理用户选中文件夹内部的任何节点时，仍然能够正确识别根路径
                if (normalized_file_path.startswith(normalized_root_path + os.sep) or
                        normalized_root_path.startswith(normalized_file_path + os.sep)):
                    root_to_remove = root_path
                    break

            if not root_to_remove:
                QMessageBox.warning(self, "警告", "请选择一个已导入的文件夹!")
                logger.warning(f"选中的路径不是已导入的文件夹: {file_path}")
                logger.warning(f"当前导入的路径列表: {self.imported_root_paths}")
                return

            # 确认操作
            reply = QMessageBox.question(self, "确认",
                                         f"确定要从管理中移除 '{root_to_remove}' 吗?\n(注意：这只是从软件中移除管理，不会删除文件系统中的文件)",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                # 从持久化存储中移除该路径
                self.ui.remove_imported_path(root_to_remove)

                # 从导入的路径列表中移除
                if root_to_remove in self.imported_root_paths:
                    self.imported_root_paths.remove(root_to_remove)

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
                logger.info(f"从管理中移除文件夹: {root_to_remove}")
        except Exception as e:
            logger.error(f"移除文件夹时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"移除文件夹时发生异常: {str(e)}")

    def open_recycle_bin(self):
        """
        问题5修复：打开回收站对话框，显示所有导入文件夹下的delete目录
        """
        try:
            # 收集所有导入路径下的delete目录
            all_recycle_bins = []
            for root_path in self.imported_root_paths:
                recycle_bin_path = os.path.join(root_path, self.delete_folder)
                if os.path.exists(recycle_bin_path):
                    all_recycle_bins.append(recycle_bin_path)
                else:
                    # 如果回收站不存在则创建
                    os.makedirs(recycle_bin_path)
                    all_recycle_bins.append(recycle_bin_path)
                    logger.debug(f"创建回收站目录: {recycle_bin_path}")

            if not all_recycle_bins:
                QMessageBox.information(self, "提示", "没有找到回收站目录")
                return

            # 打开统一的回收站对话框，传递所有回收站路径
            dialog = RecycleBinDialog(all_recycle_bins, self)
            dialog.exec()

            # 回收站关闭后，刷新视图并保持展开状态
            self.refresh_view_keep_expanded()

            logger.debug("打开回收站对话框")
        except Exception as e:
            logger.error(f"打开回收站时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"打开回收站时发生异常: {str(e)}")

    def select_previous_file(self, current_file_path=None):
        """
        选择前一个文件

        Args:
            current_file_path (str, optional): 当前文件路径，如果不提供则从TreeView获取
        """
        try:
            logger.info("选择前一个文件")

            # 如果没有提供当前文件路径，则尝试从TreeView获取
            if not current_file_path:
                current_index = self.ui.tree_view.currentIndex() if self.ui and self.ui.tree_view else None
                if current_index and current_index.isValid():
                    current_file_path = self.ui.model.get_file_path(current_index) if self.ui and self.ui.model else ""

            # 如果还是没有当前文件路径，尝试从主窗口的预览面板获取
            if not current_file_path:
                main_window = self.window()
                if main_window and hasattr(main_window, 'preview_panel'):
                    current_file_path = main_window.preview_panel.current_file_path

            if not current_file_path:
                logger.warning("无法获取当前文件路径，无法切换")
                return

            # 收集所有文件
            all_files = self._collect_all_files()
            if not all_files:
                return

            # 查找当前文件在列表中的位置
            current_pos = -1
            for i, file_info in enumerate(all_files):
                if file_info['path'] == current_file_path:
                    current_pos = i
                    break

            if current_pos == -1:
                logger.warning(f"当前文件不在文件列表中: {current_file_path}")
                return

            # 查找前一个支持的文件
            prev_pos = current_pos - 1
            while prev_pos >= 0:
                prev_file_info = all_files[prev_pos]
                if self.is_supported_file(prev_file_info['path']):
                    # 找到了前一个文件，选中它
                    self._select_file_by_path(prev_file_info['path'])
                    # 触发预览
                    self.events.file_selected.emit(prev_file_info['path'])

                    # 如果算法测试对话框打开，更新其中的图片
                    if hasattr(self, 'algorithm_test_dialog') and self.algorithm_test_dialog and self.algorithm_test_dialog.isVisible():
                        self.algorithm_test_dialog.set_current_file(prev_file_info['path'])
                    return
                prev_pos -= 1

            logger.info("已经是第一个文件，无法继续向前切换")

        except Exception as e:
            logger.error(f"选择前一个文件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def select_next_file(self, current_file_path=None):
        """
        选择后一个文件

        Args:
            current_file_path (str, optional): 当前文件路径，如果不提供则从TreeView获取
        """
        try:
            logger.info("选择后一个文件")

            # 如果没有提供当前文件路径，则尝试从TreeView获取
            if not current_file_path:
                current_index = self.ui.tree_view.currentIndex() if self.ui and self.ui.tree_view else None
                if current_index and current_index.isValid():
                    current_file_path = self.ui.model.get_file_path(current_index) if self.ui and self.ui.model else ""

            # 如果还是没有当前文件路径，尝试从主窗口的预览面板获取
            if not current_file_path:
                main_window = self.window()
                if main_window and hasattr(main_window, 'preview_panel'):
                    current_file_path = main_window.preview_panel.current_file_path

            if not current_file_path:
                logger.warning("无法获取当前文件路径，无法切换")
                return

            # 收集所有文件
            all_files = self._collect_all_files()
            if not all_files:
                return

            # 查找当前文件在列表中的位置
            current_pos = -1
            for i, file_info in enumerate(all_files):
                if file_info['path'] == current_file_path:
                    current_pos = i
                    break

            if current_pos == -1:
                logger.warning(f"当前文件不在文件列表中: {current_file_path}")
                return

            # 查找下一个支持的文件
            next_pos = current_pos + 1
            while next_pos < len(all_files):
                next_file_info = all_files[next_pos]
                if self.is_supported_file(next_file_info['path']):
                    # 找到了下一个文件，选中它
                    self._select_file_by_path(next_file_info['path'])
                    # 触发预览
                    self.events.file_selected.emit(next_file_info['path'])

                    # 如果算法测试对话框打开，更新其中的图片
                    if hasattr(self, 'algorithm_test_dialog') and self.algorithm_test_dialog and self.algorithm_test_dialog.isVisible():
                        self.algorithm_test_dialog.set_current_file(next_file_info['path'])
                    return
                next_pos += 1

            logger.info("已经是最后一个文件，无法继续向后切换")

        except Exception as e:
            logger.error(f"选择后一个文件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def _collect_all_files(self):
        """
        收集模型中所有的文件(递归)

        Returns:
            list: 文件信息列表，每项包含 {'path': 文件路径, 'name': 文件名}
        """
        try:
            all_files = []
            if not self.ui or not self.ui.model:
                return all_files

            # 从根节点开始递归收集
            root_item = self.ui.model.invisibleRootItem()
            self._collect_files_from_item(root_item, all_files)

            return all_files
        except Exception as e:
            logger.error(f"收集所有文件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return []

    def _collect_files_from_item(self, parent_item, files_list):
        """
        从指定项递归收集文件

        Args:
            parent_item: 父项
            files_list: 文件列表(用于累积结果)
        """
        try:
            if not parent_item:
                return

            # 遍历所有子项
            for row in range(parent_item.rowCount()):
                child_item = parent_item.child(row, 0)
                if not child_item:
                    continue

                file_path = child_item.data(Qt.ItemDataRole.UserRole)
                if not file_path:
                    continue

                # 如果是文件，添加到列表
                if os.path.isfile(file_path):
                    files_list.append({
                        'path': file_path,
                        'name': os.path.basename(file_path)
                    })

                # 如果是文件夹，检查是否需要加载子内容
                if os.path.isdir(file_path):
                    # 如果有占位项，先加载实际内容
                    if child_item.rowCount() > 0:
                        first_grandchild = child_item.child(0)
                        if first_grandchild and first_grandchild.text() == "加载中...":
                            self.ui.model.load_children(child_item)

                    # 递归收集子项
                    self._collect_files_from_item(child_item, files_list)

        except Exception as e:
            logger.error(f"从项收集文件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def _select_file_by_path(self, file_path):
        """
        【重构】根据文件路径选中文件

        Args:
            file_path: 文件路径

        Returns:
            bool: 是否成功选中
        """
        try:
            if not self.ui or not self.ui.model or not self.ui.tree_view:
                logger.warning("UI组件未初始化")
                return False

            # 在模型中查找对应的索引
            index = self._find_index_by_path(self.ui.model.invisibleRootItem(), file_path)
            if index and index.isValid():
                # 展开到该文件的父路径
                parent = index.parent()
                while parent.isValid():
                    self.ui.tree_view.expand(parent)
                    parent = parent.parent()

                # 选中该索引
                self.ui.tree_view.setCurrentIndex(index)
                # 滚动到可见
                self.ui.tree_view.scrollTo(index)
                logger.debug(f"成功选中文件: {file_path}")
                return True
            else:
                logger.warning(f"在模型中未找到文件: {file_path}")
                return False

        except Exception as e:
            logger.error(f"根据路径选中文件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return False

    def _find_index_by_path(self, parent_item, target_path):
        """
        在模型中递归查找指定路径的索引

        Args:
            parent_item: 父项
            target_path: 目标文件路径

        Returns:
            QModelIndex: 找到的索引，未找到则返回None
        """
        try:
            if not parent_item:
                return None

            # 遍历所有子项
            for row in range(parent_item.rowCount()):
                child_item = parent_item.child(row, 0)
                if not child_item:
                    continue

                file_path = child_item.data(Qt.ItemDataRole.UserRole)
                if file_path == target_path:
                    return child_item.index()

                # 如果是文件夹，递归查找
                if file_path and os.path.isdir(file_path):
                    # 如果有占位项，先加载实际内容
                    if child_item.rowCount() > 0:
                        first_grandchild = child_item.child(0)
                        if first_grandchild and first_grandchild.text() == "加载中...":
                            self.ui.model.load_children(child_item)

                    result = self._find_index_by_path(child_item, target_path)
                    if result and result.isValid():
                        return result

            return None
        except Exception as e:
            logger.error(f"查找路径索引时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return None

    def add_path_to_watcher(self, path):
        """
        问题4修复：添加路径到文件监听器

        Args:
            path (str): 要监听的路径
        """
        try:
            if os.path.isdir(path) and path not in self.file_watcher.directories():
                self.file_watcher.addPath(path)
                # 递归添加子目录
                for root, dirs, files in os.walk(path):
                    # 跳过回收站目录
                    if 'delete' in dirs:
                        dirs.remove('delete')
                    for d in dirs:
                        dir_path = os.path.join(root, d)
                        if dir_path not in self.file_watcher.directories():
                            self.file_watcher.addPath(dir_path)
                logger.debug(f"已添加监听: {path}")
        except Exception as e:
            logger.error(f"添加路径监听时发生异常: {str(e)}")

    def on_directory_changed(self, path):
        """
        问题4修复：处理目录变化事件

        Args:
            path (str): 变化的目录路径
        """
        try:
            # 刷新视图，保持展开状态
            self.refresh_view_keep_expanded()
        except Exception as e:
            logger.error(f"处理目录变化时发生异常: {str(e)}")

    def on_file_changed(self, path):
        """
        问题4修复：处理文件变化事件

        Args:
            path (str): 变化的文件路径
        """
        try:
            logger.debug(f"文件变化: {path}")
            # 刷新视图，保持展开状态
            self.refresh_view_keep_expanded()
        except Exception as e:
            logger.error(f"处理文件变化时发生异常: {str(e)}")

    def refresh_view_keep_expanded(self):
        """
        【重构】刷新视图并保持已展开的状态
        """
        try:
            if not self.ui or not self.ui.tree_view or not self.ui.model:
                return

            # 1. 保存当前展开的路径
            expanded_paths = self._get_expanded_paths()

            # 2. 刷新视图
            if self.imported_root_paths:
                valid_paths = [path for path in self.imported_root_paths if os.path.exists(path)]
                self.ui.set_root_paths(valid_paths)
            else:
                self.ui.clear_view()

            # 3. 恢复展开状态
            self._restore_expanded_paths(expanded_paths)

        except Exception as e:
            logger.error(f"刷新视图时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def _refresh_and_restore(self, expanded_paths):
        """
        问题1修复：统一的刷新并恢复展开状态方法

        Args:
            expanded_paths (set): 需要恢复的展开路径集合
        """
        # 刷新视图
        if self.imported_root_paths:
            valid_paths = [path for path in self.imported_root_paths if os.path.exists(path)]
            self.ui.set_root_paths(valid_paths)

        # 恢复展开状态
        self._restore_expanded_paths(expanded_paths)


    def _get_expanded_paths(self):
        """
        获取当前所有展开的路径

        Returns:
            set: 展开的路径集合
        """
        expanded_paths = set()
        try:
            if not self.ui or not self.ui.model or not self.ui.tree_view:
                return expanded_paths

            def collect_expanded(parent_item):
                for row in range(parent_item.rowCount()):
                    child_item = parent_item.child(row, 0)
                    if child_item:
                        index = child_item.index()
                        if self.ui.tree_view.isExpanded(index):
                            file_path = child_item.data(Qt.ItemDataRole.UserRole)
                            if file_path:
                                expanded_paths.add(file_path)
                        # 递归收集
                        collect_expanded(child_item)

            collect_expanded(self.ui.model.invisibleRootItem())
        except Exception as e:
            logger.error(f"获取展开路径时发生异常: {str(e)}")

        return expanded_paths

    def _restore_expanded_paths(self, expanded_paths):
        """
        恢复展开状态

        Args:
            expanded_paths (set): 需要展开的路径集合
        """
        try:
            if not self.ui or not self.ui.model or not self.ui.tree_view:
                return

            def expand_items(parent_item):
                for row in range(parent_item.rowCount()):
                    child_item = parent_item.child(row, 0)
                    if child_item:
                        file_path = child_item.data(Qt.ItemDataRole.UserRole)
                        if file_path in expanded_paths:
                            # 先加载子内容
                            if child_item.rowCount() > 0:
                                first_grandchild = child_item.child(0)
                                if first_grandchild and first_grandchild.text() == "加载中...":
                                    self.ui.model.load_children(child_item)
                            # 展开
                            self.ui.tree_view.expand(child_item.index())
                            # 递归展开子项
                            expand_items(child_item)

            expand_items(self.ui.model.invisibleRootItem())
        except Exception as e:
            logger.error(f"恢复展开状态时发生异常: {str(e)}")

    def _find_next_file(self, current_file_path):
        """
        【重构】查找当前文件的下一个支持预览的文件

        Args:
            current_file_path (str): 当前文件路径

        Returns:
            str or None: 下一个文件路径，如果没有则返回None
        """
        try:
            all_files = self._collect_all_files()
            if not all_files:
                return None

            # 查找当前文件位置
            current_pos = -1
            for i, file_info in enumerate(all_files):
                if file_info['path'] == current_file_path:
                    current_pos = i
                    break

            if current_pos == -1:
                return None

            # 查找下一个支持的文件
            for i in range(current_pos + 1, len(all_files)):
                if self.is_supported_file(all_files[i]['path']):
                    return all_files[i]['path']

            return None

        except Exception as e:
            logger.error(f"查找下一个文件时发生异常: {str(e)}")
            return None

    def _select_and_preview_file(self, file_path):
        """
        【重构】选中并预览指定文件

        Args:
            file_path (str): 要选中的文件路径
        """
        try:
            if not os.path.exists(file_path):
                logger.warning(f"文件不存在，无法选中: {file_path}")
                return

            # 选中文件
            success = self._select_file_by_path(file_path)
            if success:
                # 发送预览信号
                self.events.file_selected.emit(file_path)
                logger.info(f"已选中并预览文件: {file_path}")
            else:
                logger.warning(f"无法选中文件: {file_path}")

        except Exception as e:
            logger.error(f"选中并预览文件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def move_to_recycle_bin(self, file_path):
        """
        将文件或文件夹移动到回收站

        Args:
            file_path (str): 要移动的文件或文件夹路径
        """
        try:
            # 确定文件所属的根路径
            root_path = self.get_root_path_for_file(file_path)

            # 构造回收站路径
            recycle_bin_path = os.path.join(root_path, self.delete_folder)

            # 移动文件到回收站
            self.events.on_file_delete(file_path, recycle_bin_path)
        except Exception as e:
            logger.error(f"移动文件到回收站时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"移动文件到回收站时发生异常: {str(e)}")

    def get_root_path_for_file(self, file_path):
        """
        根据文件路径确定其所属的根路径

        Args:
            file_path (str): 文件路径

        Returns:
            str: 文件所属的根路径
        """
        try:
            # 如果没有导入的根路径，使用当前目录
            if not self.imported_root_paths:
                return QDir.currentPath()

            # 标准化文件路径
            normalized_file_path = os.path.normpath(file_path)

            # 查找文件路径匹配的根路径
            for root_path in self.imported_root_paths:
                normalized_root_path = os.path.normpath(root_path)
                # 检查文件是否在该根路径下
                if (normalized_file_path == normalized_root_path or
                        normalized_file_path.startswith(normalized_root_path + os.sep) or
                        normalized_file_path.startswith(normalized_root_path + os.path.sep)):
                    return root_path

            # 如果没有找到匹配的根路径，使用第一个导入的路径作为默认值
            # 这是为了保持向后兼容性
            return self.imported_root_paths[0]
        except Exception as e:
            logger.error(f"确定文件所属根路径时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            # 出现异常时使用第一个导入的路径
            return self.imported_root_paths[0] if self.imported_root_paths else QDir.currentPath()

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
                # 使用自定义模型的 get_file_path 方法
                file_path = self.ui.model.get_file_path(index) if self.ui and self.ui.model else ""
                if not file_path:
                    return

                file_info = QFileInfo(file_path)

                # 检查是否是文件夹
                if file_info.isDir():
                    # 问题1修复：点击文件夹时只展开，不折叠
                    # 用户需要一直展开文件夹列表，除非再次点击才收起
                    if self.ui and self.ui.tree_view:
                        # 无论当前是否展开，都展开文件夹
                        # 如果已经展开，再次点击则折叠
                        if self.ui.tree_view.isExpanded(index):
                            self.ui.tree_view.collapse(index)
                        else:
                            self.ui.tree_view.expand(index)
                else:
                    # 如果是文件，发送信号在预览面板中显示
                    self.events.file_selected.emit(file_path)
        except Exception as e:
            logger.error(f"处理项目点击事件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"处理项目点击事件时发生异常: {str(e)}")

    def on_selection_changed(self, current, previous):
        """
        问题4修复：处理选择变化事件(支持键盘导航)

        Args:
            current: 当前选中的索引
            previous: 之前选中的索引
        """
        try:
            # 如果正在搜索，不触发预览
            if self.is_searching:
                return

            if current.isValid():
                # 使用自定义模型的 get_file_path 方法
                file_path = self.ui.model.get_file_path(current) if self.ui and self.ui.model else ""
                if not file_path:
                    return

                file_info = QFileInfo(file_path)

                # 只处理文件，不处理文件夹
                if not file_info.isDir():
                    # 发送信号在预览面板中显示
                    self.events.file_selected.emit(file_path)
        except Exception as e:
            logger.error(f"处理选择变化事件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def on_file_selected(self, file_path):
        """
        处理文件选中事件

        Args:
            file_path (str): 选中的文件路径
        """
        pass

    def on_file_deleted(self, file_path):
        """
        处理文件删除事件

        Args:
            file_path (str): 已删除的文件路径
        """
        try:
            # 问题2修复：使用refresh_view_keep_expanded保持文件夹展开状态
            self.refresh_view_keep_expanded()

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
        删除选中的文件，支持单个和批量删除
        """
        try:
            if not self.ui or not self.ui.tree_view:
                return

            # 获取所有选中的索引
            selected_indexes = self.ui.tree_view.selectedIndexes()
            if not selected_indexes:
                QMessageBox.warning(self, "警告", "请先选择要删除的文件或文件夹!")
                logger.warning("尝试删除但没有选中任何项目")
                return

            # 去重，只保留第0列的索引
            unique_indexes = [idx for idx in selected_indexes if idx.column() == 0]
            if not unique_indexes:
                QMessageBox.warning(self, "警告", "请先选择要删除的文件或文件夹!")
                return

            # 获取选中的文件路径
            selected_paths = []
            for index in unique_indexes:
                file_path = self.ui.model.get_file_path(index) if self.ui.model else ""
                if file_path and os.path.exists(file_path):
                    selected_paths.append(file_path)

            if not selected_paths:
                QMessageBox.warning(self, "警告", "请选择有效的文件或文件夹!")
                return

            # 判断是单个删除还是批量删除
            if len(selected_paths) == 1:
                # 单个删除
                file_path = selected_paths[0]
                file_name = os.path.basename(file_path)
                reply = QMessageBox.question(
                    self, "确认",
                    f"确定要删除 '{file_name}' 吗?\n(文件将被移动到回收站)",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
            else:
                # 批量删除
                reply = QMessageBox.question(
                    self, "确认",
                    f"确定要删除选中的 {len(selected_paths)} 个项目吗?\n(文件将被移动到回收站)",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

            if reply != QMessageBox.StandardButton.Yes:
                return

            # 保存当前展开状态
            expanded_paths = self._get_expanded_paths()

            # 执行删除操作
            for file_path in selected_paths:
                try:
                    self.move_to_recycle_bin(file_path)
                    logger.info(f"文件已移动到回收站: {file_path}")
                except Exception as e:
                    logger.error(f"删除文件 {file_path} 时发生异常: {str(e)}")
                    QMessageBox.warning(self, "警告", f"删除文件 {os.path.basename(file_path)} 时出错: {str(e)}")

            # 刷新视图并恢复展开状态
            self._refresh_and_restore(expanded_paths)

            logger.info(f"删除完成，共删除 {len(selected_paths)} 个项目")

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

                    # 添加新建文件选项
                    new_file_action = QAction("新建文件", self)
                    new_file_action.triggered.connect(lambda: self.create_new_file(file_path))
                    context_menu.addAction(new_file_action)

                    # 添加重命名文件夹选项
                    rename_action = QAction("重命名", self)
                    rename_action.triggered.connect(lambda: self.rename_file_or_folder(file_path))
                    context_menu.addAction(rename_action)

                    context_menu.addSeparator()

                    # 添加上传文件选项
                    upload_action = QAction("上传文件", self)
                    upload_action.triggered.connect(lambda: self.upload_files(file_path))
                    context_menu.addAction(upload_action)
                else:
                    # 选中的是文件，添加算法测试选项(仅对支持的文件格式)
                    if self.is_supported_file(file_path):
                        algorithm_test_action = QAction("算法测试", self)
                        algorithm_test_action.triggered.connect(lambda: self.algorithm_test(file_path))
                        context_menu.addAction(algorithm_test_action)
                        context_menu.addSeparator()

                # 添加删除选项(适用于文件和文件夹)
                delete_action = QAction("删除", self)
                delete_action.triggered.connect(lambda: self._delete_file_direct(file_path))
                context_menu.addAction(delete_action)

            # 在鼠标位置显示菜单
            if self.ui and self.ui.tree_view:
                viewport = self.ui.tree_view.viewport()
                if viewport:
                    context_menu.exec(viewport.mapToGlobal(position))
            logger.debug(f"显示上下文菜单: {file_path}")
        except Exception as e:
            logger.error(f"显示上下文菜单时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"显示上下文菜单时发生异常: {str(e)}")

    def _delete_file_direct(self, file_path):
        """
        直接删除指定文件的方法，用于右键菜单调用

        Args:
            file_path (str): 要删除的文件路径
        """
        try:
            if not file_path or not os.path.exists(file_path):
                QMessageBox.warning(self, "警告", "请选择一个有效的文件或文件夹!")
                logger.warning("尝试删除无效的文件或文件夹")
                return

            # 先选中该文件，然后调用统一的删除方法
            self._select_file_by_path(file_path)
            self.delete_selected_file()

        except Exception as e:
            logger.error(f"删除文件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"删除文件时发生异常: {str(e)}")

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


    def _refresh_and_restore(self, expanded_paths):
        """
        问题1修复：统一的刷新并恢复展开状态方法

        Args:
            expanded_paths (set): 需要恢复的展开路径集合
        """
        # 刷新视图
        if self.imported_root_paths:
            valid_paths = [path for path in self.imported_root_paths if os.path.exists(path)]
            self.ui.set_root_paths(valid_paths)

        # 恢复展开状态
        self._restore_expanded_paths(expanded_paths)

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
                # 问题1修复：刷新视图并保持展开状态
                self.refresh_view_keep_expanded()
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
        问题1修复：处理文件拖拽放置事件，支持批量移动

        Args:
            source_path (str): 源文件路径
            target_path (str): 目标文件夹路径
        """
        try:
            # 检查源和目标是否有效
            if not os.path.exists(source_path):
                logger.warning(f"源文件不存在: {source_path}")
                return

            if not os.path.exists(target_path):
                logger.warning(f"目标文件夹不存在: {target_path}")
                return

            # 检查目标是否是文件夹
            if not os.path.isdir(target_path):
                target_path = os.path.dirname(target_path)

            # 检查是否是同一个位置
            if os.path.dirname(source_path) == target_path:
                logger.debug("源文件和目标位置相同，无需移动")
                return  # 相同目录，无需移动

            # 检查目标是否是源的子目录(避免移动到自己的子目录中)
            source_abs = os.path.abspath(source_path)
            target_abs = os.path.abspath(target_path)
            try:
                common_path = os.path.commonpath([source_abs, target_abs])
                if common_path == source_abs and source_path != target_path:
                    logger.warning("不能将文件夹移动到自己的子目录中")
                    return
            except ValueError:
                # 在不同的驱动器上，可以继续
                pass

            # 执行移动操作(批量移动时不显示确认对话框)
            try:
                source_name = os.path.basename(source_path)
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
            except Exception as e:
                QMessageBox.critical(self, "错误", f"移动文件失败: {str(e)}")
                logger.error(f"移动文件失败: {str(e)}", exc_info=True)
        except Exception as e:
            logger.error(f"处理文件拖拽放置事件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

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

                # 问题1修复：刷新视图并保持展开状态
                self.refresh_view_keep_expanded()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建文件夹失败: {str(e)}")
                logger.error(f"创建文件夹失败: {str(e)}", exc_info=True)
        except Exception as e:
            logger.error(f"创建新文件夹时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"创建新文件夹时发生异常: {str(e)}")

    def create_new_file(self, parent_path):
        """
        在指定路径下创建新文件

        Args:
            parent_path (str): 父文件夹路径
        """
        try:
            # 弹出输入对话框获取新文件名称
            file_name, ok = QInputDialog.getText(self, "新建文件", "请输入文件名称:")
            if not ok or not file_name:
                logger.debug("取消创建新文件")
                return

            # 检查文件名称是否有效
            file_name = file_name.strip()
            if not file_name:
                QMessageBox.warning(self, "警告", "文件名称不能为空!")
                logger.warning("文件名称为空")
                return

            # 检查是否包含非法字符
            illegal_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
            if any(char in file_name for char in illegal_chars):
                QMessageBox.warning(self, "警告", "文件名称包含非法字符!\n非法字符包括: / \\ : * ? \" < > |")
                logger.warning(f"文件名称包含非法字符: {file_name}")
                return

            # 构造新文件路径
            new_file_path = os.path.join(parent_path, file_name)

            # 检查文件是否已存在
            if os.path.exists(new_file_path):
                QMessageBox.warning(self, "警告", f"文件 '{file_name}' 已存在!")
                logger.warning(f"文件已存在: {new_file_path}")
                return

            try:
                # 创建新文件
                with open(new_file_path, 'w', encoding='utf-8') as f:
                    # 可以根据文件扩展名添加默认内容
                    _, ext = os.path.splitext(file_name)
                    if ext.lower() in ['.txt', '.md']:
                        f.write("")
                    elif ext.lower() in ['.py']:
                        f.write("# -*- coding: utf-8 -*-\n\n")
                    elif ext.lower() in ['.json']:
                        f.write("{}\n")
                    elif ext.lower() in ['.xml']:
                        f.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
                    else:
                        f.write("")

                logger.info(f"创建新文件: {new_file_path}")

                # 刷新视图并保持展开状态
                self.refresh_view_keep_expanded()

                # 选中并预览新创建的文件
                self._select_and_preview_file(new_file_path)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建文件失败: {str(e)}")
                logger.error(f"创建文件失败: {str(e)}", exc_info=True)
        except Exception as e:
            logger.error(f"创建新文件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"创建新文件时发生异常: {str(e)}")

    def upload_files(self, local_path):
        """
        上传文件到远程服务器

        Args:
            local_path (str): 本地文件或目录路径
        """
        try:
            # 导入必要的模块
            from src.remote_server.server_config import ServerConfigManager
            from src.remote_server.file_transfer_dialog import FileTransferDialog, RemoteBrowserDialog

            # 创建服务器配置管理器
            server_manager = ServerConfigManager()
            server_configs = server_manager.get_server_configs()

            # 检查是否有配置的服务器
            if not server_configs:
                QMessageBox.warning(self, "警告", "请先配置远程服务器!")
                logger.warning("尝试上传文件但没有配置的服务器")
                return

            # 让用户选择服务器(无论有几个服务器配置)
            selected_server = None
            if len(server_configs) == 1:
                # 只有一个服务器配置，直接使用但仍然显示选择
                selected_server = server_configs[0]
            else:
                # 有多个服务器配置，让用户选择
                from PyQt6.QtWidgets import QInputDialog
                server_names = [sc.name for sc in server_configs]
                selected_name, ok = QInputDialog.getItem(
                    self, "选择服务器", "请选择要上传到的服务器:", server_names, 0, False
                )

                if ok and selected_name:
                    # 查找选中的服务器配置
                    for sc in server_configs:
                        if sc.name == selected_name:
                            selected_server = sc
                            break

            # 如果选择了服务器，继续上传流程
            if selected_server:
                # 浏览远程目录以选择上传路径
                remote_dialog = RemoteBrowserDialog(selected_server, self)
                if remote_dialog.exec() == QDialog.DialogCode.Accepted:
                    remote_path = remote_dialog.get_selected_path()
                    # 创建文件传输对话框
                    dialog = FileTransferDialog(selected_server, "upload", self)
                    # 设置远程路径
                    dialog.remote_path_edit.setText(remote_path)
                    # 添加要上传的文件或目录
                    if os.path.isfile(local_path) or os.path.isdir(local_path):
                        dialog.add_transfer_items([local_path])
                    else:
                        QMessageBox.warning(self, "警告", "选择的路径既不是文件也不是目录!")
                        return
                    dialog.exec()

            logger.info(f"上传文件: {local_path}")
        except Exception as e:
            logger.error(f"上传文件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"上传文件时发生异常: {str(e)}")

    def keyPressEvent(self, a0):
        """
        处理键盘按键事件

        Args:
            a0: 键盘事件
        """
        try:
            # 检查是否是Delete键
            if a0 and a0.key() == Qt.Key.Key_Delete:
                # 调用删除方法
                self.delete_selected_file()
                return

            # 检查是否是回车键
            elif a0 and a0.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                # 如果有确认对话框打开，则模拟点击"是"按钮
                focused_widget = self.focusWidget()
                if isinstance(focused_widget, QMessageBox):
                    yes_button = focused_widget.button(QMessageBox.StandardButton.Yes)
                    if yes_button and yes_button.isEnabled():
                        yes_button.click()
                        return

            # 检查是否是ESC键
            elif a0 and a0.key() == Qt.Key.Key_Escape:
                # 如果有确认对话框打开，则模拟点击"否"按钮
                focused_widget = self.focusWidget()
                if isinstance(focused_widget, QMessageBox):
                    no_button = focused_widget.button(QMessageBox.StandardButton.No)
                    if no_button and no_button.isEnabled():
                        no_button.click()
                        return

            # 调用父类的处理方法
            super().keyPressEvent(a0)
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

    def get_supported_files_list(self):
        """
        获取所有支持预览的文件列表，按照文件树中的显示顺序

        Returns:
            list: 支持预览的文件路径列表
        """
        try:
            if not self.ui or not self.ui.model or not self.ui.proxy_model or not self.ui.tree_view:
                return []

            supported_files = []

            # 从树视图的根索引开始遍历
            root_index = self.ui.tree_view.rootIndex()
            self._collect_supported_files_recursive(self.ui.proxy_model, self.ui.model, root_index, supported_files)

            return supported_files
        except Exception as e:
            logger.error(f"获取支持的文件列表时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return []

    def _collect_supported_files_recursive(self, proxy_model, source_model, proxy_index, supported_files):
        """
        递归收集支持预览的文件

        Args:
            proxy_model: 代理模型
            source_model: 源文件系统模型
            proxy_index: 当前代理索引
            supported_files: 支持的文件列表
        """
        try:
            # 如果索引无效，获取根索引下的所有子项
            if not proxy_index.isValid():
                # 遍历根索引下的所有行
                row_count = proxy_model.rowCount()
                for row in range(row_count):
                    child_proxy_index = proxy_model.index(row, 0)
                    self._collect_supported_files_recursive(proxy_model, source_model, child_proxy_index, supported_files)
                return

            # 将代理索引映射到源索引
            source_index = proxy_model.mapToSource(proxy_index)
            if not source_index.isValid():
                return

            # 获取文件路径
            file_path = source_model.filePath(source_index)

            # 检查是否是文件且支持预览
            if os.path.isfile(file_path) and self.is_supported_file(file_path):
                supported_files.append(file_path)

            # 递归处理子项
            rows = proxy_model.rowCount(proxy_index)
            for row in range(rows):
                child_index = proxy_model.index(row, 0, proxy_index)
                self._collect_supported_files_recursive(proxy_model, source_model, child_index, supported_files)
        except Exception as e:
            logger.error(f"递归收集支持的文件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def get_current_file_position_info(self, file_path):
        """
        获取当前文件在文件列表中的位置信息

        Args:
            file_path (str): 当前文件路径

        Returns:
            dict: 包含current_position和total_files的字典
        """
        try:
            # 获取所有支持预览的文件列表
            supported_files = self.get_supported_files_list()

            # 查找当前文件在列表中的位置
            try:
                current_position = supported_files.index(file_path) + 1  # 位置从1开始计数
            except ValueError:
                current_position = -1

            return {
                'current_position': current_position,
                'total_files': len(supported_files)
            }
        except Exception as e:
            logger.error(f"获取当前文件位置信息时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return {
                'current_position': -1,
                'total_files': 0
            }

    def get_current_selected_file(self):
        """
        获取当前选中的文件路径

        Returns:
            str: 当前选中的文件路径，如果没有选中则返回None
        """
        try:
            if not self.ui or not self.ui.tree_view or not self.ui.model or not self.ui.proxy_model:
                return None

            # 获取当前选中的索引
            current_index = self.ui.tree_view.currentIndex()
            if not current_index.isValid():
                return None

            # 将代理索引映射到源索引
            source_index = self.ui.proxy_model.mapToSource(current_index)
            if not source_index.isValid():
                return None

            # 获取文件路径
            file_path = self.ui.model.filePath(source_index)

            # 检查是否是文件且支持预览
            if os.path.isfile(file_path) and self.is_supported_file(file_path):
                return file_path

            return None
        except Exception as e:
            logger.error(f"获取当前选中文件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return None

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
                # Bug修复：检查是否重命名的是已导入的根路径
                is_imported_root = file_path in self.imported_root_paths

                # 执行重命名操作
                os.rename(file_path, new_path)
                logger.info(f"重命名: {file_path} -> {new_path}")

                # Bug修复：如果重命名的是已导入的根路径，需要同步更新导入路径列表和持久化存储
                if is_imported_root:
                    # 从持久化存储中移除旧路径
                    self.ui.remove_imported_path(file_path)
                    # 从导入路径列表中移除旧路径
                    if file_path in self.imported_root_paths:
                        self.imported_root_paths.remove(file_path)

                    # 添加新路径到导入列表
                    self.imported_root_paths.append(new_path)
                    # 保存新路径到持久化存储
                    self.ui.save_imported_path(new_path)

                    logger.info(f"已导入根路径重命名同步完成: {file_path} -> {new_path}")

                # 刷新视图并保持展开状态
                self.refresh_view_keep_expanded()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"重命名失败: {str(e)}")
                logger.error(f"重命名失败: {str(e)}", exc_info=True)
        except Exception as e:
            logger.error(f"重命名文件或文件夹时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"重命名文件或文件夹时发生异常: {str(e)}")

    def algorithm_test(self, file_path):
        """
        问题2修复：算法测试功能，关闭后保持展开状态

        Args:
            file_path (str): 要测试的文件路径
        """
        try:
            # 导入算法测试面板
            from src.preview.algorithm_test_panel import AlgorithmTestPanel

            # 创建算法测试对话框
            self.algorithm_test_dialog = AlgorithmTestPanel(file_path)

            # 连接信号(但不直接连接到文件管理器的选择方法，避免影响主预览面板)
            # 而是连接到专门处理算法测试面板内部切换的方法
            self.algorithm_test_dialog.switch_to_previous.connect(self.on_algorithm_test_prev)
            self.algorithm_test_dialog.switch_to_next.connect(self.on_algorithm_test_next)

            # 显示对话框
            self.algorithm_test_dialog.exec()

            # 问题2修复：对话框关闭后保持展开状态(只刷新不改变展开)
            # 注意：这里不需要刷新，因为算法测试只是预览，不会修改文件系统

            logger.info(f"算法测试完成: {file_path}")
        except Exception as e:
            logger.error(f"算法测试时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"算法测试时发生异常: {str(e)}")

    def on_algorithm_test_prev(self):
        """
        处理算法测试面板的上一张请求
        """
        # 发射信号通知主窗口切换到上一张资源，但不直接操作文件管理器的选择
        # 这样可以避免影响主预览面板
        if hasattr(self, 'algorithm_test_dialog') and self.algorithm_test_dialog:
            # 获取当前文件所在目录的文件列表
            current_dir = os.path.dirname(self.algorithm_test_dialog.current_file_path)
            if os.path.exists(current_dir):
                # 获取支持的文件列表
                files = []
                for f in os.listdir(current_dir):
                    file_path = os.path.join(current_dir, f)
                    if os.path.isfile(file_path) and self.is_supported_file(file_path):
                        files.append(file_path)

                # 排序文件列表
                files.sort()

                # 找到当前文件的索引
                try:
                    current_index = files.index(self.algorithm_test_dialog.current_file_path)
                    # 切换到上一个文件
                    if current_index > 0:
                        prev_file = files[current_index - 1]
                        self.algorithm_test_dialog.set_current_file(prev_file)
                except ValueError:
                    # 当前文件不在列表中
                    pass

    def on_algorithm_test_next(self):
        """
        处理算法测试面板的下一张请求
        """
        # 发射信号通知主窗口切换到下一张资源，但不直接操作文件管理器的选择
        # 这样可以避免影响主预览面板
        if hasattr(self, 'algorithm_test_dialog') and self.algorithm_test_dialog:
            # 获取当前文件所在目录的文件列表
            current_dir = os.path.dirname(self.algorithm_test_dialog.current_file_path)
            if os.path.exists(current_dir):
                # 获取支持的文件列表
                files = []
                for f in os.listdir(current_dir):
                    file_path = os.path.join(current_dir, f)
                    if os.path.isfile(file_path) and self.is_supported_file(file_path):
                        files.append(file_path)

                # 排序文件列表
                files.sort()

                # 找到当前文件的索引
                try:
                    current_index = files.index(self.algorithm_test_dialog.current_file_path)
                    # 切换到下一个文件
                    if current_index < len(files) - 1:
                        next_file = files[current_index + 1]
                        self.algorithm_test_dialog.set_current_file(next_file)
                except ValueError:
                    # 当前文件不在列表中
                    pass
