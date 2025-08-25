import os
import shutil
import time
import json
import zipfile
import requests
import argparse
import subprocess
import re
from datetime import datetime
from notify import send

# ={'spaces':[]} 则备份所有空间 'space_blocks':[] 则备份整个空间
# block id格式切记为-隔开!!!
DEFAULT_BACKUP_CONFIG = {
    "spaces": [
        {
            "space_name": "space_name",
            "space_blocks": [
                {
                    "block_id": "12345678-1234-1234-1234-123456789123",
                    "block_name": "Home1",
                },
                {
                    "block_id": "12345678-1234-1234-1234-123456789123",
                    "block_name": "Home2",
                },
            ],
        }
    ]
}

# 是否去除所有文件和文件夹的id
REMOVE_FILES_ID = False

# 默认配置无需更改
NOTION_TIMEZONE = os.getenv("NOTION_TIMEZONE", "Asia/Shanghai")
NOTION_LOCALE = os.getenv("NOTION_TIMEZONE", "en")
NOTION_API = os.getenv("NOTION_API", "https://www.notion.so/api/v3")
# 邮箱和用户名
NOTION_EMAIL = os.getenv("NOTION_EMAIL", "")
NOTION_PASSWORD = os.getenv("NOTION_PASSWORD", "")
# 修改为浏览器内获取到的token
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "YOUR TOKEN")
# 登录后获取 下载文件需要
NOTION_FILE_TOKEN = ""
NOTION_EXPORT_TYPE = os.getenv("NOTION_EXPORT_TYPE", "markdown")  # html pdf
# 备份文件保存目录
SAVE_DIR = "backup"
# git相关信息
REPOSITORY_URL = "https://github.com/git_user_name/xxx.git"
REPOSITORY_BRANCH = "main"
GIT_USERNAME = "git_user_name"
GIT_EMAIL = "git@git.com"


def run_command(cmd):
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )
        # flag,stdout,stderr
        if proc.stderr != "":
            print("cmd:{} stdout:{} stderr:{}".format(cmd, proc.stdout, proc.stderr))
        return proc.stderr == "", proc.stdout, proc.stderr
    except Exception as e:
        return False, "", str(e)


def writeLog(s):
    with open("log.txt", "a") as log:
        msg = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) + " " + s
        print(msg)
        send("notion备份", msg)
        log.write(msg + "\n")


def unzip(filename: str, saveDir: str = ""):
    try:
        file = zipfile.ZipFile(filename)
        dirname = filename.replace(".zip", "")
        if saveDir != "":
            dirname = saveDir
        # 如果存在与压缩包同名文件夹 提示信息并跳过
        if os.path.exists(dirname):
            print(f"{dirname} 已存在,将被覆盖")
            shutil.rmtree(dirname)
        # 创建文件夹,并解压
        os.mkdir(dirname)
        file.extractall(dirname)
        file.close()
        return dirname
    except Exception as e:
        print(f"{filename} unzip fail,{str(e)}")


def zip_dir(dirpath, outFullName):
    """
    压缩指定文件夹
    :param dirpath: 目标文件夹路径
    :param outFullName: 压缩文件保存路径+xxxx.zip
    :return: 无
    """
    zip = zipfile.ZipFile(outFullName, "w", zipfile.ZIP_DEFLATED)
    for path, dirnames, filenames in os.walk(dirpath):
        # 去掉目标跟路径，只对目标文件夹下边的文件及文件夹进行压缩
        fpath = path.replace(dirpath, "")
        for filename in filenames:
            zip.write(os.path.join(path, filename), os.path.join(fpath, filename))
    zip.close()


def initNotionToken():
    global NOTION_TOKEN
    if not NOTION_EMAIL and not NOTION_PASSWORD:
        print("使用已设置的token:{}".format(NOTION_TOKEN))
        return NOTION_TOKEN
    loginData = {"email": NOTION_EMAIL, "password": NOTION_PASSWORD}
    headers = {
        # Notion obviously check this as some kind of (bad) test of CSRF
        "host": "www.notion.so"
    }
    response = requests.post(
        NOTION_API + "/loginWithEmail", json=loginData, headers=headers
    )
    response.raise_for_status()

    NOTION_TOKEN = response.cookies["token_v2"]
    print("使用账户获取到的token:{}".format(NOTION_TOKEN))
    return response.cookies["token_v2"]


def exportSpace(spaceId):
    return {
        "task": {
            "eventName": "exportSpace",
            "request": {
                "spaceId": spaceId,
                "exportOptions": {
                    "exportType": NOTION_EXPORT_TYPE,
                    "timeZone": NOTION_TIMEZONE,
                    "locale": NOTION_LOCALE,
                    "flattenExportFiletree": False,
                },
            },
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
        "task": {
            "eventName": "exportBlock",
            "request": {
                "block": {"id": blockId, "spaceId": spaceId},
                "recursive": True,
                "exportOptions": {
                    "exportType": NOTION_EXPORT_TYPE,
                    "timeZone": NOTION_TIMEZONE,
                    "locale": NOTION_LOCALE,
                    "flattenExportFiletree": False,
                },
            },
        }
    }


def request_post(endpoint: str, params: object, max_retries=3, retry_time_seconds=10):
    global NOTION_FILE_TOKEN
    print(
        "request post:{} max_retries:{} retry_time_seconds:{}".format(
            endpoint, max_retries, retry_time_seconds
        )
    )
    attempt = 0
    while attempt < max_retries:
        try:
            response = requests.post(
                f"{NOTION_API}/{endpoint}",
                data=json.dumps(params).encode("utf8"),
                headers={
                    "content-type": "application/json",
                    "cookie": f"token_v2={NOTION_TOKEN};",
                },
                timeout=60,
            )
            if response.status_code in [504, 500, 503]:
                raise Exception("504 Gateway Time-out,尝试重新连接")
            if response:
                # 使用 get 方法避免 keyError
                file_token = response.cookies.get("file_token")
                if not NOTION_FILE_TOKEN and file_token:
                    NOTION_FILE_TOKEN = file_token
                return response.json()
            else:
                print(f"Request url:{endpoint} error response: {response}")
        except Exception as e:
            print(f"Request url:{endpoint} error {e}")
            attempt += 1
        time.sleep(20)

    print(
        f"Failed to get a valid response from {endpoint} after {max_retries} attempts."
    )
    return None


def getUserContent():
    return request_post("loadUserContent", {})["recordMap"]


def exportUrl(taskId):
    url = False
    print("Polling for export task: {}".format(taskId))
    while True:
        res = request_post(
            "getTasks", {"taskIds": [taskId]}, max_retries=5, retry_time_seconds=15
        )
        tasks = res.get("results")
        task = next(t for t in tasks if t["id"] == taskId)
        if task["state"] == "success":
            url = task["status"]["exportURL"]
            print("download url:" + url)
            break
        elif task["state"] == "failure":
            print(task["error"])
        else:
            print("{}.".format(task["state"]), end="", flush=True)
            time.sleep(20)
    return url


def remove_files_id():
    if not REMOVE_FILES_ID:
        return
    for root, dirs, files in os.walk(SAVE_DIR):
        for file in files:
            path = os.path.join(root, file)
            filename_id = re.compile(r"[a-fA-F\d]{32}").findall(file)
            if filename_id:
                new_filename = file.replace(" " + filename_id[0], "")
                new_path = os.path.join(root, new_filename)
                os.rename(path, new_path)
    while True:
        rename_dir_flag = False
        for root, dirs, files in os.walk(SAVE_DIR):
            for dir in dirs:
                path = os.path.join(root, dir)
                dir_id = re.compile(
                    r"[a-fA-F\d]{8}-[a-fA-F\d]{4}-[a-fA-F\d]{4}-[a-fA-F\d]{4}-[a-fA-F\d]{12}"
                ).findall(dir)
                if dir_id:
                    new_dirname = dir.replace("-" + dir_id[0], "")
                    new_path = os.path.join(root, new_dirname)
                    os.rename(path, new_path)
                    rename_dir_flag = True
                    break
        if not rename_dir_flag:
            break


def downloadAndUnzip(url, filename):
    os.makedirs(SAVE_DIR, exist_ok=True)
    savePath = SAVE_DIR + "/" + filename
    with requests.get(
        url, stream=True, headers={"cookie": f"file_token={NOTION_FILE_TOKEN}"}
    ) as r:
        with open(savePath, "wb") as f:
            shutil.copyfileobj(r.raw, f)
    unzip(savePath)
    if os.path.exists(savePath):
        print("保存文件:" + savePath)
    else:
        print("保存文件:" + savePath + "失败")

    save_dir = savePath.replace(".zip", "")
    for file in os.listdir(save_dir):
        file_path = os.path.join(save_dir, file)
        if ".zip" in file_path:
            unzip(file_path)
            os.remove(file_path)
    if REMOVE_FILES_ID:
        remove_files_id()
        os.remove(savePath)
        zip_dir(save_dir, savePath)


def initGit():
    run_command(f"git config --global user.name {GIT_USERNAME}")
    run_command(f"git config --global user.email {GIT_EMAIL}")
    run_command(f"git config pull.ff false")
    run_command(f"git init")
    run_command(f"git remote add origin {REPOSITORY_URL}")
    run_command(f"git branch -M {REPOSITORY_BRANCH}")
    run_command(f"git fetch --all && git reset --hard origin/{REPOSITORY_BRANCH}")
    run_command(f"git pull origin {REPOSITORY_BRANCH}")


def pull():
    run_command(f"git pull origin {REPOSITORY_BRANCH}")


def push():
    run_command(
        f'git add . && git commit -m "backup" && git push origin {REPOSITORY_BRANCH}'
    )


def wait_seconds(seconds=60):
    print("wait {} seconds".format(seconds))
    time.sleep(seconds)


def executeBackup():

    # 初始化Token
    initNotionToken()

    # 获取用户信息
    userContent = getUserContent()
    time.sleep(3)

    # userId = list(userContent['notion_user'].keys())[0]
    # print(f'User id: {userId}')
    if "space" not in userContent:
        writeLog("notion备份失败:获取信息失败,userContent:{}".format(userContent))
        return

    spaces = [
        (space_id, space_details["value"]["name"])
        for (space_id, space_details) in userContent["space"].items()
    ]
    backup_space_names = []
    backup_space_config = {}
    for backup_config_item in DEFAULT_BACKUP_CONFIG["spaces"]:
        if backup_config_item["space_name"]:
            backup_space_names.append(backup_config_item["space_name"])
            backup_space_config[backup_config_item["space_name"]] = backup_config_item
    print(f"Available spaces total:{len(spaces)}")
    for spaceId, spaceName in spaces:
        print(f"\t-  {spaceId}:{spaceName}")
        taskId = ""

        # 备份所有空间
        if len(backup_space_names) == 0:
            taskId = request_post("enqueueTask", exportSpace(spaceId)).get("taskId")
            url = exportUrl(taskId)
            downloadAndUnzip(url, f"{spaceName}.zip")

            wait_seconds(60)

        elif spaceName in backup_space_names:
            # 指定了space下的block
            if (
                "space_blocks" in backup_space_config[spaceName]
                and backup_space_config[spaceName]["space_blocks"]
            ):
                for space_block in backup_space_config[spaceName]["space_blocks"]:
                    block_id = space_block["block_id"]
                    block_name = space_block["block_name"]
                    res = request_post(
                        "enqueueTask", exportSpaceBlock(spaceId, block_id)
                    )
                    if res == None:
                        print("enqueueTask get task id failed")
                        raise Exception("enqueueTask get task id failed")
                    taskId = res.get("taskId")
                    url = exportUrl(taskId)
                    downloadAndUnzip(url, f"{spaceName}-{block_name}.zip")

                    wait_seconds(60)
            else:
                # 没指定space block则备份整个空间
                taskId = request_post("enqueueTask", exportSpace(spaceId)).get("taskId")
                url = exportUrl(taskId)
                downloadAndUnzip(url, f"{spaceName}.zip")

                wait_seconds(60)

        else:
            print("space:{}跳过 不在备份列表".format(spaceName))


def main():
    initGit()

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    new_name = f"backup_{timestamp}"
    # 先不需要备份到另一个文件夹
    # if os.path.exists(SAVE_DIR):
    #     try:
    #         shutil.move(SAVE_DIR, new_name)
    #         print(f"目录{SAVE_DIR}已重命名为: {new_name}")
    #     except Exception as e:
    #         print(f"重命名{new_name}失败: {e}")
    #         raise e
    try:
        executeBackup()
        print("开始提交代码")
        pull()
        push()

        writeLog("notion备份完成")
        # 删除重命名后的目录
        # try:
        #     # 获取当前工作目录
        #     current_dir = os.getcwd()
        #     full_path = os.path.join(current_dir, new_name)
        #     print(f"尝试删除目录: {full_path}")

        #     if not os.path.exists(full_path):
        #         print(f"目录不存在: {full_path}")
        #         return

        #     # 使用rm命令强制删除目录
        #     cmd = f'rm -rf "{full_path}"'
        #     success, stdout, stderr = run_command(cmd)
        #     if success:
        #         print(f"目录 {full_path} 已删除")
        #     else:
        #         print(f"删除目录失败: {stderr}")
        # except Exception as e:
        #     print(f"删除 {new_name} 失败: {e}")
        #     print(f"当前工作目录: {current_dir}")
    except Exception as e:
        print(f"备份失败: {e}")
        # 恢复目录名字
        #shutil.move(new_name, SAVE_DIR)
        raise e


def run_retry():
    count = 0
    while True:
        try:
            main()
            break
        except Exception as e:
            count += 1
            writeLog("notion备份执行出错:" + str(e))
            print("执行出错:", str(e))
        if count > 3:
            writeLog("notion备份尝试{}次出错".format(count))
            print("尝试{}次出错".format(count))
            break
        time.sleep(15)


if __name__ == "__main__":
    writeLog("开始执行notion备份")
    parser = argparse.ArgumentParser(description="ArgUtils")
    parser.add_argument(
        "-c",
        type=str,
        default="",
        required=False,
        help='配置文件路径,内容格式为 {"spaces": [{"space_name": "xxx", "space_blocks": [{"block_id": "12345678-1234-1234-1234-123456789123", "block_name": "xx"}]}]}',
    )

    args = parser.parse_args()
    if args.c:
        try:
            with open(args.c, "r") as f:
                c = f.read()
                print("读取文件:{}内容为:\n{}".format(args.c, c))
                DEFAULT_BACKUP_CONFIG = json.loads(c)
                print("使用参数 DEFAULT_BACKUP_CONFIG:{}".format(DEFAULT_BACKUP_CONFIG))
        except Exception as e:
            print("参数格式错误,请检查是否为合法的json字符串")
            print(
                '{"spaces": [{"space_name": "xxx", "space_blocks": [{"block_id": "12345678-1234-1234-1234-123456789123", "block_name": "xx"}]}]}'
            )
            raise Exception("参数格式错误,请检查是否为合法的json字符串:" + str(e))
    else:
        print("使用默认配置 DEFAULT_BACKUP_CONFIG:{}".format(DEFAULT_BACKUP_CONFIG))

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
