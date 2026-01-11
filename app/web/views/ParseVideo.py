import asyncio
import os
import time
import re

import yaml
from pywebio.input import *
from pywebio.output import *
from pywebio_battery import put_video

from app.web.views.ViewsUtils import ViewsUtils

from crawlers.hybrid.hybrid_crawler import HybridCrawler

HybridCrawler = HybridCrawler()

# 读取上级再上级目录的配置文件
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'config.yaml')
with open(config_path, 'r', encoding='utf-8') as file:
    config = yaml.safe_load(file)


# 校验输入值/Validate input value
def valid_check(input_data: str):
    # 检索出所有链接并返回列表/Retrieve all links and return a list
    url_list = ViewsUtils.find_url(input_data)
    # 总共找到的链接数量/Total number of links found
    total_urls = len(url_list)
    if total_urls == 0:
        warn_info = ViewsUtils.t('没有检测到有效的链接，请检查输入的内容是否正确。',
                                 'No valid link detected, please check if the input content is correct.')
        return warn_info
    else:
        # 最大接受提交URL的数量/Maximum number of URLs accepted
        max_urls = config['Web']['Max_Take_URLs']
        if total_urls > int(max_urls):
            warn_info = ViewsUtils.t(f'输入的链接太多啦，当前只会处理输入的前{max_urls}个链接！',
                                     f'Too many links input, only the first {max_urls} links will be processed!')
            return warn_info


# 错误处理/Error handling
def error_do(reason: str, value: str) -> None:
    # 输出一个毫无用处的信息
    put_html("<hr>")
    put_error(
        ViewsUtils.t("发生了一个错误，程序将跳过这个输入值，继续处理下一个输入值。",
                     "An error occurred, the program will skip this input value and continue to process the next input value."))
    put_html(f"<h3>⚠{ViewsUtils.t('详情', 'Details')}</h3>")
    put_table([
        [
            ViewsUtils.t('原因', 'reason'),
            ViewsUtils.t('输入值', 'input value')
        ],
        [
            reason,
            value
        ]
    ])
    put_markdown(ViewsUtils.t('> 可能的原因:', '> Possible reasons:'))
    put_markdown(ViewsUtils.t("- 视频已被删除或者链接不正确。",
                              "- The video has been deleted or the link is incorrect."))
    put_markdown(ViewsUtils.t("- 接口风控，请求过于频繁。",
                              "- Interface risk control, request too frequent.")),
    put_markdown(ViewsUtils.t("- 没有使用有效的Cookie，如果你部署后没有替换相应的Cookie，可能会导致解析失败。",
                              "- No valid Cookie is used. If you do not replace the corresponding Cookie after deployment, it may cause parsing failure."))
    put_markdown(ViewsUtils.t("> 寻求帮助:", "> Seek help:"))
    put_markdown(ViewsUtils.t(
        "- 你可以尝试再次解析，或者尝试自行部署项目，然后替换`./app/crawlers/平台文件夹/config.yaml`中的`cookie`值。",
        "- You can try to parse again, or try to deploy the project by yourself, and then replace the `cookie` value in `./app/crawlers/platform folder/config.yaml`."))

    put_markdown(
        "- GitHub Issue: [Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API/issues)")
    put_html("<hr>")


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


# 批量下载视频函数
async def download_all_videos(video_info_list):
    """
    异步批量下载所有视频
    video_info_list: 包含视频信息的列表 [{'url': url, 'desc': desc, 'type': type}, ...]
    """
    with use_scope('download_progress', clear=True):
        put_markdown(f"### {ViewsUtils.t('正在准备下载...', 'Preparing to download...')}")
        
        # 过滤出只有视频的项
        video_items = [item for item in video_info_list if item['type'] == ViewsUtils.t('视频', 'Video')]
        
        if not video_items:
            put_warning(ViewsUtils.t('没有找到可下载的视频！', 'No videos found to download!'))
            return
        
        total = len(video_items)
        put_markdown(f"**{ViewsUtils.t('准备下载', 'Ready to download')} {total} {ViewsUtils.t('个视频', 'videos')}**")
        put_html('<br>')
        
        # 创建下载任务
        put_markdown(ViewsUtils.t('### 📥 开始下载，请在浏览器下载管理器中查看进度...', 
                                  '### 📥 Download started, please check progress in browser download manager...'))
        
        # 使用JavaScript触发多个下载
        download_script = ""
        for idx, item in enumerate(video_items, 1):
            url = item['url']
            desc = item['desc']
            
            # 清理描述作为文件名
            clean_desc = sanitize_filename(desc)
            
            # URL编码文件名，避免特殊字符问题
            import urllib.parse
            encoded_filename = urllib.parse.quote(clean_desc)
            
            # 构建下载链接，将自定义文件名作为参数传递
            download_url = f"/api/download?url={urllib.parse.quote(url)}&prefix=false&with_watermark=false&naming={encoded_filename}"
            
            # 添加延迟以避免浏览器阻止多个下载（每个下载间隔100ms）
            delay = idx * 100
            download_script += f"""
                setTimeout(function() {{
                    var link = document.createElement('a');
                    link.href = '{download_url}';
                    link.download = '{clean_desc}.mp4';
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                }}, {delay});
            """
        
        # 执行下载脚本
        put_html(f"<script>{download_script}</script>")
        
        # 显示下载列表
        put_html('<br>')
        put_markdown(f"### {ViewsUtils.t('下载列表:', 'Download list:')}")
        
        download_table = [[ViewsUtils.t('序号', 'No.'), ViewsUtils.t('文件名', 'Filename')]]
        for idx, item in enumerate(video_items, 1):
            clean_desc = sanitize_filename(item['desc'])
            download_table.append([idx, f"{clean_desc}.mp4"])
        
        put_table(download_table)
        
        put_html('<br>')
        put_success(ViewsUtils.t(
            f'✅ 已触发 {total} 个下载任务！请在浏览器的下载管理器中查看和管理下载。',
            f'✅ Triggered {total} download tasks! Please check and manage downloads in your browser\'s download manager.'
        ))
        
        put_info(ViewsUtils.t(
            '💡 提示：部分浏览器可能会阻止多个文件同时下载，请在浏览器提示中允许多个下载。',
            '💡 Tip: Some browsers may block multiple downloads. Please allow multiple downloads when prompted by your browser.'
        ))


def parse_video():
    placeholder = ViewsUtils.t(
        "批量解析请直接粘贴多个口令或链接，无需使用符号分开，支持抖音和TikTok链接混合，暂时不支持作者主页链接批量解析。",
        "Batch parsing, please paste multiple passwords or links directly, no need to use symbols to separate, support for mixing Douyin and TikTok links, temporarily not support for author home page link batch parsing.")
    input_data = textarea(
        ViewsUtils.t('请将抖音或TikTok的分享口令或网址粘贴于此',
                     "Please paste the share code or URL of [Douyin|TikTok] here"),
        type=TEXT,
        validate=valid_check,
        required=True,
        placeholder=placeholder,
        position=0)
    url_lists = ViewsUtils.find_url(input_data)
    # 解析开始时间
    start = time.time()
    # 成功/失败统计
    success_count = 0
    failed_count = 0
    # 链接总数
    url_count = len(url_lists)
    # 解析成功的url
    success_list = []
    # 解析失败的url
    failed_list = []
    # 存储视频信息用于批量下载
    video_info_list = []
    
    # 输出一个提示条
    with use_scope('loading_text'):
        # 输出一个分行符
        put_row([put_html('<br>')])
        put_warning(ViewsUtils.t('Server酱正收到你输入的链接啦！(◍•ᴗ•◍)\n正在努力处理中，请稍等片刻...',
                                 'ServerChan is receiving your input link! (◍•ᴗ•◍)\nEfforts are being made, please wait a moment...'))
    # 结果页标题
    put_scope('result_title')
    # 遍历链接列表
    for url in url_lists:
        # 链接编号
        url_index = url_lists.index(url) + 1
        # 解析
        try:
            data = asyncio.run(HybridCrawler.hybrid_parsing_single_video(url, minimal=True))
        except Exception as e:
            error_msg = str(e)
            with use_scope(str(url_index)):
                error_do(reason=error_msg, value=url)
            failed_count += 1
            failed_list.append(url)
            continue

        # 创建一个视频/图集的公有变量
        url_type = ViewsUtils.t('视频', 'Video') if data.get('type') == 'video' else ViewsUtils.t('图片', 'Image')
        platform = data.get('platform')
        desc = data.get('desc', 'video')
        
        # 保存视频信息用于批量下载
        video_info_list.append({
            'url': url,
            'desc': desc,
            'type': url_type
        })
        
        table_list = [
            [ViewsUtils.t('类型', 'type'), ViewsUtils.t('内容', 'content')],
            [ViewsUtils.t('解析类型', 'Type'), url_type],
            [ViewsUtils.t('平台', 'Platform'), platform],
            [f'{url_type} ID', data.get('aweme_id')],
            [ViewsUtils.t(f'{url_type}描述', 'Description'), desc],
            [ViewsUtils.t('作者昵称', 'Author nickname'), data.get('author').get('nickname')],
            [ViewsUtils.t('作者ID', 'Author ID'), data.get('author').get('unique_id')],
            [ViewsUtils.t('API链接', 'API URL'),
             put_link(
                 ViewsUtils.t('点击查看', 'Click to view'),
                 f"/api/hybrid/video_data?url={url}&minimal=false",
                 new_window=True)],
            [ViewsUtils.t('API链接-精简', 'API URL-Minimal'),
             put_link(ViewsUtils.t('点击查看', 'Click to view'),
                      f"/api/hybrid/video_data?url={url}&minimal=true",
                      new_window=True)]

        ]
        # 如果是视频/If it's video
        if url_type == ViewsUtils.t('视频', 'Video'):
            # 添加视频信息
            wm_video_url_HQ = data.get('video_data').get('wm_video_url_HQ')
            nwm_video_url_HQ = data.get('video_data').get('nwm_video_url_HQ')
            if wm_video_url_HQ and nwm_video_url_HQ:
                table_list.insert(4, [ViewsUtils.t('视频链接-水印', 'Video URL-Watermark'),
                                      put_link(ViewsUtils.t('点击查看', 'Click to view'),
                                               wm_video_url_HQ, new_window=True)])
                table_list.insert(5, [ViewsUtils.t('视频链接-无水印', 'Video URL-No Watermark'),
                                      put_link(ViewsUtils.t('点击查看', 'Click to view'),
                                               nwm_video_url_HQ, new_window=True)])
            table_list.insert(6, [ViewsUtils.t('视频下载-水印', 'Video Download-Watermark'),
                                  put_link(ViewsUtils.t('点击下载', 'Click to download'),
                                           f"/api/download?url={url}&prefix=true&with_watermark=true",
                                           new_window=True)])
            table_list.insert(7, [ViewsUtils.t('视频下载-无水印', 'Video Download-No-Watermark'),
                                  put_link(ViewsUtils.t('点击下载', 'Click to download'),
                                           f"/api/download?url={url}&prefix=true&with_watermark=false",
                                           new_window=True)])
            # 添加视频信息
            table_list.insert(0, [
                put_video(data.get('video_data').get('nwm_video_url_HQ'), poster=None, loop=True, width='50%')])
        # 如果是图片/If it's image
        elif url_type == ViewsUtils.t('图片', 'Image'):
            # 添加图片下载链接
            table_list.insert(4, [ViewsUtils.t('图片打包下载-水印', 'Download images ZIP-Watermark'),
                                  put_link(ViewsUtils.t('点击下载', 'Click to download'),
                                           f"/api/download?url={url}&prefix=true&with_watermark=true",
                                           new_window=True)])
            table_list.insert(5, [ViewsUtils.t('图片打包下载-无水印', 'Download images ZIP-No-Watermark'),
                                  put_link(ViewsUtils.t('点击下载', 'Click to download'),
                                           f"/api/download?url={url}&prefix=true&with_watermark=false",
                                           new_window=True)])
            # 添加图片信息
            no_watermark_image_list = data.get('image_data').get('no_watermark_image_list')
            for image in no_watermark_image_list:
                table_list.append(
                    [ViewsUtils.t('图片预览(如格式可显示): ', 'Image preview (if the format can be displayed):'),
                     put_image(image, width='50%')])
                table_list.append([ViewsUtils.t('图片直链: ', 'Image URL:'),
                                   put_link(ViewsUtils.t('⬆️点击打开图片⬆️', '⬆️Click to open image⬆️'), image,
                                            new_window=True)])
        # 向网页输出表格/Put table on web page
        with use_scope(str(url_index)):
            # 显示进度
            put_info(
                ViewsUtils.t(f'正在解析第{url_index}/{url_count}个链接: ',
                             f'Parsing the {url_index}/{url_count}th link: '),
                put_link(url, url, new_window=True), closable=True)
            put_table(table_list)
            put_html('<hr>')
        scroll_to(str(url_index))
        success_count += 1
        success_list.append(url)
        
    # 全部解析完成跳出for循环/All parsing completed, break out of for loop
    with use_scope('result_title'):
        put_row([put_html('<br>')])
        put_markdown(ViewsUtils.t('## 📝解析结果:', '## 📝Parsing results:'))
        put_row([put_html('<br>')])
    with use_scope('result'):
        # 清除进度条
        clear('loading_text')
        # 滚动至result
        scroll_to('result')
        # for循环结束，向网页输出成功提醒
        put_success(ViewsUtils.t('解析完成啦 ♪(･ω･)ﾉ\n请查看以下统计信息，如果觉得有用的话请在GitHub上帮我点一个Star吧！',
                                 'Parsing completed ♪(･ω･)ﾉ\nPlease check the following statistics, and if you think it\'s useful, please help me click a Star on GitHub!'))
        # 将成功，失败以及总数量显示出来并且显示为代码方便复制
        put_markdown(
            f'**{ViewsUtils.t("成功", "Success")}:** {success_count} **{ViewsUtils.t("失败", "Failed")}:** {failed_count} **{ViewsUtils.t("总数量", "Total")}:** {success_count + failed_count}')
        # 成功列表
        if success_count != url_count:
            put_markdown(f'**{ViewsUtils.t("成功列表", "Success list")}:**')
            put_code('\n'.join(success_list))
        # 失败列表
        if failed_count > 0:
            put_markdown(f'**{ViewsUtils.t("失败列表", "Failed list")}:**')
            put_code('\n'.join(failed_list))
        # 将url_lists显示为代码方便复制
        put_markdown(ViewsUtils.t('**以下是您输入的所有链接：**', '**The following are all the links you entered:**'))
        put_code('\n'.join(url_lists))
        # 解析结束时间
        end = time.time()
        # 计算耗时,保留两位小数
        time_consuming = round(end - start, 2)
        # 显示耗时
        put_markdown(f"**{ViewsUtils.t('耗时', 'Time consuming')}:** {time_consuming}s")
        
        # 添加批量下载按钮（仅当有视频时显示）
        video_count = sum(1 for item in video_info_list if item['type'] == ViewsUtils.t('视频', 'Video'))
        if video_count > 0:
            put_html('<br>')
            put_button(
                ViewsUtils.t(f'📥 一键下载全部无水印视频 ({video_count}个)', 
                           f'📥 Download All No-Watermark Videos ({video_count})'), 
                onclick=lambda: asyncio.run(download_all_videos(video_info_list)), 
                color='primary', 
                outline=True
            )
        
        put_html('<br>')
        # 放置一个按钮，点击后跳转到顶部
        put_button(ViewsUtils.t('回到顶部', 'Back to top'), onclick=lambda: scroll_to('1'), color='success',
                   outline=True)
        # 返回主页链接
        put_link(ViewsUtils.t('再来一波 (つ´ω`)つ', 'Another wave (つ´ω`)つ'), '/')
        
        # 下载进度显示区域
        put_scope('download_progress')