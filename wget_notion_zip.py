import requests
import os
from tqdm import tqdm
import schedule
from schedule import every, repeat
import functools
import time
from notify import send

#下载git仓库文件到指定位置,这个位置可以设置百度网盘或者其他网盘的自动备份

TOKEN = 'github_pat_xxxxxxxxxxx'
SAVE_PATH = "C:/backup/notion/lk-notion-backup.zip"
COPY_PATH = "H:/backup/notion/lk-notion-backup.zip" # 为空则不拷贝
URL = "https://codeload.github.com/LoneKingCode/xxxxxxxxxxx/zip/refs/heads/main"
HEADERS = {"Authorization": "token " + TOKEN}


def catch_exceptions(cancel_on_failure=False):
    def catch_exceptions_decorator(job_func):
        @functools.wraps(job_func)
        def wrapper(*args, **kwargs):
            try:
                return job_func(*args, **kwargs)
            except:
                import traceback
                print(traceback.format_exc())
                if cancel_on_failure:
                    return schedule.CancelJob

        return wrapper

    return catch_exceptions_decorator


@catch_exceptions(cancel_on_failure=True)
@repeat(every().day.at("09:00"))
def run():
    if os.path.exists(SAVE_PATH):
        os.remove(SAVE_PATH)
        print(f"{SAVE_PATH} 文件已删除")
    else:
        print(f"{SAVE_PATH} 文件不存在")

    print('开始下载文件,保存到:{}'.format(SAVE_PATH))
    response = requests.get(URL, headers=HEADERS, stream=True)

    file_size = int(response.headers.get('Content-Length', 0))
    block_size = 8192
    progress_bar = tqdm(total=file_size, unit='iB', unit_scale=True)

    with open(SAVE_PATH, 'wb') as file:
        for data in response.iter_content(block_size):
            progress_bar.update(len(data))
            file.write(data)

    progress_bar.close()

    if file_size != 0 and progress_bar.n != file_size:
        print("下载失败")
        send('notion_zip_download 下载失败', '下载失败')
        return
    else:
        print("下载完成")
    if COPY_PATH == '':
        return
    print('开始拷贝文件:{}到:{}'.format(SAVE_PATH, COPY_PATH))

    # 获取文件大小
    total_size = os.path.getsize(SAVE_PATH)
    # 拷贝文件并显示进度条
    with open(SAVE_PATH, 'rb') as fsrc:
        with open(COPY_PATH, 'wb') as fdst:
            with tqdm(total=total_size, unit='B', unit_scale=True, desc=SAVE_PATH.split('\\')[-1]) as pbar:
                while True:
                    buf = fsrc.read(1024 * 1024)
                    if not buf:
                        break
                    fdst.write(buf)
                    pbar.update(len(buf))

    send('notion_zip_download 完成', '完成')


if __name__ == '__main__':
    print('开始等待执行...')
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except Exception as e:
        send('notion_zip_download 出错', str(e))
