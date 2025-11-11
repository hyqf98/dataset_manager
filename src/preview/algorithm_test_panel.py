import os
import cv2
import numpy as np
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QLabel, QComboBox, QTextEdit, QMessageBox, QSplitter, QDialog
from PyQt5.QtCore import Qt, pyqtSignal, QUrl
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene
from ..logging_config import logger

# 延迟导入YOLO，避免在模块加载时就尝试导入
def import_yolo():
    try:
        import ultralytics
        # 使用 getattr 来获取 YOLO 类
        YOLO = getattr(ultralytics, 'YOLO')
        return YOLO
    except (ImportError, AttributeError):
        return None


class AlgorithmTestPanel(QDialog):
    """
    算法测试面板类，用于测试YOLO模型并显示原始图片和识别后图片的对比
    """
    # 定义信号
    switch_to_previous = pyqtSignal()
    switch_to_next = pyqtSignal()
    video_processing_finished = pyqtSignal(str)  # 视频处理完成信号
    video_processing_error = pyqtSignal(str)     # 视频处理错误信号

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.model_path = ""
        self.classes = []
        self.current_file_path = file_path  # 当前文件路径
        self.media_player = None
        self.video_item = None
        self.video_view = None
        self.scene = None
        self.video_thread = None  # 视频处理线程
        self.init_ui()
        self.load_file()

        # 连接模型和分类输入的变化信号
        self.model_combo.currentTextChanged.connect(self.on_model_or_classes_changed)
        self.classes_edit.textChanged.connect(self.on_model_or_classes_changed)

        # 视频处理信号（将在子线程中直接调用方法）
        pass

    def closeEvent(self, a0):
        """
        窗口关闭事件处理

        Args:
            a0: 关闭事件
        """
        # 停止正在进行的视频处理线程
        if self.video_thread and self.video_thread.isRunning():
            # 停止视频处理
            if hasattr(self.video_thread, 'stop'):
                self.video_thread.stop()
            # 等待线程结束
            self.video_thread.wait()

        # 停止媒体播放器
        if self.media_player:
            self.media_player.stop()

        # 调用父类的关闭事件
        super().closeEvent(a0)



    def init_ui(self):
        """
        初始化界面
        """
        self.setWindowTitle("算法测试")
        # 窗口大小将在加载文件时动态调整

        # 创建主布局
        main_layout = QVBoxLayout(self)

        # 创建上半部分：模型选择和分类输入
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_widget.setFixedHeight(100)  # 固定上半部分高度

        # 减小各部分之间的间距
        top_layout.setSpacing(10)  # 设置间距为10像素

        # 模型选择部分
        model_layout = QHBoxLayout()
        model_label = QLabel("YOLO模型:")
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setFixedWidth(150)  # 减小宽度

        # 从models.txt文件读取模型列表
        self.load_models_from_file()

        # 初始化模型路径
        self.init_model_paths()

        self.model_button = QPushButton("选择模型文件")
        self.model_button.clicked.connect(self.select_model_file)
        self.model_button.setFixedWidth(100)  # 固定按钮宽度

        # 减小模型标签和输入框之间的间距
        model_layout.setSpacing(5)  # 设置间距为5像素

        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo)
        model_layout.addWidget(self.model_button)

        # 分类输入部分
        classes_layout = QHBoxLayout()
        classes_label = QLabel("分类(可选):")
        self.classes_edit = QTextEdit()
        self.classes_edit.setFixedHeight(60)
        self.classes_edit.setPlaceholderText("每行输入一个分类，例如：\nperson\ncar\ndog")
        # 减小标签和输入框之间的间距
        classes_layout.addWidget(classes_label)
        classes_layout.addWidget(self.classes_edit)

        # 识别按钮
        self.test_button = QPushButton("识别")
        self.test_button.clicked.connect(self.run_test)
        self.test_button.setFixedWidth(60)  # 减小宽度

        # 上一张和下一张按钮
        self.prev_button = QPushButton("上一张")
        self.prev_button.clicked.connect(self.prev_image)
        self.next_button = QPushButton("下一张")
        self.next_button.clicked.connect(self.next_image)

        # 添加控件到上半部分布局
        top_layout.addLayout(model_layout)
        top_layout.addLayout(classes_layout)
        top_layout.addWidget(self.test_button)
        top_layout.addWidget(self.prev_button)
        top_layout.addWidget(self.next_button)
        top_layout.addStretch()

        # 减小按钮之间的间距
        top_layout.setSpacing(5)  # 设置间距为5像素

        # 创建下半部分：文件对比显示
        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout(bottom_widget)

        # 创建分割器用于左右对比
        splitter = QSplitter(Qt.Horizontal)  # type: ignore

        # 左侧：原始文件显示区域（动态大小）
        self.original_container = QWidget()
        self.original_layout = QVBoxLayout(self.original_container)
        self.original_layout.setContentsMargins(0, 0, 0, 0)
        # 垂直居中对齐通过其他方式实现
        self.original_image_label = QLabel("原始文件")
        self.original_image_label.setAlignment(Qt.AlignCenter)  # type: ignore
        self.original_image_label.setMinimumSize(400, 400)  # 动态大小
        self.original_image_label.setStyleSheet("border: 1px solid gray;")

        # 创建视频播放器组件
        self.setup_video_player()

        self.original_layout.addWidget(self.original_image_label)
        self.original_container.setLayout(self.original_layout)

        # 右侧：识别后的文件显示区域（动态大小）
        self.result_container = QWidget()
        self.result_layout = QVBoxLayout(self.result_container)
        self.result_layout.setContentsMargins(0, 0, 0, 0)
        # 垂直居中对齐通过其他方式实现
        self.result_image_label = QLabel("识别后文件")
        self.result_image_label.setAlignment(Qt.AlignCenter)  # type: ignore
        self.result_image_label.setMinimumSize(400, 400)  # 动态大小
        self.result_image_label.setStyleSheet("border: 1px solid gray;")
        self.result_layout.addWidget(self.result_image_label)
        self.result_container.setLayout(self.result_layout)

        # 添加到分割器
        splitter.addWidget(self.original_container)
        splitter.addWidget(self.result_container)
        splitter.setSizes([400, 400])  # 设置初始大小（动态大小）

        # 添加到下半部分布局
        bottom_layout.addWidget(splitter)

        # 添加到主布局
        main_layout.addWidget(top_widget)
        main_layout.addWidget(bottom_widget)

        self.setLayout(main_layout)

    def setup_video_player(self):
        """
        设置视频播放器
        """
        # 创建媒体播放器和视频项
        self.media_player = QMediaPlayer()
        self.video_item = QGraphicsVideoItem()
        self.video_view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.video_view.setScene(self.scene)
        self.scene.addItem(self.video_item)
        self.media_player.setVideoOutput(self.video_item)

        # 隐藏视频播放器，只在需要时显示
        self.video_view.hide()

        # 连接媒体播放器信号
        self.media_player.stateChanged.connect(self.media_state_changed)

        # 连接视频项大小变化信号
        self.video_item.nativeSizeChanged.connect(self.video_native_size_changed)

        # 将视频视图添加到原始文件显示区域
        self.original_layout.insertWidget(0, self.video_view)

    def video_native_size_changed(self, size):
        """
        视频原生大小改变事件处理

        Args:
            size: 视频原始大小
        """
        # 当视频大小确定后，调整视频项大小以适应视图
        self.resize_video_item()

    def select_model_file(self):
        """
        选择模型文件
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择YOLO模型文件",
            "",
            "模型文件 (*.pt *.pth *.h5 *.onnx);;所有文件 (*)"
        )
        if file_path:
            self.model_combo.setEditText(file_path)

    def init_model_paths(self):
        """
        初始化模型路径，创建用户目录下的.dataset_m/models路径用于缓存
        """
        try:
            # 获取用户主目录
            home_dir = os.path.expanduser("~")
            # 构建模型目录路径
            models_dir = os.path.join(home_dir, ".dataset_m", "models")

            # 如果目录不存在，创建它
            if not os.path.exists(models_dir):
                os.makedirs(models_dir)

            # 不再将目录中的模型文件添加到下拉列表，仅用作缓存目录
        except Exception as e:
            logger.error(f"初始化模型路径失败: {str(e)}")

    def load_models_from_file(self):
        """
        从models.txt文件加载模型列表
        """
        try:
            # 获取项目根目录
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            models_file = os.path.join(project_root, "models.txt")
            
            # 如果文件存在，读取模型列表
            if os.path.exists(models_file):
                with open(models_file, 'r', encoding='utf-8') as f:
                    models = [line.strip() for line in f.readlines() if line.strip()]
                    self.model_combo.addItems(models)
            else:
                # 如果文件不存在，使用默认模型列表
                self.model_combo.addItems([
                    "yolov8n.pt",
                    "yolov8s.pt",
                    "yolov8m.pt",
                    "yolov8l.pt",
                    "yolov8x.pt",
                    "yolov8s-world.pt",
                    "yolov8s-worldv2.pt"
                ])
        except Exception as e:
            logger.error(f"加载模型列表失败: {str(e)}")
            # 出现错误时使用默认模型列表
            self.model_combo.addItems([
                "yolov8n.pt",
                "yolov8s.pt",
                "yolov8m.pt",
                "yolov8l.pt",
                "yolov8x.pt",
                "yolov8s-world.pt",
                "yolov8s-worldv2.pt"
            ])

    def get_model_path(self, model_name):
        """
        获取模型文件路径，如果不存在则下载

        Args:
            model_name (str): 模型名称

        Returns:
            str: 模型文件路径
        """
        try:
            # 获取用户主目录
            home_dir = os.path.expanduser("~")
            # 构建模型目录路径
            models_dir = os.path.join(home_dir, ".dataset_m", "models")

            # 如果目录不存在，创建它
            if not os.path.exists(models_dir):
                os.makedirs(models_dir)

            # 构建模型文件路径
            model_path = os.path.join(models_dir, model_name)

            # 检查模型文件是否存在
            if os.path.exists(model_path):
                return model_path

            # 如果是预定义的YOLO模型，尝试下载
            predefined_models = ["yolov8n.pt", "yolov8s.pt", "yolov8m.pt", "yolov8l.pt", "yolov8x.pt", "yolov8s-world.pt", "yolov8s-worldv2.pt"]
            if model_name in predefined_models:
                # 尝试从Ultralytics下载模型
                try:
                    YOLO = import_yolo()
                    if YOLO is not None:
                        # 创建模型实例会自动下载
                        model = YOLO(model_name)
                        # 获取下载的模型路径
                        return model_path
                except Exception as e:
                    logger.error(f"下载模型失败: {str(e)}")
                    # 如果下载失败，返回模型名称（让YOLO库处理）
                    return model_name

            # 如果不是预定义模型且文件不存在，返回原路径
            return model_name
        except Exception as e:
            logger.error(f"获取模型路径失败: {str(e)}")
            # 如果出现错误，返回原始模型名称
            return model_name

    def show_image(self, file_path):
        """
        显示图片文件

        Args:
            file_path (str): 图片文件路径
        """
        # 隐藏视频播放器
        if self.video_view:
            self.video_view.hide()
            if self.media_player:
                self.media_player.stop()

        # 显示图片标签
        self.original_image_label.show()

        # 加载原始图片
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            return

        # 缩放图片以适应显示区域（保持宽高比）
        scaled_pixmap = pixmap.scaled(880, 800, Qt.KeepAspectRatio, Qt.SmoothTransformation)  # type: ignore
        self.original_image_label.setPixmap(scaled_pixmap)
        self.original_image_label.setAlignment(Qt.AlignCenter)  # type: ignore

        # 如果有模型路径，自动运行测试以更新右侧对比图片
        if self.model_path:
            self.run_test()

    def adjust_window_size_for_image(self, image_path):
        """
        根据图片大小调整窗口大小

        Args:
            image_path (str): 图片文件路径
        """
        try:
            # 使用OpenCV获取图片尺寸
            image = cv2.imread(image_path)
            if image is not None:
                height, width, _ = image.shape

                # 计算窗口大小：左侧资源宽度 + 右侧识别区域宽度(300) + 高度(资源高度 + 上部控件高度)
                window_width = min(width * 2, 1920)  # 左右两侧各一个资源宽度
                window_height = min(height + 200, 1080)  # 资源高度 + 上部控件高度

                # 调整窗口大小
                self.resize(window_width, window_height)
        except Exception as e:
            logger.error(f"调整图片窗口大小失败: {str(e)}")
            # 使用默认大小
            self.resize(1600, 1000)

    def show_video(self, file_path):
        """
        显示视频文件

        Args:
            file_path (str): 视频文件路径
        """
        # 隐藏图片标签
        self.original_image_label.hide()

        # 显示视频播放器
        if self.video_view and self.media_player and self.video_item:
            self.video_view.show()

            # 设置视频媒体文件
            media_content = QMediaContent(QUrl.fromLocalFile(file_path))
            self.media_player.setMedia(media_content)

            # 调整视频项大小以适应视图
            self.resize_video_item()

            # 确保视频播放器垂直居中
            self.video_view.setAlignment(Qt.AlignCenter)  # type: ignore

            # 自动播放视频
            # 使用 QTimer 延迟播放以确保媒体加载完成
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(100, self.media_player.play)

    def adjust_window_size_for_video(self, video_path):
        """
        根据视频大小调整窗口大小

        Args:
            video_path (str): 视频文件路径
        """
        try:
            # 使用OpenCV获取视频尺寸
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()

                # 计算窗口大小：左侧资源宽度 + 右侧识别区域宽度(资源宽度) + 高度(资源高度 + 上部控件高度)
                window_width = min(width * 2, 1920)  # 左右两侧各一个资源宽度
                window_height = min(height + 200, 1080)  # 资源高度 + 上部控件高度

                # 调整窗口大小
                self.resize(window_width, window_height)
        except Exception as e:
            logger.error(f"调整视频窗口大小失败: {str(e)}")
            # 使用默认大小
            self.resize(1600, 1000)

    def resize_video_item(self):
        """
        调整视频项大小以适应视图
        """
        if self.video_view and self.video_item:
            # 获取视图大小
            view_size = self.video_view.size()
            # 调整视频项大小
            from PyQt5.QtCore import QSizeF
            self.video_item.setSize(QSizeF(view_size))

            # 同步调整右侧显示区域大小
            self.sync_display_areas_size(view_size)

    def sync_display_areas_size(self, video_size):
        """
        同步调整左右两侧显示区域大小

        Args:
            video_size: 视频尺寸
        """
        try:
            # 设置左右两侧显示区域大小一致
            self.original_image_label.setMinimumSize(video_size.width(), video_size.height())
            self.result_image_label.setMinimumSize(video_size.width(), video_size.height())

            # 确保视频播放器大小与标签一致
            if self.video_view:
                self.video_view.setMinimumSize(video_size.width(), video_size.height())

            # 调整分割器大小
            # 通过调整窗口大小来触发布局更新
            current_size = self.size()
            self.resize(current_size.width(), current_size.height())
        except Exception as e:
            logger.error(f"同步显示区域大小失败: {str(e)}")

    def media_state_changed(self, state):
        """
        媒体状态改变事件处理

        Args:
            state: 媒体播放器状态
        """
        # 可以在这里处理播放状态变化
        pass

    def stop_current_video_processing(self):
        """
        停止当前正在进行的视频处理
        """
        try:
            # 停止正在进行的视频处理线程
            if hasattr(self, 'video_thread') and self.video_thread and self.video_thread.isRunning():
                # 停止视频处理
                if hasattr(self.video_thread, 'stop'):
                    self.video_thread.stop()
                # 等待线程结束
                self.video_thread.wait()

            # 停止媒体播放器
            if self.media_player:
                self.media_player.stop()

            # 停止结果视频播放器
            if hasattr(self, 'result_media_player') and self.result_media_player:
                self.result_media_player.stop()
        except Exception as e:
            logger.error(f"停止当前视频处理失败: {str(e)}")

    def clear_result_display(self):
        """
        清空右侧结果显示区域
        """
        try:
            # 清空右侧显示区域
            self.result_image_label.clear()
            self.result_image_label.setText("识别后文件")
            self.result_image_label.setAlignment(Qt.AlignCenter)  # type: ignore

            # 隐藏结果视频播放器
            if hasattr(self, 'result_video_view') and self.result_video_view:
                self.result_video_view.hide()
        except Exception as e:
            logger.error(f"清空右侧显示区域失败: {str(e)}")

    def load_file(self):
        """
        加载并显示原始文件（图片或视频）
        """
        if not os.path.exists(self.current_file_path):
            return

        # 停止当前正在进行的视频处理线程
        self.stop_current_video_processing()

        # 获取文件扩展名
        _, ext = os.path.splitext(self.current_file_path)
        ext = ext.lower()

        # 支持的图片格式
        image_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
        # 支持的视频格式
        video_formats = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv']

        # 如果是图片格式
        if ext in image_formats:
            self.show_image(self.current_file_path)
            # 调整窗口大小以适应图片
            self.adjust_window_size_for_image(self.current_file_path)
        # 如果是视频格式
        elif ext in video_formats:
            self.show_video(self.current_file_path)
            # 调整窗口大小以适应视频
            self.adjust_window_size_for_video(self.current_file_path)
        else:
            # 不支持的格式
            self.original_image_label.setText("不支持的文件格式")
            self.original_image_label.setAlignment(Qt.AlignCenter)  # type: ignore

    def on_model_or_classes_changed(self):
        """
        当模型或分类发生变化时，自动重新运行测试
        """
        # 如果已经设置了模型路径，则自动重新运行测试
        if self.model_path:
            self.run_test()

    def run_test(self):
        """
        运行算法测试
        """
        # 获取模型路径
        model_name = self.model_combo.currentText().strip()
        if not model_name:
            # 如果没有选择模型，清空结果图片
            self.result_image_label.clear()
            self.result_image_label.setText("识别后文件")
            return

        # 获取模型文件路径（如果不存在则下载）
        self.model_path = self.get_model_path(model_name)

        # 获取分类列表
        classes_text = self.classes_edit.toPlainText().strip()
        if classes_text:
            self.classes = [cls.strip() for cls in classes_text.split('\n') if cls.strip()]
        else:
            self.classes = []

        # 获取文件扩展名
        _, ext = os.path.splitext(self.current_file_path)
        ext = ext.lower()

        # 支持的图片格式
        image_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']
        # 支持的视频格式
        video_formats = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv']

        # 如果是图片格式，进行YOLO识别
        if ext in image_formats:
            try:
                # 导入YOLO
                YOLO = import_yolo()
                if YOLO is None:
                    QMessageBox.critical(self, "错误", "未安装ultralytics库，请先安装YOLO模型支持!")
                    return

                # 加载YOLO模型
                model = YOLO(self.model_path)

                # 进行推理
                if self.classes:
                    # 如果指定了分类，使用分类过滤
                    results = model(self.current_file_path)
                    # 过滤结果
                    filtered_results = []
                    for result in results:
                        if hasattr(result, 'names'):
                            filtered_boxes = []
                            for box in result.boxes:
                                class_id = int(box.cls)
                                if class_id < len(result.names) and result.names[class_id] in self.classes:
                                    filtered_boxes.append(box)
                            result.boxes = filtered_boxes
                            filtered_results.append(result)
                    results = filtered_results
                else:
                    # 否则检测所有类别
                    results = model(self.current_file_path)

                # 处理结果并绘制边界框
                self.display_result_image(results)

            except Exception as e:
                # 不显示错误消息，因为可能是模型正在加载或其他临时问题
                logger.error(f"算法测试失败: {str(e)}")
                # 清空结果图片
                self.result_image_label.clear()
                self.result_image_label.setText("识别后文件")
                self.result_image_label.setAlignment(Qt.AlignCenter)  # type: ignore
        # 如果是视频格式，进行视频帧识别
        elif ext in video_formats:
            try:
                # 导入YOLO
                YOLO = import_yolo()
                if YOLO is None:
                    QMessageBox.critical(self, "错误", "未安装ultralytics库，请先安装YOLO模型支持!")
                    return

                # 加载YOLO模型
                model = YOLO(self.model_path)

                # 使用流式处理视频
                self.display_result_video_stream(model)

            except Exception as e:
                # 不显示错误消息，因为可能是模型正在加载或其他临时问题
                logger.error(f"视频算法测试失败: {str(e)}")
                # 清空结果图片
                self.result_image_label.clear()
                self.result_image_label.setText("识别后文件")
                self.result_image_label.setAlignment(Qt.AlignCenter)  # type: ignore
        else:
            # 对于非图片和非视频文件，显示提示信息
            self.result_image_label.clear()
            self.result_image_label.setText("仅支持图片和视频文件识别")
            self.result_image_label.setAlignment(Qt.AlignCenter)  # type: ignore

    def display_result_image(self, results):
        """
        显示识别后的图片
        """
        try:
            # 读取原始图片
            image = cv2.imread(self.current_file_path)
            if image is None:
                return

            # 在图片上绘制检测结果
            for result in results:
                boxes = result.boxes if hasattr(result, 'boxes') else []
                if boxes is not None:
                    for box in boxes:
                        # 获取边界框坐标
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

                        # 获取类别ID和置信度
                        class_id = int(box.cls)
                        confidence = float(box.conf)

                        # 获取类别名称
                        if hasattr(result, 'names') and class_id < len(result.names):
                            class_name = result.names[class_id]
                        else:
                            class_name = str(class_id)

                        # 绘制边界框
                        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)

                        # 绘制标签
                        label = f"{class_name}: {confidence:.2f}"
                        cv2.putText(image, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            # 转换为QImage并显示
            height, width, channel = image.shape
            bytes_per_line = 3 * width
            # 使用正确的构造函数
            q_img = QImage(image.data.tobytes(), width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
            pixmap = QPixmap.fromImage(q_img)

            # 缩放图片以适应显示区域（保持宽高比）
            scaled_pixmap = pixmap.scaled(880, 800, Qt.KeepAspectRatio, Qt.SmoothTransformation)  # type: ignore
            self.result_image_label.setPixmap(scaled_pixmap)
            self.result_image_label.setAlignment(Qt.AlignCenter)  # type: ignore

        except Exception as e:
            QMessageBox.critical(self, "错误", f"显示识别结果失败: {str(e)}")
            logger.error(f"显示识别结果失败: {str(e)}")

    def display_result_video_stream(self, model):
        """
        使用流式处理显示视频识别后的结果

        Args:
            model: YOLO模型实例
        """
        try:
            # 隐藏图片标签
            self.result_image_label.hide()

            # 创建或显示视频结果播放器
            if not hasattr(self, 'result_video_view') or not self.result_video_view:
                self.setup_result_video_player()

            # 显示视频结果播放器
            self.result_video_view.show()

            # 启动实时视频流处理
            self.start_real_time_video_processing(model)

        except Exception as e:
            logger.error(f"显示视频识别结果失败: {str(e)}")
            # 显示错误信息
            self.result_video_view.hide()
            self.result_image_label.show()
            self.result_image_label.setText(f"视频识别失败: {str(e)}")
            self.result_image_label.setAlignment(Qt.AlignCenter)  # type: ignore

    def start_real_time_video_processing(self, model):
        """
        启动实时视频流处理

        Args:
            model: YOLO模型实例
        """
        try:
            # 创建实时视频处理线程
            from PyQt5.QtCore import QThread, pyqtSignal

            class RealTimeVideoProcessingThread(QThread):
                # 定义信号
                frame_processed = pyqtSignal(object)  # 处理后的帧信号
                processing_error = pyqtSignal(str)     # 处理错误信号

                def __init__(self, parent, video_path, model):
                    super().__init__(parent)
                    self.video_path = video_path
                    self.model = model
                    self.parent = parent
                    self.running = True

                def run(self):
                    try:
                        # 使用OpenCV读取原始视频并进行实时识别处理
                        cap = cv2.VideoCapture(self.video_path)
                        if not cap.isOpened():
                            raise Exception("无法打开视频文件")

                        while self.running:
                            ret, frame = cap.read()
                            if not ret:
                                break

                            # 进行推理（对每一帧都进行识别）
                            results = self.model(frame)

                            # 在帧上绘制检测结果
                            for result in results:
                                boxes = result.boxes if hasattr(result, 'boxes') else []
                                if boxes is not None:
                                    for box in boxes:
                                        # 获取边界框坐标
                                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                                        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

                                        # 获取类别ID和置信度
                                        class_id = int(box.cls)
                                        confidence = float(box.conf)

                                        # 获取类别名称
                                        if hasattr(result, 'names') and class_id < len(result.names):
                                            class_name = result.names[class_id]
                                        else:
                                            class_name = str(class_id)

                                        # 绘制边界框
                                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                                        # 绘制标签
                                        label = f"{class_name}: {confidence:.2f}"
                                        cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                            # 发射信号传递处理后的帧
                            self.frame_processed.emit(frame)

                        cap.release()

                    except Exception as e:
                        logger.error(f"实时视频流处理失败: {str(e)}")
                        # 发射错误信号
                        self.processing_error.emit(str(e))

                def stop(self):
                    """
                    停止视频处理
                    """
                    self.running = False

            # 启动实时视频处理线程
            self.video_thread = RealTimeVideoProcessingThread(self, self.current_file_path, model)

            # 连接信号
            self.video_thread.frame_processed.connect(self.display_processed_frame)
            self.video_thread.processing_error.connect(self.show_video_error)

            # 启动线程
            self.video_thread.start()

        except Exception as e:
            logger.error(f"启动实时视频流处理失败: {str(e)}")

    def display_processed_frame(self, frame):
        """
        显示处理后的视频帧

        Args:
            frame: 处理后的视频帧
        """
        try:
            # 转换为QImage并显示
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            q_img = QImage(frame.data.tobytes(), width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
            pixmap = QPixmap.fromImage(q_img)

            # 获取原始视频的尺寸
            original_size = self.original_image_label.size()

            # 缩放图片以适应显示区域（保持宽高比），与原始视频大小保持一致
            scaled_pixmap = pixmap.scaled(original_size.width(), original_size.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)  # type: ignore
            self.result_image_label.setPixmap(scaled_pixmap)
            self.result_image_label.setAlignment(Qt.AlignCenter)  # type: ignore

            # 显示图片标签
            self.result_image_label.show()

            # 隐藏视频播放器
            if hasattr(self, 'result_video_view') and self.result_video_view:
                self.result_video_view.hide()

            # 确保左右两侧显示区域大小一致
            self.sync_display_areas_size(original_size)

        except Exception as e:
            logger.error(f"显示处理后的视频帧失败: {str(e)}")

    def update_result_video(self, temp_video_path):
        """
        更新结果视频显示

        Args:
            temp_video_path (str): 临时视频文件路径
        """
        try:
            if temp_video_path and os.path.exists(temp_video_path):
                # 设置识别结果视频媒体文件
                media_content = QMediaContent(QUrl.fromLocalFile(temp_video_path))
                self.result_media_player.setMedia(media_content)

                # 调整视频项大小
                from PyQt5.QtCore import QSizeF
                self.result_video_item.setSize(QSizeF(self.result_video_view.size()))

                # 自动播放视频
                self.result_media_player.play()
            else:
                # 如果无法创建识别结果视频，显示错误信息
                self.result_video_view.hide()
                self.result_image_label.show()
                self.result_image_label.setText("视频识别失败")
                self.result_image_label.setAlignment(Qt.AlignCenter)  # type: ignore
        except Exception as e:
            logger.error(f"更新结果视频失败: {str(e)}")

    def show_video_error(self, error_message):
        """
        显示视频处理错误

        Args:
            error_message (str): 错误信息
        """
        try:
            # 显示错误信息
            self.result_video_view.hide()
            self.result_image_label.show()
            self.result_image_label.setText(f"视频识别失败: {error_message}")
            self.result_image_label.setAlignment(Qt.AlignCenter)  # type: ignore
        except Exception as e:
            logger.error(f"显示视频错误失败: {str(e)}")

    def setup_result_video_player(self):
        """
        设置识别结果视频播放器
        """
        # 创建媒体播放器和视频项
        self.result_media_player = QMediaPlayer()
        self.result_video_item = QGraphicsVideoItem()
        self.result_video_view = QGraphicsView()
        self.result_scene = QGraphicsScene()
        self.result_video_view.setScene(self.result_scene)
        self.result_scene.addItem(self.result_video_item)
        self.result_media_player.setVideoOutput(self.result_video_item)

        # 隐藏视频播放器，只在需要时显示
        self.result_video_view.hide()

        # 连接媒体播放器信号
        self.result_media_player.stateChanged.connect(self.result_media_state_changed)

        # 连接视频项大小变化信号
        self.result_video_item.nativeSizeChanged.connect(self.result_video_native_size_changed)

        # 将视频视图添加到结果文件显示区域
        self.result_layout.insertWidget(0, self.result_video_view)

    def result_video_native_size_changed(self, size):
        """
        识别结果视频原生大小改变事件处理

        Args:
            size: 视频原始大小
        """
        # 当视频大小确定后，调整视频项大小以适应视图
        if self.result_video_view and self.result_video_item:
            # 获取视图大小
            view_size = self.result_video_view.size()
            # 调整视频项大小
            from PyQt5.QtCore import QSizeF
            self.result_video_item.setSize(QSizeF(view_size))

    def result_media_state_changed(self, state):
        """
        识别结果视频媒体状态改变事件处理

        Args:
            state: 媒体播放器状态
        """
        # 可以在这里处理播放状态变化
        pass

    def create_temp_video_with_detections(self, cap, model):
        """
        创建带有检测结果的临时视频文件

        Args:
            cap: OpenCV视频捕获对象
            model: YOLO模型实例

        Returns:
            str: 临时视频文件路径，如果失败则返回None
        """
        try:
            # 获取视频属性
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # 创建临时文件路径
            import tempfile
            temp_dir = tempfile.gettempdir()
            temp_video_path = os.path.join(temp_dir, f"temp_result_{os.getpid()}.mp4")

            # 创建视频写入器
            fourcc = cv2.VideoWriter.fourcc(*'mp4v')
            out = cv2.VideoWriter(temp_video_path, fourcc, fps, (width, height))

            if not out.isOpened():
                raise Exception("无法创建视频写入器")

            frame_index = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # 进行推理（对每一帧都进行识别以确保准确性）
                results = model(frame)

                # 在帧上绘制检测结果
                for result in results:
                    boxes = result.boxes if hasattr(result, 'boxes') else []
                    if boxes is not None:
                        for box in boxes:
                            # 获取边界框坐标
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

                            # 获取类别ID和置信度
                            class_id = int(box.cls)
                            confidence = float(box.conf)

                            # 获取类别名称
                            if hasattr(result, 'names') and class_id < len(result.names):
                                class_name = result.names[class_id]
                            else:
                                class_name = str(class_id)

                            # 绘制边界框
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                            # 绘制标签
                            label = f"{class_name}: {confidence:.2f}"
                            cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                # 写入帧到输出视频
                out.write(frame)
                frame_index += 1

            # 释放资源
            out.release()

            return temp_video_path if os.path.exists(temp_video_path) else None

        except Exception as e:
            logger.error(f"创建带检测结果的临时视频失败: {str(e)}")
            return None

    def prev_image(self):
        """
        切换到上一张文件
        """
        # 发射信号通知文件管理器切换到上一张文件
        self.switch_to_previous.emit()  # type: ignore

    def next_image(self):
        """
        切换到下一张文件
        """
        # 发射信号通知文件管理器切换到下一张文件
        self.switch_to_next.emit()  # type: ignore

    def set_current_file(self, file_path):
        """
        设置当前文件路径并重新加载文件

        Args:
            file_path (str): 新的文件路径
        """
        # 停止当前正在进行的视频处理
        self.stop_current_video_processing()

        # 清空右侧显示区域，为新资源做准备
        self.clear_result_display()

        self.current_file_path = file_path
        self.load_file()
        # 重新运行测试以显示新文件的结果
        if self.model_path:
            self.run_test()
