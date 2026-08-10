# ============================================================
# atguigu/import_process/nodes/node_md_img.py
# ============================================================
# 作用：Markdown 图片处理节点（NodeMDImg）。
#       对 Markdown 中的图片进行多模态理解：
#       调用视觉语言模型（VLM）描述图片内容，生成图片摘要替代纯图片链接。
#       当前为骨架代码，process() 只透传状态。
# ============================================================
import base64
import os
import re
import time
from collections import deque
from pathlib import Path

from langchain.chat_models import init_chat_model
from minio.deleteobjects import DeleteObject

from atguigu.config.config import LLMConfig, MinIOConfig
from atguigu.import_process import state
# 导入抽象基类
from atguigu.import_process.base import NodeBase
# 导入工作流状态类型
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger
from atguigu.tool.minio_client_tool import get_minio_client, minio_client


class NodeMDImg(NodeBase):
    """
    Markdown 图片处理节点：多模态图片理解
    职责：
    1. 从 Markdown 内容中提取所有图片引用（![]() 语法）
    2. 将图片发送给视觉语言模型（VLM / GPT-4o 等）
    3. 用模型生成的图片描述文本替换或补充原始图片链接
    4. 将增强后的 Markdown 写回 state.md_content
    """

    # 覆盖基类的 name 属性，标识此节点名称为 "node_md_img"
    name = "node_md_img"


    def get_image_with_summary_list(self, img_with_context_list):
        # step3 逐张调用视觉模型生成摘要
        # 模型只需初始化一次，循环内复用
        llm = init_chat_model(
            model=LLMConfig.vl_model,
            model_provider="openai",
            base_url=LLMConfig.openai_base,
            api_key=LLMConfig.openai_api_key,
            temperature=LLMConfig.llm_default_temperature,
        )

        # 因为模型有tpm限制，故需构建滑动窗口，平稳控制单位时间内的 token 消耗量，避免短时间请求量超限触发接口限流，导致整体工作流执行中断。
        dq = deque(maxlen=30)
        img_with_summary_list = []

        for img_with_context in img_with_context_list:
            # 每轮都取当前时间，才能正确判断窗口内的请求是否已过期
            current_time = time.time()
            while dq and current_time - dq[0] > 60:
                dq.popleft()  # 先移除过期请求
            # logit1. 上一步清理了过期请求，目前有位置   logit2. 上一步没有清理过期请求，代表目前队列还是满的
            if len(dq) == dq.maxlen:
                time_to_wait = 60 - (current_time - dq[0])
                if time_to_wait > 0:
                    logger.info(f"触发限流保护，等待{time_to_wait:.1f}秒")
                    time.sleep(time_to_wait)
                current_time = time.time()
                while dq and current_time - dq[0] > 60:
                    dq.popleft()
            dq.append(current_time)

            # 图片内容➡️base64
            img_path = img_with_context["img_path"]
            with open(img_path, "rb") as f:
                image_data = f.read()
                base64_str = base64.b64encode(image_data).decode('utf-8')

            # VL处理模块
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                # 这个格式就是base64在使用的时候的规定
                                "url": "data:image/jpeg;base64," + base64_str,
                            },
                        },
                        {"type": "text", "text": f"""
                                        这是一张图片，图片上文部分为"{img_with_context.get("pre_text")}"，
                                        下文部分为"{img_with_context.get("post_text")}"，
                                        请用中文简要总结这张图片的摘要,字数在50字以内。"""
                         },
                    ],
                },
            ]
            res = llm.invoke(messages)
            logger.info(f"图片摘要生成成功：{img_with_context['img_name']}")
            img_with_summary_list.append({
                "img_name": img_with_context["img_name"],
                "summary": res.content,
                "img_path": img_with_context["img_path"]
            })

        return img_with_summary_list

    def get_image_with_content_list(self, img_dir_path_obj, img_name_list, md_content):
        IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
        MAX_CONTEXT_LENGHT = 250
        img_with_context_list = []
        for img_name in img_name_list:
            if Path(img_name).suffix not in IMAGE_EXTENSIONS:
                logger.warning(f"不支持的图片格式：{Path(img_name).suffix}")
                continue
            # 构建图片在md中的正则对象
            pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(img_name) + r"\)")
            match = pattern.search(md_content)  # 匹配图片
            if not match:
                logger.warning(f"{img_name}图片未被引用。")
                continue
            # 匹配的图片获取头尾位置
            start, end = match.span()
            pre_text = md_content[max(0, start - MAX_CONTEXT_LENGHT):start]  # 获取图片前250个字符
            post_text = md_content[end:min(len(md_content), end + MAX_CONTEXT_LENGHT)]  # 获取图片后250个字符

            img_path = str(img_dir_path_obj / img_name)  # 图片路径

            # 图片、上下文以及路径构成一个字典
            img_with_context_list.append({
                "img_path": img_path,
                "pre_text": pre_text,
                "post_text": post_text,
                "img_name": img_name
            })
        return img_with_context_list

    def get_md_content(self,state):
        # step1 获取文件内容以及图片名字列表
        md_path = state.get("md_path", "")
        # markdown文件路径
        if not md_path:
            logger.error("未提供markdown路径")
            raise ValueError("未提供markdown路径")

        md_path_obj = Path(md_path)
        # markdown文件对象
        if not md_path_obj.exists():
            logger.error("markdown文件 %s 不存在", md_path)
            raise FileNotFoundError("markdown文件不存在")

        with open(md_path_obj, 'r', encoding='utf-8') as f:
            # 读取markdown文件内容
            md_content = f.read()
            logger.info(f"获取markdown内容成功")

        if not md_content:
            # 判断markdown内容是否为空
            logger.error("markdown内容 %s 为空", md_path)
            raise ValueError("markdown内容为空")
        return md_content, md_path_obj

    def get_img_with_summary_url_list(self, img_with_summary_list):
        upload_dir = MinIOConfig.minio_img_dir
        minio_client = get_minio_client()
        #幂等删除这个目录当中的图片
        #1.拿到桶中这个目录中的所有图片
        old_img_list = minio_client.list_objects(bucket_name=MinIOConfig.minio_bucket_name,prefix=upload_dir,recursive=True)
        #2.删除这个目录中的所有图片
        delete_img_list = [DeleteObject(obj.object_name) for obj in old_img_list]
        erros = minio_client.remove_objects(
            bucket_name=MinIOConfig.minio_bucket_name,
            delete_object_list=delete_img_list)
        for error in erros:
            logger.error("删除对象时发生错误: %s", error)

        #upload img to minio
        img_with_summary_url_list = []
        for img_with_summary in img_with_summary_list:
            minio_client.fput_object(
                bucket_name=MinIOConfig.minio_bucket_name,
                object_name=upload_dir + "/" + img_with_summary.get("img_name"),
                file_path=img_with_summary.get("img_path")
            )
            url = f"http://{MinIOConfig.minio_endpoint}/{MinIOConfig.minio_bucket_name}/{upload_dir}/{img_with_summary.get("img_name")}"
            img_with_summary_url_list.append({
                **img_with_summary,
                "image_url": url
                 })

        return img_with_summary_url_list

    def replace_md_img(self,img_with_summary_url_list,md_path_obj,md_content):
        for img_with_summary_url in img_with_summary_url_list:
            pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(img_with_summary_url.get("img_name")) + r"\)")
            md_content = pattern.sub(
                lambda _: f"![{img_with_summary_url.get('summary')}]({img_with_summary_url.get('image_url')})",
                md_content
            )

        #备份新的md文件
        new_md_path_obj = md_path_obj.parent / str(md_path_obj.stem + "_new.md" )
        with open(new_md_path_obj, 'w', encoding='utf-8') as f:
            f.write(md_content)
        return {"md_content": md_content,
                "md_path":str(new_md_path_obj)}




    def process(self, state: ImportGraphState) -> ImportGraphState:
        """
        Markdown 图片 → 文本描述的核心逻辑（当前为骨架占位）
        预期实现：
        1. 从 state.md_content 中正则匹配所有 ![](url) 或 <img> 标签
        2. 下载或读取本地图片文件
        3. 调用 VLM（如 GPT-4o）生成图片描述
        4. 将描述文本插入 Markdown，替代或补充图片链接
        5. 将处理后的 Markdown 写回 state.md_content

        :param state: 工作流状态字典
        :return:     更新后的状态字典（当前直接透传）
        """
        # step1 取得md内容以及路径对象
        md_content, md_path_obj = self.get_md_content(state)

        # 构造图片存储路径
        img_dir_path_obj = md_path_obj.parent / "images"
        if not img_dir_path_obj.exists():
            logger.warning("图片目录不存在，跳过图片处理")
            return {"md_content": md_content}

        img_name_list = os.listdir(img_dir_path_obj)  # 列出目录下所有文件名以及文件夹名
        if not img_name_list:
            logger.warning("图片目录为空，跳过图片处理")
            return {"md_content": md_content}

        # step2 取得图片的上下文列表，根据图片正则拿到图片位置，获取上下文
        img_with_context_list = self.get_image_with_content_list(img_dir_path_obj, img_name_list, md_content)


        # step3 调用视觉模型生成摘要
        img_with_summary_list = self.get_image_with_summary_list(img_with_context_list)


        #step4 上传图片到minio,自己构造图片的线上url，放到列表当中
        img_with_summary_url_list = self.get_img_with_summary_url_list(img_with_summary_list)

        # step5 替换md中的图片链接
        result = self.replace_md_img(img_with_summary_url_list, md_path_obj, md_content)
        md_content, new_md_path_obj = result["md_content"], result["md_path"]

        return {"md_content": md_content,}











if __name__ == '__main__':
    node = NodeMDImg()
    init_state = {
        "md_path": r"I:\study\课堂资料\12_尚硅谷大模型之智库掌柜\11、掌柜智库01\资料\05-设备手册汇总\doc\hak180产品安全手册\hak180产品安全手册.md"
    }
    result = node(init_state)
    logger.info(json_format(result))