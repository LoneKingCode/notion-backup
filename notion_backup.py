import os
import shutil
import time
import json
import zipfile
import requests
import subprocess
import re
from notify import send

# 备份哪些页面只改这里。整空间导出暂不可用，必须填写 space_blocks。
# block id 用 - 隔开
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

# git相关信息
REPOSITORY_URL = "https://github.com/git_user_name/xxx.git"
REPOSITORY_BRANCH = "main"
GIT_USERNAME = "git_user_name"
GIT_EMAIL = "git@git.com"


# 是否去除所有文件和文件夹的id
REMOVE_FILES_ID = False

# 默认配置无需更改
NOTION_TIMEZONE = os.getenv("NOTION_TIMEZONE", "Asia/Shanghai")
NOTION_LOCALE = os.getenv("NOTION_LOCALE", "en")
NOTION_API = os.getenv("NOTION_API", "https://app.notion.com/api/v3")
NOTION_ORIGIN = "https://app.notion.com"
# 跟当前网页导出使用同一套客户端标识, 否则任务不会写进 task_output
NOTION_USER_AGENT = os.getenv(
    "NOTION_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36 Edg/155.0.0.0",
)
NOTION_CLIENT_VERSION = os.getenv("NOTION_CLIENT_VERSION", "23.13.20261030.0540")
NOTION_USER_ID = os.getenv("NOTION_USER_ID", "")
NOTION_CELL_HINT = os.getenv("NOTION_CELL_HINT", "")
NOTION_ACTIVE_SPACE_ID = ""
# task_output 连续没有记录超过这么多次就重新入队
EXPORT_STUB_LIMIT = 8
EXPORT_POLL_SECONDS = 20
EXPORT_TIMEOUT_SECONDS = 30 * 60
EXPORT_ENQUEUE_ATTEMPTS = 3
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


def export_options():
    return {
        "exportType": NOTION_EXPORT_TYPE,
        "timeZone": NOTION_TIMEZONE,
        "locale": NOTION_LOCALE,
        "collectionViewExportType": "currentView",
        "includeContents": "everything",
        "flattenExportFiletree": False,
        "preferredViewMap": {},
    }


def skip_whole_space_export(space_name):
    print("暂不可用: 空间 {} 不支持整空间导出，请在 space_blocks 里指定页面".format(space_name))


def exportSpaceBlock(spaceId, blockId):
    # 网页「导出」现在走 enqueueExportBlock, 不再走 enqueueTask/exportBlock
    return {
        "endpoint": "enqueueExportBlock",
        "body": {
            "block": {"id": blockId, "spaceId": spaceId},
            "recursive": True,
            "shouldExportComments": False,
            "exportOptions": export_options(),
        },
    }


def notion_headers():
    cookie = f"token_v2={NOTION_TOKEN}"
    if NOTION_USER_ID:
        cookie += f"; notion_user_id={NOTION_USER_ID}"
    if NOTION_FILE_TOKEN:
        cookie += f"; file_token={NOTION_FILE_TOKEN}"
    headers = {
        "content-type": "application/json",
        "cookie": cookie,
        "user-agent": NOTION_USER_AGENT,
        "notion-client-version": NOTION_CLIENT_VERSION,
        "notion-audit-log-platform": "web",
        "origin": NOTION_ORIGIN,
        "referer": NOTION_ORIGIN + "/",
    }
    if NOTION_USER_ID:
        headers["x-notion-active-user-header"] = NOTION_USER_ID
    if NOTION_ACTIVE_SPACE_ID:
        headers["x-notion-space-id"] = NOTION_ACTIVE_SPACE_ID
    if NOTION_CELL_HINT:
        headers["x-notion-cell-hint"] = NOTION_CELL_HINT
        headers["x-notion-cell-hint-source"] = "space-id-mapping"
    return headers


def remember_response(response):
    global NOTION_FILE_TOKEN, NOTION_CELL_HINT
    file_token = response.cookies.get("file_token")
    if not NOTION_FILE_TOKEN and file_token:
        NOTION_FILE_TOKEN = file_token
    hint = response.headers.get("x-notion-cell-hint")
    if hint:
        NOTION_CELL_HINT = hint


def request_post(endpoint: str, params: object, max_retries=3, retry_time_seconds=10):
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
                headers=notion_headers(),
                timeout=60,
            )
            if response.status_code in [504, 500, 503]:
                raise Exception("504 Gateway Time-out,尝试重新连接")
            if response:
                remember_response(response)
                return response.json()
            else:
                snippet = (response.text or "").replace("\n", " ")[:300]
                print(
                    "Request url:{} status:{} body:{}".format(
                        endpoint, response.status_code, snippet
                    )
                )
                attempt += 1
        except Exception as e:
            print(f"Request url:{endpoint} error {e}")
            attempt += 1
        if attempt < max_retries:
            time.sleep(retry_time_seconds)

    print(
        f"Failed to get a valid response from {endpoint} after {max_retries} attempts."
    )
    return None


def getUserContent():
    return request_post("loadUserContent", {})["recordMap"]


def record_value(record):
    """兼容旧的 value.name 和新的 value.value.name."""
    value = (record or {}).get("value") or {}
    if not isinstance(value, dict):
        return {}
    nested = value.get("value")
    if isinstance(nested, dict) and (
        "role" in value or "name" in nested or "id" in nested or "lifecycle" in nested
    ):
        return nested
    return value


def set_active_user(user_content):
    global NOTION_USER_ID
    if NOTION_USER_ID:
        print("使用已设置的用户:{}".format(NOTION_USER_ID))
        return
    roots = list((user_content.get("user_root") or {}).keys())
    users = list((user_content.get("notion_user") or {}).keys())
    NOTION_USER_ID = (roots or users or [""])[0]
    print("notion user id:{}".format(NOTION_USER_ID or "未找到"))


def list_spaces(user_content):
    spaces = []
    for space_id, space_details in (user_content.get("space") or {}).items():
        value = record_value(space_details)
        name = value.get("name")
        if not name:
            print("space {} 没有 name, keys:{}".format(space_id, list(value.keys())))
            continue
        spaces.append((space_id, name))
    return spaces


def export_link_from_status(status):
    if not isinstance(status, dict):
        return None
    for key in ("exportURL", "exportUrl", "export_url", "url"):
        link = status.get(key)
        if isinstance(link, str) and link:
            return link
    return None


def fetch_export_url_from_notifications(space_id, start_time_ms):
    """导出地址如果没写进 task_output，再从通知里找。返回 (url, ok)。"""
    try:
        response = requests.post(
            f"{NOTION_API}/getNotificationLogV2",
            data=json.dumps(
                {
                    "spaceId": space_id,
                    "size": 20,
                    "type": "unread_and_read",
                    "variant": "no_grouping",
                }
            ).encode("utf8"),
            headers=notion_headers(),
            timeout=30,
        )
        remember_response(response)
        if not response.ok:
            print(f"getNotificationLogV2 status:{response.status_code}")
            return None, False
        data = response.json()
    except Exception as e:
        print(f"getNotificationLogV2 error:{e}")
        return None, False

    activities = ((data or {}).get("recordMap") or {}).get("activity") or {}
    for activity in activities.values():
        raw = (activity or {}).get("value") or {}
        nested = raw.get("value") if isinstance(raw, dict) else None
        value = nested if isinstance(nested, dict) and nested.get("type") else raw
        if not isinstance(value, dict) or value.get("type") != "export-completed":
            continue
        try:
            started = float(value.get("start_time"))
        except (TypeError, ValueError):
            continue
        if started < start_time_ms:
            continue
        edits = value.get("edits") or []
        if edits and isinstance(edits[0].get("link"), str) and edits[0]["link"]:
            return edits[0]["link"], True
    return None, True


def find_export_url(value, depth=0):
    if not isinstance(value, dict) or depth > 4:
        return None
    link = export_link_from_status(value)
    if link:
        return link
    for key in ("value", "status", "result"):
        link = find_export_url(value.get(key), depth + 1)
        if link:
            return link
    return None


def task_output_value(res, output_id):
    """task_output[id].value.value 是任务, 其中 value.exportURL 是下载地址."""
    table = ((res or {}).get("recordMap") or {}).get("task_output") or {}
    record = table.get(output_id)
    if record is None and len(table) == 1:
        record = next(iter(table.values()))
    if not isinstance(record, dict):
        return None
    wrapper = record.get("value")
    if not isinstance(wrapper, dict):
        return None
    body = wrapper.get("value") if isinstance(wrapper.get("value"), dict) else wrapper
    result = body.get("value") if isinstance(body.get("value"), dict) else {}
    export_url = result.get("exportURL") or result.get("exportUrl")
    if not isinstance(export_url, str) or not export_url:
        export_url = find_export_url(body)
    return {
        "lifecycle": body.get("lifecycle") or body.get("state"),
        "status": body.get("status") or result.get("type"),
        "exportURL": export_url,
        "pagesExported": result.get("pagesExported"),
        "error": body.get("error"),
    }


def enqueue_output_id(res):
    if not isinstance(res, dict):
        return None
    if isinstance(res.get("outputKey"), str) and res["outputKey"]:
        return res["outputKey"]
    for key in ("taskId", "id"):
        if isinstance(res.get(key), str) and res[key]:
            return res[key]
    for key in ("result", "task", "data"):
        found = enqueue_output_id(res.get(key))
        if found:
            return found
    return None


def poll_task_output(output_id, space_id, start_time_ms):
    """轮询 task_output. 网页导出完成后, 下载地址在这里, 不在 getTasks."""
    deadline = time.time() + EXPORT_TIMEOUT_SECONDS
    empty_count = 0
    notif_fail = 0
    while time.time() < deadline:
        res = request_post(
            "syncRecordValuesMain",
            {
                "requests": [
                    {
                        "pointer": {
                            "table": "task_output",
                            "id": output_id,
                            "spaceId": space_id,
                        },
                        "version": -1,
                    }
                ],
                "spacePointer": {"table": "space", "id": space_id},
            },
            max_retries=3,
            retry_time_seconds=10,
        )
        output = task_output_value(res, output_id)
        if not output:
            empty_count += 1
            print(
                "task_output 还没有记录 ({}/{})".format(empty_count, EXPORT_STUB_LIMIT)
            )
            if empty_count >= EXPORT_STUB_LIMIT:
                print("导出结果一直没有写入,准备重新入队")
                return None
            time.sleep(EXPORT_POLL_SECONDS)
            continue

        empty_count = 0
        lifecycle = output.get("lifecycle")
        status = output.get("status")
        export_url = output.get("exportURL")
        print(
            "task_output:{} lifecycle:{} status:{} pages:{}".format(
                output_id, lifecycle or "-", status or "-", output.get("pagesExported")
            )
        )
        if lifecycle in ("failure", "failed", "dead") or status in (
            "failure",
            "failed",
        ):
            raise Exception(
                "export task failure: {}".format(
                    output.get("error") or lifecycle or status
                )
            )
        # lifecycle=success 且 status=complete 时, value.exportURL 已经可用
        if export_url:
            print("download url:" + export_url)
            return export_url

        if notif_fail < 3:
            notif_url, notif_ok = fetch_export_url_from_notifications(
                space_id, start_time_ms
            )
            if notif_url:
                print("download url from notification:" + notif_url)
                return notif_url
            if not notif_ok:
                notif_fail += 1
        time.sleep(EXPORT_POLL_SECONDS)

    print("轮询超过 {} 秒,准备重新入队".format(EXPORT_TIMEOUT_SECONDS))
    return None


def exportUrl(task_payload, space_id):
    global NOTION_ACTIVE_SPACE_ID
    previous_space = NOTION_ACTIVE_SPACE_ID
    NOTION_ACTIVE_SPACE_ID = space_id
    endpoint = task_payload["endpoint"]
    body = task_payload["body"]
    print(
        "导出 {} user:{} space:{}".format(
            endpoint, NOTION_USER_ID or "未设置", space_id
        )
    )
    last_error = None
    try:
        for attempt in range(1, EXPORT_ENQUEUE_ATTEMPTS + 1):
            start_time_ms = int(time.time() * 1000) - 2000
            res = request_post(endpoint, body)
            output_id = enqueue_output_id(res)
            print("{} output:{}".format(endpoint, output_id))
            if not output_id:
                last_error = Exception(
                    "{} 没有返回任务 id: {}".format(endpoint, res)
                )
                print(str(last_error))
            else:
                print(
                    "Polling task_output: {} attempt {}/{}".format(
                        output_id, attempt, EXPORT_ENQUEUE_ATTEMPTS
                    )
                )
                try:
                    url = poll_task_output(output_id, space_id, start_time_ms)
                except Exception as e:
                    last_error = e
                    print("导出任务失败: {}".format(e))
                    url = None
                if url:
                    return url
                last_error = last_error or Exception(
                    "export {} stuck".format(output_id)
                )
            if attempt < EXPORT_ENQUEUE_ATTEMPTS:
                wait_seconds(30)
    finally:
        NOTION_ACTIVE_SPACE_ID = previous_space
    raise last_error or Exception("export task failed")


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
    cookie = f"token_v2={NOTION_TOKEN}"
    if NOTION_FILE_TOKEN:
        cookie += f"; file_token={NOTION_FILE_TOKEN}"
    with requests.get(
        url,
        stream=True,
        headers={
            "cookie": cookie,
            "user-agent": NOTION_USER_AGENT,
            "referer": NOTION_ORIGIN + "/",
        },
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
    set_active_user(userContent)
    time.sleep(3)

    if "space" not in userContent:
        writeLog("notion备份失败:获取信息失败,userContent:{}".format(userContent))
        return

    spaces = list_spaces(userContent)
    if not spaces:
        writeLog(
            "notion备份失败:没有解析到空间,space keys:{}".format(
                list((userContent.get("space") or {}).keys())
            )
        )
        return
    backup_space_names = []
    backup_space_config = {}
    for backup_config_item in DEFAULT_BACKUP_CONFIG["spaces"]:
        if backup_config_item["space_name"]:
            backup_space_names.append(backup_config_item["space_name"])
            backup_space_config[backup_config_item["space_name"]] = backup_config_item
    print(f"Available spaces total:{len(spaces)}")
    for spaceId, spaceName in spaces:
        print(f"\t-  {spaceId}:{spaceName}")

        # 整空间导出已不可用, 只备份配置了页面的空间
        if len(backup_space_names) == 0:
            skip_whole_space_export(spaceName)

        elif spaceName in backup_space_names:
            # 指定了space下的block
            if (
                "space_blocks" in backup_space_config[spaceName]
                and backup_space_config[spaceName]["space_blocks"]
            ):
                for space_block in backup_space_config[spaceName]["space_blocks"]:
                    block_id = space_block["block_id"]
                    block_name = space_block["block_name"]
                    url = exportUrl(exportSpaceBlock(spaceId, block_id), spaceId)
                    downloadAndUnzip(url, f"{spaceName}-{block_name}.zip")

                    wait_seconds(60)
            else:
                skip_whole_space_export(spaceName)

        else:
            print("space:{}跳过 不在备份列表".format(spaceName))


def main():
    initGit()
    try:
        executeBackup()
        print("开始提交代码")
        pull()
        push()
        writeLog("notion备份完成")
    except Exception as e:
        print(f"备份失败: {e}")
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
    print("使用顶部配置 DEFAULT_BACKUP_CONFIG:{}".format(DEFAULT_BACKUP_CONFIG))
    run_retry()
