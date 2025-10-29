from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QSlider, QLabel, QSizePolicy, QGraphicsView, QGraphicsScene
from PyQt5.QtCore import Qt, QTimer, QUrl, QEvent, QRectF, QSizeF, pyqtSignal
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QGraphicsVideoItem
import os
from ..logging_config import logger


class VideoPlayer(QWidget):
    """
    视频播放器类，用于播放视频文件
    支持播放、暂停、快进、快退功能
    """

    # 定义资源切换信号
    switch_to_previous = pyqtSignal()
    switch_to_next = pyqtSignal()

    def __init__(self):
        """
        初始化视频播放器
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
        self.init_ui()
        self.setup_player()
        self.is_playing = False

        # 设置焦点策略，确保能接收键盘事件
        self.setFocusPolicy(Qt.StrongFocus)

    def init_ui(self):
        """
        初始化视频播放器界面
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

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
        layout.addWidget(self.video_view)

        # 创建控制按钮容器，设置为悬浮在视频上方
        self.control_container = QWidget(self)
        control_layout = QHBoxLayout(self.control_container)
        self.control_container.setLayout(control_layout)
        self.control_container.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 180);
                border-radius: 5px;
            }
        """)

        # 设置控制容器的位置和大小
        self.control_container.setGeometry(0, 0, 400, 40)
        self.control_container.move(
            (self.width() - self.control_container.width()) // 2,
            self.height() - self.control_container.height() - 20
        )

        self.play_btn = QPushButton("▶ 播放")
        self.play_btn.clicked.connect(self.play_pause)
        self.play_btn.setStyleSheet("QPushButton { color: white; border: none; }")

        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.clicked.connect(self.stop)
        self.stop_btn.setStyleSheet("QPushButton { color: white; border: none; }")

        self.forward_btn = QPushButton("⏩ 快进")
        self.forward_btn.clicked.connect(self.fast_forward)
        self.forward_btn.setStyleSheet("QPushButton { color: white; border: none; }")

        self.backward_btn = QPushButton("⏪ 快退")
        self.backward_btn.clicked.connect(self.fast_backward)
        self.backward_btn.setStyleSheet("QPushButton { color: white; border: none; }")

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
        control_layout.addWidget(self.time_slider)
        control_layout.addWidget(self.time_label)

        # 创建快捷键提示标签 - 修正版本
        self.shortcut_label = QLabel("空格: 播放/暂停  A: 上一个  D: 下一个  Delete: 删除")
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

        # 调整控制容器位置，使其悬浮在视频上方且不影响视频居中
        if self.control_container:
            self.control_container.move(
                (self.width() - self.control_container.width()) // 2,
                self.height() - self.control_container.height() - 20
            )

        # 确保视频在调整大小后仍然居中
        self.video_view.centerOn(self.scene.sceneRect().center())
        
        # 调整快捷键提示标签位置以跟随视频
        self.update_shortcut_label_position()

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

    def set_media(self, file_path):
        """
        设置要播放的媒体文件

        Args:
            file_path (str): 媒体文件路径
        """
        if os.path.exists(file_path):
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
        else:
            super().keyPressEvent(event)
