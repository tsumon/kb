import shutil
import uuid
from datetime import datetime
from pathlib import Path
import fastapi
import uvicorn
from fastapi import BackgroundTasks, FastAPI, File, UploadFile
from starlette.middleware.cors import CORSMiddleware
from atguigu.config.config import MinIOConfig
from atguigu.import_process.main_graph import MainGraphRunner
from atguigu.tool.logger import logger
from atguigu.tool.minio_client_tool import get_minio_client
from atguigu.tool.task_utils import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PROCESSING,
    add_done_task,
    add_running_task,
    get_task_info,
    update_task_status,
)

# 创建FastAPI应用实例，配置基本信息
app = FastAPI(
    title="掌柜智库导入模块接口服务",
    description="导入模块的各个api接口服务",
    version="0.1.0",
)

# 配置CORS跨域中间件，允许所有来源访问（开发环境用，生产环境要限制）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # 允许所有来源访问
    allow_credentials=True,     # 允许携带 cookie
    allow_methods=["*"],        # 允许所有 HTTP 方法
    allow_headers=["*"],        # 允许所有请求头
)

#执行graph的后台任务函数
def run_main_graph(task_id:str, local_dir:str, local_file_path:str):
    """后台执行整个导入流程的graph"""
    try:
        # 初始化状态，传递给graph
        init_state = {
            "task_id": task_id,
            "local_dir": local_dir,
            "local_file_path": local_file_path,
        }
        update_task_status(task_id, TASK_STATUS_PROCESSING)
        # 创建并执行graph，跑完整个导入流水线
        MainGraphRunner.create_and_run(init_state)
        update_task_status(task_id, TASK_STATUS_COMPLETED)
    except Exception as e:
        # 记录详细的错误信息
        logger.error(f"工作流执行失败: {str(e)}", exc_info=True)
        # 出错就标记为失败
        update_task_status(task_id, TASK_STATUS_FAILED)


@app.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(..., description="The file to upload")):
    """
    上传文件接口
    - 生成唯一task_id用于追踪
    - 保存文件到本地D:/output/日期目录
    - 备份到MinIO对象存储
    - 后台触发导入流程graph
    """
    #step 1 . 生成uuid作为任务的唯一标识
    task_id = str(uuid.uuid4())

    #标记上传文件开始（正在运行状态）
    add_running_task(task_id, "upload_file")

    #step 2 . 保存文件到指定位置
    local_dir = rf"D:\output\{datetime.now().strftime('%Y%m%d')}"
    local_dir_obj = Path(local_dir)
    if not local_dir_obj.exists():
        local_dir_obj.mkdir(parents=True, exist_ok=True)
    local_file_path = str(local_dir_obj / file.filename)

    #分块写入，避免内存爆掉
    with open(local_file_path, "wb") as f:
        shutil.copyfileobj(file.file, f, 1024*1024)
    print(f"File saved to {local_file_path}")

    #step 3 . 备份文件到MinIO（对象存储）
    minio_client = get_minio_client()
    minio_client.fput_object(
        bucket_name=MinIOConfig.minio_bucket_name,
        object_name=f"pdf_file/{datetime.now().strftime('%Y%m%d')}/{task_id}/{file.filename}",
        file_path=local_file_path,
    )
    logger.info(f"File uploaded to MinIO: {file.filename}")

    #标记上传文件完成（已完成状态）
    add_done_task(task_id, "upload_file")

    #step 4 . 调用后台任务，连接graph，异步执行整个导入流程
    #用后台任务是为了不阻塞接口，上传完立即返回给前端
    background_tasks.add_task(run_main_graph, task_id=task_id, local_dir=local_dir, local_file_path=local_file_path)

    #返回响应给前端，最主要的是task_id，前端用来查询进度
    return {"task_id": task_id,"file_name": file.filename,"file_size": file.size}


@app.get("/status/{task_id}")
async def get_status(task_id: str = fastapi.Path(..., description="The task ID")):
    """查询任务状态接口，前端轮询调用这个接口获取进度"""
    return get_task_info(task_id)

if __name__ == '__main__':
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )