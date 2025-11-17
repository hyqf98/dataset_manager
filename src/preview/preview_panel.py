import os
import traceback
from typing import Optional

from PyQt6 import sip
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea

from src.preview.image_preview_panel import ImagePreviewPanel
from src.preview.video_preview_panel import VideoPreviewPanel
from src.preview.text_preview_panel import TextPreviewPanel
from ..logging_config import logger


class PreviewPanel(QWidget):
    """
    预览面板类，用于显示选中文件的内容
    """

    # 定义删除文件信号
    file_deleted = pyqtSignal(str)  # 文件路径
    # 定义资源切换信号
    switch_to_previous = pyqtSignal()
    switch_to_next = pyqtSignal()
    # 定义全屏模式切换信号
    toggle_fullscreen = pyqtSignal()

    def __init__(self, width=None, height=None):
        """
        初始化预览面板

        Args:
            width (int, optional): 面板宽度
            height (int, optional): 面板高度
        """
        super().__init__()
        # 存储尺寸参数作为内部属性
        self.panel_width = width
        self.panel_height = height

        self.init_ui()
        self.current_file_path = None  # 保存当前文件路径
        self.current_preview_panel = None  # 当前预览面板
        self.content_label = None  # 内容显示标签
        self.is_fullscreen = False  # 全屏模式标志

        # 支持的图片格式
        self.supported_image_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
        # 支持的视频格式
        self.supported_video_formats = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv']
        # 支持的文本格式
        self.supported_text_formats = ['.txt', '.json', '.xml', '.py', '.yaml', '.yml']

        # 预览面板缓存，提高切换性能
        self.panel_cache = {}  # 格式: {file_path: preview_panel}
        self.max_cache_size = 5  # 最大缓存5个面板

        # 设置焦点策略，确保能接收键盘事件
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def init_ui(self):
        """
        初始化预览面板的用户界面
        """
        layout = QVBoxLayout(self)

        # 创建滚动区域用于显示内容
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)  # 设置为True以适应内容
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 如果有尺寸参数，则设置滚动区域的尺寸
        if self.panel_width is not None and self.panel_height is not None:
            self.scroll_area.setMinimumWidth(self.panel_width)
            self.scroll_area.setMinimumHeight(self.panel_height)
            self.setMinimumWidth(self.panel_width)
            self.setMinimumHeight(self.panel_height)

        layout.addWidget(self.scroll_area)
        self.setLayout(layout)

    def set_fullscreen(self, fullscreen):
        """
        设置全屏模式

        Args:
            fullscreen (bool): 是否进入全屏模式
        """
        self.is_fullscreen = fullscreen
        # 将全屏模式状态传递给当前预览面板(如果有)
        if self.current_preview_panel:
            if hasattr(self.current_preview_panel, 'set_fullscreen'):
                self.current_preview_panel.set_fullscreen(fullscreen)

            # 如果是图片预览面板，在全屏模式下触发一次图片大小的缩放操作
            if fullscreen and isinstance(self.current_preview_panel, ImagePreviewPanel):
                # 触发图片重新适应视图大小
                self.current_preview_panel.image_label.fit_image_to_view()

    def preview_file(self, file_path):
        """
        根据文件类型预览文件

        Args:
            file_path (str): 文件路径
        """
        if not os.path.exists(file_path):
            self.show_message("文件不存在")
            return

        # 保存当前文件路径
        self.current_file_path = file_path

        # 根据文件扩展名选择合适的预览方式
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        # 如果是支持的图片格式，则显示图片预览面板
        if ext in self.supported_image_formats:
            self.show_image_preview(file_path)
        # 如果是支持的视频格式，则显示视频预览面板
        elif ext in self.supported_video_formats:
            self.show_video_preview(file_path)
        # 如果是支持的文本格式，则显示文本预览面板
        elif ext in self.supported_text_formats:
            self.show_text_preview(file_path)
        else:
            self.show_message("不支持的文件格式")

    def show_message(self, message):
        """
        在内容区域显示消息

        Args:
            message (str): 要显示的消息
        """

        # 确保使用正确的显示标签
        if self.scroll_area.widget() != self.content_label:
            # 清理当前控件
            old_widget = self.scroll_area.takeWidget()
            if old_widget and not sip.isdeleted(old_widget):
                old_widget.setParent(None)
                old_widget.deleteLater()
            # 确保content_label对象仍然有效
            if self.content_label is None or sip.isdeleted(self.content_label):
                self.content_label = QLabel()
                self.content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.content_label.setWordWrap(True)
            self.scroll_area.setWidget(self.content_label)

        # 确保content_label对象仍然有效
        if self.content_label is None or sip.isdeleted(self.content_label):
            self.content_label = QLabel()
            self.content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_label.setWordWrap(True)

        self.content_label.setText(message)
        self.content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def show_image_preview(self, file_path):
        """
        显示图片预览

        Args:
            file_path (str): 图片文件路径
        """
        # 清理缓存中已删除的对象
        self.cleanup_cache()
        
        # 检查缓存中是否存在该面板且未被删除
        image_preview_panel = None
        if file_path in self.panel_cache:
            cached_panel = self.panel_cache[file_path]
            # 检查面板是否仍然有效
            if cached_panel and not sip.isdeleted(cached_panel):
                image_preview_panel = cached_panel
                # 如果处于全屏模式，通知图片预览面板
                if self.is_fullscreen:
                    image_preview_panel.set_fullscreen(True)
                    image_preview_panel.image_label.fit_image_to_view()
            else:
                # 从缓存中移除已删除的面板
                self.panel_cache.pop(file_path, None)

        if image_preview_panel is None:
            # 获取当前预览面板的尺寸
            width = self.width()
            height = self.height()

            # 创建新的图片预览面板，传递尺寸参数
            image_preview_panel = ImagePreviewPanel(width=width, height=height)

            # 显示图片
            image_preview_panel.show_image_with_annotation(file_path)

            # 如果处于全屏模式，通知图片预览面板
            if self.is_fullscreen:
                image_preview_panel.set_fullscreen(True)
                # 立即触发图片尺寸调整以适应全屏
                image_preview_panel.image_label.fit_image_to_view()

            # 添加到缓存
            self._add_to_cache(file_path, image_preview_panel)

        # 替换显示内容为图片预览面板
        self.scroll_area.setWidget(image_preview_panel)
        self.current_preview_panel = image_preview_panel

        # 设置焦点到预览面板，确保能接收键盘事件
        image_preview_panel.setFocus()

        return True

    def show_video_preview(self, file_path):
        """
        显示视频预览

        Args:
            file_path (str): 视频文件路径
        """
        # 创建新的视频预览面板
        video_preview_panel = VideoPreviewPanel()

        # 设置视频媒体文件
        video_preview_panel.set_media(file_path)

        # 连接信号
        video_preview_panel.switch_to_previous.connect(self.switch_to_previous_resource)
        video_preview_panel.switch_to_next.connect(self.switch_to_next_resource)

        # 如果处于全屏模式，通知视频预览面板
        if self.is_fullscreen:
            video_preview_panel.set_fullscreen(True)

        # 替换显示内容为视频预览面板
        self.scroll_area.setWidget(video_preview_panel)
        self.current_preview_panel = video_preview_panel

        # 设置焦点到预览面板，确保能接收键盘事件
        video_preview_panel.setFocus()

    def show_text_preview(self, file_path):
        """
        显示文本预览

        Args:
            file_path (str): 文本文件路径
        """
        # 创建新的文本预览面板
        text_preview_panel = TextPreviewPanel()

        # 加载文本文件
        text_preview_panel.load_text_file(file_path)

        # 连接文件保存信号
        text_preview_panel.file_saved.connect(self.on_text_file_saved)

        # 替换显示内容为文本预览面板
        self.scroll_area.setWidget(text_preview_panel)
        self.current_preview_panel = text_preview_panel

        # 设置焦点到预览面板，确保能接收键盘事件
        text_preview_panel.setFocus()

        return True

    def on_text_file_saved(self, file_path):
        """
        处理文本文件保存事件

        Args:
            file_path (str): 保存的文件路径
        """
        # 可以在这里添加保存后的处理逻辑
        pass

    def wheelEvent(self, a0: Optional[QWheelEvent]):
        """
        处理鼠标滚轮事件

        Args:
            a0 (Optional[QWheelEvent]): 滚轮事件
        """
        if self.scroll_area:
            # 调用滚动区域的滚轮事件处理
            self.scroll_area.wheelEvent(a0)
        else:
            super().wheelEvent(a0)

    def keyPressEvent(self, a0):
        """
        处理键盘按键事件

        Args:
            a0: 键盘事件
        """
        if not a0:
            super().keyPressEvent(a0)
            return
            
        # 处理Delete键删除当前预览的图片
        if a0.key() == Qt.Key.Key_Delete:
            self.delete_current_image()
        # 处理A/D键切换前后资源
        elif a0.key() == Qt.Key.Key_A:
            self.switch_to_previous_resource()
        elif a0.key() == Qt.Key.Key_D:
            self.switch_to_next_resource()
        # 处理F11键切换全屏模式
        elif a0.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen.emit()
        # 处理ESC键退出全屏模式
        elif a0.key() == Qt.Key.Key_Escape and self.is_fullscreen:
            self.toggle_fullscreen.emit()
        # 处理W/Q键的标注模式(转发给当前预览面板)
        elif a0.key() in [Qt.Key.Key_W, Qt.Key.Key_Q]:
            # 如果当前有预览面板且是图片预览面板，则转发按键事件
            if (self.current_preview_panel and
                isinstance(self.current_preview_panel, ImagePreviewPanel)):
                self.current_preview_panel.keyPressEvent(a0)
            else:
                super().keyPressEvent(a0)
        else:
            super().keyPressEvent(a0)

    def delete_current_image(self):
        """
        删除当前预览的图片
        """
        # 发出删除文件信号，让主窗口处理实际的删除操作
        if self.current_file_path:
            self.file_deleted.emit(self.current_file_path)

    def switch_to_previous_resource(self):
        """
        切换到前一个资源
        """
        # 发出切换到前一个资源的信号
        self.switch_to_previous.emit()

    def switch_to_next_resource(self):
        """
        切换到后一个资源
        """
        # 发出切换到后一个资源的信号
        self.switch_to_next.emit()

    def _add_to_cache(self, file_path, panel):
        """
        添加面板到缓存，超过最大缓存数时移除最旧的
        
        Args:
            file_path (str): 文件路径
            panel: 预览面板实例
        """
        # 如果缓存已满，移除最旧的项
        if len(self.panel_cache) >= self.max_cache_size:
            # 移除第一个项（最旧的）
            oldest_key = next(iter(self.panel_cache))
            old_panel = self.panel_cache.pop(oldest_key)
            # 清理旧面板
            if old_panel and not sip.isdeleted(old_panel):
                old_panel.setParent(None)
                old_panel.deleteLater()
        
        self.panel_cache[file_path] = panel

    def clear_cache(self):
        """
        清除所有缓存的预览面板
        """
        for panel in self.panel_cache.values():
            if panel and not sip.isdeleted(panel):
                panel.setParent(None)
                panel.deleteLater()
        self.panel_cache.clear()

    def cleanup_cache(self):
        """
        清理缓存中已删除的对象
        """
        # 创建一个新的字典，只包含有效的面板
        valid_cache = {}
        for file_path, panel in self.panel_cache.items():
            if panel and not sip.isdeleted(panel):
                valid_cache[file_path] = panel
        self.panel_cache = valid_cache

    def mousePressEvent(self, event):
        """
        处理鼠标点击事件，确保点击时获取焦点
        
        Args:
            event: 鼠标事件
        """
        super().mousePressEvent(event)
        # 确保点击后获取焦点
        self.setFocus()
        # 如果有当前预览面板，也给它设置焦点
        if self.current_preview_panel:
            self.current_preview_panel.setFocus()

    def showEvent(self, event):
        """
        处理显示事件，确保显示时获取焦点
        
        Args:
            event: 显示事件
        """
        super().showEvent(event)
        # 显示时主动获取焦点
        self.setFocus()
        if self.current_preview_panel:
            self.current_preview_panel.setFocus()
