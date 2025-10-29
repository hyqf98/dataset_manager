from abc import ABC, abstractmethod
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QSizePolicy
from ..logging_config import logger
import os
import sip


class PreviewStrategy(ABC):
    """
    预览策略抽象基类
    定义了所有预览策略必须实现的接口
    """

    @abstractmethod
    def preview(self, file_path, preview_panel):
        """
        预览文件的抽象方法

        Args:
            file_path (str): 文件路径
            preview_panel: 预览面板实例
        """
        pass

    @abstractmethod
    def supported_formats(self):
        """
        返回该策略支持的文件格式列表

        Returns:
            list: 支持的文件扩展名列表
        """
        pass


class ImagePreviewStrategy(PreviewStrategy):
    """
    图片预览策略类
    """

    def preview(self, file_path, preview_panel):
        """
        预览图片文件，确保原始分辨率显示

        Args:
            file_path (str): 图片文件路径
            preview_panel: 预览面板实例
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                preview_panel.show_message(f"文件不存在: {file_path}")
                logger.warning(f"尝试预览不存在的图片文件: {file_path}")
                return False

            # 使用带标注功能的图片显示方式
            result = preview_panel.show_image_with_annotation(file_path)

            # 更新预览面板的标题或状态栏信息，而不是覆盖图片显示
            logger.info(f"图片已加载: {os.path.basename(file_path)}")
            return result
        except Exception as e:
            # 确保preview_panel对象仍然有效
            try:
                preview_panel.show_message(f"加载图片出错: {str(e)}")
            except RuntimeError as re:
                logger.error(f"预览面板已被删除: {str(re)}")
            logger.error(f"加载图片出错: {str(e)}", exc_info=True)
            return False

    def supported_formats(self):
        """
        返回支持的图片格式列表

        Returns:
            list: 支持的图片文件扩展名列表
        """
        return ['.jpg', '.jpeg', '.png', '.bmp', '.gif']


class VideoPreviewStrategy(PreviewStrategy):
    """
    视频预览策略类
    """

    def preview(self, file_path, preview_panel):
        """
        预览视频文件
        
        Args:
            file_path (str): 视频文件路径
            preview_panel: 预览面板实例
        """
        try:
            # 创建视频播放器
            from ..preview.player import VideoPlayer
            
            # 如果当前显示的不是content_label，则先移除当前控件
            if preview_panel.scroll_area.widget() != preview_panel.content_label:
                # 确保正确清理之前的控件，但不要删除image_label
                old_widget = preview_panel.scroll_area.takeWidget()
                if old_widget and not sip.isdeleted(old_widget) and old_widget != preview_panel.image_label:
                    old_widget.setParent(None)
                    old_widget.deleteLater()
                
            # 创建新的视频播放器实例
            video_player = VideoPlayer()
            # 设置父级关系确保正确显示
            video_player.setParent(preview_panel.scroll_area)
            video_player.set_media(file_path)
            
            # 设置视频播放器尺寸策略，确保填充整个滚动区域
            video_player.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            video_player.setMinimumSize(1, 1)
            
            # 连接资源切换信号
            video_player.switch_to_previous.connect(preview_panel.switch_to_previous_resource)
            video_player.switch_to_next.connect(preview_panel.switch_to_next_resource)
            
            # 替换显示内容为视频播放器
            preview_panel.scroll_area.setWidget(video_player)
            
            # 确保视频播放器能接收键盘事件
            video_player.setFocusPolicy(Qt.StrongFocus)
            video_player.setFocus()
            
            # 隐藏标注工具栏，视频不需要标注功能
            preview_panel.toolbar_widget.setVisible(False)
            # 隐藏图片预览的快捷键提示，避免重复显示
            preview_panel.shortcut_label.setVisible(False)
            logger.info(f"视频播放器已创建并设置媒体文件: {file_path}")
            return True
        except Exception as e:
            # 确保preview_panel对象仍然有效
            try:
                preview_panel.show_message(f"加载视频出错: {str(e)}")
            except RuntimeError as re:
                logger.error(f"预览面板已被删除: {str(re)}")
            logger.error(f"加载视频出错: {str(e)}", exc_info=True)
            return False

    def supported_formats(self):
        """
        返回支持的视频格式列表

        Returns:
            list: 支持的视频文件扩展名列表
        """
        return ['.mp4', '.avi', '.mov', '.wmv', '.flv']


class UnsupportedPreviewStrategy(PreviewStrategy):
    """
    不支持的文件格式预览策略类
    """

    def preview(self, file_path, preview_panel):
        """
        处理不支持的文件格式

        Args:
            file_path (str): 文件路径
            preview_panel: 预览面板实例
        """
        preview_panel.show_message("不支持的文件格式")
        logger.warning(f"不支持的文件格式: {file_path}")

        # 保持工具栏可见，不隐藏
        # preview_panel.toolbar_widget.setVisible(False)
        return False

    def supported_formats(self):
        """
        返回支持的文件格式列表（空）

        Returns:
            list: 空列表
        """
        return []








