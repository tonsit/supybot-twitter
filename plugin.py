###
# Copyright (c) 2010-2016, buckket
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

import supybot.utils as utils
from supybot.commands import *

import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import supybot.schedule as schedule
import supybot.ircmsgs as ircmsgs
import supybot.log as log

import re
import tweepy
import HTMLParser


class Twitter(callbacks.Plugin):
    """Hello. This is Twitter."""

    def __init__(self, irc):
        self.__parent = super(Twitter, self)
        self.__parent.__init__(irc)

        self.regexp = re.compile(r"(?:https?://(?:[^.]+.)?twitter.com/(?P<username>[^/]*)/status(?:es)?/)?(?P<status_id>\d+)")

    def _is_bot_enabled(self, msg, irc=None):
        if self.registryValue("botEnabled", msg.args[0]):
            return True
        if irc:
            irc.reply("Dieser Kanal hat keinen Twitter Account.")
        return False

    def _get_twitter_api(self, msg):
        auth = tweepy.OAuthHandler(self.registryValue("consumerKey", msg.args[0]),
                                   self.registryValue("consumerSecret", msg.args[0]))
        auth.set_access_token(self.registryValue("accessKey", msg.args[0]),
                              self.registryValue("accessSecret", msg.args[0]))
        return tweepy.API(auth)

    def _get_status_id(self, tweet, search=False):
        regexp = self.regexp
        if search:
            m = re.search(regexp, tweet)
        else:
            m = re.match(regexp, tweet)
        if m and m.group("status_id"):
            return m.group("status_id")
        else:
            return False

    def _tweet(self, irc, msg, text, tweet=None):
        if not self._is_bot_enabled(msg, irc):
            return
        try:
            api = self._get_twitter_api(msg)
            if tweet:
                status_id = self._get_status_id(tweet)
                if status_id:
                    if not text.startswith("@"):
                        username = api.get_status(status_id).user.screen_name
                        text = "@{} {}".format(username, text)
                    message = utils.str.ellipsisify(text, 140)
                    status = api.update_status(status=message, in_reply_to_status_id=status_id)
                else:
                    irc.reply("Du musst mir schon einen Tweet geben, auf den sich der Unsinn beziehen soll.")
                    return
            else:
                message = utils.str.ellipsisify(text, 140)
                status = api.update_status(status=message)
            irc.reply("https://twitter.com/{bot}/status/{status_id}".format(
                bot=self.registryValue("botNick", msg.args[0]), status_id=status.id))
        except tweepy.TweepError as e:
            log.error("Twitter.tweet: {}".format(repr(e)))
            irc.reply("Das hat nicht geklappt.")

    def twitter(self, irc, msg, args):
        """Returns the link to the bot's Twitter profile."""
        if self.registryValue("botEnabled", msg.args[0]):
            irc.reply("http://twitter.com/{}".format(self.registryValue("botNick", msg.args[0])))
        else:
            irc.reply("Dieser Kanal hat keinen Twitter Account.")

    def tweet(self, irc, msg, args, text):
        """<text>

        Tweets <text>
        """
        self._tweet(irc, msg, text)

    def reply(self, irc, msg, args, tweet, text):
        """<tweet url or id> <text>

        Tweets <text> as reply to <tweet url or id>
        """
        self._tweet(irc, msg, text, tweet)

    def fav(self, irc, msg, args, tweet):
        """<tweet url or id>

        Favs tweet <tweet url or id>
        """
        if not self._is_bot_enabled(msg, irc):
            return
        status_id = self._get_status_id(tweet)
        if status_id:
            try:
                api = self._get_twitter_api(msg)
                api.create_favorite(status_id)
                irc.reply("Alles klar.")
            except tweepy.TweepError as e:
                log.error("Twitter.fav: {}".format(repr(e)))
                irc.reply("Das hat nicht geklappt.")

    def rt(self, irc, msg, args, tweet):
        """<tweet url or id>

        RTs tweet <tweet url or id>
        """
        if not self._is_bot_enabled(msg, irc):
            return
        status_id = self._get_status_id(tweet)
        if status_id:
            try:
                api = self._get_twitter_api(msg)
                api.retweet(status_id)
                irc.reply("Alles klar.")
            except tweepy.TweepError as e:
                log.error("Twitter.rt: {}".format(repr(e)))
                irc.reply("Das hat nicht geklappt.")

    def delete(self, irc, msg, args, tweet):
        """<tweet url or id>

        Deletes tweet <tweet url or id>
        """
        if not self._is_bot_enabled(msg, irc):
            return
        status_id = self._get_status_id(tweet)
        if status_id:
            try:
                api = self._get_twitter_api(msg)
                api.destroy_status(status_id)
                irc.reply("Alles klar.")
            except tweepy.TweepError as e:
                log.error("Twitter.delete: {}".format(repr(e)))
                irc.reply("Das hat nicht geklappt.")

    def doPrivmsg(self, irc, msg):
        if ircmsgs.isCtcp(msg) and not ircmsgs.isAction(msg):
            return
        if ircutils.isChannel(msg.args[0]) and self.registryValue("resolve", msg.args[0]):
            if msg.args[1].find("twitter") != -1:
                status_id = self._get_status_id(msg.args[1], search=True)
                if status_id:
                    try:
                        api = self._get_twitter_api(msg)
                        tweet = api.get_status(status_id)
                        text = tweet.text.replace("\n", " ")
                        text = HTMLParser.HTMLParser().unescape(text)
                        message = u"Tweet von @{}: {}".format(tweet.user.screen_name, text)
                        message = ircutils.safeArgument(message.encode('utf-8'))
                        irc.queueMsg(ircmsgs.notice(msg.args[0], message))
                    except tweepy.TweepError as e:
                        log.error("Twitter.doPrivmsg: {}".format(repr(e)))
                        return

    twitter = wrap(twitter, ["public"])
    tweet = wrap(tweet, ["public", "text"])
    reply = wrap(reply, ["public", "somethingWithoutSpaces", "text"])
    fav = wrap(fav, ["public", "somethingWithoutSpaces"])
    rt = wrap(rt, ["public", "somethingWithoutSpaces"])
    delete = wrap(delete, ["public", "somethingWithoutSpaces"])


Class = Twitter
