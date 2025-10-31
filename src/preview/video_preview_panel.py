import os

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QSlider, QLabel, QSizePolicy, QGraphicsView, QGraphicsScene, QSplitter, QListWidget, QListWidgetItem, QInputDialog
from PyQt5.QtCore import Qt, QTimer, QUrl, QEvent, QRectF, QSizeF, pyqtSignal
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt5.QtGui import QPixmap, QIcon
import cv2
from src.logging_config import logger


class VideoPreviewPanel(QWidget):
    """
    视频预览面板类，用于播放视频文件
    支持播放、暂停、快进、快退功能
    """

    # 定义资源切换信号
    switch_to_previous = pyqtSignal()
    switch_to_next = pyqtSignal()

    def __init__(self):
        """
        初始化视频预览面板
        """
        super().__init__()
        self.media_player = QMediaPlayer()
        self.video_item = QGraphicsVideoItem()
        self.video_view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.video_view.setScene(self.scene)
        self.scene.addItem(self.video_item)
        self.media_player.setVideoOutput(self.video_item)
        self.control_container = None
        self.shortcut_label = None
        self.current_file_path = None
        self.thumbnail_list = None
        self.thumbnail_list_widget = None
        self.auto_capture_interval = 5  # 默认5秒自动抽帧
        self.auto_capture_timer = QTimer()
        self.auto_capture_timer.timeout.connect(self.capture_frame)
        self.captured_frames = []
        self.init_ui()
        self.setup_player()
        self.is_playing = False

        # 设置焦点策略，确保能接收键盘事件
        self.setFocusPolicy(Qt.StrongFocus)

    def init_ui(self):
        """
        初始化视频预览面板界面
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建主分割器
        self.main_splitter = QSplitter(Qt.Horizontal)

        # 左侧视频播放区域
        self.video_container = QWidget()
        video_layout = QVBoxLayout(self.video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)

        # 设置视频播放器的策略，使其能够扩展填充可用空间
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_view.setMinimumSize(1, 1)  # 设置最小尺寸以确保显示

        # 隐藏滚动条
        self.video_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.video_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 设置视频视图的对齐方式为居中
        self.video_view.setAlignment(Qt.AlignCenter)

        # 创建视频显示区域
        video_layout.addWidget(self.video_view)

        # 创建快捷键提示标签
        self.shortcut_label = QLabel("空格: 播放/暂停  A: 上一个  D: 下一个  W: 抽帧  Delete: 删除")
        self.shortcut_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 150);
                padding: 5px 10px;
                border-radius: 3px;
                font-size: 12px;
                font-family: Arial, sans-serif;
            }
        """)
        self.shortcut_label.setAttribute(Qt.WA_TranslucentBackground, True)
        self.shortcut_label.setParent(self.video_view)
        self.shortcut_label.move(10, 10)

        # 创建控制按钮容器，放置在视频下方
        self.control_container = QWidget()
        control_layout = QHBoxLayout(self.control_container)
        self.control_container.setLayout(control_layout)
        self.control_container.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 180);
                border-radius: 5px;
                padding: 5px;
            }
        """)
        self.control_container.setParent(self.video_view)
        self.control_container.move(0, 0)  # 初始位置，会在resizeEvent中调整

        self.play_btn = QPushButton("▶ 播放")
        self.play_btn.clicked.connect(self.play_pause)
        self.play_btn.setStyleSheet("QPushButton { color: white; border: none; padding: 5px; }")

        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.clicked.connect(self.stop)
        self.stop_btn.setStyleSheet("QPushButton { color: white; border: none; padding: 5px; }")

        self.forward_btn = QPushButton("⏩ 快进")
        self.forward_btn.clicked.connect(self.fast_forward)
        self.forward_btn.setStyleSheet("QPushButton { color: white; border: none; padding: 5px; }")

        self.backward_btn = QPushButton("⏪ 快退")
        self.backward_btn.clicked.connect(self.fast_backward)
        self.backward_btn.setStyleSheet("QPushButton { color: white; border: none; padding: 5px; }")

        # 添加抽帧按钮
        self.capture_btn = QPushButton("📸 抽帧")
        self.capture_btn.clicked.connect(self.capture_frame)
        self.capture_btn.setStyleSheet("QPushButton { color: white; border: none; padding: 5px; }")

        # 添加自动抽帧按钮
        self.auto_capture_btn = QPushButton("🔁 自动抽帧")
        self.auto_capture_btn.setCheckable(True)
        self.auto_capture_btn.clicked.connect(self.toggle_auto_capture)
        self.auto_capture_btn.setStyleSheet("QPushButton { color: white; border: none; padding: 5px; }")

        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.setRange(0, 0)
        self.time_slider.sliderMoved.connect(self.set_position)
        self.time_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #ddd;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: white;
                border: 1px solid #ddd;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #4CAF50;
                border-radius: 3px;
            }
        """)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("QLabel { color: white; }")

        control_layout.addWidget(self.play_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.backward_btn)
        control_layout.addWidget(self.forward_btn)
        control_layout.addWidget(self.capture_btn)
        control_layout.addWidget(self.auto_capture_btn)
        control_layout.addWidget(self.time_slider)
        control_layout.addWidget(self.time_label)

        video_layout.addWidget(self.control_container)

        # 右侧抽帧图片显示列表
        self.thumbnail_list = QWidget()
        thumbnail_layout = QVBoxLayout(self.thumbnail_list)
        thumbnail_layout.setContentsMargins(0, 0, 0, 0)

        self.thumbnail_list_widget = QListWidget()
        self.thumbnail_list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.thumbnail_list_widget.setResizeMode(QListWidget.Adjust)
        self.thumbnail_list_widget.setViewMode(QListWidget.IconMode)
        self.thumbnail_list_widget.setIconSize(QSizeF(120, 90).toSize())
        self.thumbnail_list_widget.setSpacing(5)
        self.thumbnail_list_widget.setMovement(QListWidget.Static)

        thumbnail_layout.addWidget(QLabel("抽帧图片:"))
        thumbnail_layout.addWidget(self.thumbnail_list_widget)

        self.main_splitter.addWidget(self.video_container)
        self.main_splitter.addWidget(self.thumbnail_list)
        self.main_splitter.setSizes([800, 200])

        layout.addWidget(self.main_splitter)
        self.setLayout(layout)

        # 确保视频播放器在初始化时居中显示
        self.video_view.centerOn(self.scene.sceneRect().center())

    def setup_player(self):
        """
        设置媒体播放器
        """
        # 连接媒体播放器信号
        self.media_player.stateChanged.connect(self.media_state_changed)
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        # 连接视频大小变化信号
        self.video_item.nativeSizeChanged.connect(self.video_native_size_changed)

        # 设置视频填充模式，确保视频能够充满显示区域
        self.video_item.setAspectRatioMode(Qt.KeepAspectRatio)
        self.video_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_view.setMinimumSize(1, 1)

        # 确保视频控件可以获取焦点以接收按键事件
        self.video_view.setFocusPolicy(Qt.StrongFocus)
        self.video_view.viewport().setFocusPolicy(Qt.StrongFocus)
        self.setFocusPolicy(Qt.StrongFocus)

        # 设置场景的对齐方式
        self.video_view.setAlignment(Qt.AlignCenter)

    def resizeEvent(self, event):
        """
        处理窗口大小调整事件
        """
        super().resizeEvent(event)

        view_rect = self.video_view.rect()
        self.scene.setSceneRect(QRectF(view_rect))

        # 确保视频在调整大小后仍然居中
        self.video_view.centerOn(self.scene.sceneRect().center())

        # 调整快捷键提示标签位置以跟随视频
        self.update_shortcut_label_position()

        # 调整控制容器位置到视频底部
        if self.control_container:
            container_width = self.control_container.width()
            view_width = self.video_view.width()
            self.control_container.move((view_width - container_width) // 2, self.video_view.height() - self.control_container.height() - 10)

    def update_shortcut_label_position(self):
        """
        更新快捷键提示标签位置，使其始终位于视频显示区域的左上角
        """
        if self.shortcut_label and self.video_item:
            # 获取视频项在视图中的位置
            video_pos = self.video_item.pos()
            # 将提示标签位置设置为视频左上角偏移10像素
            self.shortcut_label.move(int(video_pos.x()) + 10, int(video_pos.y()) + 10)

    def video_native_size_changed(self, size):
        """
        视频原生大小改变事件处理

        Args:
            size: 视频原始大小
        """
        # 当视频大小确定后，调整视频项大小以适应视图
        if self.video_item and size.isValid():
            # 使用适合视图的尺寸保持视频比例
            view_rect = self.video_view.rect()
            # 修复：将QSize转换为QSizeF以匹配scaled方法的参数要求
            view_size = QSizeF(view_rect.size())
            scaled_size = size.scaled(view_size, Qt.KeepAspectRatio)
            self.video_item.setSize(scaled_size)

            # 重新居中场景
            self.video_view.centerOn(self.scene.sceneRect().center())

            # 确保场景矩形正确
            self.scene.setSceneRect(QRectF(0, 0, max(1, view_rect.width()), max(1, view_rect.height())))

            # 确保视频视图居中对齐
            self.video_view.setAlignment(Qt.AlignCenter)
            # 确保视频项在场景中居中
            if not self.media_player.state() == QMediaPlayer.StoppedState:
                self.video_item.setPos(
                    (view_rect.width() - scaled_size.width()) / 2,
                    (view_rect.height() - scaled_size.height()) / 2
                )
                # 调整快捷键提示标签位置，使其跟随视频显示区域
                self.update_shortcut_label_position()

                # 调整控制容器位置到视频底部
                if self.control_container:
                    container_width = self.control_container.width()
                    view_width = self.video_view.width()
                    self.control_container.move((view_width - container_width) // 2, self.video_view.height() - self.control_container.height() - 10)

    def set_media(self, file_path):
        """
        设置要播放的媒体文件

        Args:
            file_path (str): 媒体文件路径
        """
        if os.path.exists(file_path):
            self.current_file_path = file_path
            media_content = QMediaContent(QUrl.fromLocalFile(file_path))
            self.media_player.setMedia(media_content)
            self.play_btn.setEnabled(True)
            self.time_label.setText("00:00 / 00:00")
            # 记录日志
            logger.info(f"设置视频媒体文件: {file_path}")
            # 自动播放视频
            self.media_player.play()
            # 显示控制容器
            self.control_container.show()
            # 确保视频居中显示
            self.video_view.centerOn(self.scene.sceneRect().center())
            # 确保视频视图居中对齐
            self.video_view.setAlignment(Qt.AlignCenter)

            # 清空抽帧列表
            self.thumbnail_list_widget.clear()
            self.captured_frames = []

            # 设置焦点到预览面板，确保能接收键盘事件
            self.setFocus()
        else:
            # 文件不存在时显示错误信息
            self.scene.clear()
            error_label = QLabel(f"视频文件不存在: {file_path}")
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
            self.scene.addWidget(error_label)
            self.play_btn.setEnabled(False)
            # 记录错误日志
            logger.error(f"视频文件不存在: {file_path}")

    def play_pause(self):
        """
        播放/暂停切换
        """
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
            logger.info("视频暂停播放")
        else:
            self.media_player.play()
            logger.info("视频开始播放")

    def stop(self):
        """
        停止播放，将视频定位到第1秒并暂停
        """
        # 将视频定位到第1秒(1000毫秒)
        self.media_player.setPosition(1000)
        # 暂停播放而不是停止播放，以保持视频显示
        self.media_player.pause()
        logger.info("视频停止播放并定位到第1秒")

    def fast_forward(self):
        """
        快进10秒
        """
        current_position = self.media_player.position()
        new_position = min(current_position + 10000, self.media_player.duration())  # 快进10秒
        self.media_player.setPosition(new_position)
        logger.info(f"视频快进到位置: {new_position}ms")

    def fast_backward(self):
        """
        快退10秒
        """
        current_position = self.media_player.position()
        new_position = max(current_position - 10000, 0)  # 快退10秒
        self.media_player.setPosition(new_position)
        logger.info(f"视频快退到位置: {new_position}ms")

    def set_position(self, position):
        """
        设置播放位置

        Args:
            position (int): 位置（毫秒）
        """
        self.media_player.setPosition(position)

    def media_state_changed(self, state):
        """
        媒体状态改变事件处理

        Args:
            state: 媒体播放器状态
        """
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.play_btn.setText("⏸ 暂停")
        else:
            self.play_btn.setText("▶ 播放")

    def position_changed(self, position):
        """
        播放位置改变事件处理

        Args:
            position (int): 当前位置（毫秒）
        """
        self.time_slider.setValue(position)
        self.update_time_label(position, self.media_player.duration())

    def duration_changed(self, duration):
        """
        媒体时长改变事件处理

        Args:
            duration (int): 总时长（毫秒）
        """
        self.time_slider.setRange(0, duration)
        self.update_time_label(self.media_player.position(), duration)

    def update_time_label(self, position, duration):
        """
        更新时间标签显示

        Args:
            position (int): 当前位置（毫秒）
            duration (int): 总时长（毫秒）
        """
        position_str = self.format_time(position)
        duration_str = self.format_time(duration)
        self.time_label.setText(f"{position_str} / {duration_str}")

    def format_time(self, ms):
        """
        格式化时间为 mm:ss 格式

        Args:
            ms (int): 毫秒数

        Returns:
            str: 格式化后的时间字符串
        """
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def capture_frame(self):
        """
        抽取当前帧并保存为图片
        """
        if not self.current_file_path:
            return

        # 获取当前播放位置
        position = self.media_player.position()

        # 创建保存帧图片的目录
        video_dir = os.path.dirname(self.current_file_path)
        video_name = os.path.splitext(os.path.basename(self.current_file_path))[0]
        frames_dir = os.path.join(video_dir, video_name)
        os.makedirs(frames_dir, exist_ok=True)

        # 生成文件名
        frame_time = self.format_time(position).replace(":", "-")
        frame_filename = f"frame_{frame_time}_{position}ms.jpg"
        frame_path = os.path.join(frames_dir, frame_filename)

        # 使用OpenCV捕获当前帧
        cap = cv2.VideoCapture(self.current_file_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, position)
        ret, frame = cap.read()

        if ret:
            cv2.imwrite(frame_path, frame)
            logger.info(f"帧已保存: {frame_path}")

            # 添加到抽帧列表
            self.add_frame_to_list(frame_path)
        else:
            logger.error(f"无法捕获帧: {position}ms")

        cap.release()

    def add_frame_to_list(self, frame_path):
        """
        将抽帧图片添加到列表显示

        Args:
            frame_path (str): 帧图片路径
        """
        # 创建列表项
        item = QListWidgetItem()
        item.setData(Qt.UserRole, frame_path)

        # 设置图标
        pixmap = QPixmap(frame_path)
        icon = QIcon(pixmap)
        item.setIcon(icon)

        # 设置显示文本
        frame_name = os.path.basename(frame_path)
        item.setText(frame_name)

        # 添加到列表
        self.thumbnail_list_widget.addItem(item)
        self.captured_frames.append(frame_path)

    def toggle_auto_capture(self):
        """
        切换自动抽帧状态
        """
        if self.auto_capture_btn.isChecked():
            # 获取抽帧间隔
            interval, ok = QInputDialog.getInt(self, "自动抽帧设置", "请输入抽帧间隔(秒):", self.auto_capture_interval, 1, 60)
            if ok:
                self.auto_capture_interval = interval
                # 启动自动抽帧定时器
                self.auto_capture_timer.start(self.auto_capture_interval * 1000)  # 转换为毫秒
                self.auto_capture_btn.setText("⏹ 停止自动抽帧")
                logger.info(f"启动自动抽帧，间隔: {self.auto_capture_interval}秒")
            else:
                self.auto_capture_btn.setChecked(False)
        else:
            # 停止自动抽帧
            self.auto_capture_timer.stop()
            self.auto_capture_btn.setText("🔁 自动抽帧")
            logger.info("停止自动抽帧")

    def delete_selected_frames(self):
        """
        删除选中的抽帧图片
        """
        selected_items = self.thumbnail_list_widget.selectedItems()
        if not selected_items:
            return

        for item in selected_items:
            frame_path = item.data(Qt.UserRole)
            try:
                os.remove(frame_path)
                logger.info(f"删除帧图片: {frame_path}")
                # 从列表中移除
                row = self.thumbnail_list_widget.row(item)
                self.thumbnail_list_widget.takeItem(row)
                # 从内部列表中移除
                if frame_path in self.captured_frames:
                    self.captured_frames.remove(frame_path)
            except Exception as e:
                logger.error(f"删除帧图片失败: {frame_path}, 错误: {e}")

    def keyPressEvent(self, event):
        """
        处理键盘按键事件

        Args:
            event: 键盘事件
        """
        # 处理空格键播放/暂停切换
        if event.key() == Qt.Key_Space:
            self.play_pause()
            event.accept()
        # 处理A/D键切换前后资源
        elif event.key() == Qt.Key_A:
            # 发送信号通知切换到前一个资源
            self.switch_to_previous.emit()
            logger.info("请求切换到前一个资源")
            event.accept()
        elif event.key() == Qt.Key_D:
            # 发送信号通知切换到后一个资源
            self.switch_to_next.emit()
            logger.info("请求切换到后一个资源")
            event.accept()
        # 处理W键抽帧
        elif event.key() == Qt.Key_W:
            self.capture_frame()
            event.accept()
        # 处理Delete键删除选中的抽帧图片
        elif event.key() == Qt.Key_Delete:
            self.delete_selected_frames()
            event.accept()
        else:
            super().keyPressEvent(event)
