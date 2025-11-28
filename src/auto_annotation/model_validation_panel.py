import os
import tempfile
import gc
from typing import List, Dict, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QMessageBox, QScrollArea,
    QGridLayout, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSemaphore
from ..logging_config import logger

# 尝试延迟导入ultralytics，避免启动时失败
def import_ultralytics():
    try:
        import ultralytics
        return ultralytics
    except Exception:
        return None


class ValidationWorker(QThread):
    """
    单模型验证线程
    """
    result_ready = pyqtSignal(str, dict)  # model_label, metrics
    error_happened = pyqtSignal(str, str)  # model_label, error
    finished_signal = pyqtSignal()  # 完成信号

    def __init__(self, model_path, display_name, dataset_path, custom_params=None, semaphore=None):
        super().__init__()
        self.model_path = model_path
        self.display_name = display_name
        self.dataset_path = dataset_path
        self.custom_params = custom_params or {}
        self.semaphore = semaphore

    def run(self):
        model = None
        try:
            ul = import_ultralytics()
            if ul is None:
                raise RuntimeError("未安装ultralytics库，无法进行模型验证")

            YOLO = getattr(ul, 'YOLO', None)
            if YOLO is None:
                raise RuntimeError("未找到YOLO类，请更新ultralytics版本")

            # 构建data配置字典
            data_cfg = self._build_data_cfg(self.dataset_path)
            # 加载模型
            model = YOLO(self._resolve_model_path(self.model_path))

            # 执行验证（尽量使用val接口）
            try:
                # 合并自定义参数，添加内存优化参数
                val_kwargs = {
                    'data': data_cfg,
                    'verbose': False,  # 减少输出
                    'plots': False,    # 不生成图表，节省内存
                }
                # 如果用户未指定batch，使用保守的batch size
                if 'batch' not in self.custom_params:
                    val_kwargs['batch'] = 4  # 小批次，降低内存占用
                val_kwargs.update(self.custom_params)
                results = model.val(**val_kwargs)
            except Exception as e:
                # 某些数据结构不符合YOLO val要求时，回退为预测并统计简单指标
                logger.error(f"val失败，回退predict统计: {str(e)}")
                # 尝试在images子目录中查找图片
                images_path = os.path.join(self.dataset_path, 'images')
                test_path = images_path if os.path.exists(images_path) else self.dataset_path
                # 使用小批次预测
                batch_size = self.custom_params.get('batch', 4)
                results = model(test_path, batch=batch_size, verbose=False)

            metrics = self._extract_metrics(results)
            self.result_ready.emit(self.display_name, metrics)
        except Exception as e:
            logger.error(f"模型验证失败[{self.display_name}]: {str(e)}")
            self.error_happened.emit(self.display_name, str(e))
        finally:
            # 显式清理模型和结果，释放内存
            if model is not None:
                try:
                    del model
                except:
                    pass
            # 强制垃圾回收
            gc.collect()
            # 释放信号量
            if self.semaphore:
                self.semaphore.release()
            self.finished_signal.emit()

    def _build_data_cfg(self, dataset_path: str) -> Dict:
        # 支持两类结构：
        # 1) 任意图片根目录 + labels子目录 + classes.txt
        # 2) YOLO标准数据集结构(包含images/labels等)时也尽量兼容
        
        # 查找labels目录和classes.txt
        labels_dir = os.path.join(dataset_path, 'labels')
        names = {}
        classes_file = os.path.join(labels_dir, 'classes.txt')
        if os.path.exists(classes_file):
            with open(classes_file, 'r', encoding='utf-8') as f:
                cls = [line.strip() for line in f if line.strip()]
                names = {i: name for i, name in enumerate(cls)}

        # 智能检测图片目录：优先使用images子目录，否则使用根目录
        images_dir = os.path.join(dataset_path, 'images')
        if os.path.exists(images_dir):
            # YOLO标准结构：有images子目录
            val_path = 'images'  # 相对于path的路径
        else:
            # 非标准结构：图片直接在根目录
            val_path = '.'  # 当前目录
        
        # 构建data配置
        data_cfg = {
            'path': dataset_path,
            'val': val_path,
            'test': val_path,
        }
        if names:
            data_cfg['names'] = names
        return data_cfg

    def _resolve_model_path(self, model_name: str) -> str:
        # 如果是绝对路径且存在，直接使用
        if os.path.isabs(model_name) and os.path.exists(model_name):
            return model_name
        # 统一使用~/.dataset_m/models作为缓存目录，与其他面板一致
        user_home = os.path.expanduser("~")
        model_cache_dir = os.path.join(user_home, ".dataset_m", "models")
        os.makedirs(model_cache_dir, exist_ok=True)
        model_path = os.path.join(model_cache_dir, model_name)
        # 如果本地存在，则用本地；否则让ultralytics按名称处理(会自动下载)
        return model_path if os.path.exists(model_path) else model_name

    def _extract_metrics(self, results) -> Dict:
        # 兼容不同返回结构，尽力提取常见指标
        metrics = {
            'mAP50': None,
            'mAP50-95': None,
            'precision': None,
            'recall': None,
        }
        try:
            m = getattr(results, 'metrics', None)
            if m is not None:
                # Ultralytics v8: metrics.box.map50 / metrics.box.map
                box = getattr(m, 'box', None)
                if box is not None:
                    metrics['mAP50'] = getattr(box, 'map50', None)
                    metrics['mAP50-95'] = getattr(box, 'map', None)
                # 可能存在precision/recall
                metrics['precision'] = getattr(m, 'precision', None)
                metrics['recall'] = getattr(m, 'recall', None)
            # 某些版本可能提供results_dict
            d = getattr(results, 'results_dict', None)
            if isinstance(d, dict):
                metrics['mAP50'] = metrics['mAP50'] or d.get('metrics/mAP50')
                metrics['mAP50-95'] = metrics['mAP50-95'] or d.get('metrics/mAP50-95')
                metrics['precision'] = metrics['precision'] or d.get('precision')
                metrics['recall'] = metrics['recall'] or d.get('recall')
        except Exception as e:
            logger.error(f"提取验证指标失败: {str(e)}")
        # 将None替换为0，方便对比展示
        for k in metrics:
            metrics[k] = metrics[k] if isinstance(metrics[k], (int, float)) and metrics[k] is not None else 0.0
        return metrics


class ModelValidationPanel(QWidget):
    """
    模型验证与对比面板
    """

    def __init__(self):
        super().__init__()
        self.selected_models: List[str] = []
        self.dataset_path: str = ''
        self.results: Dict[str, Dict] = {}
        self.workers: List[ValidationWorker] = []  # 存储所有工作线程
        self.completed_count: int = 0  # 已完成的任务计数
        self.total_count: int = 0  # 总任务数
        self.custom_params: Dict = {}  # 自定义参数
        # 使用信号量控制并发数（降低为1个并发验证任务，避免内存溢出）
        self.semaphore = QSemaphore(1)
        self.init_ui()

    def init_ui(self):
        # 使用水平布局分割左右两侧
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # ========== 左侧面板 ==========
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # 左侧标题
        left_title = QLabel("模型验证配置")
        left_title.setStyleSheet(
            """
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 8px;
                background-color: #f5f5f5;
                border-radius: 4px;
            }
            """
        )
        left_layout.addWidget(left_title)

        # 数据集选择区域
        dataset_group = QWidget()
        dataset_layout = QVBoxLayout(dataset_group)
        dataset_layout.setContentsMargins(0, 0, 0, 0)
        dataset_layout.setSpacing(5)
        
        dataset_label = QLabel("测试数据集:")
        dataset_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        dataset_layout.addWidget(dataset_label)
        
        dataset_input_layout = QHBoxLayout()
        self.dataset_edit = QLineEdit()
        self.dataset_edit.setPlaceholderText("选择测试数据集根目录(需包含待测图片及labels)")
        self.dataset_edit.setStyleSheet(
            """
            QLineEdit {
                padding: 6px;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 12px;
            }
            QLineEdit:focus { border-color: #2196F3; }
            """
        )
        browse_btn = QPushButton("浏览")
        browse_btn.setFixedWidth(80)
        browse_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 6px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
            """
        )
        browse_btn.clicked.connect(self.select_dataset_path)
        dataset_input_layout.addWidget(self.dataset_edit)
        dataset_input_layout.addWidget(browse_btn)
        dataset_layout.addLayout(dataset_input_layout)
        
        left_layout.addWidget(dataset_group)

        # 模型列表区域
        model_group = QWidget()
        model_layout = QVBoxLayout(model_group)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(5)
        
        model_label = QLabel("模型列表:")
        model_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        model_layout.addWidget(model_label)
        
        # 模型操作按钮
        model_btn_layout = QHBoxLayout()
        add_btn = QPushButton("➕ 添加模型")
        add_btn.clicked.connect(self.add_model)
        add_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
            """
        )
        remove_btn = QPushButton("➖ 删除选中")
        remove_btn.clicked.connect(self.remove_selected_models)
        remove_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #da190b; }
            """
        )
        model_btn_layout.addWidget(add_btn)
        model_btn_layout.addWidget(remove_btn)
        model_btn_layout.addStretch()
        model_layout.addLayout(model_btn_layout)
        
        # 模型列表树形控件
        self.model_tree = QTreeWidget()
        self.model_tree.setHeaderLabels(["模型文件路径", "选择"])
        self.model_tree.setRootIsDecorated(False)
        self.model_tree.setAlternatingRowColors(True)
        self.model_tree.setMinimumHeight(250)  # 增加最小高度
        self.model_tree.setStyleSheet(
            """
            QTreeWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
                alternate-background-color: #f9f9f9;
            }
            QTreeWidget::item { padding: 8px; }
            QTreeWidget::item:selected { background-color: #e3f2fd; color: black; }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 8px;
                border: 1px solid #ddd;
                font-weight: bold;
            }
            """
        )
        # 设置第一列(模型名称)宽度
        self.model_tree.setColumnWidth(0, 350)
        model_layout.addWidget(self.model_tree)
        
        left_layout.addWidget(model_group)

        # 自定义参数区域
        params_group = QWidget()
        params_layout = QVBoxLayout(params_group)
        params_layout.setContentsMargins(0, 0, 0, 0)
        params_layout.setSpacing(5)
        
        params_label = QLabel("自定义验证参数 (可选):")
        params_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        params_layout.addWidget(params_label)
        
        self.params_text = QTextEdit()
        self.params_text.setPlaceholderText(
            "输入YOLO验证参数，每行一个，格式: 参数名=值\n"
            "例如:\n"
            "imgsz=640\n"
            "conf=0.25\n"
            "iou=0.45\n"
            "batch=4  (建议小批次，避免内存溢出)\n"
            "device=0\n"
            "workers=2  (降低数据加载线程数)"
        )
        self.params_text.setMaximumHeight(120)
        self.params_text.setStyleSheet(
            """
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px;
                font-family: monospace;
                font-size: 12px;
                background-color: #fafafa;
            }
            QTextEdit:focus { border-color: #2196F3; }
            """
        )
        params_layout.addWidget(self.params_text)
        
        left_layout.addWidget(params_group)

        # 开始验证按钮
        start_btn = QPushButton("🚀 开始验证")
        start_btn.clicked.connect(self.start_validation)
        start_btn.setMinimumHeight(40)
        start_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #F57C00; }
            """
        )
        left_layout.addWidget(start_btn)
        
        # 进度提示标签
        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet(
            """
            QLabel {
                color: #666;
                font-size: 12px;
                padding: 5px;
            }
            """
        )
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore
        left_layout.addWidget(self.progress_label)

        left_layout.addStretch()

        # ========== 右侧面板 ==========
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # 右侧标题
        self.result_title = QLabel("验证指标对比图")
        self.result_title.setStyleSheet(
            """
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 8px;
                background-color: #f5f5f5;
                border-radius: 4px;
            }
            """
        )
        right_layout.addWidget(self.result_title)
        
        # 创建滚动区域包裹图片标签
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            """
            QScrollArea {
                border: 2px solid #ddd;
                border-radius: 6px;
                background-color: white;
            }
            """
        )
        
        self.result_image = QLabel("执行验证后将在此显示对比图")
        self.result_image.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore
        self.result_image.setStyleSheet(
            """
            QLabel {
                padding: 20px;
                color: #999;
                font-size: 14px;
            }
            """
        )
        
        scroll_area.setWidget(self.result_image)
        right_layout.addWidget(scroll_area)

        # 添加左右面板到主布局，设置宽度比例 (左:右 = 2:3)
        main_layout.addWidget(left_widget, 2)
        main_layout.addWidget(right_widget, 3)

    def select_dataset_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择测试数据集路径")
        if path:
            self.dataset_path = path
            self.dataset_edit.setText(path)

    def add_model(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择YOLO模型文件",
            "",
            "模型文件 (*.pt *.pth *.h5 *.onnx);;所有文件 (*)"
        )
        if file_path:
            item = QTreeWidgetItem(self.model_tree)
            item.setText(0, file_path)
            item.setCheckState(1, Qt.CheckState.Checked)  # type: ignore

    def remove_selected_models(self):
        # 移除选中的(打勾)模型
        rows_to_remove = []
        for i in range(self.model_tree.topLevelItemCount()):
            item = self.model_tree.topLevelItem(i)
            if item.checkState(1) == Qt.CheckState.Checked:  # type: ignore
                rows_to_remove.append(item)
        for item in rows_to_remove:
            index = self.model_tree.indexOfTopLevelItem(item)
            if index >= 0:
                self.model_tree.takeTopLevelItem(index)


    def start_validation(self):
        # 校验数据集
        if not self.dataset_edit.text().strip() or not os.path.exists(self.dataset_edit.text().strip()):
            QMessageBox.warning(self, "警告", "请先选择有效的测试数据集路径")
            return
        self.dataset_path = self.dataset_edit.text().strip()

        # 解析自定义参数
        self.custom_params = {}
        params_text = self.params_text.toPlainText().strip()
        if params_text:
            for line in params_text.split('\n'):
                line = line.strip()
                if line and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # 尝试转换数值类型
                    try:
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                    except ValueError:
                        pass  # 保持字符串
                    self.custom_params[key] = value
        
        logger.info(f"自定义验证参数: {self.custom_params}")

        # 收集选中模型路径
        self.selected_models = []
        model_tasks = []
        for i in range(self.model_tree.topLevelItemCount()):
            item = self.model_tree.topLevelItem(i)
            if item.checkState(1) == Qt.CheckState.Checked:  # type: ignore
                model_path = item.text(0).strip()
                if model_path:
                    display_name = os.path.basename(model_path)
                    self.selected_models.append(display_name)
                    model_tasks.append((model_path, display_name))
        if not self.selected_models:
            QMessageBox.warning(self, "警告", "请至少选择一个模型进行验证")
            return

        # 初始化结果
        self.results = {}
        self.completed_count = 0
        self.total_count = len(model_tasks)
        self.result_image.setText(f"正在执行模型验证，请稍候...\n(0/{self.total_count})")
        self.result_image.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore
        self.progress_label.setText(f"验证进度: 0/{self.total_count}")

        # 清空之前的工作线程
        self.workers.clear()
        
        # 使用多线程并发执行验证（信号量控制并发数）
        for model_path, display_name in model_tasks:
            # 获取信号量（如果达到并发上限，会阻塞）
            self.semaphore.acquire()
            
            worker = ValidationWorker(
                model_path, display_name, self.dataset_path, 
                self.custom_params, self.semaphore
            )
            worker.result_ready.connect(self._on_worker_result)
            worker.error_happened.connect(self._on_worker_error)
            worker.finished_signal.connect(self._on_worker_finished)
            
            self.workers.append(worker)
            worker.start()
        
        logger.info(f"已启动 {len(model_tasks)} 个验证任务，最大并发数: 1 (串行执行以节省内存)")

    def _on_worker_finished(self):
        """
        单个工作线程完成时的回调
        """
        self.completed_count += 1
        self.progress_label.setText(f"验证进度: {self.completed_count}/{self.total_count}")
        
        # 更新提示信息
        if self.completed_count < self.total_count:
            self.result_image.setText(f"正在执行模型验证，请稍候...\n({self.completed_count}/{self.total_count})")
        
        # 所有任务完成，渲染对比图
        if self.completed_count >= self.total_count:
            logger.info("所有验证任务已完成，开始渲染对比图")
            self._render_comparison_chart()

    def _on_worker_result(self, model_label: str, metrics: Dict):
        """
        接收工作线程的成功结果
        """
        self.results[model_label] = metrics
        logger.info(f"模型 {model_label} 验证完成")
        # 强制垃圾回收，及时释放内存
        gc.collect()

    def _on_worker_error(self, model_label: str, error: str):
        """
        接收工作线程的错误信息
        """
        logger.error(f"模型 {model_label} 验证失败: {error}")
        # 不再弹窗，只记录错误
        self.results[model_label] = {'mAP50': 0.0, 'mAP50-95': 0.0, 'precision': 0.0, 'recall': 0.0}

    def _render_comparison_chart(self):
        # 没有结果
        if not self.results:
            self.result_image.setText("未获取到验证结果")
            self.result_image.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore
            return

        # 准备绘图数据
        labels: List[str] = []
        map50: List[float] = []
        map5095: List[float] = []
        prec: List[float] = []
        rec: List[float] = []

        # 使用选择顺序的模型名称作为标签
        for name in self.selected_models:
            labels.append(name)
            r = self.results.get(name, {})
            map50.append(float(r.get('mAP50', 0.0)))
            map5095.append(float(r.get('mAP50-95', 0.0)))
            prec.append(float(r.get('precision', 0.0)))
            rec.append(float(r.get('recall', 0.0)))

        # 生成图片(不引入图表控件，直接保存图片显示，避免依赖冲突)
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            fig, axes = plt.subplots(2, 2, figsize=(10, 7))
            ax_list = [axes[0, 0], axes[0, 1], axes[1, 0], axes[1, 1]]
            metrics_data = [map50, map5095, prec, rec]
            titles = ['mAP@50', 'mAP@50-95', 'Precision', 'Recall']

            for ax, data, title in zip(ax_list, metrics_data, titles):
                ax.bar(labels, data, color='#2196F3')
                ax.set_title(title)
                ax.set_ylabel('Score')
                ax.set_ylim(0, 1)
                ax.tick_params(axis='x', rotation=20)
                # 标注提升(相对第一个模型)
                if len(data) > 1:
                    base = data[0]
                    for i, v in enumerate(data):
                        delta = v - base
                        ax.text(i, v + 0.02, f"Δ{delta:.3f}", ha='center', fontsize=9)

            fig.tight_layout()
            # 保存到临时文件
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            fig.savefig(tmp_file.name, dpi=120)
            plt.close(fig)
            
            # 清理matplotlib资源
            del fig, axes, ax_list
            gc.collect()

            # 显示到标签(不缩放，保持原始大小以显示完整)
            from PyQt6.QtGui import QPixmap
            pix = QPixmap(tmp_file.name)
            self.result_image.setPixmap(pix)  # 不缩放，让滚动区域处理大小
            self.result_image.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore
            self.result_image.adjustSize()  # 调整标签大小以适应图片
            
            # 删除临时文件
            try:
                os.unlink(tmp_file.name)
            except:
                pass
        except Exception as e:
            logger.error(f"生成对比图失败: {str(e)}")
            self.result_image.setText(f"生成对比图失败: {str(e)}")
            self.result_image.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore
