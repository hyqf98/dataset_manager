import os
import traceback

from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtWidgets import QMainWindow, QHBoxLayout, QWidget, QSplitter, QMessageBox, QApplication, QDialog

from ..file_manager.file_manager_panel import FileManagerPanel
from ..logging_config import logger
from ..preview.preview_panel import PreviewPanel


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

            # 创建中央部件和主布局
            central_widget = QWidget()
            self.setCentralWidget(central_widget)

            # 创建文件管理面板和预览面板
            self.file_manager_panel = FileManagerPanel()
            self.preview_panel = PreviewPanel()

            # 连接文件管理器和预览面板
            self.setup_connections()

            # 创建分割器实现两栏布局，调整比例为1:2
            splitter = QSplitter(Qt.Horizontal)

            # 添加面板到分割器
            splitter.addWidget(self.file_manager_panel)
            splitter.addWidget(self.preview_panel)

            # 设置各面板的初始大小比例为1:2
            # 通过设置合适的初始尺寸来实现比例分配
            total_width = window_width - 20  # 窗口宽度减去一些边距
            left_width = int(total_width * 0.10)    # 20%宽度给左侧文件管理面板
            right_width = int(total_width * 0.90)   # 80%宽度给右侧预览面板
            splitter.setSizes([left_width, right_width])

            # 创建主布局并添加分割器
            main_layout = QHBoxLayout(central_widget)
            main_layout.addWidget(splitter)
            central_widget.setLayout(main_layout)
        except Exception as e:
            logger.error(f"初始化主窗口UI时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            raise

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
        except Exception as e:
            logger.error(f"设置信号与槽连接时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            raise

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
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
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

    def on_annotations_updated(self, file_path, modified_annotation):
        """
        处理标注更新事件

        Args:
            file_path (str): 文件路径
            modified_annotation (Annotation): 被修改的标注对象
        """
        logger.debug(f"处理标注更新事件: {file_path}")
        # 可以在这里添加其他处理逻辑

    def on_annotation_selected_in_image(self, annotation):
        """
        处理图片上选中标注的事件

        Args:
            annotation: 被选中的标注对象(矩形或多边形)
        """
        logger.debug(f"处理图片上选中标注事件: {annotation}")
        # 可以在这里添加其他处理逻辑

    def eventFilter(self, obj, event):
        """
        事件过滤器，用于捕获全局按键事件

        Args:
            obj: 事件对象
            event: 事件

        Returns:
            bool: 是否处理了事件
        """
        try:
            # 检查是否是按键事件
            if event.type() == QEvent.KeyPress:
                key_event = event
                # 检查是否是回车键
                if key_event.key() in (Qt.Key_Return, Qt.Key_Enter):
                    # 查找当前活动的模态对话框
                    modal_widgets = QApplication.topLevelWidgets()
                    for widget in modal_widgets:
                        if isinstance(widget, (QMessageBox, QDialog)) and widget.isActiveWindow():
                            # 如果是确认对话框，点击"Yes"按钮
                            if hasattr(widget, 'button'):
                                yes_button = widget.button(QMessageBox.Yes)
                                if yes_button and yes_button.isEnabled():
                                    yes_button.click()
                                    return True
                            break

                # 检查是否是ESC键
                elif key_event.key() == Qt.Key_Escape:
                    # 查找当前活动的模态对话框
                    modal_widgets = QApplication.topLevelWidgets()
                    for widget in modal_widgets:
                        if isinstance(widget, (QMessageBox, QDialog)) and widget.isActiveWindow():
                            # 如果是确认对话框，点击"No"按钮或者关闭对话框
                            if hasattr(widget, 'button'):
                                no_button = widget.button(QMessageBox.No)
                                if no_button and no_button.isEnabled():
                                    no_button.click()
                                    return True
                            # 如果没有"No"按钮，关闭对话框
                            widget.close()
                            return True
                    return False

            return super().eventFilter(obj, event)
        except Exception as e:
            logger.error(f"事件过滤器处理时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")
            return False

    def showEvent(self, event):
        """
        窗口显示事件，安装事件过滤器

        Args:
            event: 显示事件
        """
        try:
            super().showEvent(event)
            # 安装事件过滤器来捕获全局按键事件
            QApplication.instance().installEventFilter(self)
        except Exception as e:
            logger.error(f"窗口显示事件处理时发生异常: {str(e)}")
            logger.error(f"异常详情:\n{traceback.format_exc()}")










