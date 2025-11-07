import os

from PyQt5.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal

from PyQt5.QtGui import QPixmap, QPainter, QPen, QPolygon, QFont, QIcon, QColor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QInputDialog, \
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QPushButton, QSizePolicy, QAction, QScrollArea


from src.logging_config import logger
from src.persist.yolo_utils import save_yolo_annotations, load_yolo_annotations


class Annotation:
    """统一的注解基类"""

    def __init__(self, label=""):
        self.label = label
        self.selected = False
        self.highlighted = False
        self.id = None  # ID将在加载时或创建时设置

    def get_type(self):
        """获取注解类型"""
        raise NotImplementedError

    def contains_point(self, point):
        """检查点是否在注解内部"""
        raise NotImplementedError

    def move_by(self, offset):
        """移动注解位置"""
        raise NotImplementedError

    def draw(self, painter, scale_factor):
        """绘制注解"""
        raise NotImplementedError

    def get_center(self):
        """获取注解中心点"""
        raise NotImplementedError


class RectangleAnnotation(Annotation):
    """矩形注解类"""

    def __init__(self, rectangle, label=""):
        super().__init__(label)
        self.rectangle = rectangle

    def get_type(self):
        return 'rectangle'

    def contains_point(self, point):
        return self.rectangle.contains(point)

    def move_by(self, offset):
        self.rectangle.moveTo(self.rectangle.topLeft() + offset)

    def draw(self, painter, scale_factor, selected_control_point=None):
        # 在ImageLabel的paintEvent中已经计算了偏移量，这里我们只需要使用它
        # 创建缩放后的矩形
        scaled_rect = QRect(
            int(self.rectangle.x() * scale_factor),
            int(self.rectangle.y() * scale_factor),
            int(self.rectangle.width() * scale_factor),
            int(self.rectangle.height() * scale_factor)
        )

        # 根据状态设置画笔
        if self.selected:
            painter.setPen(QPen(Qt.green, 1, Qt.SolidLine))  # 将线宽从3改为1
        elif self.highlighted:
            # 批量选中时使用绿色高亮，线宽与选中状态一致
            painter.setPen(QPen(Qt.green, 1, Qt.SolidLine))  # 将线宽从3改为1
        else:
            painter.setPen(QPen(Qt.red, 1, Qt.SolidLine))  # 将线宽从2改为1

        # 绘制矩形
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(scaled_rect)

        # 绘制标签
        if self.label:
            font = QFont()
            font.setPointSize(10)  # 将字体大小从14改为10
            painter.setFont(font)
            # 将标签显示在矩形框的左上方，进一步减小距离
            text_x = scaled_rect.left()
            text_y = scaled_rect.top() - 6  # 在矩形框上方6像素处显示
            painter.drawText(text_x, text_y, self.label)

        # 如果被选中，绘制控制点
        if self.selected:
            handle_size = 3  # 将控制点大小从6改为3
            painter.setPen(QPen(Qt.green, 1, Qt.SolidLine))
            painter.setBrush(Qt.green)
            painter.drawEllipse(scaled_rect.topLeft(), handle_size, handle_size)
            painter.drawEllipse(scaled_rect.topRight(), handle_size, handle_size)
            painter.drawEllipse(scaled_rect.bottomLeft(), handle_size, handle_size)
            painter.drawEllipse(scaled_rect.bottomRight(), handle_size, handle_size)
            painter.setBrush(Qt.NoBrush)

    def get_center(self):
        return self.rectangle.center()


class PolygonAnnotation(Annotation):
    """多边形注解类"""

    def __init__(self, points=None, label=""):
        super().__init__(label)
        self.points = points if points is not None else []
        self.closed = False

    def get_type(self):
        return 'polygon'

    def contains_point(self, point):
        """检查点是否在多边形内部或接近多边形的顶点"""
        if len(self.points) < 1:
            return False

        # 如果多边形已闭合且点数大于等于3，检查点是否在多边形内部
        if self.closed and len(self.points) >= 3:
            polygon = QPolygon()
            for p in self.points:
                polygon.append(p)
            if polygon.containsPoint(point, Qt.OddEvenFill):
                return True

        # 检查点是否接近多边形的顶点（控制点）
        threshold = 10  # 点击检测范围
        for p in self.points:
            distance = ((point.x() - p.x()) ** 2 + (point.y() - p.y()) ** 2) ** 0.5
            if distance <= threshold:
                return True

        return False

    def move_by(self, offset):
        """移动多边形"""
        for i, point in enumerate(self.points):
            self.points[i] = point + offset

    def draw(self, painter, scale_factor, selected_control_point=None):
        """绘制多边形"""
        if len(self.points) < 1:
            return

        # 根据状态设置画笔
        if self.selected:
            painter.setPen(QPen(Qt.green, 1, Qt.SolidLine))  # 将线宽从3改为1
        elif self.highlighted:
            # 批量选中时使用绿色高亮，线宽与选中状态一致
            painter.setPen(QPen(Qt.green, 1, Qt.SolidLine))  # 将线宽从3改为1
        else:
            painter.setPen(QPen(Qt.red, 1, Qt.SolidLine))  # 将线宽从2改为1

        # 绘制点之间的连接线（缩放后）
        scaled_points = []
        for point in self.points:
            scaled_points.append(QPoint(
                int(point.x() * scale_factor),
                int(point.y() * scale_factor)
            ))

        if not self.closed:
            for i in range(len(scaled_points) - 1):
                painter.drawLine(scaled_points[i], scaled_points[i + 1])
        else:
            # 如果多边形已经闭合，绘制完整的多边形边框
            for i in range(len(scaled_points)):
                painter.drawLine(scaled_points[i], scaled_points[(i + 1) % len(scaled_points)])

        # 如果被选中，绘制控制点
        if self.selected:
            painter.setPen(QPen(Qt.green, 1, Qt.SolidLine))
            painter.setBrush(Qt.green)
            for point_index, scaled_point in enumerate(scaled_points):
                # 检查是否是选中的控制点
                is_selected_control_point = (selected_control_point is not None and
                                             selected_control_point[0] == self and
                                             selected_control_point[1] == point_index)

                if is_selected_control_point:
                    # 特殊高亮选中的控制点
                    painter.setPen(QPen(Qt.blue, 1, Qt.SolidLine))  # 将线宽从2改为1
                    painter.setBrush(Qt.yellow)  # 黄色填充
                    painter.drawEllipse(scaled_point, 4, 4)  # 将控制点大小从8改为4
                    # 恢复原来的画笔设置
                    painter.setPen(QPen(Qt.green, 1, Qt.SolidLine))
                    painter.setBrush(Qt.green)
                elif point_index == 0:
                    # 起始点用较大绿色圆形点绘制
                    painter.drawEllipse(scaled_point, 4, 4)  # 将控制点大小从6改为4
                else:
                    # 其他点用普通绿色圆形点绘制
                    painter.drawEllipse(scaled_point, 3, 3)  # 将控制点大小从5改为3

        # 绘制标签
        # 绘制标签
        if self.label and len(self.points) > 0:
            # 计算多边形的第一个点作为标签显示位置
            first_point = self.points[0]
            scaled_first_point = QPoint(
                int(first_point.x() * scale_factor),
                int(first_point.y() * scale_factor)
            )

            # 设置文本颜色
            if self.selected:
                painter.setPen(QPen(Qt.green, 1, Qt.SolidLine))
            elif self.highlighted:
                # 批量选中时使用绿色高亮
                painter.setPen(QPen(Qt.green, 1, Qt.SolidLine))
            else:
                painter.setPen(QPen(Qt.red, 1, Qt.SolidLine))
            # 绘制标签文本（显示在第一个点的左上方，进一步减小距离）
            font = QFont()
            font.setPointSize(10)  # 将字体大小从14改为10
            painter.setFont(font)
            painter.drawText(scaled_first_point.x() - 4, scaled_first_point.y() - 4, self.label)

    def get_center(self):
        """获取多边形中心点"""
        if not self.points:
            return QPoint(0, 0)
        center_x = sum(point.x() for point in self.points) / len(self.points)
        center_y = sum(point.y() for point in self.points) / len(self.points)
        return QPoint(int(center_x), int(center_y))


class PolygonData:
    def __init__(self):
        self.points = []  # 存储多边形的点
        self.closed = False  # 标记多边形是否已闭合
        self.label = ""  # 存储多边形的标注信息


class ImageLabel(QLabel):
    # 全局标注模式状态
    global_annotation_mode = False
    global_annotation_label = ""

    def __init__(self):
        super().__init__()
        self.pixmap = None
        self.scaled_pixmap = None  # 添加缓存的缩放图片
        self.mode = 'rectangle'  # 默认模式为矩形模式
        self.scale_factor = 1.0  # 添加缩放因子属性，用于控制图片缩放级别
        self.zoom_count = 0  # 添加缩放计数器，用于限制缩放次数
        self.file_path = None  # 图片文件路径
        self.class_names = []  # 类别名称列表
        self.mouse_pos = QPoint()  # 鼠标位置
        self.annotation_mode = False  # 标注模式开关
        self.current_annotation_label = ""  # 当前标注的标签内容
        self.show_annotation_hint = False  # 是否显示标注提示
        self.user_scaled = False  # 添加标志，跟踪是否是用户手动缩放

        # 注解相关属性
        self.annotations = []  # 存储所有已完成的注解
        self.current_rectangle = None  # 当前正在绘制的矩形框
        self.current_polygon = PolygonData()  # 当前正在绘制的多边形
        self.selected_annotation = None  # 当前选中的注解
        self.highlighted_annotations = []  # 当前高亮的注解列表（仅高亮，不可编辑）
        self.drawing = False
        self.dragging = False  # 是否正在拖动注解

        self.resizing = False  # 是否正在调整矩形框大小
        self.drag_start_point = QPoint()  # 拖动起始点

        self.drag_annotation_start_pos = QPoint()  # 被拖动注解的初始位置
        self.resize_handle = None  # 调整大小的控制点位置

        self.resize_rectangle_start_rect = QRect()  # 调整大小时矩形框的初始状态

        # 多边形相关属性
        self.selected_point_info = None  # 当前选中的点信息 (polygon_index, point_index)
        self.selected_control_point = None  # 当前选中的控制点信息 (polygon, point_index)
        self.dragging_polygon = False  # 是否正在拖拽多边形
        self.drag_start_position = QPoint()  # 拖拽起始位置
        self.original_polygon_points = []  # 拖拽前的多边形点位置

        # 添加对父组件的引用，用于直接调用方法更新详情面板
        self.preview_panel = None

        # 设置焦点策略
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()
        self.setAttribute(Qt.WA_KeyCompression, True)
        self.setMouseTracking(True)
        # 设置默认鼠标样式
        self.setCursor(Qt.ArrowCursor)

        # 设置尺寸策略，使其填充可用空间但不超出
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def focusInEvent(self, event):
        """处理获得焦点事件"""
        super().focusInEvent(event)
        # 确保ImageLabel能够接收键盘事件
        self.setAttribute(Qt.WA_KeyCompression, True)

    def set_image(self, file_path):
        self.file_path = file_path
        self.pixmap = QPixmap(file_path)
        self.scale_factor = 1.0  # 重置缩放因子
        self.user_scaled = False  # 重置用户缩放标志
        self.zoom_count = 0  # 重置缩放计数器

        # 重置注解相关属性
        self.annotations = []
        self.current_rectangle = None
        self.selected_annotation = None
        self.highlighted_annotations = []  # 重置高亮注解列表
        self.drawing = False
        self.dragging = False
        self.resizing = False

        # 重置多边形相关属性
        self.current_polygon = PolygonData()
        self.selected_point_info = None
        self.selected_control_point = None
        self.dragging_polygon = False

        # 加载已有的YOLO标注
        self.load_yolo_annotations()

        # 自动调整缩放因子以适应显示区域
        self.fit_image_to_view()

    def get_available_size(self):
        """获取可用于显示图片的区域大小，考虑详情面板占用的宽度"""
        # 如果在滚动区域中，获取滚动区域的视口大小
        if self.parent() and hasattr(self.parent(), 'viewport'):
            viewport = self.parent().viewport()
            # 获取父级图片预览面板的宽度
            parent_width = viewport.width()
            parent_height = viewport.height()

            # 如果存在图片预览面板父级，需要考虑详情面板占用的宽度
            # 查找图片预览面板父级
            image_preview_panel = None
            parent = self.parent()
            while parent:
                if parent.objectName() == "image_container" or (hasattr(parent, 'metaObject') and
                                                                parent.metaObject().className() == "ImagePreviewPanel"):
                    image_preview_panel = parent
                    break
                parent = parent.parent()

            # 如果找到了图片预览面板，需要减去详情面板的宽度
            if image_preview_panel and hasattr(image_preview_panel, 'parent') and image_preview_panel.parent():
                # 获取主分割器
                main_splitter = image_preview_panel.parent()
                if main_splitter and hasattr(main_splitter, 'sizes'):
                    sizes = main_splitter.sizes()
                    if len(sizes) >= 2:
                        # 图片容器宽度是第一个，详情面板宽度是第二个
                        image_container_width = sizes[0]
                        details_panel_width = sizes[1]
                        # 使用图片容器宽度作为可用宽度
                        parent_width = image_container_width - 20  # 留出一些边距

            # 留出一些边距
            return QSize(parent_width - 20, parent_height - 20)
        elif self.parent():
            return self.parent().size()
        else:
            # 默认返回一个合理的大小
            return QSize(800, 600)

    def fit_image_to_view(self):
        """自动调整图片大小以适应视图，考虑高分辨率屏幕和详情面板宽度"""
        if not self.pixmap or self.pixmap.isNull():
            return

        # 获取可用显示区域大小
        available_size = self.get_available_size()
        if available_size.width() <= 0 or available_size.height() <= 0:
            return

        # 计算缩放比例，使图片适应可用区域（保持宽高比）
        scale_x = available_size.width() / self.pixmap.width()
        scale_y = available_size.height() / self.pixmap.height()

        # 使用较小的缩放比例，确保整个图片可见（完整显示）
        self.scale_factor = min(scale_x, scale_y)

        # 限制最大缩放比例，避免过度放大
        self.scale_factor = min(self.scale_factor, 5.0)

        # 重置用户缩放标志，因为这是自动调整
        self.user_scaled = False

        # 生成高质量缩放后的图片缓存
        self.update_scaled_pixmap()

        # 设置ImageLabel的大小以匹配缩放后的图片
        scaled_width = int(self.pixmap.width() * self.scale_factor)
        scaled_height = int(self.pixmap.height() * self.scale_factor)
        self.setFixedSize(scaled_width, scaled_height)

        # 更新显示
        self.update()

    def update_scaled_pixmap(self):
        """生成高质量缩放后的图片缓存，并设置正确的devicePixelRatio"""
        if not self.pixmap or self.pixmap.isNull():
            self.scaled_pixmap = None
            return

        # 获取设备像素比率
        device_pixel_ratio = self.devicePixelRatioF()

        # 计算缩放后的尺寸，考虑设备像素比率
        scaled_width = int(self.pixmap.width() * self.scale_factor * device_pixel_ratio)
        scaled_height = int(self.pixmap.height() * self.scale_factor * device_pixel_ratio)

        # 生成高质量缩放后的图片
        self.scaled_pixmap = self.pixmap.scaled(
            scaled_width,
            scaled_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        # 设置正确的devicePixelRatio以适应高分辨率屏幕
        self.scaled_pixmap.setDevicePixelRatio(device_pixel_ratio)

        # 强制刷新界面以确保图片正确显示
        self.update()

    def resizeEvent(self, event):
        """处理大小改变事件"""
        # 只有在非用户手动缩放时才重新调整图片以适应新的视图大小
        if not self.user_scaled:
            self.fit_image_to_view()
        super().resizeEvent(event)
        self.update()

    def wheelEvent(self, event):
        """处理鼠标滚轮事件，支持图片缩放"""
        # 兼容不同操作系统的缩放快捷键
        # Windows/Linux使用Ctrl键，Mac使用Cmd键
        if event.modifiers() == Qt.ControlModifier or event.modifiers() == Qt.MetaModifier:
            # 获取鼠标位置
            mouse_pos = event.pos()

            # 记录缩放前的滚动位置
            old_scale = self.scale_factor
            old_scroll_x = 0
            old_scroll_y = 0
            scroll_area = None

            # 获取滚动区域和当前滚动位置
            if self.parent() and hasattr(self.parent(), 'horizontalScrollBar') and hasattr(self.parent(), 'verticalScrollBar'):
                scroll_area = self.parent()
                old_scroll_x = scroll_area.horizontalScrollBar().value()
                old_scroll_y = scroll_area.verticalScrollBar().value()

            # Ctrl/Cmd+滚轮进行缩放，每次滚动缩放10%
            zoom_step = 0.1  # 每次滚动的缩放步长
            if event.angleDelta().y() > 0:
                # 放大
                self.scale_factor *= (1 + zoom_step)
            else:
                # 缩小
                self.scale_factor /= (1 + zoom_step)

            # 限制缩放范围（0.1倍到10倍）
            self.scale_factor = max(0.1, min(self.scale_factor, 10.0))

            # 标记为用户手动缩放
            self.user_scaled = True

            # 更新缩放图片缓存
            self.update_scaled_pixmap()

            # 更新图片标签大小
            if self.pixmap:
                scaled_width = int(self.pixmap.width() * self.scale_factor)
                scaled_height = int(self.pixmap.height() * self.scale_factor)

                # 如果有鼠标位置信息，调整滚动条使鼠标位置保持不变
                new_scroll_x = 0
                new_scroll_y = 0
                if scroll_area:
                    # 检查鼠标是否在图片区域内
                    # 使用图片的实际尺寸来判断鼠标位置
                    image_rect = QRect(0, 0, scaled_width, scaled_height)
                    if image_rect.contains(mouse_pos):
                        # 鼠标在图片区域内，围绕鼠标位置缩放
                        # 计算鼠标在当前图片中的相对位置
                        relative_x = (old_scroll_x + mouse_pos.x()) / (self.pixmap.width() * old_scale) if old_scale > 0 else 0
                        relative_y = (old_scroll_y + mouse_pos.y()) / (self.pixmap.height() * old_scale) if old_scale > 0 else 0
                    else:
                        # 鼠标不在图片区域内，围绕图片中心缩放
                        relative_x = 0.5
                        relative_y = 0.5

                    # 计算新的滚动位置，使指定位置保持不变
                    new_center_x = relative_x * scaled_width
                    new_center_y = relative_y * scaled_height

                    # 设置新的滚动位置
                    new_scroll_x = new_center_x - mouse_pos.x()
                    new_scroll_y = new_center_y - mouse_pos.y()

                # 设置图片标签大小
                self.setFixedSize(scaled_width, scaled_height)

                # 设置滚动条位置
                if scroll_area:
                    scroll_area.horizontalScrollBar().setValue(int(new_scroll_x))
                    scroll_area.verticalScrollBar().setValue(int(new_scroll_y))

                # 通知滚动区域内容大小已改变
                self.updateGeometry()

            self.update()
        else:
            # 普通滚轮事件交给父类处理（滚动视图）
            super().wheelEvent(event)

    def load_yolo_annotations(self):
        """加载YOLO格式的标注文件"""
        if not self.file_path or not os.path.exists(self.file_path):
            return

        # 获取图片文件的基本信息
        image_dir = os.path.dirname(self.file_path)
        image_name = os.path.basename(self.file_path)
        image_name_without_ext = os.path.splitext(image_name)[0]

        # 按优先级查找标注文件
        annotation_paths = []

        # 1. 先找图片同一个路径下面的labels路径下有没有标注文件
        labels_dir_same_level = os.path.join(image_dir, 'labels')
        if os.path.exists(labels_dir_same_level):
            annotation_path = os.path.join(labels_dir_same_level, image_name_without_ext + '.txt')
            if os.path.exists(annotation_path):
                annotation_paths.append(annotation_path)

        # 2. 再找图片同一个路径下面有没有同名标注文件
        same_dir_annotation = os.path.join(image_dir, image_name_without_ext + '.txt')
        if os.path.exists(same_dir_annotation):
            annotation_paths.append(same_dir_annotation)

        # 3. 再找图片所属目录同级目录下面有没有同名标注文件
        parent_dir = os.path.dirname(image_dir)
        if parent_dir:
            same_level_annotation = os.path.join(parent_dir, image_name_without_ext + '.txt')
            if os.path.exists(same_level_annotation):
                annotation_paths.append(same_level_annotation)

        # 4. 再找图片所属目录同级目录下面的labels路径下面有没有标注文件
        if parent_dir:
            labels_dir_parent_level = os.path.join(parent_dir, 'labels')
            if os.path.exists(labels_dir_parent_level):
                annotation_path = os.path.join(labels_dir_parent_level, image_name_without_ext + '.txt')
                if os.path.exists(annotation_path):
                    annotation_paths.append(annotation_path)

        # 使用找到的第一个有效的标注文件
        annotation_file = None
        for path in annotation_paths:
            if os.path.exists(path):
                annotation_file = path
                break

        # 加载类别名称
        classes_file = None

        # 按优先级查找类别文件
        classes_paths = []

        # 查找classes.txt文件的路径
        if annotation_file:
            # 如果找到了标注文件，优先在标注文件同目录下查找
            classes_paths.append(os.path.join(os.path.dirname(annotation_file), 'classes.txt'))

        # 在labels目录下查找
        if os.path.exists(labels_dir_same_level):
            classes_paths.append(os.path.join(labels_dir_same_level, 'classes.txt'))

        # 在图片同级目录下查找
        classes_paths.append(os.path.join(image_dir, 'classes.txt'))

        # 在图片上级目录下查找
        if parent_dir:
            classes_paths.append(os.path.join(parent_dir, 'classes.txt'))

            # 在上级目录的labels目录下查找
            if os.path.exists(labels_dir_parent_level):
                classes_paths.append(os.path.join(labels_dir_parent_level, 'classes.txt'))

        # 使用找到的第一个有效的类别文件
        for path in classes_paths:
            if os.path.exists(path):
                classes_file = path
                break

        # 加载类别名称
        if classes_file and os.path.exists(classes_file):
            with open(classes_file, 'r', encoding='utf-8') as f:
                self.class_names = [line.strip() for line in f.readlines() if line.strip()]
        else:
            # 如果没有找到classes.txt，尝试从标注文件中推断类别
            self.class_names = []

        # 加载标注信息
        if annotation_file and os.path.exists(annotation_file):
            annotations = load_yolo_annotations(self.file_path, self.class_names, annotation_file)
            for index, annotation in enumerate(annotations):
                if annotation['type'] == 'rectangle':
                    rect_annotation = RectangleAnnotation(annotation['rectangle'], annotation['label'])
                    rect_annotation.id = index  # 使用索引作为ID
                    self.annotations.append(rect_annotation)
                elif annotation['type'] == 'polygon':
                    polygon_annotation = PolygonAnnotation(annotation['points'], annotation['label'])
                    polygon_annotation.closed = True  # 从文件加载的多边形应该是闭合的

                    polygon_annotation.id = index  # 使用索引作为ID
                    self.annotations.append(polygon_annotation)

    def save_yolo_annotations(self):
        """保存YOLO格式的标注文件"""
        if not self.file_path:
            return

        # 收集所有类别名称
        class_names = []
        for annotation in self.annotations:
            if annotation.label and annotation.label not in class_names:
                class_names.append(annotation.label)

        if self.current_polygon.label and self.current_polygon.label not in class_names:
            class_names.append(self.current_polygon.label)

        # 保存标注文件
        save_yolo_annotations(self.file_path, self, class_names)

    def get_annotations(self):
        """获取所有标注信息，包括位置和标签

        Returns:
            list: 包含所有标注信息的列表，每个标注包含类型、位置和标签
        """
        annotations = []

        # 添加注解信息
        for index, annotation in enumerate(self.annotations):
            # 确保每个标注都有ID
            if annotation.id is None:
                annotation.id = index

            if isinstance(annotation, RectangleAnnotation):
                annotations.append({
                    'type': 'rectangle',
                    'rectangle': annotation.rectangle,
                    'label': annotation.label,
                    'id': annotation.id  # 添加ID
                })
            elif isinstance(annotation, PolygonAnnotation):
                annotations.append({
                    'type': 'polygon',
                    'points': annotation.points,
                    'label': annotation.label,
                    'id': annotation.id  # 添加ID
                })

        # 添加当前正在绘制的多边形（如果有点的话）
        if len(self.current_polygon.points) > 0:
            annotations.append({
                'type': 'polygon',
                'points': self.current_polygon.points,
                'label': self.current_polygon.label
            })

        return annotations

    def has_selected_annotation(self):
        """
        检查是否有选中的标注元素（矩形框、多边形或点）

        Returns:
            bool: 如果有选中的标注元素返回True，否则返回False
        """
        return (self.selected_point_info is not None or
                self.selected_annotation is not None or
                self.selected_control_point is not None)

    def delete_selected(self):
        """删除选中的标注（点、多边形或矩形框）"""
        # 如果选中了多边形的控制点，则删除该控制点
        if self.selected_control_point is not None:
            annotation, point_index = self.selected_control_point

            # 删除选中的控制点
            del annotation.points[point_index]

            # 取消多边形的闭合状态
            annotation.closed = False

            # 清除选中的控制点
            self.selected_control_point = None

            # 如果删除点后点数少于3个，则清除标签
            if len(annotation.points) < 3:
                annotation.label = ""

            # 启动绘制多边形的操作
            self.current_polygon = PolygonData()
            self.current_polygon.points = annotation.points[:]
            self.current_polygon.label = annotation.label

            # 从annotations中移除该多边形
            if annotation in self.annotations:
                self.annotations.remove(annotation)

            # 启动标注模式以继续编辑未闭合的多边形
            self.start_annotation_mode()
            self.mode = 'polygon'

            self.update()
        elif self.selected_annotation:
            # 如果选中了注解，则删除注解
            if self.selected_annotation in self.annotations:
                self.annotations.remove(self.selected_annotation)
            self.selected_annotation = None
            self.selected_control_point = None
            self.update()

        # 清除高亮状态
        self.clear_highlights()

        # 保存YOLO标注
        self.save_yolo_annotations()

        # 直接调用方法更新详情面板，而不是使用信号
        if self.preview_panel:
            annotations = self.get_annotations()
            self.preview_panel.details_panel.update_annotations(annotations)

    def delete_annotation_by_data(self, annotation_data):
        """
        根据注解数据删除注解

        Args:
            annotation_data: 注解数据字典，包含type和其他相关信息
        """
        annotation_to_delete = None

        if annotation_data['type'] == 'rectangle':
            # 查找匹配的矩形注解
            for annotation in self.annotations:
                if (isinstance(annotation, RectangleAnnotation) and
                        annotation.rectangle == annotation_data['rectangle'] and
                        annotation.label == annotation_data['label']):
                    annotation_to_delete = annotation
                    break
        elif annotation_data['type'] == 'polygon':
            # 查找匹配的多边形注解
            for annotation in self.annotations:
                if (isinstance(annotation, PolygonAnnotation) and
                        annotation.points == annotation_data['points'] and
                        annotation.label == annotation_data['label']):
                    annotation_to_delete = annotation
                    break

        # 如果找到了要删除的注解
        if annotation_to_delete:
            # 如果删除的是当前选中的注解，清除选中状态
            if self.selected_annotation == annotation_to_delete:
                self.selected_annotation = None
                self.selected_control_point = None

            # 从annotations列表中移除
            self.annotations.remove(annotation_to_delete)

            # 如果删除的注解在高亮列表中，也需要从高亮列表中移除
            if annotation_to_delete in self.highlighted_annotations:
                self.highlighted_annotations.remove(annotation_to_delete)

            # 更新显示
            self.update()
            # 保存YOLO标注
            self.save_yolo_annotations()

            # 直接调用方法更新详情面板，而不是使用信号
            if self.preview_panel:
                annotations = self.get_annotations()
                self.preview_panel.details_panel.update_annotations(annotations)

            return True

        return False

    def edit_annotation_label(self, annotation):
        """编辑注解的标签"""
        label, ok = QInputDialog.getText(self, "编辑标注信息", "请输入标注内容:", text=annotation.label)
        if ok:
            annotation.label = label
            self.update()
            # 保存YOLO标注
            self.save_yolo_annotations()
            # 直接调用方法更新详情面板，而不是使用信号
            if self.preview_panel:
                annotations = self.get_annotations()
                self.preview_panel.details_panel.update_annotations(annotations)

    def get_resize_handle_at_point(self, point, rectangle):
        """检查点是否在矩形框的调整大小控制点上"""
        handle_size = 10  # 增大点击范围
        # 左上角
        if QRect(rectangle.topLeft() - QPoint(handle_size, handle_size),
                 rectangle.topLeft() + QPoint(handle_size, handle_size)).contains(point):
            return "top_left"
        # 右上角
        elif QRect(rectangle.topRight() - QPoint(handle_size, handle_size),
                   rectangle.topRight() + QPoint(handle_size, handle_size)).contains(point):
            return "top_right"
        # 左下角
        elif QRect(rectangle.bottomLeft() - QPoint(handle_size, handle_size),
                   rectangle.bottomLeft() + QPoint(handle_size, handle_size)).contains(point):
            return "bottom_left"
        # 右下角
        elif QRect(rectangle.bottomRight() - QPoint(handle_size, handle_size),
                   rectangle.bottomRight() + QPoint(handle_size, handle_size)).contains(point):
            return "bottom_right"
        return None

    def get_point_near_click(self, click_pos):
        """检查点击位置是否接近已有的点，如果是则返回点的信息 (polygon_index, point_index)"""
        threshold = 10  # 点击检测范围

        # 检查已完成的多边形
        for poly_index, polygon in enumerate(self.annotations):
            # 只检查闭合的多边形并且是多边形注解
            if isinstance(polygon, PolygonAnnotation) and polygon.closed:
                for point_index, point in enumerate(polygon.points):
                    distance = ((click_pos.x() - point.x()) ** 2 + (click_pos.y() - point.y()) ** 2) ** 0.5
                    if distance <= threshold:
                        return (poly_index, point_index)

        # 检查当前正在绘制的多边形（只有在闭合后才可选中点）
        if self.current_polygon.closed:
            for point_index, point in enumerate(self.current_polygon.points):
                distance = ((click_pos.x() - point.x()) ** 2 + (click_pos.y() - point.y()) ** 2) ** 0.5
                if distance <= threshold:
                    return (-1, point_index)  # -1表示当前多边形

        return None

    def get_polygon_at_point(self, point):
        """检查点是否在已完成多边形内部，如果是则返回多边形索引"""
        for poly_index, polygon in enumerate(self.annotations):
            if isinstance(polygon, PolygonAnnotation) and polygon.closed and len(polygon.points) >= 3:
                polygon_obj = QPolygon()
                for p in polygon.points:
                    polygon_obj.append(p)
                if polygon_obj.containsPoint(point, Qt.OddEvenFill):
                    return poly_index
        return None

    def is_point_near_start(self, point):
        """检查点是否接近当前多边形的起始点"""
        if not self.current_polygon.points:
            return False
        start_point = self.current_polygon.points[0]
        # 定义一个阈值，如果点距离起始点小于该阈值，则认为是点击了起始点
        threshold = 10
        distance = ((point.x() - start_point.x()) ** 2 + (point.y() - start_point.y()) ** 2) ** 0.5
        return distance <= threshold

    def is_point_in_current_polygon(self, point):
        """检查点是否在当前多边形内部"""
        if not self.current_polygon.closed or len(self.current_polygon.points) < 3:
            return False

        polygon = QPolygon()
        for p in self.current_polygon.points:
            polygon.append(p)

        return polygon.containsPoint(point, Qt.OddEvenFill)

    def clear_selection(self):
        """
        统一清除所有选中状态的方法

        清除所有选中的标注元素（矩形框、多边形或点）的选中状态，
        同时清除高亮状态
        """
        # 清除所有选中状态
        self.selected_annotation = None
        self.selected_point_info = None
        self.selected_control_point = None

        # 清除高亮状态
        self.clear_highlights()

        # 更新界面
        self.update()

    def select_annotation(self, annotation):
        """
        选中指定的注解（可编辑状态）

        Args:
            annotation: 要选中的注解对象
        """
        # 只有当当前选中的不是这个注解时才更新
        if self.selected_annotation != annotation:
            self.selected_annotation = annotation
            self.selected_point_info = None
            self.selected_control_point = None
            # 清除高亮状态
            self.clear_highlights()

    def select_annotation_by_data(self, annotation_data):
        """
        根据注解数据选中注解

        Args:
            annotation_data: 注解数据字典，包含type和其他相关信息
        """
        logger.debug(f"选中注解数据: {annotation_data}")
        # 处理取消选中的情况
        if annotation_data is None:
            # 清除选中状态
            self.clear_selection()
            return

        if annotation_data['type'] == 'rectangle':
            # 查找匹配的矩形注解
            for annotation in self.annotations:
                if (isinstance(annotation, RectangleAnnotation) and
                        annotation.rectangle == annotation_data['rectangle'] and
                        annotation.label == annotation_data['label']):
                    self.select_annotation(annotation)
                    return
        elif annotation_data['type'] == 'polygon':
            # 查找匹配的多边形注解
            for annotation in self.annotations:
                if (isinstance(annotation, PolygonAnnotation) and
                        annotation.points == annotation_data['points'] and
                        annotation.label == annotation_data['label']):
                    self.select_annotation(annotation)
                    return
        else:
            # 如果没有找到匹配的注解，清除选中状态
            self.clear_selection()

    def highlight_annotations_by_data(self, annotations_data):
        """
        根据注解数据列表高亮注解

        Args:
            annotations_data: 注解数据字典列表
        """
        # 查找匹配的注解对象
        matched_annotations = []

        for annotation_data in annotations_data:
            if annotation_data['type'] == 'rectangle':
                # 查找匹配的矩形注解
                for annotation in self.annotations:
                    if (isinstance(annotation, RectangleAnnotation) and
                            annotation.rectangle == annotation_data['rectangle'] and
                            annotation.label == annotation_data['label']):
                        matched_annotations.append(annotation)
                        break
            elif annotation_data['type'] == 'polygon':
                # 查找匹配的多边形注解
                for annotation in self.annotations:
                    if (isinstance(annotation, PolygonAnnotation) and
                            annotation.points == annotation_data['points'] and
                            annotation.label == annotation_data['label']):
                        matched_annotations.append(annotation)
                        break

        # 高亮显示匹配的注解
        self.highlighted_annotations = matched_annotations
        self.update()

    def highlight_annotations_by_labels(self, labels):
        """
        根据标签高亮所有相关的注解

        Args:
            labels: 要高亮的标签列表
        """
        # 查找匹配标签的注解数据
        matched_annotations_data = []
        for annotation in self.annotations:
            if annotation.label in labels:
                # 构建注解数据
                if isinstance(annotation, RectangleAnnotation):
                    annotation_data = {
                        'type': 'rectangle',
                        'rectangle': annotation.rectangle,
                        'label': annotation.label
                    }
                    matched_annotations_data.append(annotation_data)
                elif isinstance(annotation, PolygonAnnotation):
                    annotation_data = {
                        'type': 'polygon',
                        'points': annotation.points,
                        'label': annotation.label
                    }
                    matched_annotations_data.append(annotation_data)

        # 调用highlight_annotations_by_data方法来处理高亮
        self.highlight_annotations_by_data(matched_annotations_data)

    def clear_highlights(self, data_to_clear=None):
        """
        统一清除高亮方法

        Args:
            data_to_clear: 需要清除高亮的数据对象
                - None 或空列表: 清除所有高亮状态
                - 标注对象列表: 清除指定标注的高亮状态
        """
        # 如果传入的是空列表或None，清除所有高亮状态
        if not data_to_clear:
            self.highlighted_annotations = []
            self.update()
            return

        # 如果传入的是标注对象列表
        if isinstance(data_to_clear, list):
            # 遍历并清除特定标注的高亮
            for annotation in data_to_clear:
                if annotation in self.highlighted_annotations:
                    self.highlighted_annotations.remove(annotation)
            self.update()
            return

        # 如果是其他情况，默认清除所有高亮
        self.highlighted_annotations = []
        self.update()

    def mousePressEvent(self, event):
        if self.pixmap:
            # 调整点击坐标以考虑图片偏移（现在图片始终在左上角，所以偏移为0）
            offset_x = 0
            offset_y = 0
            clicked_point = QPoint(
                int((event.pos().x() - offset_x) / self.scale_factor),
                int((event.pos().y() - offset_y) / self.scale_factor)
            )

            # 如果在标注模式下，开始绘制新的标注
            if self.annotation_mode:
                if self.mode == 'rectangle':
                    # 开始绘制矩形
                    self.drawing = True
                    self.current_rectangle = QRect(clicked_point, clicked_point)
                    self.update()
                    return
                elif self.mode == 'polygon':
                    # 对于多边形模式，需要检查是否点击了起始点以实现闭环
                    # 检查是否点击了当前多边形的起始点并且点数大于等于3
                    if (len(self.current_polygon.points) >= 3 and
                            self.is_point_near_start(clicked_point)):
                        # 闭合当前多边形
                        self.current_polygon.closed = True
                        # 创建新的多边形注解
                        polygon_annotation = PolygonAnnotation(self.current_polygon.points, self.current_polygon.label)
                        polygon_annotation.closed = True
                        polygon_annotation.id = len(self.annotations)  # 使用当前annotations列表长度作为ID
                        self.annotations.append(polygon_annotation)
                        # 使用预设标签
                        if self.current_annotation_label:
                            polygon_annotation.label = self.current_annotation_label
                        else:
                            # 否则弹出对话框输入标注信息
                            label, ok = QInputDialog.getText(self, '多边形标注', '请输入标注信息:')
                            if ok:
                                polygon_annotation.label = label
                            else:
                                # 如果用户取消输入，则从列表中移除多边形
                                self.annotations.pop()
                        # 创建新的多边形用于接下来的绘制
                        self.current_polygon = PolygonData()
                        self.selected_point_info = None
                        self.selected_control_point = None  # 清除选中的控制点
                        # 清除高亮状态
                        self.clear_highlights()
                        # 保存YOLO标注
                        self.save_yolo_annotations()
                        # 直接调用方法更新详情面板，而不是使用信号
                        if self.preview_panel:
                            annotations = self.get_annotations()
                            self.preview_panel.details_panel.update_annotations(annotations)
                    else:
                        # 添加多边形的点
                        self.current_polygon.points.append(clicked_point)
                        self.update()
                    return

            # ========== 注解处理逻辑 ==========
            # 检查是否点击了某个已存在的注解的控制点
            if self.selected_annotation:
                # 检查是否点击了矩形的控制点
                if isinstance(self.selected_annotation, RectangleAnnotation):
                    handle = self.get_resize_handle_at_point(clicked_point, self.selected_annotation.rectangle)
                    if handle:
                        # 准备调整大小操作
                        self.resizing = True
                        self.dragging = False
                        self.dragging_polygon = False
                        self.resize_handle = handle
                        self.drag_start_point = clicked_point
                        self.resize_rectangle_start_rect = QRect(self.selected_annotation.rectangle)
                        self.update()
                        return

                # 检查是否点击了多边形的控制点
                elif isinstance(self.selected_annotation, PolygonAnnotation):
                    threshold = 10
                    for point_index, point in enumerate(self.selected_annotation.points):
                        distance = ((clicked_point.x() - point.x()) ** 2 + (clicked_point.y() - point.y()) ** 2) ** 0.5
                        if distance <= threshold:
                            # 选中了多边形的控制点
                            self.selected_control_point = (self.selected_annotation, point_index)
                            self.resizing = True  # 设置为True以启用控制点拖拽
                            self.dragging = False
                            self.selected_point_info = None  # 清除selected_point_info
                            # 保存调整大小前的多边形点位置
                            self.original_polygon_points = []
                            for p in self.selected_annotation.points:
                                self.original_polygon_points.append(QPoint(p))
                            self.drag_start_position = clicked_point
                            self.update()
                            return

            # 检查是否点击了多边形的控制点
            point_info = self.get_point_near_click(clicked_point)
            if point_info is not None:
                poly_index, point_index = point_info
                if poly_index >= 0:  # 已完成的多边形
                    polygon = self.annotations[poly_index]
                    # 选中多边形
                    self.selected_annotation = polygon
                    self.selected_point_info = point_info
                    self.drawing = False
                    self.current_rectangle = None
                    self.selected_control_point = None  # 清除选中的控制点
                    # 清除高亮状态
                    self.clear_highlights()

                    # 准备调整大小操作
                    self.resizing = True
                    self.dragging = False
                    self.dragging_polygon = False
                    self.drag_start_point = clicked_point
                    # 保存调整大小前的多边形点位置
                    self.original_polygon_points = []
                    for point in polygon.points:
                        self.original_polygon_points.append(QPoint(point))
                    self.drag_start_position = clicked_point

                    self.update()
                    return

            # 检查是否点击了某个已存在的注解
            annotation_clicked = False
            for annotation in reversed(self.annotations):  # 从上到下检查（后绘制的在上层）
                if annotation.contains_point(clicked_point):
                    annotation_clicked = True
                    # 选中注解
                    self.select_annotation(annotation)
                    self.drawing = False
                    self.current_rectangle = None
                    self.selected_point_info = None
                    self.selected_control_point = None  # 清除选中的控制点
                    # 准备拖动操作（统一处理所有类型注解）
                    self.dragging = True
                    self.resizing = False
                    self.dragging_polygon = False
                    self.drag_start_point = clicked_point
                    if isinstance(annotation, RectangleAnnotation):
                        self.drag_annotation_start_pos = annotation.rectangle.topLeft()
                    elif isinstance(annotation, PolygonAnnotation):
                        # 保存拖拽前的多边形点位置
                        self.original_polygon_points = []
                        for point in annotation.points:
                            self.original_polygon_points.append(QPoint(point))
                        self.drag_start_position = clicked_point

                    self.update()
                    return

            # 只有在点击空白区域时才清除高亮状态
            if not annotation_clicked:
                # 清除选中状态
                self.clear_selection()

    def mouseMoveEvent(self, event):
        # 更新鼠标位置
        self.mouse_pos = event.pos()

        # 调整坐标以考虑图片偏移（现在图片始终在左上角，所以偏移为0）
        offset_x = 0
        offset_y = 0
        adjusted_pos = QPoint(
            int((event.pos().x() - offset_x) / self.scale_factor),
            int((event.pos().y() - offset_y) / self.scale_factor)
        )

        # 矩形框绘制和操作处理
        if self.drawing and self.current_rectangle:
            # 更新当前矩形框的结束点
            self.current_rectangle.setBottomRight(adjusted_pos)
            self.update()
        elif self.dragging and self.selected_annotation and isinstance(self.selected_annotation, RectangleAnnotation):
            # 计算鼠标移动的距离
            offset = adjusted_pos - self.drag_start_point
            # 更新选中矩形框的位置
            new_top_left = self.drag_annotation_start_pos + offset
            self.selected_annotation.rectangle.moveTo(new_top_left)
            self.update()

        elif self.resizing and self.selected_annotation and isinstance(self.selected_annotation,
                                                                       RectangleAnnotation) and self.resize_handle:
            # 根据不同的控制点调整矩形框大小
            start_rect = self.resize_rectangle_start_rect
            offset = adjusted_pos - self.drag_start_point

            if self.resize_handle == "top_left":
                new_top_left = start_rect.topLeft() + offset
                self.selected_annotation.rectangle.setTopLeft(new_top_left)
            elif self.resize_handle == "top_right":
                new_top_right = start_rect.topRight() + offset
                self.selected_annotation.rectangle.setTopRight(new_top_right)
            elif self.resize_handle == "bottom_left":
                new_bottom_left = start_rect.bottomLeft() + offset
                self.selected_annotation.rectangle.setBottomLeft(new_bottom_left)
            elif self.resize_handle == "bottom_right":
                new_bottom_right = start_rect.bottomRight() + offset
                self.selected_annotation.rectangle.setBottomRight(new_bottom_right)

            self.update()

        # 多边形拖拽处理
        elif self.dragging and self.selected_annotation and isinstance(self.selected_annotation, PolygonAnnotation):
            # 计算鼠标移动的距离
            offset = adjusted_pos - self.drag_start_position

            # 移动选中的多边形
            for i, point in enumerate(self.selected_annotation.points):
                self.selected_annotation.points[i] = self.original_polygon_points[i] + offset

            self.update()
        # 多边形调整大小处理（控制点拖拽）
        elif self.resizing and self.selected_annotation and isinstance(self.selected_annotation,
                                                                       PolygonAnnotation) and self.selected_control_point:
            # 计算鼠标移动的距离
            offset = adjusted_pos - self.drag_start_position

            # 调整选中控制点的位置
            annotation, point_index = self.selected_control_point
            if 0 <= point_index < len(annotation.points):
                annotation.points[point_index] = self.original_polygon_points[point_index] + offset
                self.update()

        # 多边形顶点拖拽处理（通过selected_point_info）
        elif self.resizing and self.selected_annotation and isinstance(self.selected_annotation,
                                                                       PolygonAnnotation) and self.selected_point_info:
            # 计算鼠标移动的距离
            offset = adjusted_pos - self.drag_start_position

            # 调整选中点的位置
            poly_index, point_index = self.selected_point_info
            if poly_index >= 0 and poly_index < len(self.annotations):
                polygon = self.annotations[poly_index]
                if point_index < len(polygon.points):
                    polygon.points[point_index] = self.original_polygon_points[point_index] + offset
                    self.update()
        else:
            # 不满足任何特殊条件时，仍然需要更新鼠标位置
            self.update()

        # 直接调用方法更新详情面板，而不是使用信号
        if self.preview_panel:
            annotations = self.get_annotations()
            self.preview_panel.details_panel.update_annotations(annotations)

    def mouseReleaseEvent(self, event):
        # 调整坐标以考虑图片偏移（现在图片始终在左上角，所以偏移为0）
        offset_x = 0
        offset_y = 0
        adjusted_pos = QPoint(
            int((event.pos().x() - offset_x) / self.scale_factor),
            int((event.pos().y() - offset_y) / self.scale_factor)
        )

        # 矩形框处理
        if self.drawing and self.current_rectangle:
            # 设置当前矩形框的最终结束点
            self.current_rectangle.setBottomRight(adjusted_pos)

            # 只有当矩形框有足够的大小时才添加并弹出输入框
            if self.current_rectangle.width() > 5 and self.current_rectangle.height() > 5:
                # 创建新的矩形注解对象
                new_annotation = RectangleAnnotation(self.current_rectangle)
                new_annotation.id = len(self.annotations)  # 使用当前annotations列表长度作为ID
                self.annotations.append(new_annotation)

                # 使用当前标注内容作为标签
                if self.annotation_mode and self.current_annotation_label:
                    new_annotation.label = self.current_annotation_label
                else:
                    # 如果没有标注内容，弹出输入框请求标签信息
                    label, ok = QInputDialog.getText(self, "标注信息", "请输入标注内容:")
                    if ok and label:
                        new_annotation.label = label
                    else:
                        # 如果用户取消输入，则从列表中移除矩形
                        self.annotations.remove(new_annotation)
                        new_annotation = None  # 确保new_annotation变量已定义
            else:
                # 如果矩形太小，则不添加到列表中
                new_annotation = None  # 确保new_annotation变量已定义

            # 重置当前矩形框
            self.current_rectangle = None
            self.drawing = False
            self.update()
            # 保存YOLO标注
            self.save_yolo_annotations()
            # 直接调用方法更新详情面板，而不是使用信号
            if self.preview_panel:
                annotations = self.get_annotations()
                self.preview_panel.details_panel.update_annotations(annotations)
        elif self.dragging or self.resizing:
            # 完成拖动或调整大小操作
            self.dragging = False
            self.resizing = False
            self.resize_handle = None
            self.update()
            # 保存YOLO标注
            self.save_yolo_annotations()
            # 直接调用方法更新详情面板，而不是使用信号
            if self.preview_panel:
                annotations = self.get_annotations()
                self.preview_panel.details_panel.update_annotations(annotations)
        elif self.dragging or self.resizing:
            # 完成拖动或调整大小操作
            self.dragging = False
            self.resizing = False
            self.original_polygon_points = []
            self.update()
            # 保存YOLO标注
            self.save_yolo_annotations()
            # 直接调用方法更新详情面板，而不是使用信号
            if self.preview_panel:
                annotations = self.get_annotations()
                self.preview_panel.details_panel.update_annotations(annotations)
        elif not self.drawing:
            # 如果不是在绘制状态，保持当前选择不变
            self.update()

    def mouseDoubleClickEvent(self, event):
        """处理鼠标双击事件"""
        if self.pixmap:
            # 调整双击坐标以考虑图片偏移（现在图片始终在左上角，所以偏移为0）
            offset_x = 0
            offset_y = 0
            clicked_point = QPoint(
                int((event.pos().x() - offset_x) / self.scale_factor),
                int((event.pos().y() - offset_y) / self.scale_factor)
            )

            # 检查是否双击了某个已存在的注解
            for annotation in self.annotations:
                if annotation.contains_point(clicked_point):
                    # 双击注解时编辑标签
                    self.edit_annotation_label(annotation)
                    return

        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        """自定义绘制事件，绘制图像和所有标注元素"""
        # 创建绘图器
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # 计算图片左上角对齐的偏移量（始终为0，0）
        x = 0
        y = 0

        if self.scaled_pixmap and not self.scaled_pixmap.isNull():
            # 直接绘制预缩放的图片，避免在paintEvent中实时缩放
            painter.drawPixmap(x, y, self.scaled_pixmap)
        elif self.pixmap and not self.pixmap.isNull():
            # 如果没有预缩放的图片，使用旧的方式（后备方案）
            # 获取设备像素比率
            device_pixel_ratio = self.devicePixelRatioF()

            scaled_pixmap = self.pixmap.scaled(
                int(self.pixmap.width() * self.scale_factor * device_pixel_ratio),
                int(self.pixmap.height() * self.scale_factor * device_pixel_ratio),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            # 设置正确的devicePixelRatio
            scaled_pixmap.setDevicePixelRatio(device_pixel_ratio)
            painter.drawPixmap(x, y, scaled_pixmap)

        # 绘制标注提示信息
        if self.show_annotation_hint and self.annotation_mode and self.current_annotation_label:
            painter.setPen(QPen(Qt.red, 2))
            font = QFont()
            font.setPointSize(16)
            painter.setFont(font)

            # 绘制半透明背景框
            text = f"标注模式: {self.current_annotation_label}"

            text_rect = painter.fontMetrics().boundingRect(text)
            hint_rect = QRect(10, 10, text_rect.width() + 20, text_rect.height() + 10)
            # 使用半透明黄色背景
            painter.fillRect(hint_rect, QColor(255, 255, 0, 128))  # 50% 透明度
            painter.drawRect(hint_rect)

            # 绘制文本
            painter.drawText(hint_rect, Qt.AlignCenter, text)

        # 绘制所有已完成的注解
        for annotation in self.annotations:
            # 临时设置选中状态
            original_selected = annotation.selected
            # 如果是当前选中的注解或者有选中的控制点属于该注解，则设置为选中状态
            annotation.selected = (annotation == self.selected_annotation) or \
                                  (self.selected_control_point is not None and self.selected_control_point[0] == annotation)

            # 检查是否在高亮列表中
            original_highlighted = annotation.highlighted
            if annotation in self.highlighted_annotations:
                annotation.highlighted = True

            # 传递选中的控制点信息给draw方法（仅对PolygonAnnotation）
            if isinstance(annotation, PolygonAnnotation):
                # 在调用draw方法前，我们需要传递偏移量信息
                # 这里我们通过修改scale_factor来传递偏移信息
                annotation.draw(painter, self.scale_factor, self.selected_control_point)
            else:
                annotation.draw(painter, self.scale_factor)

            # 恢复原始状态
            annotation.selected = original_selected
            annotation.highlighted = original_highlighted

        # 绘制当前正在绘制的矩形框
        if self.current_rectangle:
            # 创建缩放后的矩形
            scaled_current_rect = QRect(
                int(self.current_rectangle.x() * self.scale_factor) + x,
                int(self.current_rectangle.y() * self.scale_factor) + y,
                int(self.current_rectangle.width() * self.scale_factor),
                int(self.current_rectangle.height() * self.scale_factor)
            )
            painter.setPen(QPen(Qt.red, 1, Qt.SolidLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(scaled_current_rect)

        # 绘制当前正在绘制的多边形
        current_polygon = self.current_polygon
        if len(current_polygon.points) > 1:
            painter.setPen(QPen(Qt.red, 1, Qt.SolidLine))  # 确保线条宽度为1

            # 绘制点之间的连接线（缩放后）
            scaled_points = []
            for point in current_polygon.points:
                scaled_points.append(QPoint(
                    int(point.x() * self.scale_factor) + x,
                    int(point.y() * self.scale_factor) + y
                ))

            if not current_polygon.closed:
                for i in range(len(scaled_points) - 1):
                    painter.drawLine(scaled_points[i], scaled_points[i + 1])
            else:
                # 如果多边形已经闭合，绘制完整的多边形边框
                for i in range(len(scaled_points)):
                    painter.drawLine(scaled_points[i], scaled_points[(i + 1) % len(scaled_points)])

        elif len(current_polygon.points) == 1:
            # 如果只有一个点，也要显示点
            if current_polygon.points:
                scaled_point = QPoint(
                    int(current_polygon.points[0].x() * self.scale_factor) + x,
                    int(current_polygon.points[0].y() * self.scale_factor) + y
                )
                painter.setPen(QPen(Qt.red, 1, Qt.SolidLine))
                painter.setBrush(Qt.red)
                painter.drawEllipse(scaled_point, 3, 3)  # 保持较小的控制点大小

        # 绘制当前多边形的所有点
        # 只有在特殊情况下才绘制点（如正在绘制、选中点等）
        if self.annotation_mode and self.mode == 'polygon':
            for point_index, point in enumerate(current_polygon.points):
                # 创建缩放后的点
                scaled_point = QPoint(
                    int(point.x() * self.scale_factor) + x,
                    int(point.y() * self.scale_factor) + y
                )

                # 检查是否选中了点 (仅在多边形闭合后)
                if (current_polygon.closed and self.selected_point_info is not None and
                        self.selected_point_info[0] == -1 and  # -1表示当前多边形
                        self.selected_point_info[1] == point_index):
                    # 选中的点用绿色圆形点绘制（更小更精细）
                    painter.setPen(QPen(Qt.green, 1, Qt.SolidLine))
                    painter.setBrush(Qt.green)
                    painter.drawEllipse(scaled_point, 4, 4)  # 将控制点大小从8改为4
                elif point_index == 0:
                    # 起始点用较小红色圆形点绘制
                    painter.setPen(QPen(Qt.red, 1, Qt.SolidLine))
                    painter.setBrush(Qt.red)
                    painter.drawEllipse(scaled_point, 4, 4)  # 将控制点大小从6改为4
                    # 如果是起始点且点数大于等于3且未闭合，绘制一个圆圈提示可以点击闭合
                    if len(current_polygon.points) >= 3 and not current_polygon.closed:
                        painter.setPen(QPen(Qt.green, 1, Qt.SolidLine))  # 改为绿色
                        painter.setBrush(Qt.NoBrush)  # 不填充
                        painter.drawEllipse(scaled_point, 8, 8)  # 将提示圆圈大小从12改为8
                else:
                    # 其他点用普通红色圆形点绘制
                    painter.setPen(QPen(Qt.red, 1, Qt.SolidLine))
                    painter.setBrush(Qt.red)
                    painter.drawEllipse(scaled_point, 3, 3)  # 将控制点大小从5改为3

        # 绘制当前多边形的标签
        if current_polygon.label and len(current_polygon.points) > 0:
            # 获取第一个点作为标签显示位置
            first_point = current_polygon.points[0]
            scaled_first_point = QPoint(
                int(first_point.x() * self.scale_factor) + x,
                int(first_point.y() * self.scale_factor) + y
            )

            # 设置文本颜色
            painter.setPen(QPen(Qt.red, 1, Qt.SolidLine))
            # 绘制标签文本（显示在第一个点的左上方，进一步减小距离）
            font = QFont()
            font.setPointSize(10)  # 将字体大小从14改为10
            painter.setFont(font)
            painter.drawText(scaled_first_point.x() - 4, scaled_first_point.y() - 4, current_polygon.label)

        painter.end()

    def set_mode(self, mode):
        """设置标注模式

        Args:
            mode (str): 标注模式，'rectangle' 或 'polygon'
        """
        if mode in ['rectangle', 'polygon']:
            self.mode = mode
            self.update()
        else:
            raise ValueError(f"Unsupported mode: {mode}. Use 'rectangle' or 'polygon.")

    def set_image(self, file_path):
        self.file_path = file_path
        self.pixmap = QPixmap(file_path)
        self.scaled_pixmap = None  # 清除缓存的缩放图片
        self.scale_factor = 1.0  # 重置缩放因子
        self.user_scaled = False  # 重置用户缩放标志
        self.zoom_count = 0  # 重置缩放计数器

        # 重置注解相关属性
        self.annotations = []
        self.current_rectangle = None
        self.selected_annotation = None
        self.highlighted_annotations = []  # 重置高亮注解列表
        self.drawing = False
        self.dragging = False
        self.resizing = False

        # 重置多边形相关属性
        self.current_polygon = PolygonData()
        self.selected_point_info = None
        self.selected_control_point = None
        self.dragging_polygon = False

        # 如果全局标注模式开启，则应用到当前图片
        if ImageLabel.global_annotation_mode:
            self.annotation_mode = True
            self.show_annotation_hint = True
            self.current_annotation_label = ImageLabel.global_annotation_label
            self.setCursor(Qt.CrossCursor)
        else:
            self.annotation_mode = False
            self.show_annotation_hint = False
            self.current_annotation_label = ""
            self.setCursor(Qt.ArrowCursor)

        # 加载已有的YOLO标注
        self.load_yolo_annotations()

        # 自动调整缩放因子以适应显示区域
        self.fit_image_to_view()

    def start_annotation_mode(self):
        """启动标注模式"""
        if not self.annotation_mode:  # 只有在未开启标注模式时才提示
            self.annotation_mode = True
            self.show_annotation_hint = True
            ImageLabel.global_annotation_mode = True  # 设置全局标注模式
            ImageLabel.global_annotation_label = self.current_annotation_label  # 保存全局标注标签
            self.setCursor(Qt.CrossCursor)  # 更改鼠标样式为十字
            self.update()
        else:
            # 如果已经开启了标注模式，则不需要重复开启
            pass

    def exit_annotation_mode(self):
        """退出标注模式"""
        self.annotation_mode = False
        self.show_annotation_hint = False  # 隐藏标注提示
        ImageLabel.global_annotation_mode = False  # 关闭全局标注模式
        ImageLabel.global_annotation_label = ""  # 清空全局标注标签
        self.drawing = False
        self.current_rectangle = None
        self.current_polygon = PolygonData()
        self.setCursor(Qt.ArrowCursor)  # 恢复默认鼠标样式
        self.update()

    def update_auto_scale_factor(self):
        """更新自动缩放因子以适应视图"""
        if not self.pixmap or self.pixmap.isNull():
            return

        # 获取可用显示区域大小
        available_size = self.get_available_size()
        if available_size.width() <= 0 or available_size.height() <= 0:
            return

        # 计算缩放比例，使图片适应可用区域（保持宽高比）
        scale_x = available_size.width() / self.pixmap.width()
        scale_y = available_size.height() / self.pixmap.height()

        # 使用较小的缩放比例，确保整个图片可见（完整显示）
        self.scale_factor = min(scale_x, scale_y)

        # 限制最大缩放比例，避免过度放大
        self.scale_factor = min(self.scale_factor, 5.0)

        # 更新显示
        self.update()

    def sizeHint(self):
        """返回推荐大小"""
        if self.pixmap and not self.pixmap.isNull():
            # 根据当前缩放因子计算推荐大小
            return QSize(
                int(self.pixmap.width() * self.scale_factor),
                int(self.pixmap.height() * self.scale_factor)
            )
        return QSize(400, 300)  # 默认大小

    def minimumSizeHint(self):
        """返回最小大小"""
        return QSize(200, 150)


class ImagePreviewPanel(QWidget):
    """
    图片预览面板类，用于显示图片文件并支持标注功能
    """

    def __init__(self):
        """
        初始化图片预览面板
        """
        super().__init__()
        self.current_file_path = None
        self.is_fullscreen = False  # 添加全屏模式标志
        self.init_ui()

    def init_ui(self):
        self.pixmap = QPixmap()
        self.scale_factor = 1.0
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setPixmap(self.pixmap)
        self.image_label.setScaledContents(True)
        self.image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)

        self.setCentralWidget(self.scroll_area)

        self.zoom_in_action = QAction("Zoom In", self)
        self.zoom_in_action.setShortcut("Ctrl+=")
        self.zoom_in_action.triggered.connect(self.zoom_in)

        self.zoom_out_action = QAction("Zoom Out", self)
        self.zoom_out_action.setShortcut("Ctrl+-")
        self.zoom_out_action.triggered.connect(self.zoom_out)

        self.reset_zoom_action = QAction("Reset Zoom", self)
        self.reset_zoom_action.setShortcut("Ctrl+0")
        self.reset_zoom_action.triggered.connect(self.reset_zoom)

        self.fullscreen_action = QAction("Fullscreen", self)
        self.fullscreen_action.setShortcut("F11")
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)

        self.toolbar = self.addToolBar("Zoom")
        self.toolbar.addAction(self.zoom_in_action)
        self.toolbar.addAction(self.zoom_out_action)
        self.toolbar.addAction(self.reset_zoom_action)
        self.toolbar.addAction(self.fullscreen_action)

    def load_image(self, file_path):
        """
        加载图片文件
        """
        self.current_file_path = file_path
        self.pixmap.load(file_path)
        self.image_label.setPixmap(self.pixmap)
        self.image_label.resize(self.pixmap.size())

    def zoom_in(self):
        """
        放大图片
        """
        self.scale_factor *= 1.25
        self.image_label.resize(
            int(self.pixmap.width() * self.scale_factor),
            int(self.pixmap.height() * self.scale_factor)
        )

    def zoom_out(self):
        """
        缩小图片
        """
        self.scale_factor /= 1.25
        self.image_label.resize(
            int(self.pixmap.width() * self.scale_factor),
            int(self.pixmap.height() * self.scale_factor)
        )

    def reset_zoom(self):
        """
        重置图片缩放
        """
        self.scale_factor = 1.0
        self.image_label.resize(self.pixmap.size())

    def toggle_fullscreen(self):
        """
        切换全屏模式
        """
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            self.showFullScreen()
        else:
            self.showNormal()

    def closeEvent(self, event):
        """
        处理关闭事件
        """
        if self.is_fullscreen:
            self.showNormal()
        event.accept()


class ImageDetailsPanel(QWidget):
    """
    图片详情面板类，用于显示图片标注的分类和详细信息
    """

    def __init__(self):
        """
        初始化图片详情面板
        """
        super().__init__()
        self.annotations = []  # 存储当前的标注数据
        self.selected_items = set()  # 存储选中的项
        self.preview_panel = None  # 添加对预览面板的引用
        self.init_ui()

    def init_ui(self):
        """
        初始化用户界面
        """
        layout = QVBoxLayout(self)

        # 创建分类表格
        self.class_table = QTableWidget()
        self.class_table.setColumnCount(1)
        self.class_table.setHorizontalHeaderLabels(["分类"])
        self.class_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.class_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.class_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.class_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.class_table.verticalHeader().setVisible(False)

        # 创建详情表格
        self.detail_table = QTableWidget()
        self.detail_table.setColumnCount(3)
        self.detail_table.setHorizontalHeaderLabels(["形状", "标签", "点位"])
        self.detail_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.detail_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.detail_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.detail_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.detail_table.verticalHeader().setVisible(False)

        # 连接信号槽
        self.class_table.itemSelectionChanged.connect(self.on_class_selection_changed)
        self.detail_table.itemSelectionChanged.connect(self.on_detail_selection_changed)

        # 添加到布局
        layout.addWidget(self.class_table, 1)
        layout.addWidget(self.detail_table, 2)

        self.setLayout(layout)

    def update_annotations(self, annotations):
        """
        更新标注数据

        Args:
            annotations (list): 标注数据列表
        """
        self.annotations = annotations
        self.refresh_class_table()
        self.refresh_detail_table()

    def refresh_class_table(self):
        """
        刷新分类表格
        """
        self.class_table.setRowCount(0)

        # 获取所有唯一的标签
        labels = list(set(annotation.get('label', '') for annotation in self.annotations))
        labels.sort()

        self.class_table.setRowCount(len(labels))
        for i, label in enumerate(labels):
            item = QTableWidgetItem(label)
            item.setData(Qt.UserRole, label)  # 存储标签数据
            self.class_table.setItem(i, 0, item)

    def refresh_detail_table(self):
        """
        刷新详情表格
        """
        self.detail_table.setRowCount(0)

        self.detail_table.setRowCount(len(self.annotations))
        for i, annotation in enumerate(self.annotations):
            # 形状列
            shape_type = annotation.get('type', 'unknown')
            shape_item = QTableWidgetItem(shape_type)
            shape_item.setData(Qt.UserRole, annotation)  # 存储完整的标注数据
            self.detail_table.setItem(i, 0, shape_item)

            # 标签列
            label = annotation.get('label', '')
            label_item = QTableWidgetItem(label)
            label_item.setData(Qt.UserRole, annotation)  # 存储完整的标注数据
            self.detail_table.setItem(i, 1, label_item)

            # 点位列
            points_text = ""
            if shape_type == 'rectangle':
                rect = annotation.get('rectangle')
                if rect:
                    points_text = f"({rect.x()}, {rect.y()}) - ({rect.right()}, {rect.bottom()})"
            elif shape_type == 'polygon':
                points = annotation.get('points', [])
                points_text = ", ".join([f"({p.x()}, {p.y()})" for p in points])

            points_item = QTableWidgetItem(points_text)
            points_item.setData(Qt.UserRole, annotation)  # 存储完整的标注数据
            self.detail_table.setItem(i, 2, points_item)

    def on_class_selection_changed(self):
        """
        处理分类选择变化事件
        """
        selected_labels = []
        for item in self.class_table.selectedItems():
            label = item.data(Qt.UserRole)
            if label not in selected_labels:
                selected_labels.append(label)

        if selected_labels:
            # 直接调用预览面板的方法，使用标签高亮
            if self.preview_panel:
                self.preview_panel.image_label.highlight_annotations_by_labels(selected_labels)
        else:
            # 直接调用预览面板的方法
            if self.preview_panel:
                self.preview_panel.image_label.clear_selection()

    def on_detail_selection_changed(self):
        """
        处理详情选择变化事件
        """
        selected_annotations = []
        for item in self.detail_table.selectedItems():
            annotation = item.data(Qt.UserRole)
            if annotation not in selected_annotations:
                selected_annotations.append(annotation)

        if selected_annotations:
            if self.preview_panel:
                self.preview_panel.image_label.highlight_annotations_by_data(selected_annotations)

        else:
            # 直接调用预览面板的方法
            if self.preview_panel:
                self.preview_panel.image_label.clear_selection()

    def keyPressEvent(self, event):
        """
        处理键盘按键事件

        Args:
            event: 键盘事件
        """
        if event.key() == Qt.Key_Delete:
            # 获取选中的标注
            selected_annotations = []

            # 检查分类表中的选中项
            for item in self.class_table.selectedItems():
                label = item.data(Qt.UserRole)
                matching_annotations = [ann for ann in self.annotations if ann.get('label') == label]
                for ann in matching_annotations:
                    if ann not in selected_annotations:
                        selected_annotations.append(ann)

            # 检查详情表中的选中项
            for item in self.detail_table.selectedItems():
                annotation = item.data(Qt.UserRole)
                if annotation not in selected_annotations:
                    selected_annotations.append(annotation)

            if selected_annotations:
                # 直接调用预览面板的方法
                if self.preview_panel:
                    for annotation_data in selected_annotations:
                        self.preview_panel.image_label.delete_annotation_by_data(annotation_data)
                    # 更新详情面板
                    annotations = self.preview_panel.image_label.get_annotations()
                    self.update_annotations(annotations)
        else:
            super().keyPressEvent(event)

    def clear_selection(self):
        """
        清除所有选中状态
        """
        self.class_table.clearSelection()
        self.detail_table.clearSelection()
        # 直接调用预览面板的方法
        if self.preview_panel:
            self.preview_panel.image_label.clear_selection()

    def select_annotation_by_data(self, annotation_data):
        """
        根据标注数据选中对应的项

        Args:
            annotation_data (dict): 标注数据，包含类型、标签等信息
        """
        if not annotation_data:
            return

        # 在详情表中查找匹配的标注
        for row in range(self.detail_table.rowCount()):
            for col in range(self.detail_table.columnCount()):
                item = self.detail_table.item(row, col)
                if item:
                    item_data = item.data(Qt.UserRole)
                    if item_data and self._is_annotation_match(item_data, annotation_data):
                        # 选中匹配的行
                        self.detail_table.selectRow(row)

        # 如果在详情表中没有找到，尝试在分类表中查找
        target_label = annotation_data.get('label', '')
        for row in range(self.class_table.rowCount()):
            item = self.class_table.item(row, 0)
            if item and item.data(Qt.UserRole) == target_label:
                # 选中匹配的行
                self.class_table.selectRow(row)

    def _is_annotation_match(self, item_data, annotation_data):
        """
        检查两个标注数据是否匹配

        Args:
            item_data (dict): 表格项中的标注数据
            annotation_data (dict): 要匹配的标注数据

        Returns:
            bool: 是否匹配
        """
        # 检查类型是否匹配
        if item_data.get('type') != annotation_data.get('type'):
            return False

        # 检查标签是否匹配
        if item_data.get('label') != annotation_data.get('label'):
            return False

        # 对于矩形，检查矩形是否相同
        if item_data.get('type') == 'rectangle' and annotation_data.get('type') == 'rectangle':
            rect1 = item_data.get('rectangle')
            rect2 = annotation_data.get('rectangle')
            if rect1 and rect2:
                return (rect1.x() == rect2.x() and
                        rect1.y() == rect2.y() and
                        rect1.width() == rect2.width() and
                        rect1.height() == rect2.height())

        # 对于多边形，检查点是否相同
        elif item_data.get('type') == 'polygon' and annotation_data.get('type') == 'polygon':
            points1 = item_data.get('points', [])
            points2 = annotation_data.get('points', [])
            if len(points1) == len(points2):
                for p1, p2 in zip(points1, points2):
                    if p1.x() != p2.x() or p1.y() != p2.y():
                        return False
                return True

        return True


class ImagePreviewPanel(QWidget):
    """
    图片预览面板类，专门用于显示图片文件的内容和标注功能
    """

    def __init__(self, width=None, height=None):
        """
        初始化图片预览面板

        Args:
            width (int, optional): 面板宽度
            height (int, optional): 面板高度
        """
        super().__init__()
        # 存储尺寸参数作为内部属性
        self.panel_width = width
        self.panel_height = height

        self.init_ui()
        self.current_pixmap = None  # 保存当前图片的pixmap用于缩放
        self.scale_factor = 1.0  # 缩放因子
        self.is_fullscreen = False  # 添加全屏模式标志
        self.current_file_path = None  # 当前文件路径

        # 设置焦点策略，确保能接收键盘事件
        self.setFocusPolicy(Qt.StrongFocus)

    def init_ui(self):
        """
        初始化图片预览面板的用户界面
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建主分割器
        self.main_splitter = QSplitter(Qt.Horizontal)

        # 如果有尺寸参数，则设置分割器的尺寸
        if self.panel_width is not None and self.panel_height is not None:
            # 确保总宽度不超过指定宽度，预留一些空间避免滚动条
            total_width = self.panel_width - 20  # 预留20像素空间
            total_height = self.panel_height - 20  # 预留20像素空间

            self.main_splitter.setMinimumWidth(total_width)
            self.main_splitter.setMinimumHeight(total_height)

            # 计算图片容器和详情面板的宽度分配
            # 考虑到详情面板需要一定的宽度来显示信息，我们给它20%的空间
            details_panel_width = int(total_width * 0.2)  # 20%宽度给详情面板
            image_container_width = total_width - details_panel_width  # 剩余宽度给图片容器

            # 确保详情面板有最小宽度
            if details_panel_width < 200:
                details_panel_width = 200
                image_container_width = total_width - details_panel_width

            # 设置分割器大小
            self.main_splitter.setSizes([image_container_width, details_panel_width])

        # 创建左侧面板（图片标注）
        self.image_container = QWidget()
        self.image_layout = QVBoxLayout(self.image_container)
        self.image_layout.setContentsMargins(0, 0, 0, 0)

        # 创建工具栏
        self.toolbar = QHBoxLayout()
        self.toolbar.setAlignment(Qt.AlignLeft)
        self.toolbar.setSpacing(5)
        self.toolbar.setContentsMargins(5, 5, 5, 5)  # 添加边距，避免按钮紧贴边框

        # 创建标注模式按钮，使用图标形式
        self.rect_button = QPushButton("")  # 矩形图标
        self.rect_button.setToolTip("矩形标注模式 (点击切换)")
        self.polygon_button = QPushButton("")  # 多边形图标
        self.polygon_button.setToolTip("多边形标注模式 (点击切换)")

        # 为按钮添加图标
        # 创建矩形图标
        rect_pixmap = QPixmap(20, 20)
        rect_pixmap.fill(Qt.transparent)
        rect_painter = QPainter(rect_pixmap)
        rect_painter.setPen(QPen(Qt.black, 1))
        rect_painter.drawRect(4, 4, 12, 12)
        rect_painter.end()
        self.rect_button.setIcon(QIcon(rect_pixmap))

        # 创建多边形图标
        polygon_pixmap = QPixmap(20, 20)
        polygon_pixmap.fill(Qt.transparent)
        polygon_painter = QPainter(polygon_pixmap)
        polygon_painter.setPen(QPen(Qt.black, 1))
        polygon_points = [QPoint(10, 2), QPoint(18, 10), QPoint(10, 18), QPoint(2, 10)]
        polygon_painter.drawPolygon(polygon_points, 4)
        polygon_painter.end()
        self.polygon_button.setIcon(QIcon(polygon_pixmap))

        # 设置按钮为可选中状态
        self.rect_button.setCheckable(True)
        self.polygon_button.setCheckable(True)
        self.rect_button.setChecked(True)  # 默认选中矩形模式

        # 创建按钮组确保只有一个按钮被选中
        from PyQt5.QtWidgets import QButtonGroup
        self.button_group = QButtonGroup()
        self.button_group.addButton(self.rect_button, 0)
        self.button_group.addButton(self.polygon_button, 1)

        # 连接按钮事件
        self.rect_button.clicked.connect(self.set_rectangle_mode)
        self.polygon_button.clicked.connect(self.set_polygon_mode)

        # 添加按钮到工具栏
        self.toolbar.addWidget(self.rect_button)
        self.toolbar.addWidget(self.polygon_button)

        # 创建快捷键说明标签并添加到工具栏
        from PyQt5.QtWidgets import QLabel
        self.shortcut_label = QLabel("快捷键: W/Q(标注模式), A/D(前后图片), Delete(删除), F11(全屏)")
        self.shortcut_label.setStyleSheet("color: gray; font-size: 10px;")
        self.toolbar.addWidget(self.shortcut_label)
        self.toolbar.addStretch()

        # 添加工具栏到图片布局
        self.image_layout.addLayout(self.toolbar)

        # 创建滚动区域用于显示大图像
        from PyQt5.QtWidgets import QScrollArea
        self.scroll_area = CustomScrollArea()
        self.scroll_area.setWidgetResizable(False)  # 设置为False，让ImageLabel控制自己的大小
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)  # 移除边框

        # 创建图片标签
        self.image_label = ImageLabel()
        # 设置预览面板引用，用于直接调用方法更新详情面板
        self.image_label.preview_panel = self

        # 将图片标签添加到滚动区域
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; }")  # 移除滚动区域边框

        # 将滚动区域添加到图片布局
        self.image_layout.addWidget(self.scroll_area)

        # 创建右侧面板（详情）
        self.details_panel = ImageDetailsPanel()
        # 设置预览面板引用，用于直接调用方法更新详情面板
        self.details_panel.preview_panel = self

        # 添加到分割器
        self.main_splitter.addWidget(self.image_container)
        self.main_splitter.addWidget(self.details_panel)

        # 设置初始大小比例
        self.main_splitter.setSizes([900, 150])  # 左侧占更大比例，右侧占较小比例

        layout.addWidget(self.main_splitter)
        self.setLayout(layout)

    def keyPressEvent(self, event):
        """
        处理键盘按键事件

        Args:
            event: 键盘事件
        """
        # 检查是否按下了DELETE键
        if event.key() == Qt.Key_Delete:
            # 检查是否有选中的标注框
            if self.image_label.has_selected_annotation():
                # 删除当前选中的标注框
                self.image_label.delete_selected()
                # 更新详情面板
                annotations = self.image_label.get_annotations()
                self.details_panel.update_annotations(annotations)
                event.accept()
                return
            else:
                # 如果没有选中标注框，将事件向上传递
                super().keyPressEvent(event)
                return

        # 检查是否按下了W键，开启全局标注模式
        if event.key() == Qt.Key_W:
            if not self.image_label.annotation_mode:
                # 弹出输入框获取标注标签
                label, ok = QInputDialog.getText(self, "全局标注模式", "请输入标注标签:")
                if ok and label:
                    # 启动全局标注模式
                    ImageLabel.global_annotation_mode = True
                    ImageLabel.global_annotation_label = label
                    self.image_label.annotation_mode = True
                    self.image_label.show_annotation_hint = True
                    self.image_label.current_annotation_label = label
                    self.image_label.setCursor(Qt.CrossCursor)
                    self.image_label.update()
                    # 更新详情面板
                    annotations = self.image_label.get_annotations()
                    self.details_panel.update_annotations(annotations)
            event.accept()
            return

        # 检查是否按下了Q键，退出标注模式
        elif event.key() == Qt.Key_Q:
            if self.image_label.annotation_mode:
                # 退出标注模式
                self.image_label.exit_annotation_mode()
                # 更新详情面板
                annotations = self.image_label.get_annotations()
                self.details_panel.update_annotations(annotations)
            event.accept()
            return

        # 其他按键事件交给父类处理
        super().keyPressEvent(event)

    def set_panel_size(self, width, height):
        """
        设置面板尺寸

        Args:
            width (int): 面板宽度
            height (int): 面板高度
        """
        try:
            # 预留空间给工具栏和边距，避免滚动条出现
            reserved_height = 60  # 工具栏高度 + 边距
            available_height = height - reserved_height

            # 设置主分割器的尺寸
            self.main_splitter.setMinimumWidth(width)
            self.main_splitter.setMinimumHeight(available_height)
            self.main_splitter.resize(width, available_height)

            # 计算图片容器和详情面板的宽度分配
            # 考虑到详情面板需要一定的宽度来显示信息，我们给它20%的空间
            image_container_width = int(width * 0.8)  # 80%宽度给图片容器
            details_panel_width = int(width * 0.2)  # 20%宽度给详情面板

            # 确保详情面板有最小宽度
            if details_panel_width < 200:
                details_panel_width = 200
                image_container_width = width - details_panel_width

            # 设置分割器大小
            self.main_splitter.setSizes([image_container_width, details_panel_width])

            # 触发图片重新适应视图大小
            if hasattr(self, 'image_label') and self.image_label:
                self.image_label.fit_image_to_view()

            logger.debug(f"设置图片预览面板尺寸: {width}x{height}")
        except Exception as e:
            logger.error(f"设置图片预览面板尺寸时发生异常: {str(e)}")

    def set_fullscreen(self, fullscreen):
        """
        设置全屏模式

        Args:
            fullscreen (bool): 是否进入全屏模式
        """
        self.is_fullscreen = fullscreen
        # 如果进入全屏模式，触发图片重新适应视图大小
        if fullscreen:
            # 触发图片重新适应视图大小
            self.image_label.fit_image_to_view()

    def show_image_with_annotation(self, file_path):
        """
        显示带标注功能的图片

        Args:
            file_path (str): 图片文件路径
        """
        self.current_file_path = file_path
        self.image_label.set_image(file_path)
        # 同步缩放因子
        self.image_label.scale_factor = self.image_label.scale_factor
        # 设置预览面板引用，用于直接调用方法更新详情面板
        self.image_label.preview_panel = self

        # 更新详情面板
        annotations = self.image_label.get_annotations()
        self.details_panel.update_annotations(annotations)

        # 设置焦点到预览面板，确保能接收键盘事件
        self.setFocus()
        return True

    def set_rectangle_mode(self):
        """
        设置为矩形模式
        """
        self.image_label.set_mode('rectangle')

    def set_polygon_mode(self):
        """
        设置为多边形模式
        """
        self.image_label.set_mode('polygon')

    def select_annotation(self, annotation_data):
        """
        选中指定的标注

        Args:
            annotation_data: 标注数据
        """
        # 使用ImageLabel内部的方法根据数据选中注解
        self.image_label.select_annotation_by_data(annotation_data)

        # 同步更新详情面板
        annotations = self.image_label.get_annotations()
        self.details_panel.update_annotations(annotations)

    def clear_highlights(self):
        """
        清除所有高亮状态
        """
        self.image_label.clear_highlights()

    def clear_highlights_from_details(self, data_to_clear):
        """
        从详情面板接收清除高亮的请求，并处理需要清除高亮的标注框

        Args:
            data_to_clear: 需要清除高亮的数据
        """
        self.image_label.clear_highlights(data_to_clear)

    def delete_annotation(self, annotation):
        """
        删除指定的标注

        Args:
            annotation: 要删除的标注信息
        """
        # 使用ImageLabel内部的方法根据数据删除注解
        self.image_label.delete_annotation_by_data(annotation)

        # 更新详情面板
        annotations = self.image_label.get_annotations()
        self.details_panel.update_annotations(annotations)


class CustomScrollArea(QScrollArea):
    """自定义滚动区域，用于控制滚动灵敏度"""



    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置滚动步长因子，控制滚动灵敏度
        self.horizontal_scroll_factor = 0.5  # 水平滚动步长因子，值越小滚动越慢
        self.vertical_scroll_factor = 1.0    # 垂直滚动步长因子

    def wheelEvent(self, event):
        """处理鼠标滚轮事件，调整滚动灵敏度"""
        # 检查是否是Ctrl/Cmd+滚轮组合，如果是则传递给子组件处理
        if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            # 直接将事件传递给子组件（ImageLabel）处理
            if self.widget() and hasattr(self.widget(), 'wheelEvent'):
                self.widget().wheelEvent(event)
            else:
                super().wheelEvent(event)
        else:
            # 获取滚动条
            horizontal_scrollbar = self.horizontalScrollBar()
            vertical_scrollbar = self.verticalScrollBar()

            # 检查是否按住了Shift键，按住Shift键时进行水平滚动
            if event.modifiers() & Qt.ShiftModifier:
                # 检查是否有水平滚动条且可见
                if horizontal_scrollbar.isVisible():
                    # 调试信息
                    angle_delta_y = event.angleDelta().y()
                    angle_delta_x = event.angleDelta().x()

                    # 计算滚动步长，优先使用x轴的值，如果没有则使用y轴的值
                    scroll_step = (angle_delta_x if angle_delta_x != 0 else angle_delta_y) * self.horizontal_scroll_factor
                    new_value = horizontal_scrollbar.value() - scroll_step

                    # 确保滚动值在有效范围内
                    min_value = horizontal_scrollbar.minimum()
                    max_value = horizontal_scrollbar.maximum()
                    new_value = max(min_value, min(new_value, max_value))

                    horizontal_scrollbar.setValue(int(new_value))
                    event.accept()
                else:
                    super().wheelEvent(event)
            else:
                # 检查是否有垂直滚动条且可见
                if vertical_scrollbar.isVisible():
                    # 垂直滚动
                    # 计算滚动步长
                    scroll_step = event.angleDelta().y() * self.vertical_scroll_factor
                    new_value = vertical_scrollbar.value() - scroll_step

                    # 确保滚动值在有效范围内
                    min_value = vertical_scrollbar.minimum()
                    max_value = vertical_scrollbar.maximum()
                    new_value = max(min_value, min(new_value, max_value))

                    vertical_scrollbar.setValue(int(new_value))
                    event.accept()
                else:
                    # 如果没有垂直滚动条，但有水平滚动条，则进行水平滚动
                    if horizontal_scrollbar.isVisible():
                        # 计算滚动步长
                        scroll_step = event.angleDelta().y() * self.horizontal_scroll_factor
                        new_value = horizontal_scrollbar.value() - scroll_step

                        # 确保滚动值在有效范围内
                        min_value = horizontal_scrollbar.minimum()
                        max_value = horizontal_scrollbar.maximum()
                        new_value = max(min_value, min(new_value, max_value))

                        horizontal_scrollbar.setValue(int(new_value))
                        event.accept()
                    else:
                        super().wheelEvent(event)

