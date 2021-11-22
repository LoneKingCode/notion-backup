import os
import shutil
import time
import json
import zipfile
import requests
import datetime
import subprocess
import signal

NOTION_TIMEZONE = os.getenv('NOTION_TIMEZONE', "Asia/Shanghai")
NOTION_LOCALE = os.getenv('NOTION_TIMEZONE', "en")
NOTION_EMAIL = os.getenv('NOTION_EMAIL', "")
NOTION_PASSWORD = os.getenv('NOTION_PASSWORD', "")
NOTION_API = os.getenv('NOTION_API', 'https://www.notion.so/api/v3')
NOTION_TOKEN = os.getenv('NOTION_TOKEN', '')
SAVE_DIR = "backup/"


def writeLog(s):
    with open('log.txt', 'a') as log:
        log.write(str(time.time()) + ' ' + s + '\n')


def unzip(filename: str, saveDir: str = ''):
    try:
        file = zipfile.ZipFile(filename)
        dirname = filename.replace('.zip', '')
        if saveDir != '':
            dirname = saveDir
        # 如果存在与压缩包同名文件夹 提示信息并跳过
        if os.path.exists(dirname):
            print(f'{dirname} 已存在,将被覆盖')
            shutil.rmtree(dirname)
        # 创建文件夹，并解压
        os.mkdir(dirname)
        file.extractall(dirname)
        file.close()
        return dirname
    except Exception as e:
        print(f'{filename} unzip fail,{str(e)}')


def initNotionToken():
    global NOTION_TOKEN
    if NOTION_TOKEN:
        return NOTION_TOKEN
    loginData = {'email': NOTION_EMAIL, 'password': NOTION_PASSWORD}
    headers = {
        # Notion obviously check this as some kind of (bad) test of CSRF
        'host': 'www.notion.so'
    }
    response = requests.post(NOTION_API + '/loginWithEmail', json=loginData, headers=headers)
    response.raise_for_status()

    NOTION_TOKEN = response.cookies['token_v2']
    return response.cookies['token_v2']


def exportTask(spaceId):
    return {'task': {'eventName': "exportSpace", 'request': {'spaceId': spaceId, 'exportOptions': {'exportType': 'markdown', 'timeZone': NOTION_TIMEZONE, 'locale': NOTION_LOCALE}}}}


def request_post(endpoint: str, params: object):
    response = requests.post(
        f'{NOTION_API}/{endpoint}',
        data=json.dumps(params).encode('utf8'),
        headers={
            'content-type': 'application/json',
            'cookie': f'token_v2={NOTION_TOKEN}; '
        },
    )

    return response.json()


def getUserContent():
    return request_post("loadUserContent", {})["recordMap"]


def exportUrl(taskId):
    url = False
    print('Polling for export task: {}'.format(taskId))
    while True:
        res = request_post('getTasks', {'taskIds': [taskId]})
        tasks = res.get('results')
        task = next(t for t in tasks if t['id'] == taskId)
        if task['state'] == 'success':
            url = task['status']['exportURL']
            print(url)
            break
        else:
            print('.', end="", flush=True)
            time.sleep(10)
    return url


def downloadAndUnzip(url, filename):
    os.makedirs(SAVE_DIR, exist_ok=True)
    savePath = SAVE_DIR + filename
    with requests.get(url, stream=True) as r:
        with open(savePath, 'wb') as f:
            shutil.copyfileobj(r.raw, f)
    unzip(savePath)


def push():
    os.system(f'git pull && git add . && git commit -m "backup" && git push')


def main():
    if not NOTION_TOKEN:
        initNotionToken()

    userContent = getUserContent()
    userId = list(userContent["notion_user"].keys())[0]
    print(f"User id: {userId}")

    spaces = [(space_id, space_details["value"]["name"]) for (space_id, space_details) in userContent["space"].items()]
    print("Available spaces total:{}".format(len(spaces)))
    for (spaceId, spaceName) in spaces:
        print(f"\t-  {spaceId}:{spaceName}")
        taskId = request_post('enqueueTask', exportTask(spaceId)).get('taskId')
        url = exportUrl(taskId)
        downloadAndUnzip(url, f'{spaceName}-{spaceId}.zip')

    push()

    writeLog('备份完成')


def run_retry():
    count = 0
    while True:
        try:
            main()
            break
        except Exception as e:
            count += 1
            writeLog('执行出错:' + str(e))
            print('执行出错:', str(e))
        if count > 3:
            writeLog('尝试{}次出错'.format(count))
            print('尝试{}次出错'.format(count))
            break
        time.sleep(15)


if __name__ == "__main__":
    print('开始执行')
    running = False
    while True and not running:
        now = datetime.datetime.now()
        if now.hour == 3 and now.minute == 0:
            running = True
            run_retry()
            running = False

        time.sleep(30)