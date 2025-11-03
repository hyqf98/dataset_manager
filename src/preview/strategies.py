from abc import ABC, abstractmethod
from ..logging_config import logger
import os


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
        预览图片文件，使用ImageLabel组件显示带标注功能的图片

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


class TextPreviewStrategy(PreviewStrategy):
    """
    文本预览策略类
    """

    def preview(self, file_path, preview_panel):
        """
        预览文本文件

        Args:
            file_path (str): 文本文件路径
            preview_panel: 预览面板实例
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                preview_panel.show_message(f"文件不存在: {file_path}")
                logger.warning(f"尝试预览不存在的文本文件: {file_path}")
                return False

            # 显示文本预览
            result = preview_panel.show_text_preview(file_path)

            logger.info(f"文本文件已加载: {os.path.basename(file_path)}")
            return result
        except Exception as e:
            preview_panel.show_message(f"加载文本文件出错: {str(e)}")
            logger.error(f"加载文本文件出错: {str(e)}", exc_info=True)
            return False

    def supported_formats(self):
        """
        返回支持的文本格式列表

        Returns:
            list: 支持的文本文件扩展名列表
        """
        return ['.txt', '.json', '.xml']


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
        return False

    def supported_formats(self):
        """
        返回支持的文件格式列表（空）

        Returns:
            list: 空列表
        """
        return []
