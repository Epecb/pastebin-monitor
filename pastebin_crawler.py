#!/usr/bin/env python3
"""A simple Pastebin crawler which looks for interesting things and saves them
to disk."""
from math import ceil
from argparse import ArgumentParser as OptionParser
import os
import re
import time
import sys
import tty
import termios
import requests
import magic

from pyquery import PyQuery


def get_char():
    """Returns a single character from standard input."""
    stdin_fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(stdin_fd)
    try:
        tty.setraw(sys.stdin.fileno())
        input_ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)
    return input_ch


def get_useragent():
    """Return user-agent."""
    return 'Mozilla/5.0 (Windows NT 6.1; rv:52.0) Gecko/20100101 Firefox/52.0'


def get_timestamp():
    """Return time stamp"""
    return time.strftime('%Y/%m/%d %H:%M:%S')


def all_python_encodings():
    """Return encodings list."""
    return ['ascii',
            'big5',
            'big5hkscs',
            'cp037',
            'cp424',
            'cp437',
            'cp500',
            'cp720',
            'cp737',
            'cp775',
            'cp850',
            'cp852',
            'cp855',
            'cp856',
            'cp857',
            'cp858',
            'cp860',
            'cp861',
            'cp862',
            'cp863',
            'cp864',
            'cp865',
            'cp866',
            'cp869',
            'cp874',
            'cp875',
            'cp932',
            'cp949',
            'cp950',
            'cp1006',
            'cp1026',
            'cp1140',
            'cp1250',
            'cp1251',
            'cp1252',
            'cp1253',
            'cp1254',
            'cp1255',
            'cp1256',
            'cp1257',
            'cp1258',
            'euc_jp',
            'euc_jis_2004',
            'euc_jisx0213',
            'euc_kr',
            'gb2312',
            'gbk',
            'gb18030',
            'hz',
            'iso2022_jp',
            'iso2022_jp_1',
            'iso2022_jp_2',
            'iso2022_jp_2004',
            'iso2022_jp_3',
            'iso2022_jp_ext',
            'iso2022_kr',
            'latin_1',
            'iso8859_2',
            'iso8859_3',
            'iso8859_4',
            'iso8859_5',
            'iso8859_6',
            'iso8859_7',
            'iso8859_8',
            'iso8859_9',
            'iso8859_10',
            'iso8859_13',
            'iso8859_14',
            'iso8859_15',
            'iso8859_16',
            'johab',
            'koi8_r',
            'koi8_u',
            'mac_cyrillic',
            'mac_greek',
            'mac_iceland',
            'mac_latin2',
            'mac_roman',
            'mac_turkish',
            'ptcp154',
            'shift_jis',
            'shift_jis_2004',
            'shift_jisx0213',
            'utf_32',
            'utf_32_be',
            'utf_32_le',
            'utf_16',
            'utf_16_be',
            'utf_16_le',
            'utf_7',
            'utf_8',
            'utf_8_sig']


class Logger:
    """"""

    shell_mod = {
        '': '',
        'PURPLE': '\033[95m',
        'CYAN': '\033[96m',
        'DARKCYAN': '\033[36m',
        'BLUE': '\033[94m',
        'GREEN': '\033[92m',
        'YELLOW': '\033[93m',
        'RED': '\033[91m',
        'BOLD': '\033[1m',
        'UNDERLINE': '\033[4m',
        'RESET': '\033[0m'
    }

    def log(self, message, is_bold=False, color='', log_time=True):
        """"""
        prefix = ''
        suffix = ''

        if log_time:
            prefix += '[{:s}] '.format(get_timestamp())

        if os.name == 'posix':
            if is_bold:
                prefix += self.shell_mod['BOLD']
            prefix += self.shell_mod[color.upper()]

            suffix = self.shell_mod['RESET']

        message = prefix + message + suffix
        print(message)
        sys.stdout.flush()

    def error(self, err):
        """"""
        self.log(err, True, 'RED')

    def fatal_error(self, err):
        """"""
        self.error(err)
        exit()


class Crawler:
    """Pastebin.com crawler."""
    PASTEBIN_URL = 'http://pastebin.com'
    PASTES_URL = PASTEBIN_URL + '/archive'
    REGEXES_FILE = 'regexes.txt'
    OK = 1
    ACCESS_DENIED = -1
    CONNECTION_FAIL = -2
    OTHER_ERROR = -3
    PASTES_DIR = 'archive'

    prev_checked_ids = []
    new_checked_ids = []
    pastes_for_save = []
    verbose = False

    def read_regexes(self):
        """Load regexes from regexes.txt."""
        try:
            with open(self.REGEXES_FILE, 'r') as regexes_file:
                try:
                    self.regexes = (
                        [[field.strip() for field in line.split(',')]
                         for line in regexes_file.readlines()
                         if line.strip() != '' and not line.startswith('#')])

                    # In case commas exist in the regexes...merge everything.
                    for i in range(len(self.regexes)):
                        self.regexes[i] = ([','.join(self.regexes[i][:-2])] +
                                           self.regexes[i][-2:])
                except KeyboardInterrupt:
                    raise
                except BaseException:
                    Logger().fatal_error(
                        'Malformed regexes file. Format:'
                        ' regex_pattern,URL logging file,'
                        ' directory logging file.')
        except KeyboardInterrupt:
            raise
        except BaseException:
            Logger().fatal_error('{:s} not found or not acessible.'.
                                 format(self.REGEXES_FILE))

    def __init__(self):
        self.read_regexes()

    @staticmethod
    def show_paste(paste_txt):
        """paste Feed."""
        def get_printable_size(byte_size):
            """Convert byte to KB MB GB."""
            for i in [' B', ' KB', ' MB', ' GB']:
                if byte_size < 1024.0:
                    if i == ' B':
                        return '%0.0f%s' % (byte_size, i)
                    return '%0.1f%s' % (byte_size, i)
                byte_size /= 1024.0
            return '%0.1f%s' % (byte_size, 'TB')
        message = (magic.from_buffer(paste_txt[0:1024]) +
                   ' [' + get_printable_size(len(paste_txt)) + ']')
        Logger().log(
            message=message, is_bold=False, color='BLUE',
            log_time=False)
        Logger().log(message=paste_txt[0:256],
                     is_bold=False, color='YELLOW', log_time=False)

    def get_pastes(self):
        """"""
        Logger().log('Getting pastes', True)
        try:
            page = PyQuery(url=self.PASTES_URL,
                           headers={'user-agent': get_useragent()})
        except KeyboardInterrupt:
            raise
        except BaseException:
            return self.CONNECTION_FAIL, None

        """
        There are a set of encoding issues which, coupled with some bugs in
        etree (such as in the Raspbian packages) can trigger encoding
        exceptions here. As a workaround, we try every possible encoding first,
        and even if that fails, we resort to a very hacky workaround whereby we
        manually get the page and attempt to encode it as utf-8. It's ugly, but
        it works for now.
        """
        try:
            page_html = page.html()
        except KeyboardInterrupt:
            raise
        except BaseException:
            worked = False
            for enc in all_python_encodings():
                try:
                    page_html = page.html(encoding=enc)
                    worked = True
                    break
                except KeyboardInterrupt:
                    raise
                except BaseException:
                    pass
            if not worked:
                # One last try...
                try:
                    req = requests.get(self.PASTES_URL,
                                       headers={'user-agent': get_useragent()})
                    page_html = PyQuery(req.text).html()
                except KeyboardInterrupt:
                    raise
                except BaseException:
                    return self.OTHER_ERROR, None
        if re.match(r'Pastebin\.com - Access Denied Warning', page_html,
                    re.IGNORECASE) or 'blocked your IP' in page_html:
            return self.ACCESS_DENIED, None
        else:
            return self.OK, page('.maintable img').next('a')

    def check_paste(self, paste_id):
        """"""
        paste_url = self.PASTEBIN_URL + '/raw' + paste_id
        try:
            req = requests.get(paste_url,
                               headers={'user-agent': get_useragent()})
            paste_txt = req.text

            if not self.verbose:
                self.show_paste(paste_txt)

            for regex, file, directory in self.regexes:
                if re.search(regex, paste_txt[0:1024], re.IGNORECASE):
                    Logger().log('Found a matching paste: ' +
                                 paste_url + ' (' + file + ')', True, 'CYAN')
                    self.save_result(paste_url, paste_id, file, directory,
                                     paste_txt)
                    return True
            Logger().log('Not matching paste: ' + paste_url)
            self.pastes_for_save.append({paste_id: paste_txt})
        except KeyboardInterrupt:
            raise
        except BaseException:
            Logger().log(
                'Error reading paste (probably a 404 or encoding issue).',
                True, 'YELLOW')
        return False

    def save_result(self, paste_url, paste_id, file, directory, paste_txt):
        """Save paste to hdd."""
        directory = self.PASTES_DIR + '/' + directory
        file = self.PASTES_DIR + '/' + file
        timestamp = get_timestamp()
        try:
            os.makedirs(directory)
        except KeyboardInterrupt:
            raise
        except BaseException:
            pass

        with open(file, 'a') as matching:
            matching.write(timestamp + ' - ' + paste_url + '\n')

        save_paste = (
            directory + '/' +
            timestamp.replace('/', '_').replace(':', '_').replace(' ', '__') +
            '_' + paste_id.replace('/', '') + '.txt'
        )
        with open(save_paste, mode='w') as paste:
            paste.write(paste_txt + '\n')

    def save_last_pastes(self,):
        """Save last pastes."""
        paste_url = ''
        for i in self.pastes_for_save:
            paste_id = next(iter(i))
            directory = 'saves'
            paste_txt = i[paste_id]
            file = 'saves.txt'
            self.save_result(paste_url, paste_id, file, directory, paste_txt)
        del self.pastes_for_save[:]

    def start(self, refresh_time=30, delay=1, ban_wait=5,
              flush_after_x_refreshes=100, connection_timeout=60,
              silent=False):
        """Start crawling."""
        self.verbose = silent
        count = 0
        while True:
            status, pastes = self.get_pastes()
            del self.pastes_for_save[:]

            start_time = time.time()
            if status == self.OK:
                for paste in pastes:
                    try:
                        paste_id = PyQuery(paste).attr('href')
                        self.new_checked_ids.append(paste_id)
                        if paste_id not in self.prev_checked_ids:
                            self.check_paste(paste_id)
                            time.sleep(delay)
                        count += 1
                    except KeyboardInterrupt:
                        Logger().log(
                            message=('\nQuit/Verbose/Save'
                                     '(last {:d} pastes)[q/v/s]:').
                            format(len(self.pastes_for_save)),
                            is_bold=False,
                            color='RED', log_time=False)
                        user_choice = get_char()
                        if user_choice in 'sS':
                            self.save_last_pastes()
                        if user_choice in 'vV':
                            self.verbose = not self.verbose
                        if user_choice in 'qQ':
                            raise

                if count == flush_after_x_refreshes:
                    self.prev_checked_ids = self.new_checked_ids
                    count = 0
                else:
                    self.prev_checked_ids += self.new_checked_ids
                self.new_checked_ids = []

                elapsed_time = time.time() - start_time
                sleep_time = ceil(max(0, (refresh_time - elapsed_time)))
                if sleep_time > 0:
                    Logger().log(
                        'Waiting {:d} seconds to refresh...'.
                        format(sleep_time),
                        True)
                    time.sleep(sleep_time)
            elif status == self.ACCESS_DENIED:
                Logger().log(
                    'Damn! It looks like you have been'
                    ' banned (probably temporarily)',
                    True, 'YELLOW')
                for i in range(0, ban_wait):
                    Logger().log('Please wait ' + str(ban_wait - i) +
                                 ' minute' +
                                 ('s' if (ban_wait - i) > 1 else ''))
                    time.sleep(60)
            elif status == self.CONNECTION_FAIL:
                Logger().log(
                    'Connection down. Waiting {:d} seconds and trying again'.
                    format(connection_timeout), True,
                    'RED')
                time.sleep(connection_timeout)
            elif status == self.OTHER_ERROR:
                Logger().log(
                    'Unknown error. Maybe an encoding problem?'
                    ' Trying again in {:d} seconds .'.
                    format(connection_timeout), True, 'RED')
                time.sleep(1)


def parse_input():
    """Prepare ARGS for Crawler.start"""
    parser = OptionParser()
    parser.add_argument(
        '-r',
        '--refresh-time',
        help='Set the refresh time (default: 60)',
        dest='refresh_time',
        type=int,
        default=30)
    parser.add_argument(
        '-d',
        '--delay-time',
        help='Set the delay time (default: 1)',
        dest='delay',
        type=float,
        default=3)
    parser.add_argument(
        '-b',
        '--ban-wait-time',
        help='Set the ban wait time (default: 5)',
        dest='ban_wait',
        type=int,
        default=5)
    parser.add_argument(
        '-f',
        '--flush-after-x-refreshes',
        help=('Set the number of refreshes after'
              ' which memory is flushed (default: 100)'),
        dest='flush_after_x_refreshes',
        type=int,
        default=100)
    parser.add_argument(
        '-c',
        '--connection-timeout',
        help='Set the connection timeout waiting time (default: 60)',
        dest='connection_timeout',
        type=float,
        default=60)
    parser.add_argument(
        '-s',
        '--silent',
        help='Silent mode. Log only.',
        dest='silent',
        action='store_true'
        )
    options = parser.parse_args()
    return (options.refresh_time, options.delay, options.ban_wait,
            options.flush_after_x_refreshes, options.connection_timeout,
            options.silent)


try:
    Crawler().start(*parse_input())
except KeyboardInterrupt:
    Logger().log('Bye! Hope you found what you were looking for :)', True)
