from PyQt5 import sip
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QSplitter
from PyQt5.QtCore import Qt


class VideoDetailsPanel(QWidget):
    """
    视频详情面板类，用于显示视频文件的详细信息
    """

    def __init__(self):
        """
        初始化视频详情面板
        """
        super().__init__()
        self.current_file_path = None
        self.init_ui()

    def init_ui(self):
        """
        初始化视频详情面板的用户界面
        """
        layout = QVBoxLayout(self)

        # 创建分割器实现上下布局
        self.splitter = QSplitter(Qt.Vertical)

        # 上部分：显示视频基本信息
        self.info_label = QLabel("视频信息:")
        self.info_list = QListWidget()

        # 下部分：显示视频元数据
        self.metadata_label = QLabel("元数据:")
        self.metadata_list = QListWidget()

        # 创建包含标签和列表的widget
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.addWidget(self.info_label)
        info_layout.addWidget(self.info_list)

        metadata_widget = QWidget()
        metadata_layout = QVBoxLayout(metadata_widget)
        metadata_layout.addWidget(self.metadata_label)
        metadata_layout.addWidget(self.metadata_list)

        # 添加到分割器
        self.splitter.addWidget(info_widget)
        self.splitter.addWidget(metadata_widget)

        # 设置初始大小比例为1:1
        self.splitter.setSizes([500, 500])

        layout.addWidget(self.splitter)
        self.setLayout(layout)

    def update_details(self, file_path, video_player=None):
        """
        更新视频详情面板显示的内容

        Args:
            file_path (str): 文件路径
            video_player (VideoPlayer): 视频播放器组件
        """
        # 检查列表组件是否仍然有效
        if (self.info_list and sip.isdeleted(self.info_list)) or \
           (self.metadata_list and sip.isdeleted(self.metadata_list)):
            return

        self.current_file_path = file_path

        # 清空现有内容
        if self.info_list and not sip.isdeleted(self.info_list):
            self.info_list.clear()
        if self.metadata_list and not sip.isdeleted(self.metadata_list):
            self.metadata_list.clear()

        # 显示基本信息
        if self.info_list and not sip.isdeleted(self.info_list):
            self.info_list.addItem(f"文件路径: {file_path}")
            self.info_list.addItem(f"文件名: {file_path.split('/')[-1]}")

        if video_player:
            # 显示视频相关信息
            if self.info_list and not sip.isdeleted(self.info_list):
                self.info_list.addItem("视频播放器: 已加载")

            # 如果有视频元数据，可以在这里显示
            # 这里只是一个示例，实际应用中可能需要从视频文件中提取元数据
            if self.metadata_list and not sip.isdeleted(self.metadata_list):
                self.metadata_list.addItem("时长: 未知")
                self.metadata_list.addItem("分辨率: 未知")
                self.metadata_list.addItem("编码格式: 未知")
                self.metadata_list.addItem("帧率: 未知")
