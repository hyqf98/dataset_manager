from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, pyqtSignal
from ..logging_config import logger
from ..preview.image_details import ImageDetailsPanel
from ..preview.video_details import VideoDetailsPanel


class DetailsPanel(QWidget):
    """
    详情面板类，用于显示选中文件的详细信息
    这是一个通用面板，根据文件类型显示不同的详情视图
    """

    # 定义信号，用于通知图片标签选中状态变化（转发自ImageDetailsPanel）
    tag_selected = pyqtSignal(list)  # 发送选中的标签列表
    highlights_cleared = pyqtSignal()  # 发送清除高亮信号
    annotation_deleted = pyqtSignal(dict)  # 发送需要删除的标注信息
    annotation_selected = pyqtSignal(dict)  # 统一发送选中的标注信息
    annotation_deselected = pyqtSignal()  # 新增信号，用于通知取消选中标注

    def __init__(self):
        """
        初始化详情面板
        """
        super().__init__()
        self.current_file_path = None
        self.current_view = None  # 当前显示的详情视图
        self.image_details = None  # 图片详情视图
        self.video_details = None  # 视频详情视图
        self.init_ui()

    def init_ui(self):
        """
        初始化详情面板的用户界面
        """
        layout = QVBoxLayout(self)
        self.label = QLabel("请选择文件查看详细信息")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        self.setLayout(layout)

    def update_details(self, file_path, preview_component=None):
        """
        根据文件类型更新详情面板显示的内容

        Args:
            file_path (str): 文件路径
            preview_component: 预览组件（ImageLabel或VideoPlayer）
        """
        self.current_file_path = file_path
        
        # 根据文件扩展名确定文件类型
        if file_path:
            ext = file_path.split('.')[-1].lower()
            
            # 图片文件类型
            image_extensions = ['jpg', 'jpeg', 'png', 'bmp', 'gif']
            # 视频文件类型
            video_extensions = ['mp4', 'avi', 'mov', 'wmv', 'flv']
            
            # 清除当前布局中的所有组件
            self.clear_layout()
            
            if ext in image_extensions:
                self.show_image_details(file_path, preview_component)
            elif ext in video_extensions:
                self.show_video_details(file_path, preview_component)
            else:
                # 不支持的文件类型
                self.label = QLabel("不支持的文件类型")
                self.label.setAlignment(Qt.AlignCenter)
                self.layout().addWidget(self.label)
        else:
            # 没有文件路径
            self.clear_layout()
            self.label = QLabel("请选择文件查看详细信息")
            self.label.setAlignment(Qt.AlignCenter)
            self.layout().addWidget(self.label)

    def clear_layout(self):
        """
        清除布局中的所有组件
        """
        # 移除布局中的所有widget，但不删除它们
        while self.layout().count():
            child = self.layout().takeAt(0)
            if child.widget():
                # 只是将widget从布局中移除，不删除widget本身
                child.widget().setParent(None)

    def show_image_details(self, file_path, image_label=None):
        """
        显示图片详情视图

        Args:
            file_path (str): 图片文件路径
            image_label (ImageLabel): 图片标注组件
        """
        # 创建或重用图片详情视图
        if not self.image_details:
            self.image_details = ImageDetailsPanel()
            # 连接信号
            self.image_details.tag_selected.connect(self.tag_selected)
            self.image_details.highlights_cleared.connect(self.highlights_cleared)
            self.image_details.annotation_deleted.connect(self.annotation_deleted)
            self.image_details.annotation_selected.connect(self.annotation_selected)
            self.image_details.annotation_deselected.connect(self.annotation_deselected)
        # 如果image_details已经存在但不在当前布局中，则添加到布局
        elif self.image_details.parent() != self:
            # 先从任何现有父级中移除
            if self.image_details.parent():
                self.image_details.setParent(None)
            self.layout().addWidget(self.image_details)
        
        # 更新详情信息
        self.image_details.update_details(file_path, image_label)
        
        # 设置为当前视图
        self.current_view = self.image_details

    def show_video_details(self, file_path, video_player=None):
        """
        显示视频详情视图

        Args:
            file_path (str): 视频文件路径
            video_player (VideoPlayer): 视频播放器组件
        """
        # 创建或重用视频详情视图
        if not self.video_details:
            self.video_details = VideoDetailsPanel()
        
        # 更新详情信息
        self.video_details.update_details(file_path, video_player)
        
        # 设置为当前视图
        self.current_view = self.video_details
        
        # 添加到布局
        self.layout().addWidget(self.video_details)

    def select_annotation_in_image(self, annotation):
        """
        当在图片上选中任意标注元素时，在详情面板中同步选中对应的条目

        Args:
            annotation: 被选中的标注对象(矩形或多边形)
        """
        # 只有当当前视图为图片详情视图时才处理
        if self.current_view == self.image_details and self.image_details:
            self.image_details.select_annotation_in_image(annotation)