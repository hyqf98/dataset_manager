import os
import json
from enum import Enum
from typing import Optional, Dict, Any, List
from PyQt5.QtCore import QObject, pyqtSignal
from ..logging_config import logger


class TrainingTaskType(Enum):
    """训练任务类型"""
    LOCAL = "本地训练"
    REMOTE = "服务器训练"


class TrainingTaskStatus(Enum):
    """训练任务状态"""
    STOPPED = "已停止"
    RUNNING = "训练中"
    ERROR = "错误"
    COMPLETED = "已完成"


class TrainingTask:
    """训练任务类"""
    
    def __init__(self, 
                 task_id: Optional[int] = None,
                 name: str = "",
                 task_type: TrainingTaskType = TrainingTaskType.LOCAL,
                 dataset_path: str = "",
                 save_path: str = "",
                 server_id: Optional[int] = None,
                 remote_path: str = "",
                 conda_env: str = "",
                 status: TrainingTaskStatus = TrainingTaskStatus.STOPPED,
                 process_id: Optional[int] = None,
                 results_path: str = "",
                 execution_log: str = ""):
        self.task_id = task_id
        self.name = name
        self.task_type = task_type
        self.dataset_path = dataset_path
        self.save_path = save_path
        self.server_id = server_id
        self.remote_path = remote_path
        self.conda_env = conda_env
        self.status = status
        self.process_id = process_id
        self.results_path = results_path
        self.execution_log = execution_log  # 执行过程的日志信息
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'task_id': self.task_id,
            'name': self.name,
            'task_type': self.task_type.name,
            'dataset_path': self.dataset_path,
            'save_path': self.save_path,
            'server_id': self.server_id,
            'remote_path': self.remote_path,
            'conda_env': self.conda_env,
            'status': self.status.name,
            'process_id': self.process_id,
            'results_path': self.results_path,
            'execution_log': self.execution_log
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TrainingTask':
        """从字典创建任务"""
        return cls(
            task_id=data.get('task_id'),
            name=data.get('name', ''),
            task_type=TrainingTaskType[data.get('task_type', 'LOCAL')],
            dataset_path=data.get('dataset_path', ''),
            save_path=data.get('save_path', ''),
            server_id=data.get('server_id'),
            remote_path=data.get('remote_path', ''),
            conda_env=data.get('conda_env', ''),
            status=TrainingTaskStatus[data.get('status', 'STOPPED')],
            process_id=data.get('process_id'),
            results_path=data.get('results_path', ''),
            execution_log=data.get('execution_log', '')
        )


class TrainingTaskManager(QObject):
    """训练任务管理器"""
    
    tasks_changed = pyqtSignal()
    
    def __init__(self, config_file: Optional[str] = None):
        super().__init__()
        if config_file is None:
            user_home = os.path.expanduser("~")
            dataset_manager_dir = os.path.join(user_home, ".dataset_m")
            os.makedirs(dataset_manager_dir, exist_ok=True)
            self.config_file = os.path.join(dataset_manager_dir, "training_tasks.json")
        else:
            self.config_file = config_file
        
        self.tasks: List[TrainingTask] = []
        self.load_tasks()
    
    def load_tasks(self):
        """加载任务配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.tasks = [TrainingTask.from_dict(item) for item in data]
                logger.info(f"加载了 {len(self.tasks)} 个训练任务")
            else:
                self.tasks = []
                logger.info("未找到训练任务配置文件，初始化空列表")
        except Exception as e:
            logger.error(f"加载训练任务配置时出错: {e}")
            self.tasks = []
    
    def save_tasks(self):
        """保存任务配置"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            data = [task.to_dict() for task in self.tasks]
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"保存了 {len(self.tasks)} 个训练任务")
            self.tasks_changed.emit()
        except Exception as e:
            logger.error(f"保存训练任务配置时出错: {e}")
    
    def add_task(self, task: TrainingTask):
        """添加任务"""
        if self.tasks:
            max_id = max([t.task_id for t in self.tasks if t.task_id is not None], default=0)
            task.task_id = max_id + 1
        else:
            task.task_id = 1
        
        self.tasks.append(task)
        self.save_tasks()
        logger.info(f"添加训练任务: {task.name}")
    
    def update_task(self, task: TrainingTask):
        """更新任务"""
        for i, t in enumerate(self.tasks):
            if t.task_id == task.task_id:
                self.tasks[i] = task
                self.save_tasks()
                logger.info(f"更新训练任务: {task.name}")
                return True
        return False
    
    def delete_task(self, task_id: int):
        """删除任务"""
        self.tasks = [t for t in self.tasks if t.task_id != task_id]
        self.save_tasks()
        logger.info(f"删除训练任务 ID: {task_id}")
    
    def get_tasks(self) -> List[TrainingTask]:
        """获取所有任务"""
        return self.tasks
    
    def get_task_by_id(self, task_id: int) -> Optional[TrainingTask]:
        """根据ID获取任务"""
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        return None
