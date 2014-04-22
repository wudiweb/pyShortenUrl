#!/usr/bin/env python2.6
# -*- coding: utf-8 -*-
#
############################
# pyShortenUrl is a simple Tornado web app to create short url
# it uses SQLite to save the url data
# like: http://www.wudiweb.com/news/694278 -> http://tac.xx/tRKUX2
#
# @author phychion <wudiweb@gmail.com>
# http://www.wudiweb.com/
# https://github.com/wudiweb
# MIT License
############################

import os
import sqlite3
import tornado.ioloop
import tornado.web
import tornado.httpserver
from binascii import crc32
from time import time,localtime,strftime
from tornado.options import options,define

define('debug', default = False, type = bool, help = 'is debuging?')
define('port', default = 8900, type = int, help = 'listen port')
define('authpass', default = '123456', type = str, help = 'login password')
define('num_processes', default = 1, type = int, help = 'how many processes will be running?')
define('domain', default = 'tac.xx', type = str, help = 'set the default domain')

class BaseHandler(tornado.web.RequestHandler):
    con = None
    cur = None

    def prepare(self):
        root_dir = os.path.dirname(__file__)
        db_file = os.path.join(root_dir,'urldb')
        self.con = sqlite3.connect(db_file)
        self.cur = self.con.cursor()

    def shorturl(self,url):
        '''shorten url'''
        url = crc32(url) & 0xffffffff
        result = int(url)

        output = ''
        while result > 0:
            tmp = result % 62
            if tmp > 9 and tmp <= 35:
                tmp = chr(int(tmp + 55))
            elif tmp > 35:
                tmp = chr(int(tmp + 61))

            output += str(tmp)
            result = int(result / 62)

        return str(output)

    def get_current_user(self):
        return self.get_secure_cookie("uid")

    def installed(self):
        '''SQLite table installed'''
        self.cur.execute("select count(*) as tnum from sqlite_master where type='table' and name='url' limit 1")
        return self.cur.fetchone()[0]

class MainHandler(BaseHandler):
    def get(self,uri):
        if not self.installed():
            return self.redirect('/install')
        else:
            self.cur.execute("select * from url where shorturl=:uri limit 1",{'uri':uri})
            row = self.cur.fetchone()

            self.cur.close()
            if row:
                return self.redirect(row[1])
            else:
                self.write("nothing.")

class UrlListHandler(BaseHandler):
    '''manage url list'''

    def get(self):
        if not self.installed():
            return self.redirect('/install')

        if not self.current_user:
            return self.redirect('/login')

        html = '''
        <table width="100%">
            <tr>
                <td>
                    <form method="POST">
                        Url: <input type="text" name="url" size="100">
                        <input type="submit" value="Go">
                    </form>
                </td>
                <td align="right">
                    <a href="/logout">Sign Out</a>
                </td>
            </tr>
        </table>
        '''

        html += '<table cellpadding="4" cellspacing="1" width="100%" border="1">'
        html += '<tr><td>Code</td><td>Url</td><td>Created</td></tr>'
        for row in self.cur.execute("select * from url order by created desc"):
            html += '<tr id="{code}"><td><a href="http://'+options.domain+'/{code}" target="_blank">{code}</a></td><td>{url}</td><td>{created}</td></tr>'.format(code=row[0],url=row[1],created=row[2])
        html += '</table>'

        self.cur.close()
        self.write(html)

    def post(self, *args, **kwargs):
        if not self.current_user:
            self.redirect('/login')

        url = self.get_argument('url',None)
        if url:
            self.cur.execute("select * from url where rawurl=:url limit 1",{'url':url})
            row = self.cur.fetchone()
            if row:
                self.cur.close()
                return self.redirect('/url/list#%s' % row[0])
            else:
                code = self.shorturl(url)
                created = strftime("%Y-%m-%d %H:%M:%S", localtime(time()))
                self.cur.execute("insert into url values (?,?,?)",(code,url,created))
                self.con.commit()
                self.cur.close()

                return self.redirect('/url/list#%s' % code)

        return self.redirect('/url/list')

class LoginHandler(BaseHandler):
    def get(self, *args, **kwargs):
        if self.current_user:
            return self.redirect('/url/list')

        self.write('<form method="POST">Login: <input type="password" name="password"><input type="submit" value="Go"></form>')

    def post(self, *args, **kwargs):
        password = self.get_argument("password",'')
        if str(password).lower() == options.authpass.lower():
            self.set_secure_cookie('uid','yxyx')
            return self.redirect('/url/list')
        else:
            return self.redirect('/login')

class LogoutHandler(BaseHandler):
    def get(self, *args, **kwargs):
        self.clear_cookie('uid')
        return self.redirect('/login')

class InstallHandler(BaseHandler):
    def get(self):
        if not self.current_user:
            return self.redirect('/login')

        if not self.installed():
            self.cur.execute("create table url (shorturl,rawurl,created)")
            self.cur.close()

            self.write('Install APP successfully. <a href="/url/list">Add Url</a>')
        else:
            return self.redirect('/login')

tornado.options.parse_command_line()

settings = {
    "debug": options.debug,
    "cookie_secret": "pm9cx4K3skw8",
    "login_url": "/login",
}

application = tornado.web.Application([
            (r"/install", InstallHandler),
            (r"/url/list", UrlListHandler),
            (r"/login", LoginHandler),
            (r"/logout", LogoutHandler),
            (r"/(.*)", MainHandler)
        ],**settings)

if __name__ == "__main__":
    server = tornado.httpserver.HTTPServer(application, xheaders=True)
    server.listen(int(options.port))
    server.start(num_processes=int(options.num_processes))
    tornado.ioloop.IOLoop.instance().start()

