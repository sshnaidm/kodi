# -*- coding: utf-8 -*-
import exceptions
import urllib
import urlparse
import xbmc
import xbmcplugin
import sys
import os
import re
import requests
import threading
import functools
import xbmcaddon
import xbmcgui

import html5lib
import bs4
from bs4 import BeautifulSoup

cache_plugin_path = xbmc.translatePath(
    "special://home/addons/script.common.plugin.cache/")
storage_path = os.path.join(cache_plugin_path, "lib")
sys.path.append(storage_path)
try:
    from StorageServer import StorageServer
except:
    import lib.storageserverdummy as StorageServer

youtubeAddonUrl = ("plugin://plugin.video.youtube/"
                   "?path=/root/video&action=play_video&videoid=")

YTID = re.compile(r'//www.youtube.com/embed/([^"?\']+)')
PAGE = re.compile(".*/page/(\d+)")

MAIN_MENU = (("Видео", "allvideos"), ("Лекции", "alllectures"),
             ("Науки", "science"), ("Курсы", "allcourses"))

SCIENCES = {
    "biology": "Биология",
    "pravo": "Право",
    "language": "Язык",
    "physics": "Физика",
    "philosophy": "Философия",
    "astronomy": "Астрономия",
    "culture": "Культура",
    "istoriya": "История",
    "sociology": "Социология",
    "ekonomika": "Экономика",
    "medicine": "Медицина",
    "psihologiya": "Психология",
    "chemistry": "Химия",
    "technology": "Технологии",
    "math": "Математика",
}

SITE = "http://postnauka.ru/"

URLS = {
    "allvideos": SITE + "video",
    "allcourses": SITE + "courses",
    "alllectures": SITE + "lectures",
}

XBOX = xbmc.getCondVisibility("System.Platform.xbox")


def get_plugin_name(url):
    return urlparse.urlparse(url).netloc


class Plugin:
    url = sys.argv[0]
    handle = int(sys.argv[1])
    name = get_plugin_name(sys.argv[0])
    addon = xbmcaddon.Addon(id=name)
    path = addon.getAddonInfo('path').decode('utf-8')
    profile = xbmc.translatePath(addon.getAddonInfo('profile')).decode('utf-8')


class Cache:
    main_cache = StorageServer("main_cache",
                               int(Plugin.addon.getSetting("main_cache")))
    page_cache = StorageServer("page_cache",
                               int(Plugin.addon.getSetting("page_cache")))

CACHE = Cache.__dict__


def cached_with(cache_type, func, *args, **kwargs):
    # cache_function = globals()[cache_type]
    cache_function = CACHE[cache_type]
    return cache_function.cacheFunction(func, *args, **kwargs)


def dump(a, t):
    with open(xbmc.translatePath("special://home/temp/") + a, "w", ) as f:
        f.write(t)


def requests_debug():
    import logging

    # these two lines enable debugging at httplib level
    # (requests->urllib3->httplib)
    # you will see the REQUEST, including HEADERS and DATA, and RESPONSE with
    # HEADERS but without DATA.
    # the only thing missing will be the response.body which is not logged.
    import httplib
    httplib.HTTPConnection.debuglevel = 1

    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


class PostnaukaError(exceptions.BaseException):
    pass


class MultipleActions(PostnaukaError):
    pass


class WebError(PostnaukaError):
    pass


def encoded_dict(in_dict):
    out_dict = {}
    for k, v in in_dict.iteritems():
        if isinstance(v, unicode):
            v = v.encode('utf8')
        elif isinstance(v, str):
            # Must be encoded in UTF-8
            v.decode('utf8')
        out_dict[k] = v
    return out_dict


def build_url(url, query):
    return url + '?' + urllib.urlencode(encoded_dict(query))


def digitize(s):
    return "".join([i for i in s if i.isdigit()])


class Logger(Plugin):
    levels = {
        xbmc.LOGDEBUG: "DEBUG",
        xbmc.LOGINFO: "INFO",
        xbmc.LOGERROR: "ERROR",
    }

    def __init__(self):
        self.prefix = "{base}[{addon_handle}]: ".format(
            base=self.name,
            addon_handle=self.handle)
        self.debug_enabled = self.addon.getSetting("debug_enabled")
        if self.debug_enabled:
            requests_debug()

    def __unify(self, msg):
        if isinstance(msg, unicode):
            return msg.encode('utf-8')
        else:
            return msg

    def __print_log(self, msgs, level):
        msgs = [repr(self.__unify(m)) for m in msgs]
        level_prefix = self.levels[level]
        log_message = "{prefix} [{level_prefix}] {msgs}".format(
            prefix=self.prefix,
            level_prefix=level_prefix,
            msgs=repr(" ".join(msgs)))
        # xbmc.log(log_message, level=level)
        print log_message

    def debug(self, *msgs):
        if self.debug_enabled:
            self.__print_log(msgs, level=xbmc.LOGDEBUG)

    def info(self, *msgs):
        self.__print_log(msgs, level=xbmc.LOGINFO)

    def error(self, *msgs):
        self.__print_log(msgs, level=xbmc.LOGERROR)


class Web:
    def __init__(self):
        self.url = None
        self.log = Logger()

    def get_url(self, url):
        self.url = url
        self.log.debug("Connect to URL={url}".format(url=self.url))
        try:
            request = requests.get(self.url)
            content = request.content
        except requests.HTTPError:
            self.log.error("Can not connect to {0}".format(self.url))
            raise WebError("URL unreachable")
        if not content:
            self.log.error("Can not retrieve {0}".format(self.url))
            raise WebError("HTTP page is empty")
        self.log.debug("URL {url} was retrieved successfully!".format(
            url=self.url))
        text = request.text
        text = text.encode('utf-8')
        return text

    def get_page(self, url, page=None, cache_type=None):
        if page and page != 1:
            url += "/page/{number}".format(number=page)
        if cache_type:
            return cached_with(cache_type, self.get_url, url)
        else:
            return self.get_url(url)


class Parser:
    def __init__(self):
        self.log = Logger()
        self.parser = "html5lib"
        self.log.debug("BS4 version:" + bs4.__version__)

    def get_video_details_from(self, text):
        log = self.log
        soup = BeautifulSoup(text, self.parser)
        link = soup.find("meta", itemprop="url").get("content")
        video = {"url": link}
        log.debug("Video URL: {0}".format(video["url"]))
        iframe = soup.find("iframe").attrs["src"]
        log.debug("IFRAME: {0}".format(str(iframe)))
        if "//www.youtube.com/embed" in iframe:
            youtube_id_match = YTID.search(iframe)
        else:
            log.error("Not found youtube id in iframe:" + str(iframe))
            return None
        if not youtube_id_match:
            return None
        video["id"] = youtube_id_match.group(1)
        log.debug("Video Youtube ID: {0}".format(video["id"]))
        video["play"] = youtubeAddonUrl + video["id"]
        video["title"] = soup.find("meta", itemprop="name").get("content")
        video["img"] = soup.find("meta", itemprop="image").get("content")
        video["summary"] = soup.find("meta",
                                     itemprop="description").get("content")
        video["date"] = soup.find("div", class_="p-data").contents[0]
        video["category"] = soup.select('h3[class="p-cat"] > a')[0].text
        video["views"] = int(digitize(soup.findAll("div",
                                                   class_="p-comms")[1].text))
        video["tags"] = list(soup.find("div", id="p-tags").strings)
        return video

    def extract_video_links(self, text):
        links = []
        soup = BeautifulSoup(text, self.parser)
        lis = soup.select('div[id="project"] > li')
        for li in lis:
            link = li.find("a").attrs["href"]
            links.append(link)
        if links:
            self.log.debug("Succeeded to get video links from page")
        else:
            self.log.error("Failed to get video links from page!")
        return links

    def extract_video_links_science(self, text):
        soup = BeautifulSoup(text, self.parser)
        lis = soup.select('div[id="m"] > li a[title]')
        links = list(set([i["href"] for i in lis]))
        self.log.debug("Extracted {0} links from page".format(len(links)))
        links = [
            link
            for link in links
            if "/video/" in link or "/lecture/" in link or "/course/" in link
        ]
        return links

    def _get_next_and_total_pages(self, text):
        soup = BeautifulSoup(text, self.parser)
        total_pages = current_page = next_page = None
        current_page = int(digitize(soup.find("span", class_="current").text))
        next_page_tag = soup.find("a", class_="nextpostslink")
        if next_page_tag:
            url = next_page_tag["href"]
            next_page = int(digitize(PAGE.search(url).group(1)))
        else:
            next_page = None
            total_pages = current_page
        if not total_pages:
            last_tag = soup.find("a", class_="last")
            if not last_tag and next_page:
                larger = max([int(i.text)
                              for i in soup.findAll("a",
                                                    class_="page larger")])
                total_pages = max(next_page, larger)
            else:
                url = last_tag["href"]
                total_pages = int(digitize(PAGE.search(url).group(1)))
        self.log.debug("Current:{0}, Next:{1}, Total:{2}".format(
            current_page, next_page, total_pages))
        return current_page, next_page, total_pages

    def get_next_page_item(self, text):
        current_page, next_page, total = self._get_next_and_total_pages(text)
        if current_page != total:
            next_page_item = xbmcgui.ListItem(
                label="<Следующая [{next}] из [{total}]>".format(
                    next=next_page,
                    total=total))
            next_page_item.setProperty('IsPlayable', 'false')
            return next_page_item
        else:
            return None


def kodi(sort=None):
    log = Logger()
    log.debug("Building menu with sort {0}".format(repr(sort)))

    def deca(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):

            log.debug("Building decorator with sort {0}".format(repr(sort)))
            for item in func(*args, **kwargs):
                log.debug("Decorator Building item {0}".format(repr(item)))
                xbmcplugin.addDirectoryItem(Plugin.handle, *item)
            if sort:
                xbmcplugin.addSortMethod(Plugin.handle, sort)
            xbmcplugin.endOfDirectory(Plugin.handle)

        return wrapper

    return deca


class List:
    def __init__(self):
        self.log = Logger()
        self.web = Web()
        self.parser = Parser()
        self.log.debug("Version:" + sys.version)
        self.log.debug("Platform:" + sys.platform)

    @kodi()
    def main_menu(self):
        for folder, topic in MAIN_MENU:
            list_item = xbmcgui.ListItem(label=folder,
                                         iconImage='DefaultFolder.png')
            url_params = {"action": "list", "topic": topic}
            is_folder = True
            self.log.debug("Added list item: {0} :: {1} :: {2}".format(
                build_url(Plugin.url, url_params), list_item, is_folder))
            yield (build_url(Plugin.url, url_params), list_item, is_folder)
        # For testing purposes
        test_li = xbmcgui.ListItem('Test')
        test_url = build_url(Plugin.url, {"action": "test"})
        yield (test_url, test_li)
        # End of testing purposes

    @kodi(sort=xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    def list_sciences(self):
        # items = []
        for link, science in SCIENCES.iteritems():
            list_item = xbmcgui.ListItem(label=science,
                                         iconImage='DefaultFolder.png')
            url_params = {"action": "list", "topic": link}
            is_folder = True
            yield (build_url(Plugin.url, url_params), list_item, is_folder)
            # items.append(list_item)
            # kodi_build(items, sort=xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)

    def display_topic(self, topic, page):
        self.log.debug("Listing topic {topic} page {p}".format(topic=topic,
                                                               p=page))
        if topic == "science":
            self.list_sciences()
        else:
            self.list_videos(topic, page)



    def _build_video_item(self, video):
        list_item = xbmcgui.ListItem(label=video["title"],
                                     iconImage=video["img"],
                                     thumbnailImage=video["img"],
                                     #    path=video["play"]
                                     )
        list_item.setInfo('video', {
            'title': video['title'],
            'genre': video['category'],
            'playcount': video['views'],
            'plot': video['summary'],
            'tvshowtitle': video['title'],
        })
        list_item.setProperty('IsPlayable', 'true')
        url_params = {"action": "play", "video_id": video["id"]}
        return (build_url(Plugin.url, url_params), list_item)

    def _build_next_item(self, topic, page, item):
        return (build_url(Plugin.url, {
            "action": "list",
            "topic": topic,
            "page": page + 1
        }), item, True)

    @kodi()
    def list_videos(self, topic, page=1):
        def _get_video_details(link):
            video_web_page = self.web.get_page(link, cache_type="page_cache")
            response[link] = cached_with(
                "page_cache",
                self.parser.get_video_details_from,
                video_web_page)

        self.log.debug(
            "Getting URL for {topic} and page {page}".format(topic=topic,
                                                             page=page))
        text = self.web.get_page(URLS[topic], page, "main_cache")
        parse = self.parser.extract_video_links_science if (
            topic in SCIENCES) else self.parser.extract_video_links
        links = cached_with("main_cache", parse, text)

        response, pool = {}, []
        for link in links:
            pool.append(threading.Thread(
                target=_get_video_details,
                args=(link,)))
        for t in pool:
            t.start()
        for t in pool:
            t.join()
        for data in response.itervalues():
            yield self._build_video_item(data)

        next_item = self.parser.get_next_page_item(text)
        if next_item:
            yield self._build_next_item(topic, page, next_item)
