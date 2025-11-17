#!/usr/bin/env python3
import sys
import traceback

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from src.logging_config import logger
from src.ui.main_window import MainWindow


# 确保所有模块都被导入，以便正确初始化


def main():
    """
    主函数，用于启动数据集管理应用程序
    """
    try:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        # 记录异常信息到日志
        logger.error(f"应用程序启动时发生异常: {str(e)}")
        logger.error(f"异常详情:\n{traceback.format_exc()}")
        # 以错误码退出
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 双重保障，确保异常被记录
        error_msg = f"程序启动时发生未捕获的异常: {str(e)}"
        print(error_msg)
        if 'logger' in globals():
            logger.error(error_msg)
            logger.error(f"异常详情:\n{traceback.format_exc()}")
        sys.exit(1)
