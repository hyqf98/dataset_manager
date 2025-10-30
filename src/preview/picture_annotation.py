import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QAction, QFileDialog, QInputDialog, QWidget, QHBoxLayout, QPushButton, QButtonGroup, QToolBar
from PyQt5.QtGui import QPixmap, QPainter, QPen, QImage, QPolygon, QFont
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal
from .yolo_utils import save_yolo_annotations, load_yolo_annotations
import os

from ..logging_config import logger


class Annotation:
    """统一的注解基类"""
    def __init__(self, label=""):
        self.label = label
        self.selected = False
        self.highlighted = False

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
        # 创建缩放后的矩形
        scaled_rect = QRect(
            int(self.rectangle.x() * scale_factor),
            int(self.rectangle.y() * scale_factor),
            int(self.rectangle.width() * scale_factor),
            int(self.rectangle.height() * scale_factor)
        )

        # 根据状态设置画笔
        if self.selected:
            painter.setPen(QPen(Qt.green, 3, Qt.SolidLine))
        elif self.highlighted:
            # 批量选中时使用绿色高亮，线宽与选中状态一致
            painter.setPen(QPen(Qt.green, 3, Qt.SolidLine))
        else:
            painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))

        # 绘制矩形
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(scaled_rect)

        # 绘制标签
        if self.label:
            font = QFont()
            font.setPointSize(14)
            painter.setFont(font)
            text_rect = QRect(scaled_rect.topLeft(), QPoint(
                scaled_rect.right(),
                scaled_rect.top() + 25
            ))
            painter.drawText(text_rect, Qt.AlignCenter, self.label)

        # 如果被选中，绘制控制点
        if self.selected:
            handle_size = 6
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
        self.parent = None  # 添加对父对象的引用

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
            painter.setPen(QPen(Qt.green, 3, Qt.SolidLine))
        elif self.highlighted:
            # 批量选中时使用绿色高亮，线宽与选中状态一致
            painter.setPen(QPen(Qt.green, 3, Qt.SolidLine))
        else:
            painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))

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
                    painter.setPen(QPen(Qt.blue, 2, Qt.SolidLine))  # 蓝色边框
                    painter.setBrush(Qt.yellow)  # 黄色填充
                    painter.drawEllipse(scaled_point, 8, 8)  # 更大的点
                    # 恢复原来的画笔设置
                    painter.setPen(QPen(Qt.green, 1, Qt.SolidLine))
                    painter.setBrush(Qt.green)
                elif point_index == 0:
                    # 起始点用较大绿色圆形点绘制
                    painter.drawEllipse(scaled_point, 6, 6)
                else:
                    # 其他点用普通绿色圆形点绘制
                    painter.drawEllipse(scaled_point, 5, 5)

        # 绘制标签
        if self.label and len(self.points) > 0:
            # 计算多边形的中心点（缩放后）
            scaled_points = []  # 重新计算中心点的缩放点
            for point in self.points:
                scaled_points.append(QPoint(
                    int(point.x() * scale_factor),
                    int(point.y() * scale_factor)
                ))

            center_x = sum(point.x() for point in scaled_points) / len(scaled_points)
            center_y = sum(point.y() for point in scaled_points) / len(scaled_points)

            # 设置文本颜色
            if self.selected:
                painter.setPen(QPen(Qt.green, 1, Qt.SolidLine))
            elif self.highlighted:
                # 批量选中时使用绿色高亮
                painter.setPen(QPen(Qt.green, 1, Qt.SolidLine))
            else:
                painter.setPen(QPen(Qt.red, 1, Qt.SolidLine))
            # 绘制标签文本
            font = QFont()
            font.setPointSize(14)
            painter.setFont(font)
            painter.drawText(int(center_x), int(center_y), self.label)

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


# 用于表示一个矩形框的数据结构
class RectangleInfo:
    """存储矩形框及其标签信息"""

    def __init__(self, rectangle, label=""):
        self.rectangle = rectangle
        self.label = label


class ImageLabel(QLabel):
    # 定义标注更新信号
    annotations_updated = pyqtSignal(object)  # ImageLabel对象本身
    # 当在图片上选中任何标注元素时发出信号
    annotation_selected_in_image = pyqtSignal(object)  # 选中的标注对象(矩形或多边形)，不再传递类型

    def __init__(self):
        super().__init__()
        self.pixmap = None
        self.mode = 'rectangle'  # 默认模式为矩形模式
        self.scale_factor = 1.0  # 添加缩放因子属性，用于控制图片缩放级别
        self.zoom_count = 0       # 添加缩放计数器，用于限制缩放次数
        self.file_path = None     # 图片文件路径
        self.class_names = []    # 类别名称列表
        self.mouse_pos = QPoint()  # 鼠标位置
        self.annotation_mode = False  # 标注模式开关
        self.current_annotation_label = ""  # 当前标注的标签内容

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
        self.dragging_polygon = False  # 是否正在拖拽多边形
        self.drag_start_position = QPoint()  # 拖拽起始位置
        self.original_polygon_points = []  # 拖拽前的多边形点位置

        # 添加一个属性来存储当前选中的控制点
        self.selected_control_point = None  # 当前选中的控制点 (annotation, point_index)

        # 设置焦点策略
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()
        self.setAttribute(Qt.WA_KeyCompression, True)
        self.setMouseTracking(True)
        # 设置默认鼠标样式
        self.setCursor(Qt.ArrowCursor)

    def focusInEvent(self, event):
        """处理获得焦点事件"""
        super().focusInEvent(event)
        # 确保ImageLabel能够接收键盘事件
        self.setAttribute(Qt.WA_KeyCompression, True)

    def set_image(self, file_path):
        self.file_path = file_path
        self.pixmap = QPixmap(file_path)
        self.scale_factor = 1.0  # 重置缩放因子
        self.zoom_count = 0      # 重置缩放计数器

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
        self.dragging_polygon = False

        # 加载已有的YOLO标注
        self.load_yolo_annotations()

        self.setPixmap(self.pixmap)
        self.adjustSize()

    def load_yolo_annotations(self):
        """加载YOLO格式的标注文件"""
        if not self.file_path or not os.path.exists(self.file_path):
            return

        # 加载类别名称
        classes_file = os.path.join(os.path.dirname(self.file_path), 'classes.txt')
        if os.path.exists(classes_file):
            with open(classes_file, 'r', encoding='utf-8') as f:
                self.class_names = [line.strip() for line in f.readlines() if line.strip()]

        # 加载标注信息
        annotations = load_yolo_annotations(self.file_path, self.class_names)
        for annotation in annotations:
            if annotation['type'] == 'rectangle':
                rect_annotation = RectangleAnnotation(annotation['rectangle'], annotation['label'])
                self.annotations.append(rect_annotation)
            elif annotation['type'] == 'polygon':
                polygon_annotation = PolygonAnnotation(annotation['points'], annotation['label'])
                polygon_annotation.closed = True  # 从文件加载的多边形应该是闭合的
                polygon_annotation.parent = self  # 设置父对象引用
                self.annotations.append(polygon_annotation)

        # 发出标注更新信号
        self.annotations_updated.emit(self)

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
        for annotation in self.annotations:
            if isinstance(annotation, RectangleAnnotation):
                annotations.append({
                    'type': 'rectangle',
                    'rectangle': annotation.rectangle,
                    'label': annotation.label
                })
            elif isinstance(annotation, PolygonAnnotation):
                annotations.append({
                    'type': 'polygon',
                    'points': annotation.points,
                    'label': annotation.label
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
                self.selected_annotation is not None)

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
        # 发出标注更新信号
        self.annotations_updated.emit(self)

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
            # 发出标注更新信号
            self.annotations_updated.emit(self)

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
            # 发出标注更新信号
            self.annotations_updated.emit(self)

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
        self.selected_control_point = None  # 添加清除选中的控制点

        # 清除高亮状态
        self.clear_highlights()

        # 更新界面
        self.update()

    def deselect_details_panel(self):
        """
        通知详情面板取消选中状态
        """
        # 发送None来通知详情面板取消所有选中状态
        self.annotation_selected_in_image.emit(None)

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
            # 清除高亮状态
            self.clear_highlights()
            # 发出信号，通知详情面板也选中对应的条目
            self.annotation_selected_in_image.emit(annotation)

    def show_control_points(self, annotation):
        """
        统一方法用于在选中注解时显示控制点

        Args:
            annotation: 要显示控制点的注解对象
        """
        if annotation is None:
            return

        # 设置选中状态
        annotation.selected = True

        # 根据注解类型显示相应的控制点
        if isinstance(annotation, RectangleAnnotation):
            # 矩形显示四个角点
            pass  # 矩形的控制点在draw方法中处理
        elif isinstance(annotation, PolygonAnnotation):
            # 多边形显示所有顶点
            pass  # 多边形的控制点在draw方法中处理

        self.update()

    def select_annotation_by_data(self, annotation_data):
        """
        根据注解数据选中注解

        Args:
            annotation_data: 注解数据字典，包含type和其他相关信息
        """
        # 处理取消选中的情况
        if annotation_data is None:
            # 通知详情面板取消选中状态
            self.deselect_details_panel()
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
            # 如果没有找到匹配的注解，通知详情面板取消选中状态
            self.deselect_details_panel()
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
        logger.debug(f"根据标签高亮注解: {labels}")
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
                    logger.debug(f"找到矩形注解: 标签={annotation.label}")
                elif isinstance(annotation, PolygonAnnotation):
                    annotation_data = {
                        'type': 'polygon',
                        'points': annotation.points,
                        'label': annotation.label
                    }
                    matched_annotations_data.append(annotation_data)
                    logger.debug(f"找到多边形注解: 标签={annotation.label}, 点数={len(annotation.points)}")

        logger.debug(f"总共找到 {len(matched_annotations_data)} 个注解")
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
            clicked_point = event.pos()

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
                        polygon_annotation.parent = self  # 设置父对象引用
                        self.annotations.append(polygon_annotation)
                        # 使用预设标签
                        if self.current_annotation_label:
                            polygon_annotation.label = self.current_annotation_label
                            # 输入标签后通知详情面板更新
                            self.annotation_selected_in_image.emit(polygon_annotation)
                        else:
                            # 否则弹出对话框输入标注信息
                            label, ok = QInputDialog.getText(self, '多边形标注', '请输入标注信息:')
                            if ok:
                                polygon_annotation.label = label
                                # 输入标签后通知详情面板更新
                                self.annotation_selected_in_image.emit(polygon_annotation)
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
                        # 发出标注更新信号
                        self.annotations_updated.emit(self)
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
                    # 只有当点击的不是控制点时才清除selected_control_point
                    if not (self.selected_control_point and self.selected_control_point[0] == polygon):
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

                    # 发出信号，通知详情面板也选中对应的条目
                    self.annotation_selected_in_image.emit(polygon)
                    self.update()
                    return

            # 检查是否点击了某个已存在的注解
            annotation_clicked = False
            for annotation in reversed(self.annotations):  # 从上到下检查（后绘制的在上层）
                if annotation.contains_point(clicked_point):
                    annotation_clicked = True
                    # 选中注解
                    self.selected_annotation = annotation
                    self.drawing = False
                    self.current_rectangle = None
                    self.selected_point_info = None
                    # 只有当点击的不是当前选中的控制点所属的注解时才清除selected_control_point
                    if not (self.selected_control_point and self.selected_control_point[0] == annotation):
                        self.selected_control_point = None  # 清除选中的控制点
                    # 清除高亮状态
                    self.clear_highlights()

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

                    # 发出信号，通知详情面板也选中对应的条目
                    self.annotation_selected_in_image.emit(annotation)
                    self.update()
                    return

            # 只有在点击空白区域时才清除高亮状态
            if not annotation_clicked:
                # 通知详情面板取消选中状态
                self.deselect_details_panel()
                # 清除选中状态
                self.clear_selection()

    def mouseMoveEvent(self, event):
        # 更新鼠标位置
        self.mouse_pos = event.pos()

        # 矩形框绘制和操作处理
        if self.drawing and self.current_rectangle:
            # 更新当前矩形框的结束点
            self.current_rectangle.setBottomRight(event.pos())
            self.update()
        elif self.dragging and self.selected_annotation and isinstance(self.selected_annotation, RectangleAnnotation):
            # 计算鼠标移动的距离
            offset = event.pos() - self.drag_start_point
            # 更新选中矩形框的位置
            new_top_left = self.drag_annotation_start_pos + offset
            self.selected_annotation.rectangle.moveTo(new_top_left)
            self.update()
            # 不在拖动过程中发送信号，避免递归调用
            # self.annotation_selected_in_image.emit(self.selected_annotation)
        elif self.resizing and self.selected_annotation and isinstance(self.selected_annotation, RectangleAnnotation) and self.resize_handle:
            # 根据不同的控制点调整矩形框大小
            start_rect = self.resize_rectangle_start_rect
            offset = event.pos() - self.drag_start_point

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
            offset = event.pos() - self.drag_start_position

            # 移动选中的多边形
            for i, point in enumerate(self.selected_annotation.points):
                self.selected_annotation.points[i] = self.original_polygon_points[i] + offset

            self.update()
        # 多边形调整大小处理（控制点拖拽）
        elif self.resizing and self.selected_annotation and isinstance(self.selected_annotation, PolygonAnnotation) and self.selected_control_point:
            # 计算鼠标移动的距离
            offset = event.pos() - self.drag_start_position

            # 调整选中控制点的位置
            annotation, point_index = self.selected_control_point
            if 0 <= point_index < len(annotation.points):
                annotation.points[point_index] = self.original_polygon_points[point_index] + offset
                self.update()
        # 多边形顶点拖拽处理（通过selected_point_info）
        elif self.resizing and self.selected_annotation and isinstance(self.selected_annotation, PolygonAnnotation) and self.selected_point_info:
            # 计算鼠标移动的距离
            offset = event.pos() - self.drag_start_position

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

    def mouseReleaseEvent(self, event):
        # 矩形框处理
        if self.drawing and self.current_rectangle:
            # 设置当前矩形框的最终结束点
            self.current_rectangle.setBottomRight(event.pos())

            # 只有当矩形框有足够的大小时才添加并弹出输入框
            if self.current_rectangle.width() > 5 and self.current_rectangle.height() > 5:
                # 创建新的矩形注解对象
                new_annotation = RectangleAnnotation(self.current_rectangle)
                self.annotations.append(new_annotation)

                # 使用当前标注内容作为标签
                if self.annotation_mode and self.current_annotation_label:
                    new_annotation.label = self.current_annotation_label
                    # 输入标签后通知详情面板更新
                    self.annotation_selected_in_image.emit(new_annotation)
                else:
                    # 如果没有标注内容，弹出输入框请求标签信息
                    label, ok = QInputDialog.getText(self, "标注信息", "请输入标注内容:")
                    if ok and label:
                        new_annotation.label = label
                        # 输入标签后通知详情面板更新
                        self.annotation_selected_in_image.emit(new_annotation)
                    else:
                        # 如果用户取消输入，则从列表中移除矩形
                        self.annotations.remove(new_annotation)
            # 如果矩形太小，则不添加到列表中

            # 重置当前矩形框
            self.current_rectangle = None
            self.drawing = False
            self.update()
            # 保存YOLO标注
            self.save_yolo_annotations()
            # 发出标注更新信号
            self.annotations_updated.emit(self)
        elif self.dragging or self.resizing:
            # 完成拖动或调整大小操作
            self.dragging = False
            self.resizing = False
            self.resize_handle = None
            # 不再在这里清除selected_control_point
            self.update()
            # 保存YOLO标注
            self.save_yolo_annotations()
            # 发出标注更新信号
            self.annotations_updated.emit(self)
            # 发出信号通知详情面板更新位置
            if self.selected_annotation:
                self.annotation_selected_in_image.emit(self.selected_annotation)
        elif self.dragging or self.resizing:
            # 完成拖动或调整大小操作
            self.dragging = False
            self.resizing = False
            self.original_polygon_points = []
            # 不再在这里清除selected_control_point
            self.update()
            # 保存YOLO标注
            self.save_yolo_annotations()
            # 发出标注更新信号
            self.annotations_updated.emit(self)
            # 发出信号通知详情面板更新位置
            if self.selected_annotation:
                self.annotation_selected_in_image.emit(self.selected_annotation)
        elif not self.drawing:
            # 如果不是在绘制状态，保持当前选择不变
            self.update()

    def mouseDoubleClickEvent(self, event):
        """处理鼠标双击事件"""
        if self.pixmap:
            clicked_point = event.pos()

            # 检查是否双击了某个已存在的注解
            for annotation in self.annotations:
                if annotation.contains_point(clicked_point):
                    # 双击注解时编辑标签
                    self.edit_annotation_label(annotation)
                    return

        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        """自定义绘制事件，绘制图像和所有标注元素"""
        super().paintEvent(event)

        if not self.pixmap:
            return

        # 创建绘图器
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制图像（支持缩放）
        scaled_pixmap = self.pixmap.scaled(
            self.pixmap.width() * self.scale_factor,
            self.pixmap.height() * self.scale_factor,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        painter.drawPixmap(0, 0, scaled_pixmap)

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
                int(self.current_rectangle.x() * self.scale_factor),
                int(self.current_rectangle.y() * self.scale_factor),
                int(self.current_rectangle.width() * self.scale_factor),
                int(self.current_rectangle.height() * self.scale_factor)
            )
            painter.setPen(QPen(Qt.red, 1, Qt.SolidLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(scaled_current_rect)

        # 绘制当前正在绘制的多边形
        current_polygon = self.current_polygon
        if len(current_polygon.points) > 1:
            painter.setPen(QPen(Qt.red, 1, Qt.SolidLine))

            # 绘制点之间的连接线（缩放后）
            scaled_points = []
            for point in current_polygon.points:
                scaled_points.append(QPoint(
                    int(point.x() * self.scale_factor),
                    int(point.y() * self.scale_factor)
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
                    int(current_polygon.points[0].x() * self.scale_factor),
                    int(current_polygon.points[0].y() * self.scale_factor)
                )
                painter.setPen(QPen(Qt.red, 1, Qt.SolidLine))
                painter.setBrush(Qt.red)
                painter.drawEllipse(scaled_point, 3, 3)

        # 绘制当前多边形的所有点
        # 只有在特殊情况下才绘制点（如正在绘制、选中点等）
        if self.annotation_mode and self.mode == 'polygon':
            for point_index, point in enumerate(current_polygon.points):
                # 创建缩放后的点
                scaled_point = QPoint(
                    int(point.x() * self.scale_factor),
                    int(point.y() * self.scale_factor)
                )

                # 检查是否选中了点 (仅在多边形闭合后)
                if (current_polygon.closed and self.selected_point_info is not None and
                        self.selected_point_info[0] == -1 and  # -1表示当前多边形
                        self.selected_point_info[1] == point_index):
                    # 选中的点用绿色圆形点绘制（更大更明显）
                    painter.setPen(QPen(Qt.green, 1, Qt.SolidLine))
                    painter.setBrush(Qt.green)
                    painter.drawEllipse(scaled_point, 8, 8)  # 绘制半径为8的圆形点
                elif point_index == 0:
                    # 起始点用较大红色圆形点绘制
                    painter.setPen(QPen(Qt.red, 1, Qt.SolidLine))
                    painter.setBrush(Qt.red)
                    painter.drawEllipse(scaled_point, 6, 6)  # 绘制半径为6的圆形点
                    # 如果是起始点且点数大于等于3且未闭合，绘制一个圆圈提示可以点击闭合
                    if len(current_polygon.points) >= 3 and not current_polygon.closed:
                        painter.setPen(QPen(Qt.green, 1, Qt.SolidLine))  # 改为绿色
                        painter.setBrush(Qt.NoBrush)  # 不填充
                        painter.drawEllipse(scaled_point, 12, 12)  # 绘制半径为12的圆形提示框
                else:
                    # 其他点用普通红色圆形点绘制
                    painter.setPen(QPen(Qt.red, 1, Qt.SolidLine))
                    painter.setBrush(Qt.red)
                    painter.drawEllipse(scaled_point, 5, 5)  # 绘制半径为5的圆形点

        # 绘制当前多边形的标签
        if current_polygon.label and len(current_polygon.points) > 0:
            # 计算多边形的中心点（缩放后）
            scaled_points = []
            for point in current_polygon.points:
                scaled_points.append(QPoint(
                    int(point.x() * self.scale_factor),
                    int(point.y() * self.scale_factor)
                ))

            center_x = sum(point.x() for point in scaled_points) / len(scaled_points)
            center_y = sum(point.y() for point in scaled_points) / len(scaled_points)

            # 设置文本颜色
            painter.setPen(QPen(Qt.red, 1, Qt.SolidLine))
            # 绘制标签文本
            font = QFont()
            font.setPointSize(14)  # 增大字体
            painter.setFont(font)
            painter.drawText(int(center_x), int(center_y), current_polygon.label)

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

    def start_annotation_mode(self):
        """启动标注模式"""
        self.annotation_mode = True
        self.setCursor(Qt.CrossCursor)  # 更改鼠标样式为十字
        self.update()

    def exit_annotation_mode(self):
        """退出标注模式"""
        self.annotation_mode = False
        self.drawing = False
        self.current_rectangle = None
        self.current_polygon = PolygonData()
        self.setCursor(Qt.ArrowCursor)  # 恢复默认鼠标样式
        self.update()

    def keyPressEvent(self, event):
        """处理键盘按键事件"""
        if event.key() == Qt.Key_Delete:
            self.delete_selected()
        else:
            super().keyPressEvent(event)
