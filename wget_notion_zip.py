import subprocess
from notify import send

def run_command(cmd):
    try:
        proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
        # flag,stdout,stderr
        return proc.returncode == 0, proc.stdout, proc.stderr
    except Exception as e:
        return False, '', str(e)


#下载git仓库文件到指定位置,这个位置可以设置百度网盘或者其他网盘的自动备份

token = 'github_token'
path = 'username/respository/branch/dir/'
files = ['LoneKing-Bookmark.zip']

SAVE_PATH = '/home/www/root/'
COMMAND = 'curl -o ' + SAVE_PATH + '{FILE} -H "Authorization: token {TOKEN}"  https://raw.githubusercontent.com/{PATH}{FILE}'

notify_msg = ''
for file in files:
    flag, msg, err = run_command(COMMAND.format(TOKEN=token, PATH=path, FILE=file))
    print('download {}'.format(file))
    if not flag:
        send('notion_zip_download exception', 'file:{} 下载出错 msg:{} err:{}'.format(file, msg, err))
    else:
        notify_msg += file + ' '
if notify_msg:
    notify_msg += ' 下载完成'
    send('notion_zip_download completed', notify_msg)
