#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Time : 2020-05-09 15:31
# @Author : way

from bs4 import BeautifulSoup
from SP.spiders.SPRedisSpider import SPRedisSpider
from SP.items.zhifang_items import *
from SP.utils.make_jobs import ScheduledRequest, RedisCtrl
from SP.utils.make_key import md5
from SP.utils.make_log import log
from SP.utils.tool import get_file_type


class zhifang_Spider(SPRedisSpider):
    name = 'zhifang'
    redis_key = f'{name}:start_urls'
    allowed_domains = []
    custom_settings = {
        'LOG_LEVEL': "INFO",
        'LOG_FILE': log(name),
        # 'CONCURRENT_REQUESTS': 5,  # 控制并发数，默认16 
        # 'DOWNLOAD_DELAY': 3,  # 控制下载延迟，默认0
        'ITEM_PIPELINES': {
            'SP.pipelines.pipelines_file.FilePipeline': 100,
            'SP.pipelines.zhifang_pipelines.RdbmPipeline': 200,
            # 'SP.pipelines.zhifang_pipelines.HbasePipeline': 201
        },
        'DOWNLOADER_MIDDLEWARES': {
            'SP.middlewares.UserAgentMiddleWare.UserAgentMiddleWare': 100,
            # 'SP.middlewares.HeadersMiddleWare.MiddleWare': 101,    # 在meta中增加headers
            # 'SP.middlewares.CookiesMiddleWare.MiddleWare': 102,    # 在meta中增加cookies
            # 'SP.middlewares.PayloadMiddleWare.MiddleWare': 103,    # 在meta中增加payload
            # 'SP.middlewares.ProxyMiddleWare.ProxyMiddleWare': 104,  # 使用代理ip
            # 'SP.middlewares.RequestsMiddleWare.RequestMiddleWare': 105,  # 使用requests
            # 'scrapy_splash.SplashCookiesMiddleware': 723,     # 在meta中增加splash 需要启用3个中间件
            # 'scrapy_splash.SplashMiddleware': 725,          # 在meta中增加splash 需要启用3个中间件
            # 'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware': 810,    # 在meta中增加splash 需要启用3个中间件
            'SP.middlewares.SizeRetryMiddleware.MiddleWare': 900  # 重试中间件，允许设置 MINSIZE（int），response.body 长度小于该值时，自动触发重试
        },
    }

    def get_callback(self, callback):
        # url去重设置：True 不去重 False 去重
        callback_dt = {
            'list': (self.list_parse, True),
            'detail': (self.detail_parse, True),
        }
        return callback_dt.get(callback)

    def list_parse(self, response):
        rows = BeautifulSoup(response.text, 'lxml').find_all('div', class_="fangyuan_list-con")
        reqs = []
        for row in rows:
            detail_url = row.find('a').get('href')
            list_item = zhifang_list_Item()
            # save value for your item here like:
            # list_item['title'] = row.find('a').text
            list_item['tit'] = row.find('p', class_="tit").text
            list_item['txt'] = row.find('p', class_="txt").text
            list_item['tit2'] = row.find_all('p', class_="tit")[-1].text
            list_item['price'] = row.find('p', class_="price").text
            list_item['agent'] = row.find('p', class_="name").text
            # default column
            list_item['detail_full_url'] = response.urljoin(detail_url)
            list_item['pkey'] = md5(list_item['detail_full_url'])
            list_item['pagenum'] = response.meta.get('pagenum')
            yield list_item

            req = ScheduledRequest(
                url=list_item['detail_full_url'],
                method='GET',
                callback='detail',
                body={},  # 如果是POST，在这边填写post字典
                meta={
                    'fkey': list_item['pkey'],
                    'pagenum': list_item['pagenum'],
                    # 反爬相关的meta字典也填写这边，然后在spider中启用相应的中间件
                    # 'cookies': {},      # 一般反爬
                    # 'splash': {'wait': 2}  # js加载、异步加载渲染
                }
            )
            reqs.append(req)

        # 将详情链接作为新的任务 推到redis
        RedisCtrl().reqs_push(self.redis_key, reqs)

    def detail_parse(self, response):
        soup = BeautifulSoup(response.text, 'lxml')
        prs = soup.find('div', class_="price clearfix").find_all('li')
        describe = soup.find('dl', class_="describe")
        cols = describe.find_all('dd')

        detail_item = zhifang_detail_Item()
        # save value for your item here like:
        # detail_item['title'] = soup.find('h1').text
        detail_item['type1'] = prs[0].text
        detail_item['type2'] = prs[1].text
        detail_item['type3'] = prs[2].text
        detail_item['plot_name'] = cols[0].text
        detail_item['area'] = cols[1].text
        detail_item['look_time'] = cols[2].text
        detail_item['source_id'] = cols[3].text
        # default column
        detail_item['fkey'] = response.meta.get('fkey')
        detail_item['pagenum'] = response.meta.get('pagenum')
        yield detail_item

        imgs = soup.find('ul', class_="bigImg").find_all('li')
        for px, img in enumerate(imgs, 1):
            file_url = img.find('a').get('href')
            file_item = zhifang_file_Item()
            # save value for your item here like:
            # detail_item['title'] = soup.find('h1').text
            file_item['file_url'] = response.urljoin(file_url)
            file_item['file_name'] = f"{detail_item['plot_name']}/{px}"
            file_item['file_type'] = get_file_type(file_url, 'jpg')
            # default column
            file_item['fkey'] = response.meta.get('fkey')
            file_item['pagenum'] = response.meta.get('pagenum')
            yield file_item
