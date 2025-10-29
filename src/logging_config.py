import logging
import os
from PyQt5.QtCore import QStandardPaths

# 创建日志目录
def get_log_directory():
    """
    获取日志文件存储目录
    
    Returns:
        str: 日志目录路径
    """
    # 获取用户主目录
    home_dir = QStandardPaths.writableLocation(QStandardPaths.HomeLocation)
    # 构造.dataset_m目录路径
    log_dir = os.path.join(home_dir, ".dataset_m", "logs")
    
    # 如果目录不存在则创建
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    return log_dir

# 配置日志
def setup_logging():
    """
    配置全局日志设置
    """
    # 创建日志记录器
    logger = logging.getLogger('dataset_manager')
    logger.setLevel(logging.DEBUG)
    
    # 避免重复添加处理器
    if not logger.handlers:
        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # 创建文件处理器
        log_file = os.path.join(get_log_directory(), 'dataset_manager.log')
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)  # 修改为DEBUG级别
        console_handler.setFormatter(formatter)
        
        # 添加处理器到记录器
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger

# 获取全局日志记录器实例
logger = setup_logging()