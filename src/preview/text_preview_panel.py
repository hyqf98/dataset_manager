import os
import json
import xml.dom.minidom

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QMessageBox, QFileDialog, QHBoxLayout, QLabel

from src.logging_config import logger


class TextPreviewPanel(QWidget):
    """
    文本预览面板类，用于显示和编辑文本文件
    支持JSON、TXT、XML等格式的文件预览和编辑
    """

    # 定义文件保存信号
    file_saved = pyqtSignal(str)  # 文件路径

    def __init__(self):
        """
        初始化文本预览面板
        """
        super().__init__()
        self.current_file_path = None  # 当前文件路径
        self.text_edit = None  # 文本编辑器
        self.title_label = None  # 标题标签
        self.unsaved_indicator = None  # 未保存指示器
        self.is_modified = False  # 文件是否被修改
        self.original_content = ""  # 原始内容，用于比较是否修改
        self.init_ui()

    def init_ui(self):
        """
        初始化文本预览面板界面
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建标题栏
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(5, 5, 5, 5)
        
        self.title_label = QLabel("未命名")
        self.title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #333;
            }
        """)
        
        self.unsaved_indicator = QLabel("")
        self.unsaved_indicator.setStyleSheet("""
            QLabel {
                color: #e74c3c;
                font-weight: bold;
                margin-left: 10px;
            }
        """)
        
        title_layout.addWidget(self.title_label)
        title_layout.addWidget(self.unsaved_indicator)
        title_layout.addStretch()
        
        layout.addLayout(title_layout)

        # 创建文本编辑器
        self.text_edit = QTextEdit()
        self.text_edit.setLineWrapMode(QTextEdit.NoWrap)  # 不自动换行
        
        # 设置字体
        font = QFont("Courier New", 12)
        self.text_edit.setFont(font)
        
        # 设置样式
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #f8f8f8;
                border: 1px solid #ddd;
                selection-background-color: #add8e6;
            }
        """)
        
        # 连接文本变化信号
        self.text_edit.textChanged.connect(self.on_text_changed)
        
        layout.addWidget(self.text_edit)
        self.setLayout(layout)

        # 设置焦点策略，确保能接收键盘事件
        self.setFocusPolicy(Qt.StrongFocus)
        self.text_edit.setFocusPolicy(Qt.StrongFocus)

    def load_text_file(self, file_path):
        """
        加载文本文件内容

        Args:
            file_path (str): 文件路径
        """
        if not os.path.exists(file_path):
            self.show_message("文件不存在")
            return False

        try:
            # 保存当前文件路径
            self.current_file_path = file_path

            # 更新标题
            self.title_label.setText(os.path.basename(file_path))

            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()

            # 保存原始内容用于比较
            self.original_content = content

            # 根据文件扩展名进行特殊处理
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()

            # 格式化特定类型的文件
            if ext == '.json':
                try:
                    # 解析JSON并格式化显示
                    parsed_json = json.loads(content)
                    formatted_content = json.dumps(parsed_json, indent=2, ensure_ascii=False)
                    self.text_edit.setPlainText(formatted_content)
                    self.original_content = formatted_content
                except json.JSONDecodeError:
                    # 如果JSON格式不正确，直接显示原始内容
                    self.text_edit.setPlainText(content)
            elif ext == '.xml':
                try:
                    # 解析XML并格式化显示
                    dom = xml.dom.minidom.parseString(content)
                    formatted_content = dom.toprettyxml(indent="  ")
                    # 移除XML声明前的空行
                    lines = formatted_content.split('\n')
                    formatted_content = '\n'.join(line for line in lines if line.strip())
                    self.text_edit.setPlainText(formatted_content)
                    self.original_content = formatted_content
                except Exception:
                    # 如果XML格式不正确，直接显示原始内容
                    self.text_edit.setPlainText(content)
            else:
                # 其他文本文件直接显示
                self.text_edit.setPlainText(content)

            # 重置修改状态
            self.is_modified = False
            self.update_unsaved_indicator()

            # 将光标移到开头
            self.text_edit.moveCursor(QTextCursor.Start)
            
            logger.info(f"文本文件加载成功: {file_path}")
            return True
        except Exception as e:
            error_msg = f"加载文件出错: {str(e)}"
            self.show_message(error_msg)
            logger.error(error_msg, exc_info=True)
            return False

    def save_text_file(self, file_path=None):
        """
        保存文本文件

        Args:
            file_path (str, optional): 文件路径，如果为None则使用当前文件路径
        """
        if not file_path and not self.current_file_path:
            # 如果没有指定文件路径且当前没有打开文件，则弹出保存对话框
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存文件", "", "文本文件 (*.txt *.json *.xml);;所有文件 (*)"
            )
            if not file_path:
                return False

        try:
            # 获取编辑器中的内容
            content = self.text_edit.toPlainText()

            # 如果是JSON文件，验证格式
            if file_path:
                _, ext = os.path.splitext(file_path)
            elif self.current_file_path:
                _, ext = os.path.splitext(self.current_file_path)
            else:
                ext = ""
                
            ext = ext.lower() if ext else ""
            
            if ext == '.json':
                try:
                    # 验证JSON格式
                    json.loads(content)
                except json.JSONDecodeError as e:
                    # 格式错误，提示用户
                    reply = QMessageBox.question(
                        self, "JSON格式错误", 
                        f"JSON格式有错误: {str(e)}\n是否仍要保存？",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply == QMessageBox.No:
                        return False

            # 保存文件
            save_path = file_path if file_path else self.current_file_path
            with open(save_path, 'w', encoding='utf-8') as file:
                file.write(content)

            # 更新原始内容和修改状态
            self.original_content = content
            self.is_modified = False
            self.update_unsaved_indicator()

            # 发出文件保存信号
            self.file_saved.emit(save_path)
            
            logger.info(f"文本文件保存成功: {save_path}")
            return True
        except Exception as e:
            error_msg = f"保存文件出错: {str(e)}"
            QMessageBox.critical(self, "保存失败", error_msg)
            logger.error(error_msg, exc_info=True)
            return False

    def show_message(self, message):
        """
        显示消息

        Args:
            message (str): 要显示的消息
        """
        self.text_edit.setPlainText(message)

    def keyPressEvent(self, event):
        """
        处理键盘按键事件

        Args:
            event: 键盘事件
        """
        # 处理Ctrl+S保存
        if event.key() == Qt.Key_S and event.modifiers() == Qt.ControlModifier:
            self.save_text_file()
        else:
            super().keyPressEvent(event)

    def get_supported_formats(self):
        """
        获取支持的文件格式

        Returns:
            list: 支持的文件扩展名列表
        """
        return ['.txt', '.json', '.xml']

    def on_text_changed(self):
        """
        处理文本变化事件
        """
        # 更新修改状态
        current_content = self.text_edit.toPlainText()
        self.is_modified = (current_content != self.original_content)
        self.update_unsaved_indicator()

    def update_unsaved_indicator(self):
        """
        更新未保存指示器
        """
        if self.is_modified:
            self.unsaved_indicator.setText("* 未保存")
        else:
            self.unsaved_indicator.setText("")

    def closeEvent(self, event):
        """
        处理关闭事件

        Args:
            event: 关闭事件
        """
        if self.is_modified:
            reply = QMessageBox.question(
                self, "文件未保存", 
                f"文件 '{os.path.basename(self.current_file_path)}' 已被修改，是否保存更改？",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Yes:
                if not self.save_text_file():
                    event.ignore()
                    return
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
                
        event.accept()