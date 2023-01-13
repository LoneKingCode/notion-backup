import os
import shutil
import time
import json
import zipfile
import requests
import argparse
import subprocess
from notify import send

# ={'spaces':[]} 则备份所有空间 'space_blocks':[] 则备份整个空间
# block id格式切记为-隔开!!!
DEFAULT_BACKUP_CONFIG = {
    'spaces': [{
        'space_name': 'space_name',
        'space_blocks': [{
            'block_id': '12345678-1234-1234-1234-123456789123',
            'block_name': 'Home1'
        }, {
            'block_id': '12345678-1234-1234-1234-123456789123',
            'block_name': 'Home2'
        }]
    }]
}

# 默认配置无需更改
NOTION_TIMEZONE = os.getenv('NOTION_TIMEZONE', 'Asia/Shanghai')
NOTION_LOCALE = os.getenv('NOTION_TIMEZONE', 'en')
NOTION_API = os.getenv('NOTION_API', 'https://www.notion.so/api/v3')
# 邮箱和用户名
NOTION_EMAIL = os.getenv('NOTION_EMAIL', '')
NOTION_PASSWORD = os.getenv('NOTION_PASSWORD', '')
# 修改为浏览器内获取到的token
NOTION_TOKEN = os.getenv('NOTION_TOKEN', 'YOUR TOKEN')
NOTION_EXPORT_TYPE = os.getenv('NOTION_EXPORT_TYPE', 'markdown')  # html pdf
# 备份文件保存目录
SAVE_DIR = 'backup/'
# git相关信息
REPOSITORY_URL = 'https://github.com/git_user_name/xxx.git'
REPOSITORY_BRANCH = 'main'
GIT_USERNAME = 'git_user_name'
GIT_EMAIL = 'git@git.com'


def run_command(cmd):
    try:
        proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        # flag,stdout,stderr
        if proc.stderr != '':
            print('cmd:{} stdout:{} stderr:{}'.format(cmd, proc.stdout, proc.stderr))
        return proc.stderr == '', proc.stdout, proc.stderr
    except Exception as e:
        return False, '', str(e)


def writeLog(s):
    with open('log.txt', 'a') as log:
        msg = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()) + ' ' + s
        print(msg)
        send('notion备份', msg)
        log.write(msg + '\n')


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
        # 创建文件夹,并解压
        os.mkdir(dirname)
        file.extractall(dirname)
        file.close()
        return dirname
    except Exception as e:
        print(f'{filename} unzip fail,{str(e)}')


def initNotionToken():
    global NOTION_TOKEN
    if not NOTION_EMAIL and not NOTION_PASSWORD:
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


def exportSpace(spaceId):
    return {
        'task': {
            'eventName': 'exportSpace',
            'request': {
                'spaceId': spaceId,
                'exportOptions': {
                    'exportType': NOTION_EXPORT_TYPE,
                    'timeZone': NOTION_TIMEZONE,
                    'locale': NOTION_LOCALE,
                    'flattenExportFiletree': False
                }
            }
        }
    }


# {
#     "task": {
#         "eventName": "exportBlock",
#         "request": {
#             "block": {
#                 "id": "c093243a-a553-45ae-954f-4bf80d995167",
#                 "spaceId": "38d3bbb5-37de-4891-86cc-9dcfbafc30d0"
#             },
#             "recursive": true,
#             "exportOptions": {
#                 "exportType": "markdown",
#                 "timeZone": "Asia/Shanghai",
#                 "locale": "en",
#                 "flattenExportFiletree": false
#             }
#         }
#     }
# }


def exportSpaceBlock(spaceId, blockId):
    return {
        'task': {
            'eventName': 'exportBlock',
            'request': {
                'block': {
                    'id': blockId,
                    'spaceId': spaceId
                },
                'recursive': True,
                'exportOptions': {
                    'exportType': NOTION_EXPORT_TYPE,
                    'timeZone': NOTION_TIMEZONE,
                    'locale': NOTION_LOCALE,
                    'flattenExportFiletree': False
                }
            }
        }
    }


def request_post(endpoint: str, params: object):
    print('reqeust:{} {}'.format(endpoint, params))
    response = requests.post(
        f'{NOTION_API}/{endpoint}',
        data=json.dumps(params).encode('utf8'),
        headers={
            'content-type': 'application/json',
            'cookie': f'token_v2={NOTION_TOKEN}; '
        },
    )
    #print(response.json())
    return response.json()


def getUserContent():
    return request_post('loadUserContent', {})['recordMap']


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
        elif task['state'] == 'failure':
            print(task['error'])
        else:
            print('{}.'.format(task['state']), end='', flush=True)
            time.sleep(10)

    return url


def downloadAndUnzip(url, filename):
    os.makedirs(SAVE_DIR, exist_ok=True)
    savePath = SAVE_DIR + filename
    with requests.get(url, stream=True) as r:
        with open(savePath, 'wb') as f:
            shutil.copyfileobj(r.raw, f)
    unzip(savePath)


def initGit():
    run_command(f'git config --global user.name {GIT_USERNAME}')
    run_command(f'git config --global user.email {GIT_EMAIL}')
    run_command(f'git config pull.ff false')
    run_command(f'git init')
    run_command(f'git remote add origin {REPOSITORY_URL}')
    run_command(f'git branch -M {REPOSITORY_BRANCH}')
    run_command(f'git fetch --all && git reset --hard origin/{REPOSITORY_BRANCH}')
    run_command(f'git pull origin {REPOSITORY_BRANCH}')


def pull():
    run_command(f'git pull origin {REPOSITORY_BRANCH}')


def push():
    run_command(f'git add . && git commit -m "backup" && git push origin {REPOSITORY_BRANCH}')


def main():
    # 初始化git仓库
    initGit()

    # 初始化Token
    initNotionToken()

    # 获取用户信息
    userContent = getUserContent()
    time.sleep(3)

    userId = list(userContent['notion_user'].keys())[0]
    print(f'User id: {userId}')

    spaces = [(space_id, space_details['value']['name']) for (space_id, space_details) in userContent['space'].items()]
    backup_space_names = []
    backup_space_config = {}
    for backup_config_item in DEFAULT_BACKUP_CONFIG['spaces']:
        if backup_config_item['space_name']:
            backup_space_names.append(backup_config_item['space_name'])
            backup_space_config[backup_config_item['space_name']] = backup_config_item
    print('Available spaces total:{}'.format(len(spaces)))
    for (spaceId, spaceName) in spaces:
        print(f'\t-  {spaceId}:{spaceName}')
        taskId = ''

        # 备份所有空间
        if len(backup_space_names) == 0:
            taskId = request_post('enqueueTask', exportSpace(spaceId)).get('taskId')
            url = exportUrl(taskId)
            downloadAndUnzip(url, f'{spaceName}.zip')
        elif spaceName in backup_space_names:
            # 指定了space下的block
            if 'space_blocks' in backup_space_config[spaceName] and backup_space_config[spaceName]['space_blocks']:
                for space_block in backup_space_config[spaceName]['space_blocks']:
                    block_id = space_block['block_id']
                    block_name = space_block['block_name']
                    taskId = request_post('enqueueTask', exportSpaceBlock(spaceId, block_id)).get('taskId')
                    url = exportUrl(taskId)
                    downloadAndUnzip(url, f'{spaceName}-{block_name}.zip')
            else:
                # 没指定space block则备份整个空间
                taskId = request_post('enqueueTask', exportSpace(spaceId)).get('taskId')
                url = exportUrl(taskId)
                downloadAndUnzip(url, f'{spaceName}.zip')
        else:
            print('space:{}跳过 不在备份列表'.format(spaceName))

    # git
    print('开始提交代码')
    pull()
    push()
    writeLog('notion备份完成')


def run_retry():
    count = 0
    while True:
        try:
            main()
            break
        except Exception as e:
            count += 1
            writeLog('notion备份执行出错:' + str(e))
            print('执行出错:', str(e))
        if count > 3:
            writeLog('notion备份尝试{}次出错'.format(count))
            print('尝试{}次出错'.format(count))
            break
        time.sleep(15)


if __name__ == '__main__':
    writeLog('开始执行notion备份')
    parser = argparse.ArgumentParser(description='ArgUtils')
    parser.add_argument('-c',
                        type=str,
                        default='',
                        required=False,
                        help='配置文件路径,内容格式为 {"spaces": [{"space_name": "xxx", "space_blocks": [{"block_id": "12345678-1234-1234-1234-123456789123", "block_name": "xx"}]}]}')

    args = parser.parse_args()
    if args.c:
        try:
            with open(args.c, 'r') as f:
                c = f.read()
                print('读取文件:{}内容为:\n{}'.format(args.c, c))
                DEFAULT_BACKUP_CONFIG = json.loads(c)
                print('使用参数 DEFAULT_BACKUP_CONFIG:{}'.format(DEFAULT_BACKUP_CONFIG))
        except Exception as e:
            print('参数格式错误,请检查是否为合法的json字符串')
            print('{"spaces": [{"space_name": "xxx", "space_blocks": [{"block_id": "12345678-1234-1234-1234-123456789123", "block_name": "xx"}]}]}')
            raise Exception('参数格式错误,请检查是否为合法的json字符串:' + str(e))
    else:
        print('使用默认配置 DEFAULT_BACKUP_CONFIG:{}'.format(DEFAULT_BACKUP_CONFIG))

    run_retry()

# 定时定点执行
# nohup python3 notion-backup.py -u 2>&1 >> /tmp/notion-backup.log
# if __name__ == '__main__':
#     print('开始执行')
#     running = False
#     while True and not running:
#         now = datetime.datetime.now()
#         if now.hour == 3 and now.minute == 0:
#             running = True
#             run_retry()
#             running = False

#         time.sleep(30)
