# ============================================================
# atguigu/import_process/base.py
# ============================================================
# 作用：定义所有流程节点的抽象基类 NodeBase。
#       遵循"模板方法"设计模式 —— 子类只需实现 process()，
#       基类 __call__() 统一处理日志和异常。
# 依赖：ImportGraphState（状态类型定义）、logger（彩色日志实例）
# ============================================================
import time
# Python 抽象基类（Abstract Base Class）模块
# ABC：抽象基类的基类，继承它才能定义抽象方法
# abstractmethod：装饰器，标记必须由子类实现的方法
from abc import ABC, abstractmethod

# 从 state 模块导入工作流状态类型（TypedDict），用于类型注解
from atguigu.import_process.state import ImportGraphState
# 从 tool 模块导入全局彩色日志实例
from atguigu.tool.logger import logger
from atguigu.tool.task_utils import add_running_task, add_done_task, add_node_duration


class NodeBase(ABC):
    """
    查询流程节点基类
    定义统一的节点接口规范，提供通用功能：
    1. 强制子类覆盖 name 属性 —— 防止忘记起名导致日志不可追踪
    2. __call__() 统一日志包装 —— 执行前后自动打印开始/完成日志
    3. process() 抽象方法 —— 子类只需写业务逻辑，不用管日志/异常
    """

    # 节点名称，用于日志追踪和调试
    # 子类必须覆盖此属性，否则 __init__ 会抛 ValueError
    name: str = "node_base"

    def __init__(self):
        """
        初始化防御检查：
        如果子类忘记覆盖 name 类属性，立即抛出异常，
        避免运行时才发现"无名节点"导致日志混乱。
        """
        if self.name == "node_base":
            raise ValueError(f"子类 {self.__class__.__name__} 必须覆盖 name 类属性")

    def __call__(self, state: ImportGraphState) -> ImportGraphState:
        """
        节点执行入口（使实例可像函数一样调用：node(state)）
        模板方法模式：定义算法骨架 → 子类填充具体步骤

        :param state: 工作流状态字典（TypedDict），包含所有节点共享的数据
        :return:     更新后的状态字典，传递给下一个节点
        """
        try:
            # [1] 前置日志：节点开始执行
            logger.info(f"--- {self.name} 开始啦 ---")
            task_id =  state.get("task_id")
            add_running_task(task_id, self.name)
            start_time = time.time()


            # [2] 委托给子类的 process() 执行业务逻辑
            result = self.process(state)

            # [3] 后置日志：节点执行成功
            logger.info(f"--- {self.name} 完成啦 ---")

            #修改每个节点执行完成的状态
            add_done_task(task_id, self.name)
            end_time = time.time()

            #计算用时
            add_node_duration(task_id, self.name, end_time - start_time)

            return result

        except Exception as e:
            # [4] 异常日志：捕获到异常时记录错误信息，并重新抛出
            logger.error(f"{self.name} 执行失败: {e}")
            raise  e# 重新抛出，让上层调用者（如 LangGraph 引擎）感知失败

    # ----------------------------------------------------------
    # 抽象方法：子类必须实现此方法
    # ----------------------------------------------------------
    @abstractmethod
    def process(self, state: ImportGraphState) -> ImportGraphState:
        """
        节点核心处理逻辑
        子类必须实现此方法，定义具体的业务操作

        :param state: 工作流状态对象（字典），包含任务所需的全部数据
        :return:     更新后的状态对象
        """
        ...  # 抽象方法不需要实现体，此处可用 pass 或 ... 占位
