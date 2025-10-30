from PyQt5 import sip
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QSplitter, QMenu, QAction, QApplication
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QCursor, QKeyEvent

from .picture_annotation import ImageLabel
from ..logging_config import logger


class ImageDetailsPanel(QWidget):
    """
    图片详情面板类，用于显示图片文件的详细信息
    """

    # 定义信号，用于通知图片标签选中状态变化
    tag_selected = pyqtSignal(list)  # 发送选中的标签列表
    highlights_cleared = pyqtSignal()  # 发送清除高亮信号
    annotation_deleted = pyqtSignal(dict)  # 发送需要删除的标注信息
    annotation_selected = pyqtSignal(dict)  # 统一发送选中的标注信息
    annotation_deselected = pyqtSignal()  # 新增信号，用于通知取消选中标注
    # 新增信号，用于通知清除选中状态
    selection_cleared = pyqtSignal()  # 发送清除选中状态信号

    def __init__(self):
        """
        初始化图片详情面板
        """
        super().__init__()
        self.current_file_path = None
        self.image_label = None  # 对应的图片标注组件
        self.annotations_data = []  # 存储当前的标注数据
        self.last_tag_selected_row = -1  # 上次选中的标签行号，用于Shift键批量选择
        self.last_annotation_selected_row = -1  # 上次选中的标注详情行号，用于Shift键批量选择
        self.anchor_tag_row = -1  # 标签选择的锚点行号，用于Shift键批量选择
        self.anchor_annotation_row = -1  # 标注详情选择的锚点行号，用于Shift键批量选择
        self.init_ui()

    def init_ui(self):
        """
        初始化图片详情面板的用户界面
        """
        layout = QVBoxLayout(self)

        # 创建分割器实现上下布局 (4:6比例)
        self.splitter = QSplitter(Qt.Vertical)

        # 上部分：显示当前图片的标签列表
        self.tags_label = QLabel("图片标签:")
        self.tags_list = QListWidget()
        self.tags_list.setSelectionMode(QListWidget.ExtendedSelection)  # 启用多选模式

        # 下部分：显示标签和点位信息
        self.annotations_label = QLabel("标注详情:")
        self.annotations_list = QListWidget()
        self.annotations_list.setSelectionMode(QListWidget.ExtendedSelection)  # 启用多选模式

        # 启用右键菜单
        self.tags_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tags_list.customContextMenuRequested.connect(self.show_tags_context_menu)

        self.annotations_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.annotations_list.customContextMenuRequested.connect(self.show_annotations_context_menu)

        # 连接点击事件
        self.tags_list.itemClicked.connect(self.on_tag_item_clicked)
        self.annotations_list.itemClicked.connect(self.on_annotation_item_clicked)

        # 连接选择变化事件
        self.tags_list.itemSelectionChanged.connect(self.on_tags_item_selection_changed)
        self.annotations_list.itemSelectionChanged.connect(self.on_annotations_item_selection_changed)

        # 连接鼠标点击事件到列表本身（处理点击空白区域）
        self.tags_list.clicked.connect(self.on_tag_list_clicked)
        self.annotations_list.clicked.connect(self.on_annotation_list_clicked)

        # 创建包含标签和列表的widget
        tags_widget = QWidget()
        tags_layout = QVBoxLayout(tags_widget)
        tags_layout.addWidget(self.tags_label)
        tags_layout.addWidget(self.tags_list)

        annotations_widget = QWidget()
        annotations_layout = QVBoxLayout(annotations_widget)
        annotations_layout.addWidget(self.annotations_label)
        annotations_layout.addWidget(self.annotations_list)

        # 添加到分割器
        self.splitter.addWidget(tags_widget)
        self.splitter.addWidget(annotations_widget)

        # 设置初始大小比例为4:6
        self.splitter.setSizes([400, 600])

        layout.addWidget(self.splitter)
        self.setLayout(layout)

    def keyPressEvent(self, event: QKeyEvent):
        """
        处理键盘按键事件

        Args:
            event: 键盘事件
        """
        # 处理Delete键事件
        if event.key() == Qt.Key_Delete:
            # 检查是否有选中的标签
            selected_tags = self.tags_list.selectedItems()
            if selected_tags:
                # 删除选中的标签
                self.delete_selected_tags()
                return

            # 检查是否有选中的标注详情
            selected_annotations = self.annotations_list.selectedItems()
            if selected_annotations:
                # 删除选中的标注详情
                self.delete_selected_annotations()
                return

        super().keyPressEvent(event)

    def update_details(self, file_path, image_label=None, trigger_event=None):
        """
        更新详情面板显示的内容

        Args:
            file_path (str): 文件路径
            image_label (ImageLabel): 图片标注组件
            trigger_event (str): 触发事件的来源
        """
        self.current_file_path = file_path
        self.image_label = image_label

        # 检查列表组件是否仍然有效
        if sip.isdeleted(self.annotations_list):
            logger.warning("标注详情列表已被删除")
            return

        if sip.isdeleted(self.tags_list):
            logger.warning("标签列表已被删除")
            return

        # 如果是图片文件且有标注组件，显示标注信息
        if image_label and hasattr(image_label, 'get_annotations'):
            new_annotations_data = image_label.get_annotations()

            # 提取所有唯一的标签
            new_tags = set()
            for annotation in new_annotations_data:
                if annotation.get('label'):
                    new_tags.add(annotation['label'])

            # 更新标签列表，不直接清空，而是进行对比
            current_tags = set()
            for i in range(self.tags_list.count()):
                current_tags.add(self.tags_list.item(i).text())

            # 添加新标签
            for tag in new_tags:
                if tag not in current_tags:
                    self.tags_list.addItem(tag)

            # 移除不再存在的标签
            tags_to_remove = current_tags - new_tags
            for i in range(self.tags_list.count() - 1, -1, -1):  # 从后往前遍历避免索引问题
                item = self.tags_list.item(i)
                if item and item.text() in tags_to_remove:
                    self.tags_list.takeItem(i)

            # 重新排序标签列表
            tags = []
            for i in range(self.tags_list.count()):
                tags.append(self.tags_list.item(i).text())
            tags.sort()

            # 更新标签列表显示顺序
            self.tags_list.clear()
            for tag in tags:
                self.tags_list.addItem(tag)

            # 更新标注详情列表，使用精细化的更新策略
            # 构建新标注项和其对应数据的映射
            new_annotation_items = []
            new_annotation_mapping = []
            for i, annotation in enumerate(new_annotations_data):
                if annotation['type'] == 'rectangle':
                    label = annotation.get('label', '未标记')
                    rect = annotation['rectangle']
                    item_text = f"[矩形] {label}: ({rect.x()}, {rect.y()}, {rect.width()}, {rect.height()})"
                    new_annotation_items.append(item_text)
                elif annotation['type'] == 'polygon':
                    label = annotation.get('label', '未标记')
                    points = annotation['points']
                    points_str = ', '.join([f"({p.x()}, {p.y()})" for p in points])
                    item_text = f"[多边形] {label}: {points_str}"
                    new_annotation_items.append(item_text)
                new_annotation_mapping.append(annotation)

            # 获取当前列表中的标注数据
            current_annotations_data = self.annotations_data

            # 1. 找出需要添加的项（存在于新数组但不存在于老数组）
            annotations_to_add = []
            for new_annotation in new_annotation_mapping:
                found = False
                for current_annotation in current_annotations_data:
                    # 比较标签和形状
                    if (new_annotation.get('label') == current_annotation.get('label') and
                        new_annotation.get('type') == current_annotation.get('type')):
                        # 进一步比较形状数据
                        if new_annotation['type'] == 'rectangle':
                            if new_annotation['rectangle'] == current_annotation['rectangle']:
                                found = True
                                break
                        elif new_annotation['type'] == 'polygon':
                            if new_annotation['points'] == current_annotation['points']:
                                found = True
                                break
                if not found:
                    annotations_to_add.append(new_annotation)

            # 2. 找出需要删除的项（存在于老数组但不存在于新数组）
            annotations_to_remove = []
            for current_annotation in current_annotations_data:
                found = False
                for new_annotation in new_annotation_mapping:
                    # 比较标签和形状
                    if (new_annotation.get('label') == current_annotation.get('label') and
                        new_annotation.get('type') == current_annotation.get('type')):
                        # 进一步比较形状数据
                        if new_annotation['type'] == 'rectangle':
                            if new_annotation['rectangle'] == current_annotation['rectangle']:
                                found = True
                                break
                        elif new_annotation['type'] == 'polygon':
                            if new_annotation['points'] == current_annotation['points']:
                                found = True
                                break
                if not found:
                    annotations_to_remove.append(current_annotation)

            # 3. 执行删除操作
            for annotation_to_remove in annotations_to_remove:
                for i in range(len(current_annotations_data)):
                    current_annotation = current_annotations_data[i]
                    # 比较标签和形状
                    if (annotation_to_remove.get('label') == current_annotation.get('label') and
                        annotation_to_remove.get('type') == current_annotation.get('type')):
                        # 进一步比较形状数据
                        if annotation_to_remove['type'] == 'rectangle':
                            if annotation_to_remove['rectangle'] == current_annotation['rectangle']:
                                # 找到匹配项，删除它
                                self.annotations_list.takeItem(i)
                                break
                        elif annotation_to_remove['type'] == 'polygon':
                            if annotation_to_remove['points'] == current_annotation['points']:
                                # 找到匹配项，删除它
                                self.annotations_list.takeItem(i)
                                break

            # 4. 执行添加操作
            for annotation_to_add in annotations_to_add:
                if annotation_to_add['type'] == 'rectangle':
                    label = annotation_to_add.get('label', '未标记')
                    rect = annotation_to_add['rectangle']
                    item_text = f"[矩形] {label}: ({rect.x()}, {rect.y()}, {rect.width()}, {rect.height()})"
                    self.annotations_list.addItem(item_text)
                elif annotation_to_add['type'] == 'polygon':
                    label = annotation_to_add.get('label', '未标记')
                    points = annotation_to_add['points']
                    points_str = ', '.join([f"({p.x()}, {p.y()})" for p in points])
                    item_text = f"[多边形] {label}: {points_str}"
                    self.annotations_list.addItem(item_text)

            # 5. 更新剩余项（标签或形状发生变化的项）
            # 重新构建当前列表项文本
            current_items_text = []
            for i in range(self.annotations_list.count()):
                current_items_text.append(self.annotations_list.item(i).text())
            
            # 重新构建新列表项文本
            updated_items_text = []
            for annotation in new_annotation_mapping:
                if annotation['type'] == 'rectangle':
                    label = annotation.get('label', '未标记')
                    rect = annotation['rectangle']
                    item_text = f"[矩形] {label}: ({rect.x()}, {rect.y()}, {rect.width()}, {rect.height()})"
                    updated_items_text.append(item_text)
                elif annotation['type'] == 'polygon':
                    label = annotation.get('label', '未标记')
                    points = annotation['points']
                    points_str = ', '.join([f"({p.x()}, {p.y()})" for p in points])
                    item_text = f"[多边形] {label}: {points_str}"
                    updated_items_text.append(item_text)
            
            # 更新现有项
            min_len = min(len(current_items_text), len(updated_items_text))
            for i in range(min_len):
                current_item = self.annotations_list.item(i)
                if current_item.text() != updated_items_text[i]:
                    current_item.setText(updated_items_text[i])
            
            # 如果新列表更长，添加额外项
            if len(updated_items_text) > len(current_items_text):
                for i in range(len(current_items_text), len(updated_items_text)):
                    self.annotations_list.addItem(updated_items_text[i])

            # 更新内部数据
            self.annotations_data = new_annotations_data

    def select_annotation_in_image(self, annotation):
        """
        当在图片上选中任意标注元素时，在详情面板中同步选中对应的条目

        Args:
            annotation: 被选中的标注对象(矩形或多边形)或None（表示取消选中）
        """
        # 处理取消选中的情况
        if annotation is None:
            if self.annotations_list and not sip.isdeleted(self.annotations_list):
                self.annotations_list.clearSelection()
            if self.tags_list and not sip.isdeleted(self.tags_list):
                self.tags_list.clearSelection()
            return

        # 遍历标注数据，通过标签名称和点位信息来匹配并选中对应的列表项
        for i, anno_data in enumerate(self.annotations_data):
            # 统一处理所有类型的标注，直接比较关键属性
            # 检查标签是否匹配
            label_match = anno_data.get('label') == getattr(annotation, 'label', None)

            # 检查形状数据是否匹配
            shape_match = False
            if 'rectangle' in anno_data and hasattr(annotation, 'rectangle'):
                shape_match = anno_data['rectangle'] == annotation.rectangle
            elif 'points' in anno_data and hasattr(annotation, 'points'):
                shape_match = anno_data['points'] == annotation.points

            # 如果标签和形状都匹配，则选中对应的列表项
            if label_match and shape_match:
                # 检查列表组件是否仍然有效
                if self.annotations_list and not sip.isdeleted(self.annotations_list):
                    # 清除当前选择并选中匹配项
                    item = self.annotations_list.item(i)
                    if item:
                        self.annotations_list.setCurrentItem(item)
                        self.annotations_list.scrollToItem(item)

                # 同时选中标签列表中对应的标签
                if self.tags_list and not sip.isdeleted(self.tags_list):
                    # 查找匹配的标签项并选中
                    for j in range(self.tags_list.count()):
                        tag_item = self.tags_list.item(j)
                        if tag_item and tag_item.text() == annotation.label:
                            self.tags_list.setCurrentItem(tag_item)
                            self.tags_list.scrollToItem(tag_item)
                            break

                return


    def clear_highlights_method(self, data_to_clear):
        """
        提取的清除高亮方法，接收需要清除高亮标注框的数据，
        然后遍历对需要清除高亮的标注框进行清除

        Args:
            data_to_clear: 需要清除高亮的数据，可以是标签列表或标注信息
        """
        # 直接调用ImageLabel中的统一清除高亮方法
        if isinstance(self.image_label, ImageLabel):
            self.image_label.clear_highlights(data_to_clear)

    def on_tag_list_clicked(self, index):
        """
        处理标签列表点击事件（包括点击空白区域）

        Args:
            index: 被点击的索引
        """
        # 检查列表组件是否仍然有效
        if not self.tags_list or sip.isdeleted(self.tags_list):
            return

        # 如果点击的是空白区域（没有项目被点击）
        if not self.tags_list.itemFromIndex(index):
            # 清除所有选择
            self.tags_list.clearSelection()
            # 如果有ImageLabel实例，清除高亮
            if self.image_label and hasattr(self.image_label, 'clear_highlights'):
                self.image_label.clear_highlights()
            # 重置锚点
            self.anchor_tag_row = -1

    def on_annotation_list_clicked(self, index):
        """
        处理标注详情列表点击事件（包括点击空白区域）

        Args:
            index: 被点击的索引
        """
        # 检查列表组件是否仍然有效
        if not self.annotations_list or sip.isdeleted(self.annotations_list):
            return

        # 如果点击的是空白区域（没有项目被点击）
        if not self.annotations_list.itemFromIndex(index):
            # 清除所有选择
            self.annotations_list.clearSelection()
            # 如果有ImageLabel实例，清除高亮
            if self.image_label and hasattr(self.image_label, 'clear_highlights'):
                self.image_label.clear_highlights()
            # 同时通知图片标注窗口取消选中状态
            self.annotation_deselected.emit()
            # 重置锚点
            self.anchor_annotation_row = -1

    def on_tag_item_clicked(self, item):
        """
        处理标签项点击事件 - 高亮所有相同标签的标注框（不可编辑）

        Args:
            item: 被点击的标签项
        """
        # 检查列表组件是否仍然有效
        if not self.tags_list or sip.isdeleted(self.tags_list):
            return

        # 获取当前点击的修饰键
        modifiers = QApplication.keyboardModifiers()

        row = self.tags_list.row(item)

        # 处理Ctrl键（添加/移除单个选择）
        if modifiers == Qt.ControlModifier:
            if item.isSelected():
                item.setSelected(False)
            else:
                item.setSelected(True)
                self.last_tag_selected_row = row
                # 设置锚点为当前行（仅在没有锚点时设置）
                if self.anchor_tag_row == -1:
                    self.anchor_tag_row = row
        # 处理Shift键（批量选择）
        elif modifiers == Qt.ShiftModifier:
            # 如果还没有锚点，则将当前选择的第一项作为锚点
            if self.anchor_tag_row == -1:
                selected_items = self.tags_list.selectedItems()
                if selected_items:
                    self.anchor_tag_row = self.tags_list.row(selected_items[0])
                else:
                    self.anchor_tag_row = row

            # 先清除所有选择
            self.tags_list.clearSelection()
            # 选择从锚点到当前选中的范围
            start_row = min(self.anchor_tag_row, row)
            end_row = max(self.anchor_tag_row, row)
            for i in range(start_row, end_row + 1):
                # 检查项目是否存在再设置选中状态
                tag_item = self.tags_list.item(i)
                if tag_item:
                    tag_item.setSelected(True)
            # 更新上次选中的行号为当前行
            self.last_tag_selected_row = row
        else:
            # 正常单选
            self.tags_list.clearSelection()
            item.setSelected(True)
            self.last_tag_selected_row = row
            # 设置锚点为当前行
            self.anchor_tag_row = row

        # 收集所有选中标签
        selected_labels = [item.text() for item in self.tags_list.selectedItems()]

        # 发射信号，通知图片标签高亮这些标签对应的所有标注（矩形和多边形）
        if selected_labels:
            self.annotations_list.clearSelection()
            # 使用ImageLabel的新方法高亮标注
            if self.image_label:
                self.image_label.highlight_annotations_by_labels(selected_labels)
        else:
            # 如果没有选中的标签，清除高亮
            if self.image_label:
                self.image_label.clear_highlights()

    def on_annotation_item_clicked(self, item):
        """
        处理标注详情项点击事件 - 选中对应标注框（可编辑）

        Args:
            item: 被点击的标注详情项
        """
        # 检查列表组件是否仍然有效
        if not self.annotations_list or sip.isdeleted(self.annotations_list):
            return

        # 获取当前点击的修饰键
        modifiers = QApplication.keyboardModifiers()

        row = self.annotations_list.row(item)

        # 处理Ctrl键（添加/移除单个选择）
        if modifiers == Qt.ControlModifier:
            if item.isSelected():
                item.setSelected(False)
            else:
                item.setSelected(True)
                self.last_annotation_selected_row = row
                # 设置锚点为当前行（仅在没有锚点时设置）
                if self.anchor_annotation_row == -1:
                    self.anchor_annotation_row = row
        # 处理Shift键（批量选择）
        elif modifiers == Qt.ShiftModifier:
            # 如果还没有锚点，则将当前选择的第一项作为锚点
            if self.anchor_annotation_row == -1:
                selected_items = self.annotations_list.selectedItems()
                if selected_items:
                    self.anchor_annotation_row = self.annotations_list.row(selected_items[0])
                else:
                    self.anchor_annotation_row = row

            # 先清除所有选择
            self.annotations_list.clearSelection()
            # 选择从锚点到当前选中的范围
            start_row = min(self.anchor_annotation_row, row)
            end_row = max(self.anchor_annotation_row, row)
            for i in range(start_row, end_row + 1):
                # 检查项目是否存在再设置选中状态
                annotation_item = self.annotations_list.item(i)
                if annotation_item:
                    annotation_item.setSelected(True)
            # 更新上次选中的行号为当前行
            self.last_annotation_selected_row = row
        else:
            # 正常单选
            self.annotations_list.clearSelection()
            item.setSelected(True)
            self.last_annotation_selected_row = row
            # 设置锚点为当前行
            self.anchor_annotation_row = row

        # 处理选择后的操作
        self._handle_annotation_selection()

    def _handle_annotation_selection(self):
        """
        处理标注选择后的操作
        """
        selected_items = self.annotations_list.selectedItems()
        if len(selected_items) > 0:
            # 如果只选中了一个项目，则选中对应的标注框
            if len(selected_items) == 1:
                row = self.annotations_list.row(selected_items[0])
                if 0 <= row < len(self.annotations_data):
                    annotation_data = self.annotations_data[row]
                    # 使用统一的方法处理标注选择
                    self.annotation_selected.emit(annotation_data)
            # 如果选中了多个项目，则高亮显示所有选中的标注框
            else:
                # 收集所有选中的标注数据
                selected_annotations_data = []
                for item in selected_items:
                    row = self.annotations_list.row(item)
                    if 0 <= row < len(self.annotations_data):
                        selected_annotations_data.append(self.annotations_data[row])

                # 如果有ImageLabel实例，使用其高亮方法
                if self.image_label and hasattr(self.image_label, 'highlight_annotations_by_data'):
                    self.image_label.highlight_annotations_by_data(selected_annotations_data)
        else:
            # 如果没有选中的标注，清除高亮
            if self.image_label:
                self.image_label.clear_highlights()

    def on_tags_item_selection_changed(self):
        """
        处理标签列表选中项变化事件
        """
        # 检查列表组件是否仍然有效
        if not self.tags_list or sip.isdeleted(self.tags_list):
            return

        selected_items = self.tags_list.selectedItems()
        if selected_items:
            # 获取所有选中标签的文本
            selected_labels = [item.text() for item in selected_items]
            # 发出信号，通知预览面板高亮显示对应标签的标注
            self.tag_selected.emit(selected_labels)

            # 更新上次选中的标签行号（使用第一个选中项）
            first_selected_row = self.tags_list.row(selected_items[0])
            self.last_tag_selected_row = first_selected_row
        else:
            # 没有选中项，清除高亮
            self.clear_highlights_method([])
            self.last_tag_selected_row = -1

    def on_annotations_item_selection_changed(self):
        """
        处理标注详情列表选中项变化事件
        """
        # 检查列表组件是否仍然有效
        if not self.annotations_list or sip.isdeleted(self.annotations_list):
            return

        # 获取当前选中的项目
        selected_items = self.annotations_list.selectedItems()
        if len(selected_items) > 0:
            # 收集所有选中的标注数据
            selected_annotations_data = []
            for item in selected_items:
                row = self.annotations_list.row(item)
                if 0 <= row < len(self.annotations_data):
                    selected_annotations_data.append(self.annotations_data[row])

            # 如果有ImageLabel实例，使用其高亮方法
            if self.image_label and hasattr(self.image_label, 'highlight_annotations_by_data'):
                self.image_label.highlight_annotations_by_data(selected_annotations_data)
        else:
            # 如果没有选中的标注，清除高亮
            if self.image_label:
                self.image_label.clear_highlights()
            # 通知预览面板清除选中状态
            self.annotation_deselected.emit()
            self.tags_list.clearSelection()

    def show_tags_context_menu(self, position):
        """
        显示标签列表的右键菜单

        Args:
            position: 右键点击位置
        """
        # 检查列表组件是否仍然有效
        if not self.tags_list or sip.isdeleted(self.tags_list):
            return

        item = self.tags_list.itemAt(position)
        if not item:
            return

        # 创建右键菜单
        context_menu = QMenu(self)
        delete_action = QAction("删除标签", self)
        context_menu.addAction(delete_action)

        # 连接删除动作
        delete_action.triggered.connect(self.delete_selected_tags)

        # 显示菜单
        context_menu.exec_(QCursor.pos())

    def show_annotations_context_menu(self, position):
        """
        显示标注详情列表的右键菜单

        Args:
            position: 右键点击位置
        """
        # 检查列表组件是否仍然有效
        if not self.annotations_list or sip.isdeleted(self.annotations_list):
            return

        item = self.annotations_list.itemAt(position)
        if not item:
            return

        # 创建右键菜单
        context_menu = QMenu(self)
        delete_action = QAction("删除标注", self)
        context_menu.addAction(delete_action)

        # 连接删除动作
        delete_action.triggered.connect(self.delete_selected_annotations)

        # 显示菜单
        context_menu.exec_(QCursor.pos())

    def delete_selected_tags(self):
        """
        删除选中的标签及其相关的所有标注
        """
        # 检查列表组件是否仍然有效
        if not self.tags_list or sip.isdeleted(self.tags_list):
            return

        selected_items = self.tags_list.selectedItems()
        if not selected_items:
            return

        # 收集要删除的标注信息
        annotations_to_delete = []
        tag_names = [item.text() for item in selected_items]

        for annotation in self.annotations_data:
            if annotation.get('label') in tag_names:
                annotations_to_delete.append(annotation)

        # 发射删除信号
        for annotation in annotations_to_delete:
            self.annotation_deleted.emit(annotation)

        # 从列表中移除标签项
        for item in selected_items:
            self.tags_list.takeItem(self.tags_list.row(item))

        # 重置上次选中的行号
        self.last_tag_selected_row = -1

        # 更新标注详情列表
        self.update_details(self.current_file_path, self.image_label)

    def delete_selected_annotations(self):
        """
        删除选中的标注
        """
        # 检查列表组件是否仍然有效
        if not self.annotations_list or sip.isdeleted(self.annotations_list):
            return

        selected_items = self.annotations_list.selectedItems()
        if not selected_items:
            return

        # 收集要删除的行号
        rows_to_delete = []
        for item in selected_items:
            row = self.annotations_list.row(item)
            if 0 <= row < len(self.annotations_data):
                rows_to_delete.append(row)

        # 按降序排列行号
        rows_to_delete.sort(reverse=True)

        # 收集所有要删除的注释数据和对应的列表项
        items_to_delete = []
        for row in rows_to_delete:
            items_to_delete.append({
                'annotation': self.annotations_data[row],
                'list_item': self.annotations_list.item(row)
            })

        # 发射删除信号
        for item in items_to_delete:
            self.annotation_deleted.emit(item['annotation'])

        # 从列表中移除项并从数据中移除（按降序）
        for row in rows_to_delete:
            # 确保索引仍然有效
            if row < self.annotations_list.count() and row < len(self.annotations_data):
                # 从列表中移除项
                self.annotations_list.takeItem(row)
                # 从数据中移除
                del self.annotations_data[row]

        # 重置上次选中的行号
        self.last_annotation_selected_row = -1

        # 清除选中状态
        self.annotations_list.clearSelection()

    def delete_tag(self, item):
        """
        删除标签及其相关的所有标注

        Args:
            item: 要删除的标签项
        """
        # 为了保持向后兼容，仍然保留这个方法
        tag_name = item.text()
        # 收集要删除的标注信息
        annotations_to_delete = []
        for annotation in self.annotations_data:
            if annotation.get('label') == tag_name:
                annotations_to_delete.append(annotation)

        # 发射删除信号
        for annotation in annotations_to_delete:
            self.annotation_deleted.emit(annotation)

        # 从列表中移除标签项
        self.tags_list.takeItem(self.tags_list.row(item))

        # 清除选中状态
        self.tags_list.clearSelection()

    def delete_annotation(self, item):
        """
        删除单个标注

        Args:
            item: 要删除的标注项
        """
        # 为了保持向后兼容，仍然保留这个方法
        row = self.annotations_list.row(item)
        if 0 <= row < len(self.annotations_data):
            annotation = self.annotations_data[row]
            # 发射删除信号
            self.annotation_deleted.emit(annotation)
            # 从列表中移除项
            self.annotations_list.takeItem(row)
            # 从数据中移除
            del self.annotations_data[row]

            # 清除选中状态
            self.annotations_list.clearSelection()

            # 更新预览面板
            if self.current_file_path and self.image_label:
                self.update_details(self.current_file_path, self.image_label)
