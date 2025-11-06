import os
import traceback

from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtWidgets import QMainWindow, QHBoxLayout, QWidget, QSplitter, QMessageBox, QApplication, QDialog, QMenuBar, QAction, QFileDialog, QMenu
from PyQt5.QtGui import QKeyEvent

from ..file_manager.file_manager_panel import FileManagerPanel
from ..logging_config import logger
from ..preview.preview_panel import PreviewPanel
from ..data_source.data_source_panel import DataSourcePanel
from ..preview.live_preview_panel import LivePreviewPanel
from ..auto_annotation.model_config_panel import ModelConfigPanel
from ..auto_annotation.auto_annotation_panel import AutoAnnotationPanel
from ..dataset_split.dataset_split_panel import DatasetSplitPanel
# 添加远程服务器相关导入
from ..remote_server.server_config_panel import ServerConfigPanel
from ..remote_server.file_transfer_dialog import FileTransferDialog
from ..remote_server.server_config import ServerConfigManager, ServerConfig

class MainWindow(QMainWindow):
    """
    主窗口类，负责创建应用程序的两栏布局
    左侧：文件管理面板（占1/3宽度）
    右侧：预览面板（占2/3宽度）
    """

    def __init__(self):
        """
        初始化主窗口
        """
        try:
            super().__init__()
            self.fullscreen_mode = False  # 添加全屏模式标志
            self.left_panel_visible = True  # 左侧面板可见性
            self.server_config_manager = ServerConfigManager()  # 服务器配置管理器
            self.init_ui()
            logger.info("主窗口初始化完成")
        except Exception as e:
            logger.error(f"主窗口初始化时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            raise

    def init_ui(self):
        """
        初始化用户界面
        """
        try:
            # 获取屏幕分辨率并设置窗口尺寸为屏幕的95%
            screen = QApplication.primaryScreen()
            window_width = 800  # 默认宽度
            window_height = 600  # 默认高度
            
            if screen:
                screen_geometry = screen.availableGeometry()
                screen_width = screen_geometry.width()
                screen_height = screen_geometry.height()

                window_width = int(screen_width * 0.95)
                window_height = int(screen_height * 0.95)

                # 设置窗口标题和尺寸，居中显示
                self.setWindowTitle('数据集管理器')
                self.setGeometry(
                    (screen_width - window_width) // 2,
                    (screen_height - window_height) // 2,
                    window_width,
                    window_height
                )

            # 创建菜单栏
            self.create_menu_bar()

            # 创建中央部件和主布局
            central_widget = QWidget()
            self.setCentralWidget(central_widget)

            # 计算面板尺寸
            total_width = window_width - 20  # 窗口宽度减去一些边距
            left_width = int(total_width * 0.20)    # 20%宽度给左侧文件管理面板
            right_width = int(total_width * 0.80)   # 80%宽度给右侧预览面板
            panel_height = window_height - 100

            # 创建文件管理面板和预览面板，通过构造函数传递尺寸参数
            self.file_manager_panel = FileManagerPanel(width=left_width, height=panel_height)
            self.preview_panel = PreviewPanel(width=right_width, height=panel_height)

            # 连接文件管理器和预览面板
            self.setup_connections()

            # 创建分割器实现两栏布局，调整比例为1:2
            splitter = QSplitter(Qt.Orientation.Horizontal)  # type: ignore

            # 添加面板到分割器
            splitter.addWidget(self.file_manager_panel)
            splitter.addWidget(self.preview_panel)

            # 设置各面板的初始大小比例为1:2
            # 通过设置合适的初始尺寸来实现比例分配
            splitter.setSizes([left_width, right_width])

            # 创建主布局并添加分割器
            main_layout = QHBoxLayout(central_widget)
            main_layout.addWidget(splitter)
            central_widget.setLayout(main_layout)
            
            # 保存分割器引用，以便后续控制
            self.splitter = splitter
        except Exception as e:
            logger.error(f"初始化主窗口UI时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            raise

    def resizeEvent(self, a0):  # type: ignore
        """
        处理窗口大小调整事件
        
        Args:
            a0: 窗口大小调整事件
        """
        try:
            # 获取当前窗口尺寸
            window_width = self.width()
            window_height = self.height()
            
            # 计算面板尺寸
            total_width = window_width - 20  # 窗口宽度减去一些边距
            left_width = int(total_width * 0.20)    # 20%宽度给左侧文件管理面板
            right_width = int(total_width * 0.80)   # 80%宽度给右侧预览面板
            panel_height = window_height - 100
            
            # 注意：由于我们已经移除了set_panel_size方法，这里不再调用它
            # 面板尺寸在构造时已经设置，窗口大小变化时保持比例
            
            super().resizeEvent(a0)
        except Exception as e:
            logger.error(f"处理窗口大小调整事件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            super().resizeEvent(a0)

    def setup_connections(self):
        """
        设置各组件间的信号与槽连接
        """
        try:
            # 连接文件管理器的文件选中信号到预览面板
            self.file_manager_panel.events.file_selected.connect(self.on_file_selected)

            # 连接预览面板的文件删除信号到主窗口处理函数
            self.preview_panel.file_deleted.connect(self.on_preview_file_deleted)

            # 连接预览面板的资源切换信号到文件管理器
            self.preview_panel.switch_to_previous.connect(self.file_manager_panel.select_previous_file)
            self.preview_panel.switch_to_next.connect(self.file_manager_panel.select_next_file)

            # 连接文件管理器的文件删除信号到预览面板清空
            self.file_manager_panel.events.file_deleted.connect(self.on_file_manager_file_deleted)
            
            # 连接预览面板的全屏模式切换信号
            self.preview_panel.toggle_fullscreen.connect(self.toggle_fullscreen_mode)
        except Exception as e:
            logger.error(f"设置信号与槽连接时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            raise

    def create_menu_bar(self):
        """
        创建菜单栏
        """
        try:
            menubar = self.menuBar()
            if menubar:
                # 数据源菜单
                data_source_menu = menubar.addMenu('数据源')
                if data_source_menu:
                    data_source_action = QAction('数据源管理', self)
                    data_source_action.triggered.connect(self.open_data_source_panel)
                    data_source_menu.addAction(data_source_action)

                # 自动标注菜单
                auto_annotation_menu = menubar.addMenu('自动标注')
                if auto_annotation_menu:
                    model_config_action = QAction('模型配置', self)
                    model_config_action.triggered.connect(self.open_model_config_panel)
                    auto_annotation_menu.addAction(model_config_action)
                    
                    auto_annotation_action = QAction('自动标注', self)
                    auto_annotation_action.triggered.connect(self.open_auto_annotation_panel)
                    auto_annotation_menu.addAction(auto_annotation_action)

                # 数据集划分菜单
                dataset_split_menu = menubar.addMenu('数据集划分')
                if dataset_split_menu:
                    dataset_split_action = QAction('数据集划分', self)
                    dataset_split_action.triggered.connect(self.open_dataset_split_panel)
                    dataset_split_menu.addAction(dataset_split_action)

                # 文件上传菜单
                file_upload_menu = menubar.addMenu('文件上传')
                if file_upload_menu:
                    server_management_action = QAction('服务器管理', self)
                    server_management_action.triggered.connect(self.open_server_config_panel)
                    file_upload_menu.addAction(server_management_action)
                    # 移除上传和下载菜单项

                # 视图菜单
                view_menu = menubar.addMenu('视图')
                if view_menu:
                    fullscreen_action = QAction('全屏模式', self)
                    fullscreen_action.setShortcut('F11')
                    fullscreen_action.triggered.connect(self.toggle_fullscreen_mode)
                    view_menu.addAction(fullscreen_action)
        except Exception as e:
            logger.error(f"创建菜单栏时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            raise

    def toggle_fullscreen_mode(self):
        """
        切换全屏模式
        """
        self.fullscreen_mode = not self.fullscreen_mode
        
        if self.fullscreen_mode:
            # 进入全屏模式
            self.left_panel_visible = self.file_manager_panel.isVisible()
            self.file_manager_panel.setVisible(False)
            self.preview_panel.set_fullscreen(True)
            # 进入全屏模式
            self.showFullScreen()
        else:
            # 退出全屏模式
            self.file_manager_panel.setVisible(self.left_panel_visible)
            self.preview_panel.set_fullscreen(False)
            # 退出全屏模式
            self.showNormal()

    def on_file_selected(self, file_path):
        """
        处理文件选中事件

        Args:
            file_path (str): 选中的文件路径
        """
        try:
            if file_path and os.path.exists(file_path):
                self.preview_panel.preview_file(file_path)
                logger.debug(f"处理文件选中事件: {file_path}")
        except Exception as e:
            logger.error(f"处理文件选中事件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def on_preview_file_deleted(self, file_path):
        """
        处理预览面板中删除文件的事件

        Args:
            file_path (str): 要删除的文件路径
        """
        try:
            # 确认操作
            reply = QMessageBox.question(self, "确认", f"确定要删除 '{file_path}' 吗?\n(文件将被移动到回收站)",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)  # type: ignore
            if reply == QMessageBox.StandardButton.Yes:
                # 执行删除操作
                self.file_manager_panel.move_to_recycle_bin(file_path)
                logger.info(f"删除文件: {file_path}")
        except Exception as e:
            logger.error(f"处理预览面板文件删除事件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"处理文件删除事件时发生异常: {str(e)}")

    def on_file_manager_file_deleted(self, file_path):
        """
        处理文件管理器中删除文件的事件，清空预览面板

        Args:
            file_path (str): 已删除的文件路径
        """
        try:
            # 清空预览面板
            try:
                self.preview_panel.show_message("请选择文件进行预览")
            except RuntimeError as e:
                logger.error(f"预览面板已被删除: {str(e)}")
            logger.debug("清空预览面板")
        except Exception as e:
            logger.error(f"处理文件管理器文件删除事件时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")

    def open_data_source_panel(self):
        """
        打开数据源管理面板
        """
        try:
            # 每次都创建新的实例，避免使用已销毁的对象
            self.data_source_panel = DataSourcePanel()
            # 连接播放信号
            self.data_source_panel.play_requested.connect(self.play_live_stream)
            
            # 创建对话框并显示面板
            dialog = QDialog(self)
            dialog.setWindowTitle("数据源管理")
            layout = QHBoxLayout(dialog)
            layout.addWidget(self.data_source_panel)
            dialog.resize(800, 600)
            # 设置对话框的父引用，以便在播放时可以关闭
            self.data_source_panel.dialog_parent = dialog  # type: ignore
            dialog.exec()
            
            # 断开信号连接并清理引用，避免访问已销毁的对象
            try:
                self.data_source_panel.play_requested.disconnect(self.play_live_stream)
            except (TypeError, RuntimeError):
                # 如果信号未连接或对象已销毁，则忽略错误
                pass
            if hasattr(self, 'data_source_panel'):
                delattr(self, 'data_source_panel')
        except Exception as e:
            logger.error(f"打开数据源管理面板时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"打开数据源管理面板时发生异常: {str(e)}")

    def play_live_stream(self, data_source):
        """
        播放直播流
        """
        try:
            # 创建直播预览面板
            live_preview_panel = LivePreviewPanel(data_source)

            # 连接信号
            live_preview_panel.switch_to_previous.connect(self.preview_panel.switch_to_previous_resource)
            live_preview_panel.switch_to_next.connect(self.preview_panel.switch_to_next_resource)

            # 在预览面板中显示直播预览面板
            self.preview_panel.scroll_area.setWidget(live_preview_panel)
            self.preview_panel.current_preview_panel = live_preview_panel

            # 设置焦点到预览面板，确保能接收键盘事件
            live_preview_panel.setFocus()

            logger.info(f"播放直播流: {data_source.stream_url}")
        except Exception as e:
            logger.error(f"播放直播流时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"播放直播流时发生异常: {str(e)}")

    def open_model_config_panel(self):
        """
        打开模型配置面板
        """
        try:
            # 每次都创建新的实例，避免使用已销毁的对象
            self.model_config_panel = ModelConfigPanel()
            
            # 创建对话框并显示面板
            dialog = QDialog(self)
            dialog.setWindowTitle("模型配置")
            layout = QHBoxLayout(dialog)
            layout.addWidget(self.model_config_panel)
            dialog.resize(800, 600)
            dialog.exec()
            
            # 清理引用，避免访问已销毁的对象
            if hasattr(self, 'model_config_panel'):
                delattr(self, 'model_config_panel')
        except Exception as e:
            logger.error(f"打开模型配置面板时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"打开模型配置面板时发生异常: {str(e)}")

    def open_auto_annotation_panel(self):
        """
        打开自动标注面板
        """
        try:
            # 每次都创建新的实例，避免使用已销毁的对象
            self.auto_annotation_panel = AutoAnnotationPanel()
            
            # 创建对话框并显示面板
            dialog = QDialog(self)
            dialog.setWindowTitle("自动标注")
            layout = QHBoxLayout(dialog)
            layout.addWidget(self.auto_annotation_panel)
            dialog.resize(800, 600)
            dialog.exec()
            
            # 清理引用，避免访问已销毁的对象
            if hasattr(self, 'auto_annotation_panel'):
                delattr(self, 'auto_annotation_panel')
        except Exception as e:
            logger.error(f"打开自动标注面板时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"打开自动标注面板时发生异常: {str(e)}")

    def open_dataset_split_panel(self):
        """
        打开数据集划分面板
        """
        try:
            # 每次都创建新的实例，避免使用已销毁的对象
            self.dataset_split_panel = DatasetSplitPanel()
            
            # 创建对话框并显示面板
            dialog = QDialog(self)
            dialog.setWindowTitle("数据集划分")
            layout = QHBoxLayout(dialog)
            layout.addWidget(self.dataset_split_panel)
            dialog.resize(600, 400)
            dialog.exec()
            
            # 清理引用，避免访问已销毁的对象
            if hasattr(self, 'dataset_split_panel'):
                delattr(self, 'dataset_split_panel')
        except Exception as e:
            logger.error(f"打开数据集划分面板时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"打开数据集划分面板时发生异常: {str(e)}")

    def open_server_config_panel(self):
        """
        打开服务器配置面板
        """
        try:
            # 每次都创建新的实例，避免使用已销毁的对象
            self.server_config_panel = ServerConfigPanel()
            
            # 创建对话框并显示面板
            dialog = QDialog(self)
            dialog.setWindowTitle("服务器管理")
            layout = QHBoxLayout(dialog)
            layout.addWidget(self.server_config_panel)
            dialog.resize(800, 600)
            dialog.exec()
            
            # 清理引用，避免访问已销毁的对象
            if hasattr(self, 'server_config_panel'):
                delattr(self, 'server_config_panel')
        except Exception as e:
            logger.error(f"打开服务器配置面板时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            QMessageBox.critical(self, "错误", f"打开服务器配置面板时发生异常: {str(e)}")

    def eventFilter(self, a0, a1):  # type: ignore
        """
        事件过滤器，用于捕获全局按键事件

        Args:
            a0: 事件对象
            a1: 事件

        Returns:
            bool: 是否处理了事件
        """
        try:
            # 检查是否是按键事件
            if a1 and a1.type() == QEvent.Type.KeyPress:
                key_event = a1
                # 检查是否是回车键
                if isinstance(key_event, QKeyEvent) and key_event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    # 查找当前活动的模态对话框
                    modal_widgets = QApplication.topLevelWidgets()
                    for widget in modal_widgets:
                        if isinstance(widget, (QMessageBox, QDialog)) and widget.isActiveWindow():
                            # 如果是确认对话框，点击"Yes"按钮
                            if hasattr(widget, 'button'):
                                yes_button = widget.button(QMessageBox.StandardButton.Yes)
                                if yes_button and yes_button.isEnabled():
                                    yes_button.click()
                                    return True
                            break

                # 检查是否是ESC键
                elif isinstance(key_event, QKeyEvent) and key_event.key() == Qt.Key.Key_Escape:
                    # 查找当前活动的模态对话框
                    modal_widgets = QApplication.topLevelWidgets()
                    for widget in modal_widgets:
                        if isinstance(widget, (QMessageBox, QDialog)) and widget.isActiveWindow():
                            # 如果是确认对话框，点击"No"按钮或者关闭对话框
                            if hasattr(widget, 'button'):
                                no_button = widget.button(QMessageBox.StandardButton.No)
                                if no_button and no_button.isEnabled():
                                    no_button.click()
                                    return True
                            # 如果没有"No"按钮，关闭对话框
                            widget.close()
                            return True
                    return False

            # 检查是否是ESC键且处于全屏模式
            elif a1 and a1.type() == QEvent.Type.KeyPress:
                key_event = a1
                if isinstance(key_event, QKeyEvent) and key_event.key() == Qt.Key.Key_Escape and self.fullscreen_mode:
                    self.toggle_fullscreen_mode()
                    return True
            
            return super().eventFilter(a0, a1)
        except Exception as e:
            logger.error(f"事件过滤器处理时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return False

    def showEvent(self, a0):  # type: ignore
        """
        窗口显示事件，安装事件过滤器

        Args:
            a0: 显示事件
        """
        try:
            super().showEvent(a0)
            # 安装事件过滤器来捕获全局按键事件
            app_instance = QApplication.instance()
            if app_instance:
                app_instance.installEventFilter(self)
        except Exception as e:
            logger.error(f"窗口显示事件处理时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
