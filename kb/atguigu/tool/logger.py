# ============================================================
# atguigu/tool/logger.py
# ============================================================
# 作用：统一的彩色日志配置模块。
#       使用 colorlog 库为不同日志级别赋予不同颜色，
#       整个项目通过 `from atguigu.tool.logger import logger` 复用同一个实例。
# 输出格式：时间 - 文件名:行号 - 级别 - 消息
# 颜色方案：DEBUG=青色 INFO=绿色 WARNING=黄色 ERROR=红色 CRITICAL=粗体红
# ============================================================

# logging：Python 标准库的日志模块，提供 Logger / Handler / Formatter 等基础设施
import logging
# colorlog：第三方库，为终端日志输出添加 ANSI 颜色代码
import colorlog

# 获取根 Logger 实例（全局唯一，整个进程复用）
# 注意：这里用 getLogger() 不传名称，拿到的是 root logger
logger = logging.getLogger()
# 设置日志记录的最低级别为 INFO
# 低于 INFO 的 DEBUG/Trace 消息将被过滤掉（如需调试可临时改为 DEBUG）
logger.setLevel(logging.INFO)

# 创建流处理器（StreamHandler）：将日志输出到终端（stdout/stderr）
handler = colorlog.StreamHandler()
# 设置流处理器的日志格式
handler.setFormatter(colorlog.ColoredFormatter(
    # 日志格式字符串，各字段含义：
    # %(log_color)s    — colorlog 插入的 ANSI 颜色代码（由下方 log_colors 决定）
    # %(asctime)s      — 时间戳（格式由 datefmt 控制）
    # %(filename)s     — 输出日志的源文件名
    # %(lineno)d       — 输出日志的代码行号
    # %(levelname)s    — 日志级别名称（DEBUG / INFO / WARNING / ERROR / CRITICAL）
    # %(message)s      — 日志正文内容
    '%(log_color)s%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s',
    # 时间戳格式：年-月-日 时:分:秒
    datefmt='%Y-%m-%d %H:%M:%S',
    # 日志级别 → 对应颜色的映射字典
    log_colors={
        'DEBUG': 'cyan',        # 调试信息 — 青色
        'INFO': 'green',        # 普通信息 — 绿色
        'WARNING': 'yellow',    # 警告信息 — 黄色
        'ERROR': 'red',         # 错误信息 — 红色
        'CRITICAL': 'bold_red', # 严重错误 — 粗体红色
    }
))

# 将处理器添加到 Logger 实例
# 注意：如果多次 import 此模块，Python 的模块缓存机制会复用已有 logger，
# 不会重复添加 handler（但若不放心可取消下面注释来先清空已有 handler）
# logger.handlers.clear()
logger.addHandler(handler)

# ----------------------------------------------------------
# 模块自测入口：当直接运行此文件时验证日志输出
# 用法：python -m atguigu.tool.logger
# ----------------------------------------------------------
if __name__ == '__main__':
    # 临时将 handler 级别降至 DEBUG，以便看到所有级别的日志
    handler.setLevel(logging.DEBUG)
    # 依次输出 5 个级别的测试日志，验证颜色方案是否正常
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
