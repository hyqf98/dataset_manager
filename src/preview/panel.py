import sys

from PyQt5 import sip
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QMessageBox, QHBoxLayout, QPushButton, QButtonGroup
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QWheelEvent
from ..preview.strategies import ImagePreviewStrategy, VideoPreviewStrategy, UnsupportedPreviewStrategy
from ..preview.picture_annotation import ImageLabel
from ..logging_config import logger
import os


class PreviewPanel(QWidget):
    """
    预览面板类，用于显示选中文件的内容
    使用策略模式处理不同类型文件的预览
    """

    # 定义删除文件信号
    file_deleted = pyqtSignal(str)  # 文件路径
    # 定义资源切换信号
    switch_to_previous = pyqtSignal()
    switch_to_next = pyqtSignal()
    # 定义图片标注更新信号
    annotations_updated = pyqtSignal(str, object)  # 文件路径, ImageLabel对象
    # 定义图片上选中矩形框的信号
    annotation_selected_in_image = pyqtSignal(object)  # 选中的标注对象(矩形或多边形)，不再传递类型参数

    def __init__(self):
        """
        初始化预览面板
        """
        super().__init__()
        self.init_ui()
        self.current_pixmap = None  # 保存当前图片的pixmap用于缩放
        self.current_file_path = None  # 保存当前文件路径
        self.scale_factor = 1.0     # 缩放因子
        self.video_player = None    # 视频播放器实例
        self.image_label = None     # 图片标注标签

        # 初始化预览策略
        self.strategies = [
            ImagePreviewStrategy(),
            VideoPreviewStrategy()
        ]
        self.unsupported_strategy = UnsupportedPreviewStrategy()

        # 设置焦点策略，确保能接收键盘事件
        self.setFocusPolicy(Qt.StrongFocus)

    def init_ui(self):
        """
        初始化预览面板的用户界面
        """
        layout = QVBoxLayout(self)
        # 移除固定最小尺寸设置，让面板能够根据分割器的调整自由变化
        # self.setMinimumSize(600, 400)

        # 创建工具栏用于图片标注功能
        self.toolbar = QHBoxLayout()
        self.toolbar_widget = QWidget()
        self.toolbar_widget.setLayout(self.toolbar)
        self.toolbar_widget.setVisible(False)  # 默认隐藏工具栏

        # 创建快捷键提示标签，添加更详细的说明
        self.shortcut_label = QLabel("快捷键: A-上一个文件, D-下一个文件, Delete-删除文件/标注, W-开启标注模式, Q-退出标注模式")
        self.shortcut_label.setStyleSheet("""
            QLabel {
                color: gray;
                background-color: transparent;
                padding: 2px;
                font-size: 12px;
            }
        """)
        self.shortcut_label.setVisible(False)  # 默认隐藏快捷键提示

        # 创建标注模式按钮，使用图标形式
        self.rect_button = QPushButton("□")  # 矩形图标
        self.rect_button.setToolTip("矩形标注模式 (点击切换)")
        self.polygon_button = QPushButton("◇")  # 多边形图标
        self.polygon_button.setToolTip("多边形标注模式 (点击切换)")

        # 设置按钮为可选中状态
        self.rect_button.setCheckable(True)
        self.polygon_button.setCheckable(True)
        self.rect_button.setChecked(True)  # 默认选中矩形模式

        # 创建按钮组确保只有一个按钮被选中
        self.button_group = QButtonGroup()
        self.button_group.addButton(self.rect_button, 0)
        self.button_group.addButton(self.polygon_button, 1)

        # 连接按钮事件
        self.rect_button.clicked.connect(self.switch_to_rectangle_mode)
        self.polygon_button.clicked.connect(self.switch_to_polygon_mode)

        # 添加按钮到工具栏
        self.toolbar.addWidget(self.rect_button)
        self.toolbar.addWidget(self.polygon_button)
        self.toolbar.addStretch()

        # 创建滚动区域用于显示大图像
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)  # 设置为True以适应内容
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setAlignment(Qt.AlignCenter)

        # 创建标签用于显示内容
        self.content_label = QLabel("请选择文件进行预览")
        self.content_label.setAlignment(Qt.AlignCenter)
        # 移除固定最小尺寸设置
        # self.content_label.setMinimumSize(400, 300)

        # 启用鼠标跟踪以支持鼠标事件
        self.content_label.setMouseTracking(True)
        self.content_label.installEventFilter(self)

        self.scroll_area.setWidget(self.content_label)
        layout.addWidget(self.shortcut_label)  # 添加快捷键提示标签
        layout.addWidget(self.toolbar_widget)
        layout.addWidget(self.scroll_area)

        self.setLayout(layout)

    def preview_file(self, file_path):
        """
        根据文件类型预览文件，使用策略模式

        Args:
            file_path (str): 文件路径
        """
        logger.debug(f"预览文件: {file_path}")

        if not os.path.exists(file_path):
            self.show_message("文件不存在")
            logger.warning(f"尝试预览不存在的文件: {file_path}")
            return

        # 保存当前文件路径
        self.current_file_path = file_path

        # 根据文件扩展名选择合适的预览策略
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        logger.debug(f"文件扩展名: {ext}")

        # 查找合适的策略
        strategy = self.unsupported_strategy
        for s in self.strategies:
            if ext in s.supported_formats():
                strategy = s
                logger.debug(f"使用策略: {type(s).__name__}")
                break

        # 使用选定的策略预览文件
        result = strategy.preview(file_path, self)
        logger.debug(f"预览结果: {result}")
        return result

    def show_message(self, message):
        """
        在内容区域显示消息

        Args:
            message (str): 要显示的消息
        """
        logger.debug(f"显示消息: {message}")

        # 确保使用正确的显示标签
        if self.scroll_area.widget() != self.content_label:
            # 清理当前控件，但不要删除image_label
            old_widget = self.scroll_area.takeWidget()
            if old_widget and not sip.isdeleted(old_widget) and old_widget != self.image_label:
                old_widget.setParent(None)
                old_widget.deleteLater()
            # 确保content_label对象仍然有效
            if self.content_label is None or sip.isdeleted(self.content_label):
                self.content_label = QLabel()
                self.content_label.setAlignment(Qt.AlignCenter)
                self.content_label.setWordWrap(True)
            self.scroll_area.setWidget(self.content_label)

        # 确保content_label对象仍然有效
        if self.content_label is None or sip.isdeleted(self.content_label):
            self.content_label = QLabel()
            self.content_label.setAlignment(Qt.AlignCenter)
            self.content_label.setWordWrap(True)

        self.content_label.setText(message)
        self.content_label.setAlignment(Qt.AlignCenter)
        self.toolbar_widget.setVisible(False)  # 隐藏工具栏
        self.shortcut_label.setVisible(False)  # 隐藏快捷键提示

    def wheelEvent(self, event: QWheelEvent):
        """
        处理鼠标滚轮事件，支持图片缩放

        Args:
            event (QWheelEvent): 滚轮事件
        """
        if self.current_pixmap and not self.current_pixmap.isNull():
            # 调试信息
            modifiers = event.modifiers()
            logger.debug(f"滚轮事件: modifiers={modifiers}, ctrl={bool(modifiers & Qt.ControlModifier)}, shift={bool(modifiers & Qt.ShiftModifier)}")

            # 检查是否按下Ctrl键进行缩放 (支持跨平台: Ctrl on Windows/Linux, Cmd on Mac)
            if modifiers & Qt.ControlModifier:
                # 限制缩放次数为10次
                if (event.angleDelta().y() > 0 and self.scale_factor < 10.0) or \
                   (event.angleDelta().y() < 0 and self.scale_factor > 0.1):
                    # 计算缩放因子 - 调整为每次滚动变化更大比例，确保5次滚动能达到最大缩放
                    if event.angleDelta().y() > 0:
                        self.scale_factor *= 1.1  # 放大 (每次放大10%)
                    else:
                        self.scale_factor *= 0.9  # 缩小 (每次缩小10%)
                    
                    logger.debug(f"缩放因子更新为: {self.scale_factor}")
                    self.update_image_display()
                else:
                    logger.debug(f"达到缩放限制: scale_factor={self.scale_factor}")
                return

            # Shift+滚轮水平滚动处理保持不变
            elif modifiers & Qt.ShiftModifier:
                # Shift+滚轮水平滚动
                delta = event.angleDelta().y()
                current_value = self.scroll_area.horizontalScrollBar().value()
                self.scroll_area.horizontalScrollBar().setValue(current_value - delta)
                logger.debug(f"水平滚动: delta={delta}, current_value={current_value}")
                return

        # 默认的垂直滚动处理
        if self.scroll_area:
            # 调用滚动区域的滚轮事件处理
            self.scroll_area.wheelEvent(event)
            logger.debug("处理默认垂直滚动事件")
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event):
        """
        处理键盘按键事件

        Args:
            event: 键盘事件
        """
        # 如果当前显示的是图片标注标签
        if isinstance(self.scroll_area.widget(), ImageLabel):
            image_label = self.scroll_area.widget()
            # 处理Delete键删除当前预览的图片
            if event.key() == Qt.Key_Delete:
                # 检查是否有选中的标注元素
                if image_label.has_selected_annotation():
                    # 有选中的标注元素，删除选中的标注
                    image_label.delete_selected()
                    # 发出标注更新信号
                    self.annotations_updated.emit(self.current_file_path, image_label)
                else:
                    # 没有选中的标注元素，删除当前图片
                    self.delete_current_image()
            # 处理W键开启标注模式
            elif event.key() == Qt.Key_W:
                image_label.start_annotation_mode()
            # 处理Q键退出标注模式
            elif event.key() == Qt.Key_Q:
                image_label.exit_annotation_mode()
            # 处理A/D键切换前后资源
            elif event.key() == Qt.Key_A:
                self.switch_to_previous_resource()
            elif event.key() == Qt.Key_D:
                self.switch_to_next_resource()
            else:
                super().keyPressEvent(event)
        else:
            # 处理Delete键删除当前预览的图片
            if event.key() == Qt.Key_Delete:
                # 非图片标注标签，删除当前图片
                self.delete_current_image()
            # 处理A/D键切换前后资源
            elif event.key() == Qt.Key_A:
                self.switch_to_previous_resource()
            elif event.key() == Qt.Key_D:
                self.switch_to_next_resource()
            else:
                super().keyPressEvent(event)

    def delete_current_image(self):
        """
        删除当前预览的图片
        """
        # 发出删除文件信号，让主窗口处理实际的删除操作
        if self.current_file_path:
            logger.info(f"请求删除当前文件: {self.current_file_path}")
            self.file_deleted.emit(self.current_file_path)

    def switch_to_previous_resource(self):
        """
        切换到前一个资源
        """
        # 发出切换到前一个资源的信号
        self.switch_to_previous.emit()
        logger.info("切换到前一个资源")

    def switch_to_next_resource(self):
        """
        切换到后一个资源
        """
        # 发出切换到后一个资源的信号
        self.switch_to_next.emit()
        logger.info("切换到后一个资源")

    def switch_to_rectangle_mode(self):
        """
        切换到矩形标注模式
        """
        if isinstance(self.scroll_area.widget(), ImageLabel):
            self.scroll_area.widget().set_mode('rectangle')
            logger.info("切换到矩形标注模式")

    def switch_to_polygon_mode(self):
        """
        切换到多边形标注模式
        """
        if isinstance(self.scroll_area.widget(), ImageLabel):
            self.scroll_area.widget().set_mode('polygon')
            logger.info("切换到多边形标注模式")

    def on_image_label_annotations_updated(self, image_label):
        """
        处理ImageLabel标注更新事件

        Args:
            image_label (ImageLabel): 发出信号的ImageLabel对象
        """
        # 发出标注更新信号，传递当前文件路径和更新后的ImageLabel对象
        if self.current_file_path:
            self.annotations_updated.emit(self.current_file_path, image_label)

    def on_image_label_annotation_selected(self, annotation):
        """
        处理ImageLabel上选中任意标注元素的事件
        
        Args:
            annotation: 被选中的标注对象(矩形或多边形)
        """
        logger.debug(f"图片上选中标注: annotation={annotation}")
        # 发出图片上选中标注的信号
        self.annotation_selected_in_image.emit(annotation)

    def show_image_with_annotation(self, file_path):
        """
        显示带标注功能的图片

        Args:
            file_path (str): 图片文件路径
        """
        # 创建图片标注标签
        if not self.image_label:
            self.image_label = ImageLabel()
            # 连接ImageLabel的标注更新信号
            self.image_label.annotations_updated.connect(self.on_image_label_annotations_updated)
            # 连接ImageLabel的标注选中信号
            self.image_label.annotation_selected_in_image.connect(self.on_image_label_annotation_selected)
        # 检查image_label对象是否仍然有效，如果已被删除则重新创建
        elif sip.isdeleted(self.image_label):
            self.image_label = ImageLabel()
            # 连接ImageLabel的标注更新信号
            self.image_label.annotations_updated.connect(self.on_image_label_annotations_updated)
            # 连接ImageLabel的标注选中信号
            self.image_label.annotation_selected_in_image.connect(self.on_image_label_annotation_selected)

        self.image_label.set_image(file_path)
        # 同步缩放因子
        self.image_label.scale_factor = self.scale_factor

        # 只有当当前控件不是我们要设置的image_label时才清理
        if self.scroll_area.widget() != self.image_label:
            # 清理当前控件
            old_widget = self.scroll_area.takeWidget()
            if old_widget and not sip.isdeleted(old_widget) and old_widget != self.image_label:
                old_widget.setParent(None)
                old_widget.deleteLater()

        # 替换显示内容为图片标注标签（如果尚未设置）
        if self.scroll_area.widget() != self.image_label:
            self.scroll_area.setWidget(self.image_label)

        # 显示工具栏和快捷键提示
        self.toolbar_widget.setVisible(True)
        self.shortcut_label.setVisible(True)

        # 设置焦点到预览面板，确保能接收键盘事件
        self.setFocus()

        # 发出标注更新信号
        self.annotations_updated.emit(file_path, self.image_label)

        logger.info(f"显示带标注功能的图片: {file_path}")
        return True

    def select_rectangle(self, rectangle):
        """
        选中指定的矩形框（可编辑状态）

        Args:
            rectangle: 要选中的矩形框
        """
        if isinstance(self.scroll_area.widget(), ImageLabel):
            image_label = self.scroll_area.widget()
            image_label.select_rectangle(rectangle)

    def select_polygon(self, polygon_index):
        """
        选中指定的多边形（可编辑状态）

        Args:
            polygon_index: 要选中的多边形索引
        """
        if isinstance(self.scroll_area.widget(), ImageLabel):
            image_label = self.scroll_area.widget()
            image_label.select_polygon(polygon_index)

    def select_annotation(self, annotation_data):
        """
        统一选中标注对象（可编辑状态）
        
        Args:
            annotation_data: 标注数据字典，包含type和其他相关信息
        """
        if isinstance(self.scroll_area.widget(), ImageLabel):
            image_label = self.scroll_area.widget()
            image_label.select_annotation(annotation_data)

    def highlight_polygon_indices(self, polygon_indices):
        """
        高亮指定索引的多边形列表（仅高亮，不可编辑）

        Args:
            polygon_indices: 要高亮的多边形索引列表
        """
        if isinstance(self.scroll_area.widget(), ImageLabel):
            image_label = self.scroll_area.widget()
            image_label.highlight_polygons(polygon_indices)

    def highlight_rectangles(self, rectangles):
        """
        高亮指定的矩形框列表（仅高亮，不可编辑）

        Args:
            rectangles: 要高亮的矩形框列表
        """
        if isinstance(self.scroll_area.widget(), ImageLabel):
            image_label = self.scroll_area.widget()
            image_label.highlight_rectangles(rectangles)

    def highlight_polygons(self, polygons):
        """
        高亮指定的多边形列表（仅高亮，不可编辑）

        Args:
            polygons: 要高亮的多边形列表
        """
        if isinstance(self.scroll_area.widget(), ImageLabel):
            image_label = self.scroll_area.widget()
            # 如果传入的是索引列表
            if polygons and isinstance(polygons[0], int):
                image_label.highlight_polygons(polygons)
            else:
                # 提取多边形索引
                polygon_indices = []
                for polygon_data in polygons:
                    # 在image_label.polygons中查找匹配的多边形
                    for i, polygon in enumerate(image_label.polygons):
                        if (polygon.points == polygon_data['points'] and 
                            polygon.label == polygon_data['label']):
                            polygon_indices.append(i)
                            break
                image_label.highlight_polygons(polygon_indices)

    def highlight_polygon_indices(self, polygon_indices):
        """
        高亮指定索引的多边形列表（仅高亮，不可编辑）

        Args:
            polygon_indices: 要高亮的多边形索引列表
        """
        if isinstance(self.scroll_area.widget(), ImageLabel):
            image_label = self.scroll_area.widget()
            image_label.highlight_polygons(polygon_indices)

    def highlight_annotations_by_labels(self, labels):
        """
        根据标签高亮所有相关的标注（包括矩形和多边形）

        Args:
            labels: 要高亮的标签列表
        """
        if isinstance(self.scroll_area.widget(), ImageLabel):
            image_label = self.scroll_area.widget()
            if labels:
                image_label.highlight_annotations_by_labels(labels)
            else:
                # 如果标签列表为空，清除所有高亮
                image_label.highlighted_rectangles = []
                image_label.highlighted_polygons = []
                image_label.update()

    def clear_highlights(self):
        """
        清除所有高亮状态
        """
        if isinstance(self.scroll_area.widget(), ImageLabel):
            image_label = self.scroll_area.widget()
            image_label.highlighted_rectangles = []
            image_label.highlighted_polygons = []
            image_label.update()

    def clear_highlights_from_details(self, data_to_clear):
        """
        从详情面板接收清除高亮的请求，并处理需要清除高亮的标注框
        
        Args:
            data_to_clear: 需要清除高亮的数据
        """
        if isinstance(self.scroll_area.widget(), ImageLabel):
            image_label = self.scroll_area.widget()
            
            # 清除所有高亮状态
            image_label.highlighted_rectangles = []
            image_label.highlighted_polygons = []
            image_label.update()

    def update_image_display(self):
        """
        更新图片显示（根据缩放因子调整图片大小）
        """
        if self.current_pixmap and not self.current_pixmap.isNull():
            # 根据缩放因子调整图片大小
            scaled_pixmap = self.current_pixmap.scaled(
                int(self.current_pixmap.width() * self.scale_factor),
                int(self.current_pixmap.height() * self.scale_factor),
                Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.content_label.setPixmap(scaled_pixmap)
            logger.debug(f"更新图片显示，缩放因子: {self.scale_factor}")
        elif isinstance(self.scroll_area.widget(), ImageLabel):
            # 如果是ImageLabel，更新其缩放因子并重绘
            image_label = self.scroll_area.widget()
            image_label.scale_factor = self.scale_factor
            image_label.update()

    def delete_annotation(self, annotation):
        """
        删除指定的标注

        Args:
            annotation: 要删除的标注信息
        """
        if isinstance(self.scroll_area.widget(), ImageLabel):
            image_label = self.scroll_area.widget()
            # 查找并删除对应的标注
            if annotation['type'] == 'rectangle':
                # 查找匹配的矩形框
                for rect_info in image_label.rectangle_infos:
                    if rect_info.rectangle == annotation['rectangle'] and rect_info.label == annotation['label']:
                        # 如果删除的是当前选中的矩形框，清除选中状态
                        if image_label.selected_rectangle_info == rect_info:
                            image_label.selected_rectangle_info = None
                        image_label.rectangle_infos.remove(rect_info)
                        break
                # 如果删除的矩形框在高亮列表中，也需要从高亮列表中移除
                for rect in image_label.highlighted_rectangles:
                    if rect == annotation['rectangle']:
                        image_label.highlighted_rectangles.remove(rect)
                        break
            elif annotation['type'] == 'polygon':
                # 查找匹配的多边形
                for i, polygon in enumerate(image_label.polygons):
                    if polygon.points == annotation['points'] and polygon.label == annotation['label']:
                        # 如果删除的是当前选中的多边形，清除选中状态
                        if image_label.selected_polygon_index == i:
                            image_label.selected_polygon_index = None
                        del image_label.polygons[i]
                        break
                # 如果删除的多边形在高亮列表中，也需要从高亮列表中移除
                if i in image_label.highlighted_polygons:
                    image_label.highlighted_polygons.remove(i)
                    # 更新后续索引
                    image_label.highlighted_polygons = [idx-1 if idx > i else idx for idx in image_label.highlighted_polygons]

            # 更新显示
            image_label.update()
            # 保存YOLO标注
            image_label.save_yolo_annotations()
            # 发出标注更新信号
            self.annotations_updated.emit(self.current_file_path, image_label)