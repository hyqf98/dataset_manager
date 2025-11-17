import os
import cv2
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QLabel, QSizePolicy, \
    QSplitter, QListWidget, QListWidgetItem, QMessageBox, QFileDialog, QSlider, QGraphicsView, QGraphicsScene, QInputDialog
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSizeF, QThread, QRectF
from PyQt6.QtGui import QPixmap, QImage, QIcon
from ..data_source.data_source_panel import DataSource
from ..logging_config import logger


class VideoCaptureThread(QThread):
    """
    视频捕获线程类，用于在后台线程中捕获视频帧
    """
    frame_ready = pyqtSignal(np.ndarray)
    error_occurred = pyqtSignal(str)

    def __init__(self, stream_url):
        super().__init__()
        self.stream_url = stream_url
        self.cap = None
        self.is_running = False

    def run(self):
        """
        线程主函数
        """
        try:
            # 打开视频流
            self.cap = cv2.VideoCapture(self.stream_url)
            
            if not self.cap.isOpened():
                self.error_occurred.emit("无法打开视频流")
                return

            self.is_running = True
            
            while self.is_running:
                ret, frame = self.cap.read()
                if ret:
                    # 发送帧到主线程
                    self.frame_ready.emit(frame)
                else:
                    self.error_occurred.emit("无法读取视频帧")
                    break
                    
        except Exception as e:
            self.error_occurred.emit(f"视频捕获异常: {str(e)}")
        finally:
            self.stop_capture()

    def stop_capture(self):
        """
        停止视频捕获
        """
        self.is_running = False
        if self.cap:
            self.cap.release()
            self.cap = None


class LivePreviewPanel(QWidget):
    """
    直播源预览面板类，用于播放直播流
    支持播放、录制、截图功能
    """

    # 定义资源切换信号
    switch_to_previous = pyqtSignal()
    switch_to_next = pyqtSignal()

    def __init__(self, data_source: DataSource):
        """
        初始化直播预览面板

        Args:
            data_source (DataSource): 直播源数据
        """
        super().__init__()
        self.data_source = data_source
        
        # 视频捕获线程
        self.capture_thread = None
        self.current_frame = None

        # 录制相关
        self.is_recording = False
        self.video_writer = None
        self.recorded_frames = 0
        self.record_file_path = ""

        # 截图相关
        self.captured_frames = []
        
        # 自动抽帧相关
        self.auto_capture_interval = 5  # 默认5秒自动抽帧
        self.auto_capture_timer = QTimer()
        self.auto_capture_timer.timeout.connect(self.capture_frame)

        # 定时器用于更新显示
        self.display_timer = QTimer()
        self.display_timer.timeout.connect(self.update_display)
        self.display_timer.start(33)  # 约30 FPS

        self.is_fullscreen = False  # 添加全屏模式标志
        self.init_ui()

        # 开始播放直播流
        self.set_media(data_source.stream_url)

        # 设置焦点策略，确保能接收键盘事件
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # 设置大小策略，确保能够正确填充预览区域
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def init_ui(self):
        """
        初始化直播预览面板界面
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建主分割器
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧视频播放区域
        self.video_container = QWidget()
        video_layout = QVBoxLayout(self.video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)

        # 设置视频播放器的策略，使其能够扩展填充可用空间
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_container.setMinimumSize(1, 1)  # 设置最小尺寸以确保显示

        # 创建工具栏
        self.toolbar = QHBoxLayout()
        self.toolbar.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.toolbar.setSpacing(5)
        self.toolbar.setContentsMargins(5, 5, 5, 5)  # 添加边距，避免按钮紧贴边框

        # 添加工具栏伸缩空间
        self.toolbar.addStretch()

        # 添加工具栏到视频布局
        video_layout.addLayout(self.toolbar)

        # 创建视频显示区域 (使用QGraphicsView显示图像)
        self.video_view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.video_view.setScene(self.scene)
        self.video_view.setMinimumSize(1, 1)
        
        # 隐藏滚动条
        self.video_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.video_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 设置视频视图的对齐方式为居中
        self.video_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        video_layout.addWidget(self.video_view)

        # 创建快捷键说明标签(在video_view创建之后)
        self.shortcut_label = QLabel("快捷键: 空格=播放/暂停 | W=截图 | A/D=切换资源 | F11=全屏 | Delete=删除")
        self.shortcut_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 128);
                color: white;
                padding: 5px 10px;
                border-radius: 3px;
                font-size: 12px;
            }
        """)
        self.shortcut_label.setParent(self.video_view)
        self.shortcut_label.move(10, 10)
        self.shortcut_label.show()  # 确保标签可见

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

        # 添加全屏切换按钮
        self.fullscreen_btn = QPushButton("☐ 全屏")
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen_mode)
        self.fullscreen_btn.setStyleSheet("QPushButton { color: white; border: none; padding: 5px; }")

        # 录制按钮
        self.record_btn = QPushButton("⏺ 开始录制")
        self.record_btn.setCheckable(True)
        self.record_btn.clicked.connect(self.toggle_record)
        self.record_btn.setStyleSheet("QPushButton { color: white; border: none; padding: 5px; }")

        # 截图按钮
        self.capture_btn = QPushButton("📸 抽帧")
        self.capture_btn.clicked.connect(self.capture_frame)
        self.capture_btn.setStyleSheet("QPushButton { color: white; border: none; padding: 5px; }")
        
        # 自动抽帧按钮
        self.auto_capture_btn = QPushButton("🔁 自动抽帧")
        self.auto_capture_btn.setCheckable(True)
        self.auto_capture_btn.clicked.connect(self.toggle_auto_capture)
        self.auto_capture_btn.setStyleSheet("QPushButton { color: white; border: none; padding: 5px; }")

        # 添加时间滑块和标签(虽然直播没有时间，但为了保持一致性)
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setRange(0, 0)
        self.time_slider.setEnabled(False)  # 直播流不支持时间控制
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

        self.time_label = QLabel("LIVE")
        self.time_label.setStyleSheet("QLabel { color: white; }")

        control_layout.addWidget(self.fullscreen_btn)
        control_layout.addWidget(self.play_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.backward_btn)
        control_layout.addWidget(self.forward_btn)
        control_layout.addWidget(self.record_btn)
        control_layout.addWidget(self.capture_btn)
        control_layout.addWidget(self.auto_capture_btn)
        control_layout.addWidget(self.time_slider)
        control_layout.addWidget(self.time_label)

        video_layout.addWidget(self.control_container)

        # 右侧录制视频和截图显示列表
        self.media_list = QWidget()
        media_layout = QVBoxLayout(self.media_list)
        media_layout.setContentsMargins(0, 0, 0, 0)

        self.media_list_widget = QListWidget()
        self.media_list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.media_list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.media_list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.media_list_widget.setIconSize(QSizeF(120, 90).toSize())
        self.media_list_widget.setSpacing(5)
        self.media_list_widget.setMovement(QListWidget.Movement.Static)

        media_layout.addWidget(QLabel("录制视频和抽帧图片:"))
        media_layout.addWidget(self.media_list_widget)
        
        # 添加删除按钮
        delete_btn = QPushButton("🗑️ 删除选中")
        delete_btn.clicked.connect(self.delete_selected_media)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        media_layout.addWidget(delete_btn)

        self.main_splitter.addWidget(self.video_container)
        self.main_splitter.addWidget(self.media_list)
        # 调整分割器的初始大小比例，使视频区域更宽，与视频播放面板保持一致
        self.main_splitter.setSizes([800, 200])

        layout.addWidget(self.main_splitter)
        self.setLayout(layout)

        # 加载已有的录制文件和截图
        self.load_existing_media()

        # 显示控制容器
        self.control_container.show()

    def resizeEvent(self, a0):
        """
        处理窗口大小调整事件
        """
        super().resizeEvent(a0)
        
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
        if hasattr(self, 'shortcut_label') and self.shortcut_label:
            # 将提示标签位置设置为视频左上角偏移10像素
            self.shortcut_label.move(10, 10)
            self.shortcut_label.raise_()  # 确保标签显示在最上层

    def set_media(self, stream_url):
        """
        设置要播放的直播流

        Args:
            stream_url (str): 直播流地址
        """
        if stream_url:
            # 停止现有的捕获线程
            if self.capture_thread and self.capture_thread.isRunning():
                self.capture_thread.stop_capture()
                self.capture_thread.quit()
                self.capture_thread.wait()

            # 创建新的捕获线程
            self.capture_thread = VideoCaptureThread(stream_url)
            self.capture_thread.frame_ready.connect(self.on_frame_ready)
            self.capture_thread.error_occurred.connect(self.on_capture_error)
            self.capture_thread.start()
            
            self.play_btn.setText("⏸ 暂停")
            logger.info(f"设置直播流: {stream_url}")
            
            # 确保视频居中显示
            self.video_view.centerOn(self.scene.sceneRect().center())
            # 确保视频视图居中对齐
            self.video_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            # URL无效时显示错误信息
            self.scene.clear()
            error_label = QLabel("直播流地址无效")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
            self.scene.addWidget(error_label)
            self.play_btn.setEnabled(False)
            logger.error("直播流地址无效")

    def on_frame_ready(self, frame):
        """
        处理接收到的视频帧

        Args:
            frame (np.ndarray): 视频帧
        """
        self.current_frame = frame.copy()
        
        # 如果正在录制，写入帧
        if self.is_recording and self.video_writer:
            self.video_writer.write(frame)

    def on_capture_error(self, error_msg):
        """
        处理捕获错误

        Args:
            error_msg (str): 错误信息
        """
        logger.error(f"视频捕获错误: {error_msg}")
        self.scene.clear()
        error_label = QLabel(f"错误: {error_msg}")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
        self.scene.addWidget(error_label)

    def update_display(self):
        """
        更新显示
        """
        if self.current_frame is not None:
            try:
                # 转换颜色空间 BGR to RGB
                rgb_frame = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB)
                
                # 获取帧的高度和宽度
                h, w, ch = rgb_frame.shape
                bytes_per_line = ch * w
                
                # 创建QImage
                q_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                
                # 缩放图像以适应视图大小并保持宽高比
                view_size = self.video_view.size()
                if view_size.width() > 0 and view_size.height() > 0:
                    scaled_img = q_img.scaled(view_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    pixmap = QPixmap.fromImage(scaled_img)
                    
                    # 清除场景并添加新图像
                    self.scene.clear()
                    pixmap_item = self.scene.addPixmap(pixmap)
                    
                    # 确保场景矩形正确
                    view_rect = self.video_view.rect()
                    self.scene.setSceneRect(QRectF(0, 0, max(1, view_rect.width()), max(1, view_rect.height())))
                    
                    # 确保视频项在场景中居中
                    pixmap_item.setPos(
                        (view_rect.width() - pixmap.width()) / 2,
                        (view_rect.height() - pixmap.height()) / 2
                    )
                    
                    # 居中显示
                    self.video_view.centerOn(self.scene.sceneRect().center())
            except Exception as e:
                logger.error(f"更新显示时出错: {e}")

    def play_pause(self):
        """
        播放/暂停切换
        """
        # 注意：在OpenCV实现中，暂停需要特殊处理
        # 这里简化处理，仅更改按钮文本
        if self.play_btn.text() == "▶ 播放":
            self.play_btn.setText("⏸ 暂停")
            logger.info("直播继续播放")
        else:
            self.play_btn.setText("▶ 播放")
            logger.info("直播暂停播放")

    def stop(self):
        """
        停止播放直播流
        """
        try:
            logger.info("开始停止直播播放...")
            
            # 1. 先停止自动抽帧(如果正在进行)
            if self.auto_capture_timer and self.auto_capture_timer.isActive():
                self.auto_capture_timer.stop()
                self.auto_capture_btn.setChecked(False)
                self.auto_capture_btn.setText("🔁 自动抽帧")
                logger.info("已停止自动抽帧")
            
            # 2. 停止录制(如果正在进行)
            if self.is_recording:
                self.record_btn.setChecked(False)
                self.stop_recording()
                logger.info("已停止录制")
            
            # 3. 清除当前帧(在停止线程之前，防止update_display继续处理)
            self.current_frame = None
            logger.info("已清除当前帧")
            
            # 4. 停止捕获线程
            if self.capture_thread and self.capture_thread.isRunning():
                logger.info("正在停止捕获线程...")
                self.capture_thread.stop_capture()
                self.capture_thread.quit()
                # 等待线程结束，但设置超时防止无限等待
                if not self.capture_thread.wait(3000):  # 等待最多3秒
                    logger.warning("捕获线程未能在3秒内停止")
                    self.capture_thread.terminate()  # 强制终止
                    self.capture_thread.wait(1000)  # 再等1秒
                logger.info("捕获线程已停止")
            
            # 5. 清空场景并显示停止标签
            self.scene.clear()
            stop_label = QLabel("直播已停止")
            stop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stop_label.setStyleSheet("QLabel { color: white; font-weight: bold; font-size: 16px; }")
            self.scene.addWidget(stop_label)
            
            # 6. 更新按钮状态
            self.play_btn.setText("▶ 播放")
            
            logger.info("直播播放已完全停止")
        except Exception as e:
            logger.error(f"停止直播流时出错: {e}", exc_info=True)
            # 即使出错也要确保清理资源
            try:
                self.current_frame = None
                if self.capture_thread and self.capture_thread.isRunning():
                    self.capture_thread.terminate()
                    self.capture_thread.wait(1000)
            except Exception as cleanup_error:
                logger.error(f"清理资源时出错: {cleanup_error}")

    def fast_forward(self):
        """
        快进(直播流中不实际快进，仅记录日志)
        """
        logger.info("尝试快进直播流(不支持)")

    def fast_backward(self):
        """
        快退(直播流中不实际快退，仅记录日志)
        """
        logger.info("尝试快退直播流(不支持)")

    def toggle_record(self):
        """
        切换录制状态
        """
        if self.record_btn.isChecked():
            # 开始录制
            self.start_recording()
        else:
            # 停止录制
            self.stop_recording()

    def start_recording(self):
        """
        开始录制视频
        """
        if not self.data_source.save_path:
            QMessageBox.warning(self, "警告", "未设置文件保存路径!")
            self.record_btn.setChecked(False)
            return

        if not os.path.exists(self.data_source.save_path):
            QMessageBox.warning(self, "警告", "文件保存路径不存在!")
            self.record_btn.setChecked(False)
            return

        try:
            # 生成录制文件名
            import time
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            self.record_file_path = os.path.join(self.data_source.save_path, f"record_{timestamp}.mp4")

            if self.current_frame is not None:
                h, w = self.current_frame.shape[:2]
            else:
                # 默认分辨率
                w, h = 640, 480

            # 初始化视频写入器
            self.video_writer = cv2.VideoWriter(
                self.record_file_path,
                cv2.VideoWriter_fourcc(*'mp4v'),
                20.0,  # 帧率
                (w, h)  # 分辨率
            )

            self.is_recording = True
            self.record_btn.setText("⏹ 停止录制")
            logger.info(f"开始录制视频: {self.record_file_path}")
        except Exception as e:
            logger.error(f"开始录制视频时出错: {e}")
            QMessageBox.critical(self, "错误", f"开始录制视频时出错: {e}")
            self.record_btn.setChecked(False)

    def stop_recording(self):
        """
        停止录制视频
        """
        if self.is_recording and self.video_writer:
            try:
                self.video_writer.release()
                self.video_writer = None
                self.is_recording = False
                self.record_btn.setText("⏺ 开始录制")
                logger.info(f"停止录制视频: {self.record_file_path}")

                # 添加录制的视频到媒体列表
                self.add_media_to_list(self.record_file_path)
            except Exception as e:
                logger.error(f"停止录制视频时出错: {e}")
                QMessageBox.critical(self, "错误", f"停止录制视频时出错: {e}")

    def capture_frame(self):
        """
        截取当前帧并保存为图片
        """
        if not self.data_source.save_path:
            QMessageBox.warning(self, "警告", "未设置文件保存路径!")
            return

        # 如果保存路径不存在，自动创建
        if not os.path.exists(self.data_source.save_path):
            try:
                os.makedirs(self.data_source.save_path, exist_ok=True)
                logger.info(f"创建保存路径: {self.data_source.save_path}")
            except Exception as e:
                logger.error(f"创建保存路径失败: {e}")
                QMessageBox.critical(self, "错误", f"创建保存路径失败: {e}")
                return

        if self.current_frame is None:
            QMessageBox.warning(self, "警告", "当前没有可抽帧的画面!")
            return

        try:
            # 生成抽帧文件名
            import time
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            frame_path = os.path.join(self.data_source.save_path, f"frame_{timestamp}.jpg")

            # 保存当前帧为图片
            cv2.imwrite(frame_path, self.current_frame)
            logger.info(f"抽帧已保存: {frame_path}")

            # 添加到媒体列表
            self.add_media_to_list(frame_path)
        except Exception as e:
            logger.error(f"抽帧时出错: {e}")
            QMessageBox.critical(self, "错误", f"抽帧时出错: {e}")
    
    def toggle_auto_capture(self):
        """
        切换自动抽帧状态
        """
        if self.auto_capture_btn.isChecked():
            # 获取抽帧间隔
            interval, ok = QInputDialog.getInt(self, "自动抽帧设置", "请输入抽帧间隔(秒):", self.auto_capture_interval, 1, 3600)
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

    def add_media_to_list(self, media_path):
        """
        将媒体文件添加到列表显示

        Args:
            media_path (str): 媒体文件路径
        """
        # 创建列表项
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, media_path)

        # 设置图标(根据文件类型)
        if media_path.lower().endswith(('.mp4', '.avi', '.mov')):
            # 视频文件，提取第一帧作为缩略图
            pixmap = self.extract_video_thumbnail(media_path)
            if pixmap and not pixmap.isNull():
                pixmap = pixmap.scaled(120, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                icon = QIcon(pixmap)
            else:
                # 如果提取失败，创建默认视频图标
                icon = self.create_default_video_icon()
        else:
            # 图片文件，加载缩略图
            pixmap = QPixmap(media_path)
            if pixmap.isNull():
                # 如果无法加载图像，创建默认图片图标
                icon = self.create_default_image_icon()
            else:
                # 缩放图像以适应显示
                pixmap = pixmap.scaled(120, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                icon = QIcon(pixmap)

        item.setIcon(icon)

        # 设置显示文本
        media_name = os.path.basename(media_path)
        item.setText(media_name)

        # 添加到列表
        self.media_list_widget.addItem(item)
        self.captured_frames.append(media_path)

    def extract_video_thumbnail(self, video_path):
        """
        从视频中提取第一帧作为缩略图

        Args:
            video_path (str): 视频文件路径

        Returns:
            QPixmap: 缩略图，如果提取失败返回None
        """
        try:
            # 使用OpenCV打开视频
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.warning(f"无法打开视频文件: {video_path}")
                return None

            # 读取第一帧
            ret, frame = cap.read()
            cap.release()

            if not ret or frame is None:
                logger.warning(f"无法读取视频第一帧: {video_path}")
                return None

            # 转换BGR到RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w

            # 创建QImage
            q_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            # 转换为QPixmap
            pixmap = QPixmap.fromImage(q_img.copy())

            return pixmap
        except Exception as e:
            logger.error(f"提取视频缩略图时出错: {video_path}, 错误: {e}")
            return None

    def create_default_video_icon(self):
        """
        创建默认的视频图标

        Returns:
            QIcon: 默认视频图标
        """
        # 创建一个带有播放符号的默认图标
        pixmap = QPixmap(120, 90)
        pixmap.fill(Qt.GlobalColor.darkGray)
        
        from PyQt6.QtGui import QPainter, QPen, QBrush, QPolygon
        from PyQt6.QtCore import QPoint
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制播放三角形
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.setBrush(QBrush(Qt.GlobalColor.white))
        
        # 三角形的三个顶点
        points = [
            QPoint(40, 25),
            QPoint(40, 65),
            QPoint(80, 45)
        ]
        polygon = QPolygon(points)
        painter.drawPolygon(polygon)
        
        painter.end()
        
        return QIcon(pixmap)

    def create_default_image_icon(self):
        """
        创建默认的图片图标

        Returns:
            QIcon: 默认图片图标
        """
        # 创建一个简单的默认图标
        pixmap = QPixmap(120, 90)
        pixmap.fill(Qt.GlobalColor.lightGray)
        
        from PyQt6.QtGui import QPainter, QPen
        
        painter = QPainter(pixmap)
        painter.setPen(QPen(Qt.GlobalColor.gray, 2))
        painter.drawRect(10, 10, 100, 70)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "图片")
        painter.end()
        
        return QIcon(pixmap)

    def load_existing_media(self):
        """
        加载已存在的录制视频和截图
        """
        if not self.data_source.save_path or not os.path.exists(self.data_source.save_path):
            return

        try:
            # 查找保存路径下的所有媒体文件
            for file_name in os.listdir(self.data_source.save_path):
                file_path = os.path.join(self.data_source.save_path, file_name)
                if file_name.lower().endswith(('.mp4', '.avi', '.mov', '.jpg', '.jpeg', '.png')):
                    self.add_media_to_list(file_path)
        except Exception as e:
            logger.error(f"加载现有媒体文件时出错: {e}")

    def delete_selected_media(self):
        """
        删除选中的媒体文件
        """
        selected_items = self.media_list_widget.selectedItems()
        if not selected_items:
            return

        reply = QMessageBox.question(self, "确认", f"确定要删除选中的 {len(selected_items)} 个文件吗?\n此操作不可恢复!",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            for item in selected_items:
                media_path = item.data(Qt.ItemDataRole.UserRole)
                try:
                    os.remove(media_path)
                    logger.info(f"删除媒体文件: {media_path}")
                    # 从列表中移除
                    row = self.media_list_widget.row(item)
                    self.media_list_widget.takeItem(row)
                    # 从内部列表中移除
                    if media_path in self.captured_frames:
                        self.captured_frames.remove(media_path)
                except Exception as e:
                    logger.error(f"删除媒体文件失败: {media_path}, 错误: {e}")

    def toggle_fullscreen_mode(self):
        """
        切换全屏模式
        """
        self.set_fullscreen(not self.is_fullscreen)

    def set_fullscreen(self, fullscreen):
        """
        设置全屏模式

        Args:
            fullscreen (bool): 是否进入全屏模式
        """
        self.is_fullscreen = fullscreen
        if fullscreen:
            # 隐藏媒体列表和分割器手柄
            self.media_list.setVisible(False)
            self.main_splitter.handle(1).setVisible(False)
            # 设置分割器的大小，只显示视频部分
            self.main_splitter.setSizes([self.main_splitter.width(), 0])
            # 更新按钮文本
            self.fullscreen_btn.setText("❐ 退出全屏")
        else:
            # 恢复媒体列表和分割器手柄
            self.media_list.setVisible(True)
            self.main_splitter.handle(1).setVisible(True)
            # 恢复正常的分割器大小
            self.main_splitter.setSizes([800, 200])
            # 更新按钮文本
            self.fullscreen_btn.setText("☐ 全屏")

    def keyPressEvent(self, a0):
        """
        处理键盘按键事件

        Args:
            a0: 键盘事件
        """
        # 处理空格键播放/暂停切换
        if a0.key() == Qt.Key.Key_Space:
            self.play_pause()
            a0.accept()
        # 处理A/D键切换前后资源
        elif a0.key() == Qt.Key.Key_A:
            # 发送信号通知切换到前一个资源
            self.switch_to_previous.emit()
            logger.info("请求切换到前一个资源")
            a0.accept()
        elif a0.key() == Qt.Key.Key_D:
            # 发送信号通知切换到后一个资源
            self.switch_to_next.emit()
            logger.info("请求切换到后一个资源")
            a0.accept()
        # 处理W键截图
        elif a0.key() == Qt.Key.Key_W:
            self.capture_frame()
            a0.accept()
        # 处理Delete键删除选中的媒体文件
        elif a0.key() == Qt.Key.Key_Delete:
            self.delete_selected_media()
            a0.accept()
        # 处理F11键切换全屏模式
        elif a0.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen_mode()
            a0.accept()
        else:
            super().keyPressEvent(a0)

    def closeEvent(self, a0):
        """
        关闭事件处理，确保释放资源

        Args:
            event: 关闭事件
        """
        # 停止自动截图(如果正在进行)
        if self.auto_capture_timer.isActive():
            self.auto_capture_timer.stop()
        
        # 停止录制(如果正在进行)
        if self.is_recording:
            self.stop_recording()

        # 停止捕获线程
        if self.capture_thread and self.capture_thread.isRunning():
            self.capture_thread.stop_capture()
            self.capture_thread.quit()
            self.capture_thread.wait()

        # 停止显示定时器
        if self.display_timer.isActive():
            self.display_timer.stop()

        # 释放视频写入器
        if self.video_writer:
            self.video_writer.release()

        event.accept()
        logger.info("直播预览面板已关闭")
