# -*- coding: utf-8 -*-
import sys
import urlparse
import xbmcgui
import xbmcplugin
from lib.postnaukalib import (
        Logger,
        MultipleActions,
        Parser,
        List,
        Plugin,
        SCIENCES,
        SITE,
        URLS,
        youtubeAddonUrl,
    )

args = urlparse.parse_qs(sys.argv[2][1:])

xbmcplugin.setContent(Plugin.handle, 'movies')
sci_urls_dict = dict((sci, SITE + "themes/" + sci) for sci in SCIENCES)
URLS.update(sci_urls_dict)


parser = Parser()
log = Logger()
log.debug("Base URL: {0}".format(Plugin.url))
log.debug("Args: {0}".format(args))


def play_video(video_id):
    log.debug("Playing video {video_id}".format(video_id=video_id))
    path = youtubeAddonUrl + video_id
    listitem = xbmcgui.ListItem(path=path, )
    xbmcplugin.setResolvedUrl(Plugin.handle, True, listitem)

# def test():
#     log.info("Testing")


action = args.get("action")
log.debug("Action = '{action}'".format(action=action))

menu = List()
if action is None:
    menu.main_menu()
elif len(action) > 1:
    log.error("Action: {0}".format(str(action)))
    raise MultipleActions("Multiple actions in URL!")
elif action[0] == "list":
    Plugin.handle = int(sys.argv[1])
    page = int(args["page"][0]) if "page" in args else 1
    menu.display_topic(args["topic"][0], page)
elif action[0] == "play":
    Plugin.handle = int(sys.argv[1])
    play_video(args["video_id"][0])
# elif action[0] == "test":
#     Plugin.handle = int(sys.argv[1])
#     test()
