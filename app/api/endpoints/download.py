import os
import zipfile
import re

import aiofiles
import httpx
import yaml
from fastapi import APIRouter, Request, Query, HTTPException  # 导入FastAPI组件
from starlette.responses import FileResponse

from app.api.models.APIResponseModel import ErrorResponseModel  # 导入响应模型
from crawlers.hybrid.hybrid_crawler import HybridCrawler  # 导入混合数据爬虫

router = APIRouter()
HybridCrawler = HybridCrawler()

# 读取上级再上级目录的配置文件
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'config.yaml')
with open(config_path, 'r', encoding='utf-8') as file:
    config = yaml.safe_load(file)

async def fetch_data(url: str, headers: dict = None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    } if headers is None else headers.get('headers')
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()  # 确保响应是成功的
        return response

# 下载视频专用
async def fetch_data_stream(url: str, request:Request , headers: dict = None, file_path: str = None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    } if headers is None else headers.get('headers')
    async with httpx.AsyncClient() as client:
        # 启用流式请求
        async with client.stream("GET", url, headers=headers) as response:
            response.raise_for_status()

            # 流式保存文件
            async with aiofiles.open(file_path, 'wb') as out_file:
                async for chunk in response.aiter_bytes():
                    if await request.is_disconnected():
                        print("客户端断开连接，清理未完成的文件")
                        await out_file.close()
                        os.remove(file_path)
                        return False
                    await out_file.write(chunk)
            return True


# 清理文件名中的非法字符
def sanitize_filename(filename: str) -> str:
    """
    清理文件名，移除或替换非法字符
    """
    # 移除或替换Windows和Unix系统中的非法字符
    illegal_chars = r'[<>:"/\\|?*]'
    # 将非法字符替换为下划线
    filename = re.sub(illegal_chars, '_', filename)
    # 移除前后空格
    filename = filename.strip()
    # 限制文件名长度（避免过长）
    if len(filename) > 200:
        filename = filename[:200]
    # 如果清理后为空，使用默认名称
    if not filename:
        filename = "video"
    return filename


@router.get("/download", summary="在线下载抖音|TikTok视频/图片/Online download Douyin|TikTok video/image")
async def download_file_hybrid(request: Request,
                               url: str = Query(
                                   example="https://www.douyin.com/video/7372484719365098803",
                                   description="视频或图片的URL地址，也支持抖音|TikTok的分享链接，例如：https://v.douyin.com/e4J8Q7A/"),
                               prefix: bool = True,
                               with_watermark: bool = False,
                               naming: str = Query(None, description="自定义文件名（不含扩展名），如果提供则覆盖默认命名")):
    """
    # [中文]
    ### 用途:
    - 在线下载抖音|TikTok 无水印或有水印的视频/图片
    - 通过传入的视频URL参数，获取对应的视频或图片数据，然后下载到本地。
    - 如果你在尝试直接访问TikTok单一视频接口的JSON数据中的视频播放地址时遇到HTTP403错误，那么你可以使用此接口来下载视频。
    - 这个接口会占用一定的服务器资源，所以在Demo站点是默认关闭的，你可以在本地部署后调用此接口。
    ### 参数:
    - url: 视频或图片的URL地址，也支持抖音|TikTok的分享链接，例如：https://v.douyin.com/e4J8Q7A/。
    - prefix: 下载文件的前缀，默认为True，可以在配置文件中修改。
    - with_watermark: 是否下载带水印的视频或图片，默认为False。
    - naming: 自定义文件名（不含扩展名），如果提供则覆盖默认命名规则。
    ### 返回:
    - 返回下载的视频或图片文件响应。

    # [English]
    ### Purpose:
    - Download Douyin|TikTok video/image with or without watermark online.
    - By passing the video URL parameter, get the corresponding video or image data, and then download it to the local.
    - If you encounter an HTTP403 error when trying to access the video playback address in the JSON data of the TikTok single video interface directly, you can use this interface to download the video.
    - This interface will occupy a certain amount of server resources, so it is disabled by default on the Demo site, you can call this interface after deploying it locally.
    ### Parameters:
    - url: The URL address of the video or image, also supports Douyin|TikTok sharing links, for example: https://v.douyin.com/e4J8Q7A/.
    - prefix: The prefix of the downloaded file, the default is True, and can be modified in the configuration file.
    - with_watermark: Whether to download videos or images with watermarks, the default is False.
    - naming: Custom filename (without extension), if provided, it will override the default naming rule.
    ### Returns:
    - Return the response of the downloaded video or image file.

    # [示例/Example]
    url: https://www.douyin.com/video/7372484719365098803
    naming: 我的视频 (optional)
    """
    # 是否开启此端点/Whether to enable this endpoint
    if not config["API"]["Download_Switch"]:
        code = 400
        message = "Download endpoint is disabled in the configuration file. | 配置文件中已禁用下载端点。"
        return ErrorResponseModel(code=code, message=message, router=request.url.path,
                                  params=dict(request.query_params))

    # 开始解析数据/Start parsing data
    try:
        data = await HybridCrawler.hybrid_parsing_single_video(url, minimal=True)
    except Exception as e:
        code = 400
        return ErrorResponseModel(code=code, message=str(e), router=request.url.path, params=dict(request.query_params))

    # 开始下载文件/Start downloading files
    try:
        data_type = data.get('type')
        platform = data.get('platform')
        aweme_id = data.get('aweme_id')
        file_prefix = config.get("API").get("Download_File_Prefix") if prefix else ''
        download_path = os.path.join(config.get("API").get("Download_Path"), f"{platform}_{data_type}")

        # 确保目录存在/Ensure the directory exists
        os.makedirs(download_path, exist_ok=True)

        # 下载视频文件/Download video file
        if data_type == 'video':
            # 如果提供了自定义文件名，使用自定义文件名；否则使用默认命名
            if naming:
                # 清理自定义文件名
                clean_naming = sanitize_filename(naming)
                file_name = f"{clean_naming}.mp4"
                # 存储文件时使用ID作为文件名以避免冲突
                storage_file_name = f"{file_prefix}{platform}_{aweme_id}.mp4" if not with_watermark else f"{file_prefix}{platform}_{aweme_id}_watermark.mp4"
            else:
                file_name = f"{file_prefix}{platform}_{aweme_id}.mp4" if not with_watermark else f"{file_prefix}{platform}_{aweme_id}_watermark.mp4"
                storage_file_name = file_name
            
            url = data.get('video_data').get('nwm_video_url_HQ') if not with_watermark else data.get('video_data').get(
                'wm_video_url_HQ')
            file_path = os.path.join(download_path, storage_file_name)

            # 判断文件是否存在，存在就直接返回
            if os.path.exists(file_path):
                return FileResponse(path=file_path, media_type='video/mp4', filename=file_name)

            # 获取视频文件
            __headers = await HybridCrawler.TikTokWebCrawler.get_tiktok_headers() if platform == 'tiktok' else await HybridCrawler.DouyinWebCrawler.get_douyin_headers()

            success = await fetch_data_stream(url, request, headers=__headers, file_path=file_path)
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail="An error occurred while fetching data"
                )

            # 返回文件内容，使用自定义文件名
            return FileResponse(path=file_path, filename=file_name, media_type="video/mp4")

        # 下载图片文件/Download image file
        elif data_type == 'image':
            # 如果提供了自定义文件名，使用自定义文件名；否则使用默认命名
            if naming:
                # 清理自定义文件名
                clean_naming = sanitize_filename(naming)
                zip_file_name = f"{clean_naming}.zip"
                # 存储文件时使用ID作为文件名以避免冲突
                storage_zip_file_name = f"{file_prefix}{platform}_{aweme_id}_images.zip" if not with_watermark else f"{file_prefix}{platform}_{aweme_id}_images_watermark.zip"
            else:
                zip_file_name = f"{file_prefix}{platform}_{aweme_id}_images.zip" if not with_watermark else f"{file_prefix}{platform}_{aweme_id}_images_watermark.zip"
                storage_zip_file_name = zip_file_name
            
            zip_file_path = os.path.join(download_path, storage_zip_file_name)

            # 判断文件是否存在，存在就直接返回
            if os.path.exists(zip_file_path):
                return FileResponse(path=zip_file_path, filename=zip_file_name, media_type="application/zip")

            # 获取图片文件/Get image file
            urls = data.get('image_data').get('no_watermark_image_list') if not with_watermark else data.get(
                'image_data').get('watermark_image_list')
            image_file_list = []
            for url in urls:
                # 请求图片文件/Request image file
                response = await fetch_data(url)
                index = int(urls.index(url))
                content_type = response.headers.get('content-type')
                file_format = content_type.split('/')[1]
                file_name_temp = f"{file_prefix}{platform}_{aweme_id}_{index + 1}.{file_format}" if not with_watermark else f"{file_prefix}{platform}_{aweme_id}_{index + 1}_watermark.{file_format}"
                file_path = os.path.join(download_path, file_name_temp)
                image_file_list.append(file_path)

                # 保存文件/Save file
                async with aiofiles.open(file_path, 'wb') as out_file:
                    await out_file.write(response.content)

            # 压缩文件/Compress file
            with zipfile.ZipFile(zip_file_path, 'w') as zip_file:
                for image_file in image_file_list:
                    zip_file.write(image_file, os.path.basename(image_file))

            # 返回压缩文件，使用自定义文件名
            return FileResponse(path=zip_file_path, filename=zip_file_name, media_type="application/zip")

    # 异常处理/Exception handling
    except Exception as e:
        print(e)
        code = 400
        return ErrorResponseModel(code=code, message=str(e), router=request.url.path, params=dict(request.query_params))