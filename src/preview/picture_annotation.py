import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QAction, QFileDialog, QInputDialog, QWidget, QHBoxLayout, QPushButton, QButtonGroup
from PyQt5.QtGui import QPixmap, QPainter, QPen, QImage, QPolygon, QFont
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal
from .yolo_utils import save_yolo_annotations, load_yolo_annotations
import os


class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Unified Annotation Tool")
        self.setGeometry(100, 100, 800, 600)

        # 创建菜单栏
        open_action = QAction("Open Image", self)
        open_action.triggered.connect(self.open_image)

        # 创建模式切换菜单项
        self.rect_action = QAction("Rectangle Mode", self, checkable=True)
        self.polygon_action = QAction("Polygon Mode", self, checkable=True)
        self.rect_action.setChecked(True)  # 默认为矩形模式
        self.rect_action.triggered.connect(self.switch_to_rectangle_mode)
        self.polygon_action.triggered.connect(self.switch_to_polygon_mode)

        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        file_menu.addAction(open_action)

        mode_menu = menubar.addMenu("Mode")
        mode_menu.addAction(self.rect_action)
        mode_menu.addAction(self.polygon_action)

        # 创建图像显示区域
        self.label = ImageLabel()
        self.label.set_image('/Users/haijun/Documents/图片/无人机数据集/9.jpeg')
        self.setCentralWidget(self.label)

    def open_image(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "", "Image Files (*.png *.jpg *.bmp *.jpeg);;All Files (*)", options=options
        )
        if file_name:
            self.label.set_image(file_name)

    def keyPressEvent(self, event):
        # 监听Delete键，删除选中的标注
        if event.key() == Qt.Key_Delete:
            self.label.delete_selected()
        else:
            super().keyPressEvent(event)

    def switch_to_rectangle_mode(self):
        """切换到矩形模式"""
        self.rect_action.setChecked(True)
        self.polygon_action.setChecked(False)
        self.label.set_mode('rectangle')

    def switch_to_polygon_mode(self):
        """切换到多边形模式"""
        self.rect_action.setChecked(False)
        self.polygon_action.setChecked(True)
        self.label.set_mode('polygon')


# 用于表示一个多边形的数据结构
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
        self.file_path = None     # 图片文件路径
        self.class_names = []    # 类别名称列表
        self.mouse_pos = QPoint()  # 鼠标位置

        # 矩形框相关属性
        self.rectangle_infos = []  # 存储包含标签信息的矩形框
        self.current_rectangle = None  # 当前正在绘制的矩形框
        self.selected_rectangle_info = None  # 当前选中的矩形框信息
        self.highlighted_rectangles = []  # 当前高亮的矩形框列表（仅高亮，不可编辑）
        self.drawing = False
        self.dragging = False  # 是否正在拖动矩形框
        self.resizing = False  # 是否正在调整矩形框大小
        self.drag_start_point = QPoint()  # 拖动起始点
        self.drag_rectangle_start_pos = QPoint()  # 被拖动矩形框的初始位置
        self.resize_handle = None  # 调整大小的控制点位置
        self.resize_rectangle_start_rect = QRect()  # 调整大小时矩形框的初始状态

        # 多边形相关属性
        self.polygons = []  # 存储所有已完成的多边形
        self.current_polygon = PolygonData()  # 当前正在绘制的多边形
        self.selected_polygon_index = None  # 当前选中的多边形索引
        self.selected_point_info = None  # 当前选中的点信息 (polygon_index, point_index)
        self.dragging_polygon = False  # 是否正在拖拽多边形
        self.drag_start_position = QPoint()  # 拖拽起始位置
        self.original_polygon_points = []  # 拖拽前的多边形点位置
        self.highlighted_polygons = []  # 当前高亮的多边形索引列表（仅高亮，不可编辑）

        # 设置焦点策略
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()

    def set_image(self, file_path):
        self.file_path = file_path
        self.pixmap = QPixmap(file_path)
        self.scale_factor = 1.0  # 重置缩放因子

        # 重置矩形框相关属性
        self.rectangle_infos = []
        self.current_rectangle = None
        self.selected_rectangle_info = None
        self.highlighted_rectangles = []  # 重置高亮矩形列表
        self.drawing = False
        self.dragging = False
        self.resizing = False

        # 重置多边形相关属性
        self.polygons = []
        self.current_polygon = PolygonData()
        self.selected_polygon_index = None
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
                rect_info = RectangleInfo(annotation['rectangle'], annotation['label'])
                self.rectangle_infos.append(rect_info)

        # 发出标注更新信号
        self.annotations_updated.emit(self)

    def save_yolo_annotations(self):
        """保存YOLO格式的标注文件"""
        if not self.file_path:
            return

        # 收集所有类别名称
        class_names = []
        for rect_info in self.rectangle_infos:
            if rect_info.label and rect_info.label not in class_names:
                class_names.append(rect_info.label)

        for polygon in self.polygons:
            if polygon.label and polygon.label not in class_names:
                class_names.append(polygon.label)

        if self.current_polygon.label and self.current_polygon.label not in class_names:
            class_names.append(self.current_polygon.label)

        # 保存标注文件
        save_yolo_annotations(self.file_path, self, class_names)

    def set_mode(self, mode):
        """设置当前模式"""
        self.mode = mode
        self.update()

    def get_annotations(self):
        """获取所有标注信息，包括位置和标签

        Returns:
            list: 包含所有标注信息的列表，每个标注包含类型、位置和标签
        """
        annotations = []

        # 添加矩形标注信息
        for rect_info in self.rectangle_infos:
            annotations.append({
                'type': 'rectangle',
                'rectangle': rect_info.rectangle,
                'label': rect_info.label
            })

        # 添加多边形标注信息
        for polygon in self.polygons:
            annotations.append({
                'type': 'polygon',
                'points': polygon.points,
                'label': polygon.label
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
                self.selected_polygon_index is not None or
                self.selected_rectangle_info is not None)

    def delete_selected(self):
        """删除选中的标注（点、多边形或矩形框）"""
        # 如果选中了点
        if self.selected_point_info is not None:
            poly_index, point_index = self.selected_point_info
            # 如果选中的是当前正在绘制的多边形的点
            if poly_index == -1:
                polygon = self.current_polygon
            else:
                polygon = self.polygons[poly_index]

            # 删除选中的点
            del polygon.points[point_index]

            # 如果删除点后点数少于3个，则取消闭合状态并清除标签
            if len(polygon.points) < 3:
                polygon.closed = False
                polygon.label = ""  # 清除标签信息
                # 如果是已完成的多边形，将其移回当前多边形继续编辑
                if poly_index != -1:
                    self.current_polygon = polygon
                    del self.polygons[poly_index]
                    self.selected_polygon_index = -1  # 设置为当前多边形

            # 重置选中点
            self.selected_point_info = None
            self.update()
        elif self.selected_polygon_index is not None:
            # 如果选中了整个多边形，则删除整个多边形
            if self.selected_polygon_index < len(self.polygons):
                del self.polygons[self.selected_polygon_index]
            self.selected_polygon_index = None
            self.update()
        elif self.selected_rectangle_info:
            # 如果选中了矩形框，则删除矩形框
            self.rectangle_infos.remove(self.selected_rectangle_info)
            self.selected_rectangle_info = None
            self.update()

        # 保存YOLO标注
        self.save_yolo_annotations()
        # 发出标注更新信号
        self.annotations_updated.emit(self)

    def edit_rectangle_label(self, rect_info):
        """编辑矩形框的标签"""
        label, ok = QInputDialog.getText(self, "编辑标注信息", "请输入标注内容:", text=rect_info.label)
        if ok:
            rect_info.label = label
            self.update()
            # 保存YOLO标注
            self.save_yolo_annotations()
            # 发出标注更新信号
            self.annotations_updated.emit(self)

    def edit_polygon_label(self, polygon, default_label=""):
        """编辑多边形的标签"""
        label, ok = QInputDialog.getText(self, '修改多边形标注', '请输入标注信息:', text=default_label)
        if ok:
            polygon.label = label
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
        for poly_index, polygon in enumerate(self.polygons):
            # 只检查闭合的多边形
            if polygon.closed:
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
        for poly_index, polygon in enumerate(self.polygons):
            if polygon.closed and len(polygon.points) >= 3:
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

    def select_rectangle(self, rectangle):
        """
        选中指定的矩形框（可编辑状态）

        Args:
            rectangle: 要选中的矩形框
        """
        # 查找对应的RectangleInfo对象
        for rect_info in self.rectangle_infos:
            if rect_info.rectangle == rectangle:
                # 只有当当前选中的不是这个矩形时才更新
                if self.selected_rectangle_info != rect_info:
                    self.selected_rectangle_info = rect_info
                    self.selected_polygon_index = None
                    self.selected_point_info = None
                    # 清除高亮状态
                    self.highlighted_rectangles = []
                    self.highlighted_polygons = []
                    self.update()
                    # 发出信号，通知详情面板也选中对应的条目
                    self.annotation_selected_in_image.emit(rect_info)
                return

    def select_polygon(self, polygon_index):
        """
        选中指定的多边形（可编辑状态）

        Args:
            polygon_index: 要选中的多边形索引
        """
        if 0 <= polygon_index < len(self.polygons):
            # 只有当当前选中的不是这个多边形时才更新
            if self.selected_polygon_index != polygon_index:
                self.selected_polygon_index = polygon_index
                self.selected_rectangle_info = None
                self.selected_point_info = None
                # 清除高亮状态
                self.highlighted_rectangles = []
                self.highlighted_polygons = []
                self.update()
                # 发出信号，通知详情面板也选中对应的条目
                self.annotation_selected_in_image.emit(self.polygons[polygon_index])

    def highlight_rectangles(self, rectangles):
        """
        高亮指定的矩形框列表（仅高亮，不可编辑）

        Args:
            rectangles: 要高亮的矩形框列表
        """
        self.highlighted_rectangles = rectangles
        self.highlighted_polygons = []  # 清除多边形高亮
        # 清除选中状态
        self.selected_rectangle_info = None
        self.selected_polygon_index = None
        self.selected_point_info = None
        self.update()

    def highlight_polygons_by_label(self, label):
        """
        高亮指定标签的所有多边形

        Args:
            label: 要高亮的标签
        """
        self.highlighted_polygons = []  # 存储高亮的多边形索引
        for i, polygon in enumerate(self.polygons):
            if polygon.label == label:
                self.highlighted_polygons.append(i)
        # 清除矩形高亮和其他选中状态
        self.highlighted_rectangles = []
        self.selected_rectangle_info = None
        self.selected_polygon_index = None
        self.selected_point_info = None
        self.update()

    def highlight_annotations_by_labels(self, labels):
        """
        根据标签高亮所有相关的标注（包括矩形和多边形）

        Args:
            labels: 要高亮的标签列表
        """
        # 高亮矩形
        rectangles = []
        for rect_info in self.rectangle_infos:
            if rect_info.label in labels:
                rectangles.append(rect_info.rectangle)
        self.highlighted_rectangles = rectangles

        # 高亮多边形
        self.highlighted_polygons = []
        for i, polygon in enumerate(self.polygons):
            if polygon.label in labels:
                self.highlighted_polygons.append(i)

        # 清除选中状态
        self.selected_rectangle_info = None
        self.selected_polygon_index = None
        self.selected_point_info = None
        self.update()

    def mousePressEvent(self, event):
        if self.pixmap:
            clicked_point = event.pos()

            # ========== 矩形框处理逻辑 ==========
            # 检查是否点击了某个已存在的矩形框的控制点
            if self.selected_rectangle_info:
                handle = self.get_resize_handle_at_point(clicked_point, self.selected_rectangle_info.rectangle)
                if handle:
                    # 准备调整大小操作
                    self.resizing = True
                    self.dragging = False
                    self.dragging_polygon = False
                    self.resize_handle = handle
                    self.drag_start_point = clicked_point
                    self.resize_rectangle_start_rect = QRect(self.selected_rectangle_info.rectangle)
                    self.update()
                    return

            # 检查是否点击了某个已存在的矩形框
            for rect_info in self.rectangle_infos:
                if rect_info.rectangle.contains(clicked_point):
                    # 只有当点击的不是当前选中的矩形时才更新选中状态
                    if self.selected_rectangle_info != rect_info:
                        self.selected_rectangle_info = rect_info
                        self.drawing = False
                        self.current_rectangle = None
                        self.selected_polygon_index = None
                        self.selected_point_info = None
                        # 清除高亮状态
                        self.highlighted_rectangles = []
                        self.highlighted_polygons = []

                        # 准备拖动操作
                        self.dragging = True
                        self.resizing = False
                        self.dragging_polygon = False
                        self.drag_start_point = clicked_point
                        self.drag_rectangle_start_pos = rect_info.rectangle.topLeft()

                        self.update()
                        # 发出信号，通知详情面板也选中对应的条目
                        self.annotation_selected_in_image.emit(rect_info)
                    else:
                        # 如果点击的是已选中的矩形，准备拖动
                        self.dragging = True
                        self.resizing = False
                        self.dragging_polygon = False
                        self.drag_start_point = clicked_point
                        self.drag_rectangle_start_pos = rect_info.rectangle.topLeft()
                    # 不再发送annotations_updated信号，避免冲突
                    return

            # ========== 多边形处理逻辑 ==========
            # 检查是否点击了当前多边形的起始点并且点数大于等于3
            # 这个检查必须在点选中之前，以确保优先闭合多边形
            if (len(self.current_polygon.points) >= 3 and
                    self.is_point_near_start(clicked_point)):
                # 闭合当前多边形
                self.current_polygon.closed = True
                # 将当前多边形添加到已完成多边形列表
                self.polygons.append(self.current_polygon)
                # 弹出对话框输入标注信息
                label, ok = QInputDialog.getText(self, '多边形标注', '请输入标注信息:')
                if ok:
                    self.polygons[-1].label = label
                    # 输入标签后通知详情面板更新
                    self.annotation_selected_in_image.emit(self.polygons[-1])
                else:
                    # 如果用户取消输入，则从列表中移除多边形
                    self.polygons.pop()
                # 创建新的多边形用于接下来的绘制
                self.current_polygon = PolygonData()
                self.selected_point_info = None
                self.selected_polygon_index = None
                # 清除高亮状态
                self.highlighted_rectangles = []
                self.highlighted_polygons = []
                self.update()
                # 保存YOLO标注
                self.save_yolo_annotations()
                # 发出标注更新信号
                self.annotations_updated.emit(self)
                return

            # 检查是否点击了点
            point_info = self.get_point_near_click(clicked_point)
            if point_info is not None:
                poly_index, point_index = point_info
                # 只有闭合的多边形才允许选中点
                if (poly_index == -1 and self.current_polygon.closed) or (poly_index >= 0 and self.polygons[poly_index].closed):
                    # 选中点击的点
                    self.selected_point_info = point_info
                    self.selected_polygon_index = None  # 取消多边形选中
                    self.selected_rectangle_info = None
                    # 清除高亮状态
                    self.highlighted_rectangles = []
                    self.highlighted_polygons = []

                    self.update()
                    return

            # 检查是否点击了多边形区域（仅对已完成的多边形）
            poly_index = self.get_polygon_at_point(clicked_point)
            if poly_index is not None:
                # 只有当点击的不是当前选中的多边形时才更新选中状态
                if self.selected_polygon_index != poly_index:
                    self.selected_polygon_index = poly_index
                    self.selected_point_info = None  # 取消点选中
                    self.selected_rectangle_info = None
                    # 清除高亮状态
                    self.highlighted_rectangles = []
                    self.highlighted_polygons = []
                    # 准备拖拽多边形
                    self.dragging_polygon = True
                    self.dragging = False
                    self.resizing = False
                    self.drag_start_position = clicked_point
                    # 保存拖拽前的多边形点位置
                    self.original_polygon_points = []
                    for point in self.polygons[poly_index].points:
                        self.original_polygon_points.append(QPoint(point))
                    self.update()
                    # 发出信号，通知详情面板也选中对应的条目
                    self.annotation_selected_in_image.emit(self.polygons[poly_index])
                else:
                    # 如果点击的是已选中的多边形，准备拖动
                    self.dragging_polygon = True
                    self.dragging = False
                    self.resizing = False
                    self.drag_start_position = clicked_point
                    # 保存拖拽前的多边形点位置
                    self.original_polygon_points = []
                    for point in self.polygons[self.selected_polygon_index].points:
                        self.original_polygon_points.append(QPoint(point))
                return

            # 检查是否点击了当前多边形区域（仅对已完成且闭合的当前多边形）
            if (self.current_polygon.closed and len(self.current_polygon.points) >= 3 and
                    self.is_point_in_current_polygon(clicked_point)):
                self.selected_polygon_index = -1  # -1表示当前多边形
                self.selected_point_info = None
                self.selected_rectangle_info = None
                # 清除高亮状态
                self.highlighted_rectangles = []
                self.highlighted_polygons = []
                # 准备拖拽当前多边形
                self.dragging_polygon = True
                self.dragging = False
                self.resizing = False
                self.drag_start_position = clicked_point
                # 保存拖拽前的多边形点位置
                self.original_polygon_points = []
                for point in self.current_polygon.points:
                    self.original_polygon_points.append(QPoint(point))
                self.update()
                return

            # 如果当前多边形已闭合且被选中，取消选中状态
            if self.current_polygon.closed and self.selected_polygon_index == -1:
                self.selected_polygon_index = None
                # 清除高亮状态
                self.highlighted_rectangles = []
                self.highlighted_polygons = []
                self.update()
                return

            # 如果没有点击现有图形，则开始绘制新图形或取消选中
            # 根据当前模式决定绘制哪种图形
            if self.mode == 'rectangle':
                self.drawing = True
                self.dragging = False
                self.resizing = False
                self.dragging_polygon = False
                self.selected_rectangle_info = None  # 取消之前的选择
                self.selected_polygon_index = None
                self.selected_point_info = None
                # 清除高亮状态
                self.highlighted_rectangles = []
                self.highlighted_polygons = []
                start_point = event.pos()
                self.current_rectangle = QRect(start_point, start_point)
                self.update()
                # 发出信号，通知详情面板清除选中状态
                # self.annotations_updated.emit(self)
            elif self.mode == 'polygon':
                self.drawing = False
                self.dragging = False
                self.resizing = False
                self.dragging_polygon = False
                self.selected_rectangle_info = None
                self.selected_polygon_index = None
                self.selected_point_info = None
                # 清除高亮状态
                self.highlighted_rectangles = []
                self.highlighted_polygons = []
                # 添加点击的点到当前多边形中
                self.current_polygon.points.append(event.pos())
                self.update()
                # 发出信号，通知详情面板清除选中状态
                # self.annotations_updated.emit(self)
            else:
                # 点击了空白区域，取消所有选中状态和高亮状态
                # 只有当有选中状态时才清除
                if (self.selected_rectangle_info is not None or
                    self.selected_polygon_index is not None or
                    self.selected_point_info is not None):
                    self.selected_rectangle_info = None
                    self.selected_polygon_index = None
                    self.selected_point_info = None
                    # 清除高亮状态
                    self.highlighted_rectangles = []
                    self.highlighted_polygons = []
                    self.update()

                    # 发出信号，通知详情面板清除选中状态
                    # self.annotation_selected_in_image.emit(None)

    def mouseMoveEvent(self, event):
        # 更新鼠标位置
        self.mouse_pos = event.pos()
        
        # 矩形框绘制和操作处理
        if self.drawing and self.current_rectangle:
            # 更新当前矩形框的结束点
            self.current_rectangle.setBottomRight(event.pos())
            self.update()
        elif self.dragging and self.selected_rectangle_info:
            # 计算鼠标移动的距离
            offset = event.pos() - self.drag_start_point
            # 更新选中矩形框的位置
            new_top_left = self.drag_rectangle_start_pos + offset
            self.selected_rectangle_info.rectangle.moveTo(new_top_left)
            self.update()
            # 发出信号通知详情面板更新位置
            self.annotation_selected_in_image.emit(self.selected_rectangle_info)
        elif self.resizing and self.selected_rectangle_info and self.resize_handle:
            # 根据不同的控制点调整矩形框大小
            start_rect = self.resize_rectangle_start_rect
            offset = event.pos() - self.drag_start_point

            if self.resize_handle == "top_left":
                new_top_left = start_rect.topLeft() + offset
                self.selected_rectangle_info.rectangle.setTopLeft(new_top_left)
            elif self.resize_handle == "top_right":
                new_top_right = start_rect.topRight() + offset
                self.selected_rectangle_info.rectangle.setTopRight(new_top_right)
            elif self.resize_handle == "bottom_left":
                new_bottom_left = start_rect.bottomLeft() + offset
                self.selected_rectangle_info.rectangle.setBottomLeft(new_bottom_left)
            elif self.resize_handle == "bottom_right":
                new_bottom_right = start_rect.bottomRight() + offset
                self.selected_rectangle_info.rectangle.setBottomRight(new_bottom_right)

            self.update()
        # 多边形拖拽处理
        elif self.dragging_polygon:
            # 计算鼠标移动的距离
            offset = event.pos() - self.drag_start_position

            # 移动选中的多边形
            if self.selected_polygon_index == -1:  # 当前多边形
                for i, point in enumerate(self.current_polygon.points):
                    self.current_polygon.points[i] = self.original_polygon_points[i] + offset
            elif self.selected_polygon_index is not None and 0 <= self.selected_polygon_index < len(self.polygons):  # 已完成的多边形
                polygon = self.polygons[self.selected_polygon_index]
                for i, point in enumerate(polygon.points):
                    polygon.points[i] = self.original_polygon_points[i] + offset

            self.update()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # 矩形框处理
        if self.drawing and self.current_rectangle:
            # 设置当前矩形框的最终结束点
            self.current_rectangle.setBottomRight(event.pos())

            # 只有当矩形框有足够的大小时才添加并弹出输入框
            if self.current_rectangle.width() > 5 and self.current_rectangle.height() > 5:
                # 创建新的矩形框信息对象
                new_rect_info = RectangleInfo(self.current_rectangle)
                self.rectangle_infos.append(new_rect_info)

                # 弹出输入框请求标签信息
                label, ok = QInputDialog.getText(self, "标注信息", "请输入标注内容:")
                if ok and label:
                    new_rect_info.label = label
                    # 输入标签后通知详情面板更新
                    self.annotation_selected_in_image.emit(new_rect_info)
                else:
                    # 如果用户取消输入，则从列表中移除矩形
                    self.rectangle_infos.remove(new_rect_info)
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
            self.update()
            # 保存YOLO标注
            self.save_yolo_annotations()
            # 发出标注更新信号
            self.annotations_updated.emit(self)
        elif self.dragging_polygon:
            # 完成多边形拖拽操作
            self.dragging_polygon = False
            self.original_polygon_points = []
            self.update()
            # 保存YOLO标注
            self.save_yolo_annotations()
            # 发出标注更新信号
            self.annotations_updated.emit(self)
        elif not self.drawing:
            # 如果不是在绘制状态，保持当前选择不变
            self.update()

    def paintEvent(self, event):
        """自定义绘制事件，绘制图像和所有标注元素"""
        super().paintEvent(event)
        
        if not self.pixmap:
            return
            
        # 创建绘图器
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制图像
        painter.drawPixmap(0, 0, self.pixmap)
        
        # 绘制已完成的矩形框
        for rect_info in self.rectangle_infos:
            pen = QPen(Qt.red, 2)
            # 如果是选中的矩形，改变颜色和线宽
            if rect_info == self.selected_rectangle_info:
                pen.setColor(Qt.green)
                pen.setWidth(3)
            elif rect_info.rectangle in self.highlighted_rectangles:
                pen.setColor(Qt.yellow)
                pen.setWidth(3)
            painter.setPen(pen)
            painter.drawRect(rect_info.rectangle)
            
            # 绘制标签文本
            if rect_info.label:
                font = QFont()
                font.setPointSize(10)
                painter.setFont(font)
                painter.drawText(rect_info.rectangle.topLeft() + QPoint(5, -5), rect_info.label)
                
                # 如果是选中的矩形，绘制调整大小的控制点
                if rect_info == self.selected_rectangle_info:
                    handle_size = 4
                    painter.setBrush(Qt.green)
                    painter.setPen(QPen(Qt.green))
                    painter.drawRect(QRect(rect_info.rectangle.topLeft() - QPoint(handle_size, handle_size),
                                        rect_info.rectangle.topLeft() + QPoint(handle_size, handle_size)))
                    painter.drawRect(QRect(rect_info.rectangle.topRight() - QPoint(handle_size, handle_size),
                                        rect_info.rectangle.topRight() + QPoint(handle_size, handle_size)))
                    painter.drawRect(QRect(rect_info.rectangle.bottomLeft() - QPoint(handle_size, handle_size),
                                        rect_info.rectangle.bottomLeft() + QPoint(handle_size, handle_size)))
                    painter.drawRect(QRect(rect_info.rectangle.bottomRight() - QPoint(handle_size, handle_size),
                                        rect_info.rectangle.bottomRight() + QPoint(handle_size, handle_size)))
                    painter.setBrush(Qt.NoBrush)
                    painter.setPen(pen)
        
        # 绘制当前正在绘制的矩形
        if self.current_rectangle:
            pen = QPen(Qt.blue, 2, Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(self.current_rectangle)
        
        # 绘制已完成的多边形
        for i, polygon in enumerate(self.polygons):
            if polygon.closed and len(polygon.points) >= 3:
                # 创建QPolygon对象
                qpolygon = QPolygon()
                for point in polygon.points:
                    qpolygon.append(point)
                
                # 设置画笔
                pen = QPen(Qt.red, 2)
                brush = Qt.NoBrush
                
                # 如果是选中的多边形，改变颜色和填充
                if i == self.selected_polygon_index:
                    pen.setColor(Qt.green)
                    pen.setWidth(3)
                    brush = Qt.yellow
                    brush.setStyle(Qt.FDiagPattern)
                elif i in self.highlighted_polygons:
                    pen.setColor(Qt.yellow)
                    pen.setWidth(3)
                    brush = Qt.yellow
                    brush.setStyle(Qt.FDiagPattern)
                    
                painter.setPen(pen)
                painter.setBrush(brush)
                painter.drawPolygon(qpolygon)
                
                # 绘制标签文本
                if polygon.label and len(polygon.points) > 0:
                    # 计算多边形的中心点作为标签位置
                    center_x = sum(p.x() for p in polygon.points) // len(polygon.points)
                    center_y = sum(p.y() for p in polygon.points) // len(polygon.points)
                    font = QFont()
                    font.setPointSize(10)
                    painter.setFont(font)
                    painter.setPen(QPen(Qt.black))
                    painter.drawText(center_x, center_y, polygon.label)
                    painter.setPen(pen)
        
        # 绘制当前正在绘制的多边形
        if len(self.current_polygon.points) > 0:
            pen = QPen(Qt.blue, 2, Qt.DashLine)
            painter.setPen(pen)
            
            # 绘制线条连接各个点
            for i in range(len(self.current_polygon.points) - 1):
                painter.drawLine(self.current_polygon.points[i], self.current_polygon.points[i+1])
                
            # 如果多边形已经闭合，绘制闭合线
            if self.current_polygon.closed and len(self.current_polygon.points) >= 3:
                painter.drawLine(self.current_polygon.points[-1], self.current_polygon.points[0])
                # 填充多边形
                qpolygon = QPolygon()
                for point in self.current_polygon.points:
                    qpolygon.append(point)
                painter.setBrush(QColor(255, 255, 0, 100))  # 半透明黄色
                painter.drawPolygon(qpolygon)
            else:
                # 绘制从最后一个点到鼠标位置的虚线
                if len(self.current_polygon.points) > 0:
                    pen = QPen(Qt.blue, 1, Qt.DashLine)
                    painter.setPen(pen)
                    painter.drawLine(self.current_polygon.points[-1], self.mouse_pos)
                
                # 绘制点
                painter.setPen(QPen(Qt.blue))
                painter.setBrush(Qt.blue)
                for point in self.current_polygon.points:
                    painter.drawEllipse(point, 3, 3)
                painter.setBrush(Qt.NoBrush)
                painter.setPen(pen)
                
                # 绘制起始点（用不同颜色标识）
                if len(self.current_polygon.points) > 0:
                    painter.setBrush(Qt.red)
                    painter.setPen(QPen(Qt.red))
                    start_point = self.current_polygon.points[0]
                    painter.drawEllipse(start_point, 5, 5)
                    painter.setBrush(Qt.NoBrush)
                    painter.setPen(pen)
        
        # 绘制选中的点
        if self.selected_point_info is not None:
            poly_index, point_index = self.selected_point_info
            if poly_index == -1:  # 当前多边形
                if point_index < len(self.current_polygon.points):
                    point = self.current_polygon.points[point_index]
                    painter.setPen(QPen(Qt.green, 3))
                    painter.setBrush(Qt.green)
                    painter.drawEllipse(point, 5, 5)
            else:  # 已完成的多边形
                if poly_index < len(self.polygons) and point_index < len(self.polygons[poly_index].points):
                    point = self.polygons[poly_index].points[point_index]
                    painter.setPen(QPen(Qt.green, 3))
                    painter.setBrush(Qt.green)
                    painter.drawEllipse(point, 5, 5)
        
        painter.end()
