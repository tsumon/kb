# atguigu/query_process/base.py

"""
查询流程节点基类

定义统一的节点接口规范，提供通用功能
"""
import time
from abc import abstractmethod, ABC

from atguigu.query_process.state import QueryGraphState
from atguigu.tool.logger import logger
from atguigu.tool.task_utils import add_running_task, add_done_task, add_node_duration, put_data, get_task_info


class NodeBase(ABC):

    name: str = "node_base"

    def __init__(self):
        """
        强制子类设置name
        """
        if self.name == "node_base":
            raise ValueError(f"{self.__class__.__name__} 必须设置 name 属性")

    def __call__(self, state: QueryGraphState):
        """
        节点执行入口
        """
        try:
            logger.info(f"{self.name} 开始执行...")
            task_id = state.get("task_id")
            start_time = time.time()

            # 节点开始：加入运行列表，推送 progress（data 是 get_task_info 的 dict，
            # 前端按 d.status / d.done_list / d.running_list 渲染进度条）
            add_running_task(task_id, self.name)
            put_data(task_id, "progress", get_task_info(task_id))

            result = self.process(state)

            # 节点结束：移出运行列表、加入完成列表，记录耗时，推送 progress
            add_done_task(task_id, self.name)
            add_node_duration(task_id, self.name, time.time() - start_time)
            put_data(task_id, "progress", get_task_info(task_id))
            logger.info(f"{self.name} 结束执行...")

            return result
        except Exception as e:
            logger.error(f"{self.name} 执行失败: {e}")
            raise

    @abstractmethod
    def process(self, state: QueryGraphState):
        """
        节点的核心处理逻辑
        :return:
        """
        pass
