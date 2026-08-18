import json
import uuid

from fastapi import FastAPI, Body, BackgroundTasks
from fastapi import Path
import uvicorn
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

from starlette.responses import StreamingResponse

from atguigu.query_process.main_graph import MainGraphRunner
from atguigu.tool.mongo_client_tool import delete_history, get_recent_history_list
from atguigu.tool.task_utils import (
    TASK_STATUS_PROCESSING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    get_task_info,
    update_task_status,
    create_queue,
    put_data,
    get_data,
)

app = FastAPI(
    title="检索模块对应接口",
    description="一个简单的检索模块对应前端接口",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # 允许所有来源访问
    allow_credentials=True,     # 允许携带 cookies
    allow_methods=["*"],        # 允许所有 HTTP 方法
    allow_headers=["*"],        # 允许所有请求头
)


#1 健康检查接口
@app.get("/health")
async def health():
    #随便返回什么都可以，因为前端只关心接口是否能访问到，不关心返回值
    return {"status": "healthy"}


#2 历史记录查询接口
@app.get("/history/{session_id}")
async def history(session_id: str = Path(..., description="会话ID")):
    history_list = get_recent_history_list(session_id)
    history_list = [
        {
        "_id":str(item.get("_id")),
        "role":item.get("role",""),
        "text":item.get("text",""),
        "rewritten_query":item.get("rewritten_query",""),
        "item_names":item.get("item_names",""),
        "image_urls":item.get("image_urls", []),
        "ts":item.get("ts",""),
        "session_id":item.get("session_id","")
        }
        for item in history_list
    ]

    return {"items": history_list}  #前端已完成的情况下，返回数据的时候要看前端页面写的是什么


#3 清空历史对话接口
@app.delete("/history/{session_id}")
async def clear_history(session_id: str = Path(..., description="会话ID")):

    delete_history(session_id)
    return {"msg": "删除成功"}




# 发送会话接口

class QueryParams(BaseModel):
    query: str = Field(..., description="查询内容")
    session_id: str = Field(..., description="会话ID")


def run_query_graph(task_id: str, original_query: str, session_id: str):
    """后台执行整个查询流程的graph（队列的创建/推送/清理全部走 task_utils）"""
    # 先创建队列再跑图：SSE 流无论什么时候连上来，都从同一个队列对象消费，消息不丢
    create_queue(task_id)

    try:
        init_state = {
            "task_id": task_id,
            "original_query": original_query,
            "session_id": session_id,
        }
        #更新总状态，推 progress，SSE 就能从队列中获取数据推送到前端
        update_task_status(task_id, TASK_STATUS_PROCESSING)
        put_data(task_id, "progress", get_task_info(task_id))
        result = MainGraphRunner.create_and_run(init_state)

        # 注意：不再在这里发 final——node_answer_output 已经发了带 image_urls 的 final，
        # 再发一次 image_urls:[] 会把图片覆盖掉。这里只负责更新终态 + 发 completed 进度。
        update_task_status(task_id, TASK_STATUS_COMPLETED)
        put_data(task_id, "progress", get_task_info(task_id))
    except Exception as e:
        update_task_status(task_id, TASK_STATUS_FAILED)
        put_data(task_id, "error", {"error": str(e), **get_task_info(task_id)})
        raise e


@app.post("/query")

async def query(background_tasks: BackgroundTasks, query_params: QueryParams = Body(..., description="查询请求体参数")):
    # 创建task_id
    task_id = str(uuid.uuid4())
    original_query = query_params.query
    session_id = query_params.session_id

    #调用后台接口任务执行graph
    background_tasks.add_task(run_query_graph, task_id, original_query, session_id)

    return {
        "task_id": task_id,
        "original_query": original_query,
        "session_id": session_id
    }


def generate_stream(task_id: str):
    while True:
        item = get_data(task_id)
        event = item.get("event")
        data = item.get("data")
        yield f"event: {event}\n"
        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        # 终态后关闭流
        if event in ("final", "error"):
            break





@app.get("/stream/{task_id}")
async def stream(task_id: str = Path(..., description="任务ID")):
    return StreamingResponse(generate_stream(task_id),media_type="text/event-stream")


if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8001)
