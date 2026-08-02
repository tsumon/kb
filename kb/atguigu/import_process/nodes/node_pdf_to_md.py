# ============================================================
# atguigu/import_process/nodes/node_pdf_to_md.py
# ============================================================
# 作用：PDF 转 Markdown 节点（NodePDFToMD）。
#       将 PDF 文件进行结构化解析，转换为 Markdown 格式文本。
#       使用 OCR 或文档解析工具提取文字、表格、图片引用。
#       当前为骨架代码，process() 只透传状态。
# ============================================================
from pathlib import Path

from atguigu.config.config import MineruConfig
# 导入抽象基类，复用日志/异常模板方法
from atguigu.import_process.base import NodeBase
# 导入状态类型，获得 IDE 补全支持
from atguigu.import_process.state import ImportGraphState
from atguigu.tool.json_format_tool import json_format
from atguigu.tool.logger import logger


class NodePDFToMD(NodeBase):
    """
    PDF 转 Markdown 节点：PDF 结构化解析
    职责：
    1. 读取 PDF 文件（从 state.pdf_path 获取路径）
    2. 调用文档解析工具（如 MinerU / PyMuPDF / pdfplumber）提取内容
    3. 将文字、表格、图片引用转换为 Markdown 格式
    4. 将转换后的 Markdown 文本存入 state.md_content
    5. 将输出的 .md 文件路径存入 state.md_path
    """

    # 覆盖基类的 name 属性，标识此节点名称为 "node_pdf_to_md"
    name = "node_pdf_to_md"

    def process(self, state: ImportGraphState) -> ImportGraphState:
        """
        PDF → Markdown 的核心转换逻辑（当前为骨架占位）
        预期实现：
        1. 检查 is_pdf_read_enabled，确认需要执行 PDF 转换
        2. 读取 state.pdf_path 的 PDF 文件
        3. 调用 MinerU / pdfplumber 等工具解析 PDF
        4. 生成 .md 文件并写入磁盘
        5. 将 md_path 和 md_content 写回 state

        :param state: 工作流状态字典
        :return:     更新后的状态字典（当前直接透传）
        """
        #step1 检查pdf_path是否存在
        pdf_path, pdf_path_obj, local_dir_obj = self.check_path(state)

        #step2 上传pdf到mineru 获取batch_id
        batch_id = self.upload_pdf(pdf_path,pdf_path_obj)

        #step3 等待mineru处理完成,轮询mineru获取结果,结果为zip的url
        md_zip_url = self.get_md_zip_url(batch_id)

        #step4 下载zip压缩文件,压缩,重命名,把文件内容读取保存state
        md_content,new_md_path_obj = self.download_zip_handler(md_zip_url,local_dir_obj,pdf_path_obj)
        return{
            "md_content": md_content,
            "md_path": str(new_md_path_obj)
        }



    def check_path(self, state: ImportGraphState) -> tuple[str, Path, Path]:
        pdf_path = state.get("pdf_path", "")
        if not pdf_path:
            logger.error("未提供PDF路径")
            raise ValueError("未提供PDF路径")

        pdf_path_obj = Path(pdf_path)
        if not pdf_path_obj.exists():
            logger.error("PDF文件不存在")
            raise FileNotFoundError("PDF文件不存在")

        local_dir = state.get("local_dir", "")
        if not local_dir:
            logger.error("未提供本地目录")
            raise ValueError("未提供本地目录")

        local_dir_obj = Path(local_dir)
        if not local_dir_obj.exists():
            local_dir_obj.mkdir(parents=True, exist_ok=True)
        return pdf_path, pdf_path_obj, local_dir_obj

    def upload_pdf(self,pdf_path,pdf_path_obj):
        import requests

        token = MineruConfig.mineru_token
        url = f"{MineruConfig.mineru_base_url}/file-urls/batch"
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        data = {
            "files": [
                {"name": f"{pdf_path_obj.name}", "data_id": "abcd"}
            ],
            "model_version": "vlm"
        }
        file_path = [f"{pdf_path}"]
        # 以后只要碰到需要发请求的逻辑,都要三层判断考虑
        # 判断请求是否成功
        # 判断响应数据是否成功
        # 判断响应数据是否正确
        response = requests.post(url, headers=header, json=data)
        if response.status_code != 200:
            logger.error("上传文件失败")
            raise Exception(f"上传PDF文件请求失败:{pdf_path}")
        logger.info(f"上传文件成功")
        result = response.json()

        if result["code"] != 0:
            logger.error("上传文件请求数据失败")
            raise Exception(f"上传PDF文件请求数据失败")
        logger.info(f"上传文件请求数据成功")

        batch_id = result["data"]["batch_id"]
        urls = result["data"]["file_urls"]
        for i in range(0, len(urls)):
            with open(file_path[i], 'rb') as f:
                res_upload = requests.put(urls[i], data=f)
                if res_upload.status_code == 200:
                    logger.info(f"{urls[i]} 上传成功")
                else:
                    logger.error(f"{urls[i]} 上传失败")

        return batch_id

    def get_md_zip_url(self,batch_id):
        import requests
        import time
        token = MineruConfig.mineru_token
        batch_id = batch_id
        url = f"{MineruConfig.mineru_base_url}/extract-results/batch/{batch_id}"
        header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        #计时
        total_time = 300  # 总时间
        retry_interval = 3  # 每次重试间隔秒数
        start_time = time.time()
        while True:
            try:
                res = requests.get(url, headers=header)
                if res.status_code != 200:
                    logger.error(f"获取PDF文件处理结果请求失败，状态码: {res.status_code}，响应: {res.text[:200]}")
                    raise Exception(f"获取PDF文件处理结果请求失败，状态码: {res.status_code}")

                result = res.json()
                if result["code"] != 0:
                    logger.error(f"获取PDF文件处理结果请求数据失败，code: {result['code']}，msg: {result.get('msg', '')}")
                    raise Exception(f"获取PDF文件处理结果请求数据失败，code: {result['code']}")

                data = result["data"]['extract_result'][0]
                if data['state'] != "done":
                    logger.info(f"PDF文件处理中，当前状态: {data['state']}")
                    raise Exception(f"PDF文件处理中尚未完成")

                zip_url = data['full_zip_url']
                logger.info(f"PDF文件处理完成，获取到zip_url")
                return zip_url
            except Exception as e:
                logger.error(f"PDF文件处理异常，等待{retry_interval}秒后重试: {e}")
                use_time = time.time() - start_time
                if use_time > total_time:
                    raise Exception(f"PDF文件处理超时（已等待{use_time:.0f}秒），请稍后再试")
                time.sleep(retry_interval)
                continue

    def download_zip_handler(self,md_zip_url,local_dir_obj,pdf_path_obj):
        import requests
        md_zip_res = requests.get(md_zip_url)
        if md_zip_res.status_code != 200:
            logger.error("下载PDF文件处理结果zip压缩包请求失败")
            raise Exception(f"下载PDF文件处理结果zip压缩包请求失败")
        md_zip_content = md_zip_res.content #通过文件流操作把zip内容写入磁盘文件
        md_zip_path_obj = local_dir_obj / f"{pdf_path_obj.stem}.zip" #构造下载的磁盘文件路径

        #以后读写文件如果是读写二进制,就不要加encoding='utf-8',容如果不是就加
        with open(md_zip_path_obj, 'wb') as f:
            f.write(md_zip_content)
        #解压zip文件
        import zipfile
        import shutil

        unzip_file_content = zipfile.ZipFile(md_zip_path_obj)
        unzip_file_path_obj = local_dir_obj / f"{pdf_path_obj.stem}"

        #判断压缩的目录存不存在，如果存在先删除,然后再创建
        if unzip_file_path_obj.exists():
            shutil.rmtree(unzip_file_path_obj)
        unzip_file_path_obj.mkdir(parents=True, exist_ok=True)

        unzip_file_content.extractall(unzip_file_path_obj) #真正把解压内容,放到这个目录

        #完成解压,重命名full.md
        origin_md_file_path_obj = unzip_file_path_obj / "full.md"
        new_md_file_path_obj = unzip_file_path_obj / f"{pdf_path_obj.stem}.md"
        origin_md_file_path_obj.rename(new_md_file_path_obj)

        #读取md文件,存储state
        with open(new_md_file_path_obj, 'r', encoding='utf-8') as f:
            md_content = f.read()
        return md_content, new_md_file_path_obj





if __name__ == '__main__':
    node = NodePDFToMD()
    init_state = {
        "pdf_path": r"I:\study\课堂资料\12_尚硅谷大模型之智库掌柜\11、掌柜智库01\资料\05-设备手册汇总\doc\hak180产品安全手册.pdf",
        "local_dir": r"I:\study\课堂资料\12_尚硅谷大模型之智库掌柜\11、掌柜智库01\资料\05-设备手册汇总\doc",
    }
    result = node(init_state)
    logger.info(json_format(result))
