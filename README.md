# notion-backup

## notion 自动备份脚本

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
pip3 install requests shutil zipfile signal
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

默认上传到 github，如果使用，需要自己新建一个私有仓库，然后 notion-backup.py 提交至该新仓库，然后在该仓库目录下运行 notion-backup.py 即可，记得修改`.git`文件夹中的`config`文件，把用户名和密码配置到仓库地址 https://username:password@github.com/username/notion-backup.git 上，防止脚本自动 push 代码时，需要输入用户名密码

### 5. 执行脚本

```shell
python3 notion-backup.py
```

### 6. 导出其他格式

修改代码中`exportTask`方法中的`exportType`为要导出的类型

### 7. 注意事项

windows 路径最大长度 255 字符，notion 的文件夹、文件末尾都带了类似 md5 的东西，所以文件树过深时，windows 系统上解压会报错，目录树过深时请于 linux 系统使用

### 8. 使用效果

![image](https://user-images.githubusercontent.com/11244921/115993906-66866e00-a607-11eb-8d3b-21d935e1c56f.png)
![image](https://user-images.githubusercontent.com/11244921/115993882-54a4cb00-a607-11eb-9ef0-fdd952c62159.png)

### 9. 其他使用方法

搭配`Github`的`CI/DI`以及`Schedule`，可以实现全自动定时打包，上传，而且不需要在自己的服务器上执行。
