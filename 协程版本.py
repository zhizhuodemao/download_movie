# 前言 我们需要完成这么一个需求 用户输入电影或者电视剧名称
# 我们就能自动下载该电影或者电视剧 当然电视剧的话可以选择下载第几集 也可以选择下载全部集数
# 当然 这个下载就是爬取别人网站上的资源 我们选择的网站是一个盗版视频网站 https://olevod.me/
# 该网站的资源也是盗链得来 因此我们的爬取并不违法违规
# 该项目仅用于自己练习使用 如有传播造成损失 本人概不负责

# 该计划分以下几部分进行
# 1.搜索用户输入的电影名称 找到返回的所有结果展示给用户 用户选择某个结果就下载哪个电影
# 2.请求该电影链接 拿到该电影的第一个m3u8文件 m3u8文件中包含下一个m3u8文件的地址
# 3.访问第二个m3u8文件地址,拿到返回的电影的ts文件名称及顺序以及密钥
# 4.用协程请求所有的ts文件 并保存到待解密文件夹内
# 5.用协程解密所有的ts文件
# 6.合并最终的mp4文件
# 注意:如果用户输入的是电视剧名称 并且选择多集 为了避免服务器崩溃 那么我们选择一集一集的下载
# 注意:如用携程下载ts文件时 需注意控制并发量 以及设置请求过期时间
import asyncio

import requests
from lxml import etree
import os
import time
import re
import aiohttp
import aiofiles
from Crypto.Cipher import AES
import shutil

first_url = "https://olevod.me"
headers = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36 Edg/111.0.1661.62"
}


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        pass
    try:
        import unicodedata
        unicodedata.numeric(s)
        return True
    except (TypeError, ValueError):
        pass
    return False


def remove_file():
    if os.path.exists("./encrypted"):
        os.chdir("./encrypted")
        s_list = os.listdir()
        if len(s_list):
            for s in s_list:
                os.remove(s)
    if os.path.exists("../encrypted"):
        os.chdir("../encrypted")
        s_list = os.listdir()
        if len(s_list):
            for s in s_list:
                os.remove(s)
    os.chdir("../decrypted")
    s_list = os.listdir()
    if len(s_list):
        for s in s_list:
            os.remove(s)
    os.chdir("../merge")
    s_list = os.listdir()
    if len(s_list):
        for s in s_list:
            os.remove(s)
    os.chdir("../line")
    s_list = os.listdir()
    for s in s_list:
        os.remove(s)


def send_get_and_create_etree(url, headers=None, params=None):
    """
    构造一个简单的发送请求并封装为xpath需要格式的方法

    :param url: 需要传参
    :param headers: 默认为None 需要时传参
    :param params: 默认为None 需要时传参
    :return:etree封装过的页面
    """
    try:
        resp = requests.get(url, headers=headers, params=params)
        resp.encoding = "utf-8"
        page = etree.HTML(resp.text)
        return page
    except Exception as e:
        print("出错了,错误信息为:", e)
        return None


def search_video(video_name):
    search_url = "https://olevod.me/search.html"
    params = {
        "wd": video_name,
        "submit": ""
    }
    search_result_page = send_get_and_create_etree(search_url, headers=headers, params=params)
    if search_result_page is not None:
        lis = search_result_page.xpath('//ul[@class="vodlist clearfix"]/li')
        video_info_list = []
        for num, li in enumerate(lis):
            href = first_url + "".join(li.xpath("./div[1]/a/@href")).strip().replace(" ", "")
            category = "".join(li.xpath('./div[2]/h4/span/text()')).strip().replace(" ", "")
            name = "".join(li.xpath('./div[2]/h4/a/text()')).strip().replace(" ", "")
            main_actor = "主演:" + "".join(li.xpath('./div[2]/p[1]/text()')).strip().replace(" ", "")
            director = "导演:" + "".join(li.xpath('./div[2]/p[2]/text()')).strip().replace(" ", "")
            introduction = "简介:" + "".join(li.xpath('./div[2]/p[3]/text()')).strip().replace(" ", "")
            video_info = {"num": num,
                          "href": href,
                          "category": category,
                          "name": name,
                          "main_actor": main_actor,
                          "director": director,
                          "introduction": introduction}
            video_info_list.append(video_info)
        print(f"共搜索到{len(video_info_list)}个结果,信息展示如下:")
        for video_info in video_info_list:
            print(video_info)
        select_num = int(input("请输入num编号,选择将要下载的电影或电视剧:").strip())
        while 1:
            if 0 <= select_num < len(video_info_list):
                select_video = video_info_list[select_num]
                break
            else:
                select_num = int(input("输入的序号有误,请重新输入:").strip())
        return select_video
    else:
        print("搜索出现错误,请查看错误信息并重新启动应用程序")
        return None


def get_video_page_info_list(select_video):
    if select_video is not None:
        video_page = send_get_and_create_etree(select_video["href"], headers)
        video_lis = video_page.xpath('//*[@id="bofy"]/div[2]/div[2]/div[2]/ul/li')
        video_num = len(video_lis)
        all_episode_info = []
        for each_video_num, video_li in enumerate(video_lis):
            each_video_url = "".join(video_li.xpath("./a/@href")).strip().replace(" ", "")
            each_video_name = "".join(video_li.xpath("./a/text()")).strip().replace(" ", "")
            episode_info = {
                "each_video_num": video_num - each_video_num,
                "each_video_url": each_video_url,
                "each_video_name": each_video_name
            }
            all_episode_info.append(episode_info)
        print(f"该视频共有{video_num}集,每集信息展示如下")
        for episode_info in all_episode_info:
            print(episode_info)
        select_episode_str = str(input("请选择要下载的集数,请输入each_video_num的值.超出范围视为无效输入\n"
                                       "如需下载多集,请用空格分开,请不要重复输入,重复输入视为只输入一次:"))
        select_episode_str_num = select_episode_str.strip().split(" ")
        select_episode_set_num = set()
        select_episode_list_num = []
        video_page_info_list = []
        # 去重操作
        for str_num in select_episode_str_num:
            if 1 <= int(str_num) <= video_num:
                if int(str_num) in select_episode_set_num:
                    continue
                select_episode_list_num.append(int(str_num))
                select_episode_set_num.add(int(str_num))
            else:
                print(f"{int(str_num)}为无效输入")
        for num in select_episode_list_num:
            video_page_info_list.append(all_episode_info[video_num - num])
        return video_page_info_list
    else:
        return None


def save_m3u8_url(video_url, m3u8_url_path, video_page):
    if not os.path.exists("./line"):
        os.makedirs("./line")
    if "#" in video_page["each_video_url"]:
        m3u8_url = "https://olevod.me/my_p/" + video_url.strip().split(".")[1].split("/")[2]
        page = send_get_and_create_etree(m3u8_url)
        divs = page.xpath(f"//div/text()")
        div_name_list = []
        div_num = 0
        for i, div in enumerate(divs):
            div = div.strip().replace(" ", "").replace("↓", "")
            div_name_list.append(div)
            if div == f"{video_page['each_video_name']}":
                div_num = i
        uls = page.xpath("//ul")
        lines = uls[div_num].xpath("./li/a/@value")
        address = uls[div_num].xpath("./li/a/text()")
    else:
        m3u8_url = "https://olevod.me/my_p/" + "/".join(video_url.strip().split(".")[1].split("/")[-2:])
        # print(f"开始请求{m3u8_url}获得first-m3u8地址")
        page = send_get_and_create_etree(m3u8_url)
        lines = page.xpath("//li/a/@value")
        address = page.xpath("//li/a/text()")
    other_m3u8_list = []
    with open(m3u8_url_path, "w", encoding="utf-8") as f:
        for num, line in enumerate(lines):
            for i in range(5):
                try:
                    second_m3u8_url = requests.get(line).text
                    if "#EXT-X-STREAM-INF" in second_m3u8_url:
                        # print(f"把{address[num]}的m3u8的地址写入到文件{m3u8_url_path}中")
                        f.write(address[num] + "\n")
                        if not second_m3u8_url.endswith("\n"):
                            f.write(second_m3u8_url + "\n")
                        else:
                            f.write(second_m3u8_url)
                        f.write(line + "\n")
                    else:
                        if not is_number(address[num]):
                            address[num] = "线路" + str(num + 1)
                        f.write("final-line" + address[num] + "final-line\n")
                        f.write("final-url" + line + "final-url\n")
                        # print(f"{address[num]}地址为最终的m3u8地址,故直接保存m3u8文件为{address[num]}.txt")
                        m3u8_dict = {"address": address[num],
                                     "m3u8-text": second_m3u8_url}
                        other_m3u8_list.append(m3u8_dict)
                    # print("写入成功")
                    break
                except Exception as e:
                    print(f"{address[num]}出错了,即将开始第{i + 1}次重试")
                    print(f"错误信息为{e}")
                    time.sleep(1)
    for other_m3u8 in other_m3u8_list:
        file_name = "./line/" + other_m3u8["address"] + ".txt"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(other_m3u8["m3u8-text"])


def save_m3u8_resp(m3u8_url_path):
    first_m3u8_url_list = []
    second_m3u8_url_list = []
    with open(m3u8_url_path, "r", encoding="utf-8") as f:
        second_read_lines = f.readlines()
    for second_read_line in second_read_lines:
        new_line = second_read_line.strip().replace(" ", "").replace("\n", "")
        if new_line.endswith(".m3u8") or new_line.__contains__("index.m3u8?"):
            if new_line.startswith("https:"):
                first_m3u8_url_list.append(second_read_line.strip())
            else:
                second_m3u8_url_list.append(second_read_line.strip())
    new_second_m3u8_url_list = []
    for i in range(len(first_m3u8_url_list)):
        front = "/".join(first_m3u8_url_list[i].split("/")[:3])

        back = second_m3u8_url_list[i]
        if not back.startswith("/"):
            back = "/" + back
        new_second_m3u8_url = front + back
        new_second_m3u8_url_list.append(new_second_m3u8_url)
    for i, new_second_m3u8_url in enumerate(new_second_m3u8_url_list):
        for j in range(5):
            try:
                resp = requests.get(new_second_m3u8_url, headers=headers)
                resp.encoding = "utf-8"
                if os.path.exists(f"./line/线路{i + 1}.txt"):
                    i = i + 1
                with open(f"./line/线路{i + 1}.txt", "w") as f:
                    f.write(resp.text)
                # print(f"线路{i + 1}.txt保存成功")
                break
            except Exception as e:
                print(f"线路{i + 1}出错了!错误信息为{e}")
                print(f"即将进行第{j + 1}次重试")
    # print(f"共{len(new_second_m3u8_url_list)}条可用线路,将自动选择线路一作为下载线路,同时保存其他线路的ts文件")


async def download_one_ts(ts_link, path, sem):
    ts_name = ts_link.split("/")[-1]
    ts_path = path + "/" + ts_name
    # 设置超时时间
    timeout = aiohttp.ClientTimeout(total=20)
    # 设置最大连接数
    # conn = aiohttp.TCPConnector(limit=1)
    if not os.path.exists(path):
        os.makedirs(path)
    if os.path.exists(ts_path):
        # print(f"{ts_path}已经存在,即将进入下一个文件下载")
        return
    else:
        async with sem:
            for i in range(10):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(ts_link, timeout=timeout) as resp:
                            content = await resp.content.read()
                            async with aiofiles.open(ts_path, "wb") as f:
                                await f.write(content)
                    # print(f"文件{ts_path}下载成功")
                    break
                except Exception as e:
                    # print("出错了,错误信息为", e)
                    print(f"文件{ts_link}下载失败,即将开始第{i + 1}次重新下载")
                    await asyncio.sleep(1)


async def download_all_ts(video_page, sem):
    dir_nums = os.listdir("./line")
    num = 0
    line_num_list = []
    select_line_num = 1
    for dir_num in dir_nums:
        if dir_num.startswith("线路") and dir_num.endswith(".txt"):
            line_num_list.append(int(dir_num[2]))
            num = num + 1
    for i in range(num):
        with open(f"./line/线路{line_num_list[i]}.txt", "r") as f:
            if f.readline().strip().startswith("#EXTM3U"):
                select_lines = f.readlines()
                print(f"线路{line_num_list[i]}读取完毕")
                select_line_num = line_num_list[i]
                break
            else:
                print(f"线路{i + 1}不可用,即将切换下一个线路")
                continue
    with open("m3u8-url-list.txt", "r", encoding="utf-8") as f:
        first_m3u8s = f.readlines()
    first_m3u8_list = []
    first_m3u8_dict = {}
    for first_m3u8 in first_m3u8s:
        if first_m3u8.strip().startswith("final-urlhttps"):
            url = first_m3u8.strip().replace("final-url", "")
            first_m3u8_dict.update({"url": url})
        if first_m3u8.strip().startswith("final-line线路"):
            name = first_m3u8.strip().replace("final-line", "")
            first_m3u8_dict.update({"name": name})
        if first_m3u8.strip().startswith("线路"):
            name = first_m3u8.strip()
            first_m3u8_dict.update({"name": name})
        if first_m3u8.strip().startswith("https"):
            url = first_m3u8.strip()
            first_m3u8_dict.update({"url": url})
        if len(first_m3u8_dict.keys()) == 2:
            first_m3u8_list.append(first_m3u8_dict)
            first_m3u8_dict = {}

    with open(f"./line/线路{str(select_line_num)}.txt", "r") as f:
        first_line = f.readline()
        if not first_line.strip().startswith("#EXTM3U"):
            print("所有线路均不可用,即将返回...")
            return None, None
        all_lines = f.readlines()
    print(f"最终选择线路{select_line_num}进行下载")
    if "html#" in video_page["each_video_url"]:
        front = first_m3u8_list[select_line_num - 1]["url"].split("index.m3u8")[0][:-1]
    else:
        # https://olevod.me/vod-play/20188416/v.html
        front = "/".join(first_m3u8_list[select_line_num - 1]["url"].split("/")[:3])
    encrypted_ts_list = []
    decrypted_ts_list = []
    for line in all_lines:
        if "#EXT-X-KEY" in line.strip():
            key = re.search('URI="(?P<key>.*?)"', line.strip()).group("key")
            if key.startswith("/"):
                encrypted_ts_list.append(front + key)
            else:
                encrypted_ts_list.append(front + "/" + key)
        if line.strip().startswith("#"):
            continue
        else:
            if line.strip().startswith("https:"):
                encrypt_ts = line.strip()
            else:
                if line.strip().startswith("/"):
                    encrypt_ts = front + line.strip()
                else:
                    encrypt_ts = front + "/" + line.strip()
            encrypted_ts_list.append(encrypt_ts)
    if not encrypted_ts_list[0].endswith("key"):
        decrypted_ts_list = encrypted_ts_list
    download_tasks = []
    if len(decrypted_ts_list):
        while 1:
            need_download_num = len(decrypted_ts_list)
            print(f"共需要下载{need_download_num}个文件")
            for i in range(len(encrypted_ts_list)):
                download_tasks.append(asyncio.create_task(download_one_ts(encrypted_ts_list[i], "./decrypted", sem)))
            await asyncio.wait(download_tasks)
            num = os.listdir("./decrypted")
            print(f"下载了{len(num)}个文件")
            await asyncio.sleep(1)
            if need_download_num - len(num) == 0:
                print("下载全部完成,即将开始合并全部ts文件")
                break
        return decrypted_ts_list, 0
    else:
        while 1:
            need_download_num = len(encrypted_ts_list)
            print(f"共需要下载{need_download_num}个文件")
            for i in range(len(encrypted_ts_list)):
                download_tasks.append(asyncio.create_task(download_one_ts(encrypted_ts_list[i], "./encrypted", sem)))
            await asyncio.wait(download_tasks)
            num = os.listdir("./encrypted")
            print(f"下载了{len(num)}个文件")
            await asyncio.sleep(1)
            if need_download_num - len(num) == 0:
                print("下载全部完成,即将开始解密全部ts文件")
                break
        return encrypted_ts_list, 1


async def decrypt_one_ts(ts_name, decoder):
    if os.path.exists(f"./decrypted/{ts_name}"):
        # print(ts_name, "已经存在,进行下一个文件解密")
        return
    else:
        async with aiofiles.open(f"./encrypted/{ts_name}", "rb") as f1, aiofiles.open(f"./decrypted/{ts_name}",
                                                                                      "wb") as f2:
            encrypted_ts = await f1.read()
            decrypted_ts = decoder.decrypt(encrypted_ts)
            await f2.write(decrypted_ts)


async def decrypt_all_ts(ts_list):
    ts_name_list = []
    for ts in ts_list:
        ts_name = str(ts).split("/")[-1]
        ts_name_list.append(ts_name)
    tasks = []
    with open(f"./encrypted/{ts_name_list[0]}", "rb") as f:
        key = f.read()
    decoder = AES.new(key=key, IV=b"0000000000000000", mode=AES.MODE_CBC)
    if not os.path.exists("./decrypted"):
        os.makedirs("./decrypted")
    for i, ts_name in enumerate(ts_name_list):
        if i == 0:
            continue
        tasks.append(asyncio.create_task(decrypt_one_ts(ts_name, decoder)))
    await asyncio.wait(tasks)
    print("解密完成,开始合并所有ts文件")


def merge_ts(ts_list, merge_name):
    ts_name_list = []
    for ts in ts_list:
        ts_name = str(ts).split("/")[-1]
        ts_name_list.append(ts_name)
    ts_name_list = ts_name_list[1:]

    if not os.path.exists("./merge"):
        os.mkdir("./merge")
    if not os.path.exists("./movie"):
        os.mkdir("./movie")
    # 第一次合并到merge中
    os.chdir("./decrypted")
    n = 1
    s_dir = "\\".join(os.getcwd().split("\\")[:-1])
    temp = []
    for i in range(len(ts_name_list)):
        temp.append(ts_name_list[i])
        if i != 0 and (i + 1) % 30 == 0:
            temp_str = "+".join(temp)
            command = f'copy /b {temp_str} {s_dir}\\merge\\{n}.ts'
            os.system(command)
            temp = []
            n = n + 1
    temp_str = "+".join(temp)
    command = f'copy /b {temp_str} {s_dir}\\merge\\{n}.ts'
    os.system(command)
    # 第二次合并到movie中
    os.chdir("../merge")
    s_dir = "\\".join(os.getcwd().split("\\")[:-1])
    second_merge = []
    for i in range(1, n + 1):
        second_merge.append(f"{str(i)}.ts")
    second_merge_str = "+".join(second_merge)
    command = f'copy /b {second_merge_str} {s_dir}\\movie\\{merge_name}.mp4'
    os.system(command)
    # 合并完成 切换到项目目录
    os.chdir("../")
    print("合并完成")


def main():
    """
    我们选择从main函数开始整个项目
    :return:
    """
    try:
        video_name = str(input("请输入电影或电视剧名称:"))
        sem = asyncio.Semaphore(100)

        # 搜索视频并返回视频主页链接
        select_video = search_video(video_name.strip())
        if select_video is not None:
            # 判断视频类型 并返回下载链接
            video_page_info_list = get_video_page_info_list(select_video)
            if video_page_info_list:
                for video_page in video_page_info_list:
                    print(f"即将开始下载{select_video['name']}{select_video['category']}{video_page['each_video_name']}")
                    merge_name = f"{select_video['name']}{select_video['category']}{video_page['each_video_name']}"
                    each_video_url = first_url + video_page['each_video_url']
                    print(each_video_url, "开始下载....")
                    # 下面我们要访问"https://olevod.me/my_p/20232243/ep33"地址拿到m3u8链接
                    m3u8_url_path = "m3u8-url-list.txt"
                    save_m3u8_url(each_video_url, m3u8_url_path, video_page)
                    save_m3u8_resp(m3u8_url_path)
                    ts_list, result = asyncio.run(download_all_ts(video_page, sem))
                    if result is not None:
                        if result:
                            # 解密ts文件
                            asyncio.run(decrypt_all_ts(ts_list))
                            # 合并ts文件
                            merge_ts(ts_list, merge_name)
                        else:
                            # 合并ts文件
                            merge_ts(ts_list, merge_name)
                    remove_file()
            else:
                return None
        else:
            return None
    except Exception as e:
        print("出错了,错误信息为", e)
    finally:
        remove_file()


if __name__ == '__main__':
    main()
