# -*- coding: utf-8 -*-
import sys
import re
import urlparse
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import functools
from lib.postnaukalib import (
        Logger,
        MultipleActions,
        get_plugin_name,
        build_url,
        Web,
        Parser,
        StorageServer,
        Base,
        MAIN_MENU,
        SCIENCES,
        XBOX,
        YTID,
        SITE,
        URLS
    )


base_url = sys.argv[0]
addon_handle = int(sys.argv[1])
args = urlparse.parse_qs(sys.argv[2][1:])

plugin_name = get_plugin_name(base_url)
addon = xbmcaddon.Addon(id=plugin_name)

base_info = (plugin_name, addon_handle, addon)
Base.info = base_info

addon_path = addon.getAddonInfo('path').decode('utf-8')
addon_profile = xbmc.translatePath(
    addon.getAddonInfo('profile')).decode('utf-8')


sci_urls_dict = dict((sci, SITE + "themes/" + sci) for sci in SCIENCES)
URLS.update(sci_urls_dict)

youtubeAddonUrl = ("plugin://plugin.video.youtube/"
                   "?path=/root/video&action=play_video&videoid=")

xbmcplugin.setContent(addon_handle, 'movies')
parser = Parser()
log = Logger()
log.debug("Base URL: {}".format(base_url))
log.debug("Args: {}".format(args))

main_cache = StorageServer("main_cache", int(addon.getSetting("main_cache")))
page_cache = StorageServer("page_cache", int(addon.getSetting("page_cache")))


def cached(cache_type):
    def deca(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            log.debug("Caching decorator with type {}".format(cache_type))
            if addon.getSetting(cache_type):
                cache_function = globals()[cache_type]
                log.debug("Choosing cache function {}".format(
                    cache_function))
                return cache_function.cacheFunction(func, *args, **kwargs)
            else:
                return func(*args, **kwargs)
        return wrapper
    return deca


def cache_with(cache_type, func, *args, **kwargs):
    cache_function = globals()[cache_type]
    return cache_function.cacheFunction(func, *args, **kwargs)


def get_url(url, cache_type="page_cache"):
    log.debug("Retrieving {url}".format(url=url))
    web = Web()
    if cache_type:
        cache_function = globals()[cache_type]
        return cache_function.cacheFunction(web.get_url, url)
    else:
        return web.get_url(url)


def get_page(url, subject, page):
    log.debug("Get URL for {subject} page {page}".format(
        subject=subject,
        page=page))
    cache_type = "main_cache" if "all" in subject else "page_cache"
    if page and page != 1:
        url += "/page/{number}".format(number=page)
    return get_url(url, cache_type=cache_type)


def get_videos_from_page(topic, text):
    log.debug("Getting all video links from page for {}".format(topic))
    if topic not in SCIENCES:
        links = cache_with(
                "main_cache",
                parser.extract_video_links,
                text)
    else:
        # links = cache_with(
        #         "main_cache",
        #         parser.extract_video_links_science,
        #         text)
        links = parser.extract_video_links_science(text)
    if not links:
        log.error("Failed to get video links from page for {}!".format(topic))
        return
    else:
        log.debug("Got {} video links from page".format(len(links)))
    for link in links:
        video_web_page = get_url(link, cache_type="page_cache")
        video_details = cache_with(
            "page_cache",
            parser.get_video_details_from,
            video_web_page)
        if video_details:
            log.debug("Got video details for", link)
            yield video_details
        else:
            log.error("Failed to get video details for", link)


def build_xbmc_items(topic, items):
    log.debug("Starting building items for menu")
    for number, video in enumerate(items):
        log.debug(
            "{num} from {items} Building Kodi ListItem for video {url}".format(
                num=number+1,
                items=repr(items),
                url=video["url"]))
        list_item = xbmcgui.ListItem(
            label=video["title"],
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
        log.debug("Added list item: {} :: {}".format(
                 build_url(base_url, url_params), list_item))
        yield (addon_handle, build_url(base_url, url_params), list_item)


def get_next_page(text):
    current_page, next_page, total = parser.get_next_and_total_pages(text)
    if current_page != total:
        next_page_item = xbmcgui.ListItem(
                label="<Следующая [{next}] из [{total}]>".format(
                    next=next_page,
                    total=total))
        next_page_item.setProperty('IsPlayable', 'false')
        return next_page_item
    else:
        return None


def list_videos(topic, page=1):
    log.debug("Getting URL for {topic} and page {page}".format(
        topic=topic, page=page))
    http = get_page(URLS[topic], topic, page)
    if not http:
        log.error("Failed to get HTTP page for ", topic)
        return
    log.debug("Getting Items for {topic}".format(topic=topic))
    items = get_videos_from_page(topic, http)
    if not items:
        log.error("Failed to create items for", topic)
        return
    log.debug("Building Menu list for {topic} from {items} items".format(
        topic=topic,
        items=repr(items)))
    list_items = build_xbmc_items(topic, items)
    next_page_item = get_next_page(http)
    next_page_url = build_url(
        base_url, {"action": "list", "topic": topic, "page": page + 1})
    if list_items:
        log.debug("Built Menu for {topic}".format(topic=topic))

        for item in list_items:
            xbmcplugin.addDirectoryItem(*item)
        if next_page_item:
            xbmcplugin.addDirectoryItem(
                addon_handle, next_page_url, next_page_item, isFolder=True)
        xbmcplugin.endOfDirectory(addon_handle)
        return True
    else:
        log.error("Failed to build list_items in Kodi for", topic)
        return


def list_all_sciences():
    for link, science in SCIENCES.iteritems():
        list_item = xbmcgui.ListItem(
            label=science,
            iconImage='DefaultFolder.png')
        url_params = {"action": "list", "topic": link}
        is_folder = True
        xbmcplugin.addDirectoryItem(
            addon_handle,
            build_url(base_url, url_params),
            list_item,
            is_folder)
    xbmcplugin.addSortMethod(
        addon_handle,
        xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.endOfDirectory(addon_handle)


def list_main_menu():
    menu_items = []
    for folder, topic in MAIN_MENU:
        list_item = xbmcgui.ListItem(
            label=folder,
            iconImage='DefaultFolder.png')
        url_params = {"action": "list", "topic": topic}
        is_folder = True
        log.debug("Added list item: {} :: {} :: {}".format(
            build_url(base_url, url_params), list_item, is_folder))
        menu_items.append((
            build_url(base_url, url_params),
            list_item,
            is_folder))
    # For testing purposes
    test_li = xbmcgui.ListItem('Test')
    test_url = build_url(base_url, {"action": "test"})
    xbmcplugin.addDirectoryItem(addon_handle, test_url, test_li)
    # End of testing purposes
    xbmcplugin.addDirectoryItems(addon_handle, menu_items, len(menu_items))
    xbmcplugin.addSortMethod(
        addon_handle,
        xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.endOfDirectory(addon_handle)


def list_topic(topic, page):
    log.debug("Listing topic {topic} page {p}".format(topic=topic, p=page))
    if "all" in topic:
        if not list_videos(topic, page):
            log.error("No list videos for", topic, "!")
            pass
    elif topic == "science":
        list_all_sciences()
    else:
        # It's one of sciences
        list_videos(topic, page)


def play_video(video_id):
    log.debug("Playing video {video_id}".format(video_id=video_id))
    path = youtubeAddonUrl + video_id
    listitem = xbmcgui.ListItem(path=path, )
    xbmcplugin.setResolvedUrl(addon_handle, True, listitem)
    # xbmc.executebuiltin(
    #    "XBMC.PlayMedia(plugin://plugin.video.youtube/play/?video_id=" +
    #    video_id + ")")


def test():
    import os
    log.info("Testing here haahahahhahaahahaha")
    cache_plugin_path = xbmc.translatePath(
        "special://home/addons/script.common.plugin.cache/")
    storage_path = os.path.join(cache_plugin_path, "lib")
    print storage_path
    from StorageServer import StorageServer
    print dir(StorageServer)

action = args.get("action")
log.debug("Action = '{action}'".format(action=action))

if action is None:
    list_main_menu()
elif len(action) > 1:
    log.error("Action: {}".format(str(action)))
    raise MultipleActions("Multiple actions in URL!")
elif action[0] == "list":
    addon_handle = int(sys.argv[1])
    page = int(args["page"][0]) if "page" in args else 1
    list_topic(args["topic"][0], page)
elif action[0] == "play":
    addon_handle = int(sys.argv[1])
    play_video(args["video_id"][0])
elif action[0] == "test":
    addon_handle = int(sys.argv[1])
    test()
