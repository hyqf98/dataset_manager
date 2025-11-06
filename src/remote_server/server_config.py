import os
import json
from typing import List, Optional
from PyQt5.QtCore import QObject, pyqtSignal
from ..logging_config import logger


class ServerConfig:
    """
    服务器配置类
    """

    def __init__(self, name: str, host: str, port: int = 22, username: str = "", 
                 password: str = "", private_key_path: str = "", id: Optional[int] = None):
        self.id = id
        self.name = name
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.private_key_path = private_key_path

    def to_dict(self):
        """
        将服务器配置对象转换为字典
        """
        return {
            'id': self.id,
            'name': self.name,
            'host': self.host,
            'port': self.port,
            'username': self.username,
            'password': self.password,
            'private_key_path': self.private_key_path
        }

    @classmethod
    def from_dict(cls, data):
        """
        从字典创建服务器配置对象
        """
        return cls(
            id=data['id'],
            name=data['name'],
            host=data['host'],
            port=data.get('port', 22),
            username=data['username'],
            password=data['password'],
            private_key_path=data.get('private_key_path', '')
        )


class ServerConfigManager(QObject):
    """
    服务器配置管理器
    """
    
    configs_changed = pyqtSignal()  # 配置变化信号

    def __init__(self, config_file=None):
        super().__init__()
        # 将配置文件路径设置为用户目录下的.dataset_m路径
        if config_file is None:
            user_home = os.path.expanduser("~")
            dataset_manager_dir = os.path.join(user_home, ".dataset_m")
            # 确保目录存在
            os.makedirs(dataset_manager_dir, exist_ok=True)
            self.config_file = os.path.join(dataset_manager_dir, "server_configs.json")
        else:
            self.config_file = config_file
        self.server_configs = []
        self.load_server_configs()

    def load_server_configs(self):
        """
        从配置文件加载服务器配置
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.server_configs = [ServerConfig.from_dict(item) for item in data]
                logger.info(f"加载了 {len(self.server_configs)} 个服务器配置")
            else:
                self.server_configs = []
                logger.info("未找到服务器配置文件，初始化空的服务器配置列表")
        except Exception as e:
            logger.error(f"加载服务器配置时出错: {e}")
            self.server_configs = []

    def save_server_configs(self):
        """
        保存服务器配置到配置文件
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            data = [sc.to_dict() for sc in self.server_configs]
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"保存了 {len(self.server_configs)} 个服务器配置到配置文件")
            self.configs_changed.emit()  # 发出配置变化信号
        except Exception as e:
            logger.error(f"保存服务器配置时出错: {e}")

    def add_server_config(self, server_config: ServerConfig):
        """
        添加服务器配置
        """
        # 为新服务器配置分配ID
        if self.server_configs:
            max_id = max([sc.id for sc in self.server_configs if sc.id is not None], default=0)
            server_config.id = max_id + 1
        else:
            server_config.id = 1

        self.server_configs.append(server_config)
        self.save_server_configs()
        logger.info(f"添加服务器配置: {server_config.name}")

    def update_server_config(self, server_config: ServerConfig):
        """
        更新服务器配置
        """
        for i, sc in enumerate(self.server_configs):
            if sc.id == server_config.id:
                self.server_configs[i] = server_config
                self.save_server_configs()
                logger.info(f"更新服务器配置: {server_config.name}")
                return True
        return False

    def delete_server_config(self, server_config_id: int):
        """
        删除服务器配置
        """
        self.server_configs = [sc for sc in self.server_configs if sc.id != server_config_id]
        self.save_server_configs()
        logger.info(f"删除服务器配置 ID: {server_config_id}")

    def get_server_configs(self) -> List[ServerConfig]:
        """
        获取所有服务器配置
        """
        return self.server_configs

    def get_server_config_by_id(self, server_config_id: int) -> Optional[ServerConfig]:
        """
        根据ID获取服务器配置
        """
        for sc in self.server_configs:
            if sc.id == server_config_id:
                return sc
        return None