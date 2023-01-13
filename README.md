# notion-backup

## notion 自动备份脚本
## Automatic Notion workspace backup to git and local

基于`python3`，利用 notion 官方 api，自动导出所有工作空间内数据为 markdown 格式,虽然官方 API 导出的为 zip，但是脚本会解压，然后一起上传至 github，因为在 github，所以也拥有了版本历史功能。

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
python3 -v
pip3 -V
```

需要安装相关依赖包

```
pip3 install requests
```

### 使用方法:

### 1. 使用用户名密码方式:

设置系统环境变量  
`NOTION_EMAIL` 为账户  
`NOTION_PASSWORD `为密码  
或者直接修改变量为  
`NOTION_EMAIL='yourEmail@email.com'`  
`NOTION_PASSWORD='your Password'`

### 2. 使用 token 方式:

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
默认上传到 github，如果使用，需要自己新建一个私有仓库，然后 notion-backup.py 提交至该新仓库，然后在该仓库目录下运行 notion-backup.py 即可  
注：如果不用ci执行，在服务器本地执行的话  
记得修改`.git`文件夹中的`config`文件，把用户名和密码配置到仓库地址 https://username:password@github.com/username/notion-backup.git 上，防止脚本自动 push 代码时，需要输入用户名密码
或者手动先push一次，并且设置credentials

记得设置保存备份文件仓库的.gitignore为这样
```
*.zip
/backup/*.zip
log.txt
__pycache__
```
### 5. 备份配置
notion-backup.py顶部的`DEFAULT_BACKUP_CONFIG`变量
主要`block_id`是`-`分开的注意位数
{'spaces':[]} 则备份所有空间 'space_blocks':[] 则备份整个空间
```python 
# 1.备份所有空间
{'spaces': []}
# 2.备份指定空间所有block
{'spaces': [
        {'space_name': 'space_name', 'space_blocks': []}
    ]
}
# 2.1两种方式都可以
{'spaces': [
        {'space_name': 'space_name'}
    ]
}
# 3.备份指定空间指定block及block的子页面
{'spaces': [
        {'space_name': 'space_name', 'space_blocks': [
                {'block_id': '12345678-1234-1234-1234-123456789123', 'block_name': 'Home'}
            ]
        }
    ]
}
# 4.也可以修改config.json
config.json为上面备份配置的json格式数据,注意里面符号为#双引号#
```
### 6. 执行脚本

```shell
python3 notion-backup.py
```
```shell
config.json为上面备份配置的json格式数据,注意里面符号为#双引号#
python3 notion-backup.py -c /your_dir/config.json
```
```python
run_job.py是利用python的schedule定时执行的,有需要可以用
```
### 7. 导出其他格式

修改代码中`exportTask`方法中的`exportType`为要导出的类型
markdown/html/pdf

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

搭配`Github`的`CI/DI`以及`Schedule`，可以实现全自动定时打包，上传，而且不需要在自己的服务器上执行。  
参考文件.github/workflows/backup.yml  
需要配置secret,在项目主页菜单的settings/secrets and variables/Actions中配置  
需要定时执行的话配置schedule,修改cron表达式  
```yaml
on:
  schedule:
    - cron: "0 7 * * *" # 每天7点执行
```
