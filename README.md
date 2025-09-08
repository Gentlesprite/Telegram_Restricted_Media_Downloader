<p align="center">
  <img width="15%" align="center" src="https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/logo.png" alt="logo">
</p>
  <h1 align="center">
  Telegram_Restricted_Media_Downloader
</h1>
<p align="center">
</p>
<p align="center">
  A telegram downloader on windows and linux platform based on Python.
</p>
<p align="center">
  <a style="text-decoration:none">
    <img src="https://img.shields.io/badge/Python-3.13.2-blue.svg?color=00B16A" alt="Python 3.13.2"/>
  </a>
  <a style="text-decoration:none">
    <img src="https://img.shields.io/badge/pyrogram@kurigram-2.2.10-blue.svg?color=00B16A" alt="pyrogram@kurigram 2.2.10"/>
  </a>
  <a style="text-decoration:none">
    <img src="https://img.shields.io/badge/Platform-Windows & Linux%20-blue?color=00B16A" alt="Platform Windows & Linux"/>
  </a>
</p>

> [!NOTE]
> 由于本项目**没有提供**Linux环境下的二进制文件，但**支持**Linux环境运行。  
> 故Linux用户请**阅读**:[_"3.0.在生产环境中运行(对于Linux用户)"_](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader?tab=readme-ov-file#%E5%AF%B9%E4%BA%8Elinux%E7%94%A8%E6%88%B7)。  
> 如果你**遇到任何问题**，请先**阅读**:[_"常见问题及解决方案汇总"_](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/wiki)。  
> **没有找到解决方案**再进群或私聊提问。


作者:[Gentlesprite](https://github.com/Gentlesprite)

B站视频教程:[点击观看](https://www.bilibili.com/video/BV1nCp8evEwv)

Telegram交流群:[点击加入](https://t.me/+6KKA-buFaixmNTE1)

软件免费使用!并且在GitHub开源，如果你付费那就是被骗了。

# 1.0.下载地址:

蓝奏云:[点击跳转下载](https://wwgr.lanzn.com/b0fopovuf) 密码:ceze

Github:[点击跳转下载](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/releases)

## 1.1.(选看)推荐终端:

1. _对于Windows11用户_，`Windows Terminal`默认**已经安装好**，可**跳过**下载的步骤，直接前往第3步。(将`Windows Terminal`设为**默认终端**)

2. _对于Windows10用户_，推荐使用`Windows Terminal`作为**默认终端**，仅作为推荐安装，无论安装与否**不会影响本软件的使用**，`Windows Terminal`能提供更出色的显示、交互、体验效果，以及避免出现**文字显示**乱码。

   Windows Terminal 微软商店:[点击跳转下载](https://apps.microsoft.com/detail/9n0dx20hk701?launch=true&mode=full&hl=zh-cn&gl=cn&ocid=bingwebsearch)

   Windows Terminal Github:[点击跳转下载](https://github.com/microsoft/terminal/releases)

3. 下载完成完成后`win+r`输入`wt`回车打开，然后将`Windows Terminal`设为**默认终端**再启动软件，教程如下:

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/1_1_1.png)

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/1_1_2.png)

# 2.0.快速开始:

## 2.1.申请电报API:

1. 前往网站:**https://my.telegram.org/auth**

   

2. 填写**自己绑定**`Telegram`电报的**手机号**注意手机号格式先要+地区再写入电话号码例如`+12223334455`，`+1`为地区，`222333445`为你绑定`Telegram`的**手机号**，填写后点击`Next`。

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_1_1.png)

   

3. 打开你的`Telegram`客户端，此时会收到来自`Telegram`账号的消息，将上面的验证码填入`Confirmation code`框中，然后点击`Sign in`。

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_1_2.png)

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_1_3.png)

   

4. 点击`API development tools`按照提示填入即可。

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_1_4.png)

   

5. 申请成功会得到一个`api_hash`和`api_id`保存下载，**切记不要泄露给任何人！**

## 2.2.(选看)电报机器人(bot_token)申请及使用教程:
> [!NOTE]
> 如果配置了机器人，只要**保持软件运行**，就能实现**多端发送下载命令**并且**随时进行下载**。  
> 故可以将软件部署在服务器上，无论是Windows还是Linux平台。  
> Windows平台可直接使用[releases](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/releases)里发布的二进制文件放在服务器运行。  
> Linux平台的部署教程请**阅读**:[_"3.0.在生产环境中运行(对于Linux用户)"_](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader?tab=readme-ov-file#%E5%AF%B9%E4%BA%8Elinux%E7%94%A8%E6%88%B7)。

### 	2.2.1.申请教程:

1. 前往网站:https://t.me/BotFather 

2. 打开后会**提示**"要打开 Telegram Desktop 吗?"此时**点击**"打开Telegram Desktop"如下图所示：

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_1.png)

   如果没有这个弹窗，说明电脑没有安装**Telegram客户端**，安装后再重试即可。

3. **点击开始**，如下图所示：

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_2.png)

4. 然后在当前**聊天框**中输入`/newbot`后回车，如下图所示：

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_3.png)

   它会回复你`"Alright, a new bot. How are we going to call it? Please choose a name for your bot."`意思是给机器人取一个名字，如下图所示：

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_4.png)

5. 这个名字是显示名称 (display name)，并不是唯一识别码，随便设置一下即可，之后可以通过 `/setname`命令进行修改。

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_5.png)

6. 接着设置机器人的**唯一名称**。字符串必须 以`bot`结尾，比如 `HelloWorld_bot` 或 `HelloWorldbot` 都是合法的。如果设置的名字已经被占用需要重新设置。如设置成了 `trmd_bot`但是这个名字已经有人使用了，此时会提示`"Sorry, this username is already taken. Please try something different."`意思是已经被使用了，需要拟定一个**不重复**的，如下图所示：

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_6.png)

   如果结果如**上图**所示，则就代表名字**重复**了，需要**重新拟定**一个。

7. 直到提示你`"Done! Congratulations on your new bot. . ."`如下图所示：

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_7.png)

   如果结果如**上图**所示，则代表`bot_token`申请成功了，箭头指的红框处就是你所申请的`bot_token`，**切记不要泄露给任何人！**

### 	2.2.2.使用教程:

1. 申请完成后，在软件配置时询问"是否启用「机器人」(需要提供bot_token)? - 「y|n」(默认n)"选择`y`代表**需要**使用，如下图所示：

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_8.png)

   然后在**上图**箭头所指处填入"2.2.1.申请教程"第7步申请的`bot_token`后回车，即可配置完成。

2. 在一切配置完成，软件启动成功后等待提示"「机器人」启动成功。"，就代表机器人可以使用了，如下图所示：

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_9.png)

3. 在`Telegram`客户端中找到与`BotFather`的对话框，找到"2.2.1.申请教程"第7步对话的位置(或者用你自己的方式找到你的机器人的对话框)，如下图所示：

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_10.png)

   然后在**上图**箭头所指处即可**跳转**到机器人对话框。

4. **点击**开始，如下图所示：

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_11.png)

   不出意外，会收到一条来自**机器人**发送的消息，如下图所示：

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_12.png)

   **如果没收到**尝试尝试给机器人发送任意命令。

5. 目前机器人支持的命令用法及解释如下表所示：

   | 命令               | 用法                                                         | 解释                                                         |
   | ------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
   | `/help`            | 向机器人发送发送`/help`即可。                                | 展示**可用**命令。                                           |
   | `/download`        | `/download 链接1 链接2 链接3 链接n`或`/download 频道链接 1 100` | 分配**新的**下载任务，两种方式可选(**指定链接下载**和**范围下载**，具体使用方法请见下方说明)。 |
   | `/table`           | 向机器人发送`/table`即可。                                   | 在**终端**输出**当前**下载情况的**统计信息**。               |
   | `/forward`         | `/forward https://t.me/A https://t.me/B 1 100 `              | 将**频道A**的消息转发至**频道B**，其中`1`代表`起始ID`，`100`代表截止`ID`。 |
   | `/exit`            | 向机器人发送`/exit`即可。                                    | **退出**软件。                                               |
   | `/listen_download` | `/listen_download https://t.me/A https://t.me/B https://t.me/n` | **实时**监听**频道A**、**频道B**和**频道n**的**最新消息**(视频和图片)进行下载。 |
   | `/listen_forward`  | `/listen_forward https://t.me/A https://t.me/B`              | **实时**监听**频道A**的**最新消息**(任意消息)转发至**频道B**。但当**频道A**为**私密频道**时候无法转发。 |
   | `/listen_info`     | 向机器人发送`/listen_info`即可。                             | 查看当前已经创建的监听信息。                                 |
   | `/upload`          | `/upload` `本地文件` `目标频道`                              | 上传**本地的文件**到**指定频道**。                           |

6. `/help`命令使用教程，如下图所示：

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_13.png)

7. 点击**菜单**可以显示机器人可用的命令，如下图所示：

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_14.png)

8. `/download`命令使用教程，如下图所示：

   - 方式一：
     - ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_15.png)
     - 只要发送了正确的下载命令，终端就会创建对应的下载任务，如下图所示：
     - ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_16.png)

   - 方式二：

     - 该功能为版本`≥v1.5.1`的新增功能，用于对于**单一链接**的范围下载，并且该方式要求指定**频道链接**、**起始ID**与**结束ID**：

       ```bash
       # 语法格式如下：
       /download 频道链接 起始ID 结束ID
       # 举例：
       /download https://t.me/test 1 500
       # 代表下载https://t.me/test从消息ID=1到结束ID=500的媒体。
       ```

9. `/table`命令使用教程：

   需要**注意**的是，这个表格是**实时**的**状态**，并不是**最终**下载完成的**结果**，每一次使用它都会随着**当前**的**下载记录**而更新。

   **链接统计表**的使用，如下图所示:

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_17.png)

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_18.png)

   **注意**：由于早期代码设计缺陷，**链接统计表**为后续支持的功能：

   - **链接统计表**仅会统计**所有支持的类型**，**并不会只统计**用户**当前所选择**的类型。

   - **链接统计表**对于**评论区媒体**的统计，会出现**总数统计错误**的问题，体现在**总数**为`1`，**小于**当前的**下载数**，**完成率**`>>100%`的问题(该问题已在`≥v1.5.9`修复)。

   - 当用户**未选择**下载**所有支持的类型**时，在**用户所选择的类型**下载完成后(或使用机器人发送**链接统计表**)，尽管所有用户指定类型的文件已经下载完成，当**链接统计表**显示`完成率`不为`100%`时，代表该链接还存在其他用户未指定的文件类型，但实际用户所指定的类型已经下载完成了，是正常情况。
   
   - 版本`≥v1.6.5`起已支持**导出表格**功能，通过该命令可在运行时控制**是否**在退出后**导出指定类型的表格**。
   
   **计数统计表**的使用，如下图所示:
   
   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_19.png)
   
   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_20.png)
   
10. `/forward`命令使用教程：

> [!NOTE]
> 消息能否转发，在于频道是否开启了`限制保存内容`功能。  
> 如果**无法转发**，**机器人**会在**聊天框**提供一个**下载按钮**与**下载后上传按钮(`≥v1.6.7`)**。

```bash
# 语法格式如下：
/forward 频道A 频道B 起始ID 结束ID
# 举例：
/forward https://t.me/test https://t.me/test2 1 500
# 代表转发https://t.me/test频道中从消息ID=1到结束ID=500的消息到https://t.me/test2频道。
# 若需转发至个人的收藏夹，请使用`https://t.me/用户名`。(用户名就是个人账户信息里@后面那一串)
# 举例：
# 在个人信息中查看到用户名为@developer
# 此时使用/forward https://t.me/test https://t.me/developer 1 500
# 代表转发https://t.me/test频道中从消息ID=1到结束ID=500的消息到个人收藏夹。
```

11. `/exit`命令使用教程，如下图所示：

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_2_21.png)

12. `/listen_download`命令使用教程：

    `/listen_download`监听下载用于，实时监听该链接的最新消息进行下载。

    在用户发送了正确的监听命令后，会收到机器人的成功提示，当被监听的频道有可下载的内容时，就会自动发送命令下载。

    ```bash
    # 语法格式如下：
    /listen_download https://t.me/A https://t.me/B https://t.me/n
    # /listen_download命令后面跟多个以空格分割的频道链接。
    # 取消监听方法：
    # 再次发送与之前创建监听的命令一样的,即可得到机器人发送给用户的一个内联键盘,点击确认即可。
    # 如果之前已经创建过监听,已创建的监听就会提示重复并询问是否关闭。
    # 注意:由于电报对内联键盘回调数据位数的限制为64位,若回调数据超过64位,则无法通过内联键盘进行取消,只能重启软件。
    # 举例：
    # 例如取消https://t.me/A https://t.me/B 
    # 则再次发送:
    # /listen_download https://t.me/A https://t.me/B
    # 此时在机器人发送的两个内联键盘,分别选择确定即可取消。
    # 例如取消https://t.me/n
    # 则再次发送:
    # /listen_download https://t.me/n
    # 此时所有监听任务都被取消了。
    ```

13. `/listen_forward`命令使用教程：

> [!NOTE]
> 自版本`≥v1.6.7`起：  
> 当检测到"受限转发"时,自动采用"下载后上传"的方式(默认**开启**)。  
> 当**下载并完成上传**后，可选择**是否删除本地文件**(默认**关闭**)。  
> 并且可通过`[帮助页面]`->`[设置]`->`[上传设置]`进行修改(**重新注册或注销监听转发后生效**)。

`/listen_download`监听转发用于，实时监听该链接的最新消息进行下载。

与`/forward`命令一样，消息能否转发，在于频道是否开启了`限制保存内容`功能。

在用户发送了正确的监听命令后，会收到机器人的成功提示，当被监听的频道有**任何**新内容时，就会自动转发至用户所指定的频道。

```bash
# 语法格式如下：
/listen_forward https://t.me/A https://t.me/B
# https://t.me/A代表要监听的频道。
# https://t.me/B代表要转发到的频道。
/listen_forward 监听频道 转发频道
# /listen_forward命令必须填写监听频道与转发频道。
# 取消监听方法：
# 再次发送与之前创建监听的命令一样的,即可得到机器人发送给用户的一个内联键盘,点击确认即可。
# 如果之前已经创建过监听,已创建的监听就会提示重复并询问是否关闭。
# 注意:由于电报对内联键盘回调数据位数的限制为64位,若回调数据超过64位,则无法通过内联键盘进行取消,只能重启软件。
# 举例：
# 例如取消监听频道https://t.me/A转发到https://t.me/B频道的监听转发。
# 则再次发送:
# /listen_forward https://t.me/A https://t.me/B
# 此时在机器人发送的内联键盘,选择确定即可取消。
```

14. `/listen_info`命令使用教程：

    `/listen_info`用于查看**当前**已经创建的**监听信息**，**直接发送**即可。

    ```bash
    /listen_info
    ```

15. `/upload`命令使用教程：

    `/upload`用于上传本地的文件到指定频道。

    语法格式为：`/upload` `本地文件` `目标频道`

    ### 注意：

    `Telegram` 对上传的**单个文件**大小设有**明确限制**：

    - **普通用户**：**单个文件**最大上传大小为`2000 MiB`（约 2 GB）
    - **会员用户（Telegram Premium）**：**单个文件**最大上传大小为`4000 MiB`（约 4 GB）

    ### 对于Windows用户：

    ```bash
    /upload C:\files\video.mp4 https://t.me/test
    ```

    ### 对于Linux用户：

    ```
    /upload /home/username/files/video.mp4 https://t.me/test
    ```

   ### 监听行为说明：

   1. **频道独占原则:**
   - 每个频道**同一时间**只能激活一种监听模式（下载或转发）。
   - 对于`/listen_forward`命令，"同一频道"特指**被监听**的源频道。
   - 转发目标频道**不受此限制**，仍可通过`/listen_download`创建下载任务。
   2. **操作限制:**
   - 当`频道A`正在监听转发到`频道B`时:
     - 可以**同时**在`频道B`设置下载监听。
     - 但`频道B`的下载监听不会响应来自`频道A`的转发消息。
   3. **监听切换流程:**
   - 必须先通过**同一命令**(注册监听时的命令)来取消现有监听。
   - 然后才能创建**新的监听**事件。

## 2.3.配置文件说明:

## 用户配置文件

```yaml
# 这里只是介绍每个参数的含义,软件会详细地引导配置参数。
# 如果是按照软件的提示填,选看。如果是手动打开config.yaml修改配置,请仔细阅读下面内容。
# 手动填写时请注意冒号是英文冒号,冒号加一个空格。
api_hash: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx # 申请的api_hash。
api_id: 'xxxxxxxx' # 申请的api_id。
# bot_token(选填)如果不填,就不能使用机器人功能。可前往https://t.me/BotFather免费申请。
bot_token: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
download_type: # 需要下载的类型。支持的参数:video,photo,document。
- document
- video
- photo
is_shutdown: true # 下载完成后是否自动关机。支持的参数:true,false。
links: D:\path\where\your\link\files\save\content.txt # 链接地址写法如下:
# 新建txt文本,一个链接为一行,将路径填入即可请不要加引号,在软件运行前就准备好。
# D:\path\where\your\link\txt\save\content.txt 一个链接一行。
max_retries:
  download: 5 # 最大的下载任务的重试次数。
  upload: 3 # 最大的上传任务的重试次数。
max_tasks:
  download: 5 # 最大同时下载的任务数。
  upload: 3 # 最大同时上传的任务数。
proxy: # 代理部分,如不使用请全部填null注意冒号后面有空格,否则不生效导致报错。
  enable_proxy: true # 是否开启代理。支持的参数:true,false。
  hostname: 127.0.0.1 # 代理的ip地址。
  scheme: socks5 # 代理的类型。支持的参数:http,socks4,socks5。
  port: 10808 # 代理ip的端口。支持的参数:0~65535。
  username: null # 代理的账号,没有就填null。
  password: null # 代理的密码,没有就填null。
save_directory: F:\directory\media\where\you\save # 下载的媒体保存的目录(不支持网络路径)。
```

## 全局配置文件

```yaml
# 全局配置文件无需自行配置,这里只是介绍每个参数的含义。
# Windows存放路径:%APPDATA%/TRMD
# Linux存放路径:~/.config/TRMD
# 部分参数可以通过机器人设置修改。
console_log_level: WARNING # 在终端显示的最低日志类型。
export_table:
  count: false # 控制运行结束时是否导出下载计数统计表。
  link: false # 控制运行结束时是否导出下载链接统计表。
file_log_level: INFO # 在TRMD_LOG.log文件中记录的最低日志类型。
notice: false # 控制机器人启动时候是否发送启动通知。
upload:
  delete: false # 控制/listen_forward命令遇到受限内容时,下载上传完成后是否删除已上传完成的本地文件。
  download_upload: true # 控制/listen_forward命令遇到受限内容时,是否下载后上传到指定的转发频道。
```

## 2.4.**使用注意事项:**

1. 链接获取方法：对想要保存的媒体文件点击**鼠标右键**然后选择**复制消息直链**如下图所示：

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_4_1.png)

2. 目前支持**视频**和**图片**两种类型的下载。

3. 如果当前复制的**链接**为多张图片或视频，那么程序会**自动下载当前消息所有的内容**!

4. 要下载评论区里的视频或图片，请直接打开评论区，找到任意一个视频或图片，复制它的消息直链(链接末尾会带 `?comment=123456` 这样的参数，不要删除它)。这个链接可以用来下载评论区里的所有视频和图片。注意最好不要手动在链接后面添加 `?comment=` 参数，推荐通过复制的方式获取正确链接，否则可能会错误地解析成正文内容。

5. links的文本**写法1**如下图所示：

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_4_2.png)

6. 你所需要下载的视频前提是你当前的Telegram账号，在此视频链接的频道中，否则会报错无法下载！！！

7. 常见的**错误**写法(**请不要这样写**)：

   ![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_4_3.png)

   `Telegram`字段解释如下表所示：

   | 字段                                | 解释                                          |
   | ----------------------------------- | --------------------------------------------- |
   | `?comment`                          | **评论区**的链接。                            |
   | `?single`                           | **单独**的链接。                              |
   | `?single&comment`                   | **评论区**中**单独**的链接。                  |
   | `/c`                                | **私密**频道的链接。                          |
   | `https://t.me/TEST/111/666`         | 频道`TEST`**话题**`111`的链接。               |
   | `https://t.me/c/1111111111/333/666` | **私密**频道`1111111111`**话题**`333`的链接。 |
   
   ### 链接解释说明:
   
   `Telegram`链接组成如下表所示:
   
   | 频道类型     | 链接组成                                          |
   | ------------ | ------------------------------------------------- |
   | 正常频道     | `https://t.me/频道名/消息ID`                      |
   | 私密频道     | `https://t.me/c/频道名(10位纯数字)/消息ID`        |
   | 话题频道     | `https://t.me/频道名/话题ID/消息ID`               |
   | 私密话题频道 | `https://t.me/c/频道名(10位纯数字)/话题ID/消息ID` |
   
   `Telegram`链接所有链接格式如下表所示:
   
   "所有"指的是如果有**合并发送为一组**的文件，则给定一个链接，所有**合并发送的文件**会被全部下载。
   
   "媒体"指的是**视频**和**图片**。
   
   | 链接                                       | 实际频道名 | 消息ID | 解释                                           |
   |------------------------------------------| ------ |------|----------------------------------------------|
   | `https://t.me/TEST/111`                  | `TEST` | `111` | 下载该链接的**所有媒体**。                       |
   | `https://t.me/TEST/111?single`           | `TEST` | `111` | 下载该链接的**对应的一个媒体**。                       |
   | `https://t.me/TEST/111?comment=666`      | `TEST` | `111` | 下载该链接的**视频图片**的同时，下载该链接下方的**评论区**的**对应的一个媒体。** |
   | `https://t.me/TEST/111?single&comment=666` | `TEST` | `111` | 下载该链接下方的**评论区**的**对应的一个媒体。** |
   | `https://t.me/c/1111111111/666`          | `-1001111111111` | `666` | 下载该**私密频道**链接的**所有**媒体。 |
   | `https://t.me/TEST/111/666` | `TEST` | `666` | 下载该**话题**链接的**所有**媒体。 |
   | `https://t.me/c/1111111111/333/666` | `-1001111111111` | `666` | 下载该**私密话题**链接的所有媒体。 |
   
   ### 评论区链接的下载行为规则的说明:
   
   1. **标准链接（无 `?comment` 参数）:**
      - 仅下载**消息正文内容**（即频道/群组中直接发布的原始消息）。
      - **不包含评论区内容**，即使原消息存在评论，也不会被纳入下载任务。
   2. **带 `?comment` 参数的链接:**
      - 下载**消息正文 + 关联的全部评论区内容**（完整会话结构）。
      - 若原消息**无评论区**（如频道消息或评论功能关闭），则**仅下载消息正文内容**，与无参数版本行为一致。
   
   ### 重复链接问题说明:
   
   #### **问题描述**:
   
   在提交的下载任务中，存在多个**前缀相同但参数不同**的链接（如 `?comment`、`?single` 或 `?single&comment`）。由于这些链接的**频道名**和**消息ID**完全一致，实际上指向的是**同一资源**的不同表现形式。
   
   #### **问题原因**:
   
   - 当链接包含 `?comment` 参数时，会自动下载**原始消息及其评论区内容**。
   - 如果同时提交**相同前缀但无 `?comment` 的链接**，会导致**同一资源被重复添加**至下载队列。
   - 若前一次任务尚未完成，重复提交相同资源会触发**任务冲突**，进而引发下载异常。
   
   #### **解决方案:**
   
   - **仅需提交一个完整链接**（如带 `?comment` 的版本），系统会自动处理**原始内容及评论区**，无需额外提交无参数版本。
   - **避免重复提交相同资源**，确保每条链接的 `t.me/c/<频道>/<消息ID>` 部分唯一，防止任务冗余。
   
   非下载评论区的**推荐**写法如下表所示:
   
   | 频道类型     | 链接                              |
   | ------------ | --------------------------------- |
   | 正常频道     | https://t.me/xxx/111              |
   | 私密频道     | https://t.me/c/xxxxxxxxxx/111     |
   | 话题频道     | https://t.me/xxx/xxx/111          |
   | 私密话题频道 | https://t.me/c/xxxxxxxxxx/xxx/111 |
   
   ### 关于 `?single` 及 `?single&comment` 参数的下载行为说明（v1.5.8+）:
   
   #### **功能变更概述:**
   
   自  `≥v1.5.8`版本起，链接中包含 `?single` 或 `?single&comment` 参数时，系统将启用**单文件下载模式**。此模式专为以下场景设计与优化：
   
   - 解决`≥1.5.8`版本`/listen_download`当监听到合并发送的文件时，出现**重复下载问题**。
   - 用户需求，仅需从合并发送的多媒体组中提取**特定单一文件**。
   - 用户需求，仅需下载评论区中的**单个指定媒体**（避免评论区媒体过多时，迟迟下载不到想要的文件）。
   
   #### **参数行为详解:**
   
   |       参数格式       |                下载范围                |           应用场景            |
   | :------------------: | :------------------------------------: | :---------------------------: |
   |     `xx?single`      |  仅下载消息正文中的**xx对应媒体文件**  |  从合并图组/视频组提取单文件  |
   | `?single&comment=xx` | 仅下载评论区中的**xx所对应的媒体文件** | 获取评论区单独分享的图片/视频 |
   
   #### **版本兼容性说明:**
   
   - 此特性**仅对 v1.5.8 及以上版本**生效。
   - 历史版本中这些参数可能被忽略，导致完整内容下载。
   
   #### **最佳实践建议:**
   
   1. **单一文件提取:**
      当消息包含多个媒体文件时，使用标准链接附加 `?single` 参数可精准获取首个文件：
   
      ```
      https://t.me/c/123456789/123?single
      ```
   
   2. **评论区单文件获取:**
      需从评论区单独下载文件时，应采用复合参数格式：
   
      ```
      https://t.me/c/123456789/123?single&comment=xx
      ```
   
   3. **参数互斥原则:**
   
      - 避免同时提交同一消息的完整版和单文件版链接。
      - 单文件模式与评论区下载模式（`?comment`）不可混用。
## 2.5.**软件更新教程**:

![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/2_5_1.png)

# 3.0.在生产环境中运行:

_**推荐**使用`Python==3.13.2`作为该项目环境。(避免在其他`Python`版本运行时报错)_

## 对于Windows用户:

_需自行安装`python`与`git`并配置**环境变量**。_

```shell
git clone https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader.git
cd Telegram_Restricted_Media_Downloader
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```
## 对于Linux用户:

_克隆本项目并**进入项目目录**。_

```bash
git clone https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader.git
cd Telegram_Restricted_Media_Downloader
```
_**更新**`pip`版本(推荐)。_

```bash
python3 -m pip install --upgrade pip
```

_创建并使用**虚拟环境**(可选)。_

```bash
python3 -m venv venv
source venv/bin/activate
```

_安装程序运行**所需依赖**并等待全部安装完成。_

```bash
pip3 install -r requirements.txt
```

_运行程序(到这一步就安装完成并运行了，后面是注意事项)。_

```bash
python3 main.py
```

### 注意事项：

**_如果选择创建虚拟环境运行,在下次运行时也需要先激活虚拟环境。_**

在项目目录下，**激活虚拟环境**后再运行程序。

```bash
source venv/bin/activate
python3 main.py
```

_如果提示**没有安装pip**使用如下命令进行安装：_

```bash
sudo apt update
sudo apt-get install python3-pip
```

## 关于更新:

_在**项目目录**下打开终端使用如下命令拉取仓库当前的**最新版本**_：

```shell
git pull
```

_由于新版本可能使用了**新的依赖**，使用`git pull`拉取后，最好更新一下依赖(如果是**虚拟环境**请先激活再执行)。_

```shell
pip3 install -r requirements.txt
```

# 4.0.联系作者:

  Telegram:[@Gentlesprite](https://t.me/Gentlesprite)

  邮箱:Gentlesprites@outlook.com

# 5.0.支持作者:

![image](https://github.com/Gentlesprite/Telegram_Restricted_Media_Downloader/blob/main/res/pay.png)
