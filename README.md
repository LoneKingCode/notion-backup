# notion-backup

## notion 自动备份脚本

## Automatic Notion workspace backup to git and local

基于 `python3`，调用 Notion 网页正在使用的导出接口，按脚本顶部的配置导出指定页面及其子页面。导出结果是 zip，脚本会解压，再提交到 git 仓库，从而保留版本历史。整空间导出暂不可用。

### Debian/Ubuntu 简单安装 python3 及 pip3

```
apt-get update
apt-get install python3 -y
apt-get install python3-pip -y
```

### Centos 简单安装 python3 及 pip3

```
yum update
yum install python3 -y
yum install python3-pip -y
```

### 验证安装结果

```
python3 --version
pip3 -V
```

需要安装相关依赖包

```
pip3 install requests
```

### 使用方法

### 1. 使用用户名密码方式

设置系统环境变量  
`NOTION_EMAIL` 为账户  
`NOTION_PASSWORD`为密码  
或者直接修改变量为  
`NOTION_EMAIL='yourEmail@email.com'`  
`NOTION_PASSWORD='your Password'`

### 2. 使用 token 方式

浏览器开发者工具，选择 Network，查看 notion 页面请求中的 cookie
`token_v2=xxxxxxxxxxx`  
然后设置环境变量`NOTION_TOKEN`为上面的 token_v2 后的值  
或者直接设置变量`NOTION_TOKEN='your Token'`

### 3. 存储位置

默认存储到程序目录`backup`文件夹,如需修改，修改脚本中变量`SAVE_DIR`的值

### 4. 上传到远程存储

修改以下信息

```
REPOSITORY_URL = "https://github.com/LoneKingCode/xxx.git"
REPOSITORY_BRANCH = "main"
GIT_USERNAME ='111'
GIT_EMAIL ='111@111.com'
```

默认上传到 github。需要自己新建一个私有仓库，把本项目放进该仓库，再在仓库目录下运行 `notion_backup.py`。
注：如果不用ci执行，在服务器本地执行的话  
记得修改`.git`文件夹中的`config`文件，把用户名和密码配置到仓库地址 <https://username:password@github.com/username/notion-backup.git> 上，防止脚本自动 push 代码时，需要输入用户名密码
或者手动先push一次，并且设置credentials

记得设置保存备份文件仓库的.gitignore为这样

```
*.zip
/backup/*.zip
log.txt
__pycache__
```

### 5. 备份配置

只改 `notion_backup.py` 顶部的 `DEFAULT_BACKUP_CONFIG`。脚本不读取配置文件。
`block_id` 必须是用 `-` 隔开的 UUID。
`space_blocks` 必须填写。`spaces` 为空，或者某个空间没有 `space_blocks` 时，脚本只输出「暂不可用」，不会导出该空间。

```python
{
    "spaces": [
        {
            "space_name": "space_name",
            "space_blocks": [
                {
                    "block_id": "12345678-1234-1234-1234-123456789123",
                    "block_name": "Home",
                }
            ],
        }
    ]
}
```

`space_name` 要和 Notion 里的空间名称一致。每个页面会连同子页面一起导出。

### 6. 执行脚本

```shell
python3 notion_backup.py
```

`run_job.py` 用 `schedule` 每天 03:00 执行一次，需要的话单独运行它。

### 7. 导出其他格式

修改脚本顶部的 `NOTION_EXPORT_TYPE`。可选 `markdown`、`html`、`pdf`，默认是 `markdown`。

### 8. 注意事项

#### 8.1 windows 路径最大长度 255 字符，notion 的文件夹、文件末尾都带了类似 md5 的东西，所以文件树过深时，windows 系统上解压会报错，目录树过深时请于 linux 系统使用  

#### 8.2 如果不需要提交到git注释代码中initGit() pull() push()

 ```python
    # 初始化git仓库
    #initGit()
    # git
    #print('开始提交代码')
    #pull()
    #push()
 ```

### 9. 使用效果

![image](https://user-images.githubusercontent.com/11244921/212226093-773c7c7d-3020-4bb8-825f-e9459452301a.png)
![image](https://user-images.githubusercontent.com/11244921/212226257-8b64b5fa-07a9-4eb6-b912-6d20e34c8c80.png)

### 10. 消息推送

修改`notify.py`中顶部的推送参数即可，比如TG推送就设置`push_config`的 `TG_BOT_TOKEN`和`TG_USER_ID`
![image](https://user-images.githubusercontent.com/11244921/212223591-e44c678c-d391-4108-9a62-c74cb79e16f8.png)

### 11. 其他使用方法

搭配 GitHub Actions 的定时任务，可以在云端自动打包并上传，不需要在自己的服务器上执行。
参考文件.github/workflows/backup.yml  
需要配置secret,在项目主页菜单的settings/secrets and variables/Actions中配置  
需要定时执行的话配置schedule,修改cron表达式  

```yaml
on:
  schedule:
    - cron: "0 7 * * *" # 每天7点执行
```
