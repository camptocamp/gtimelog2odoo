#!/usr/bin/env python3

import argparse
import sys
import configparser
import pathlib

from builtins import input
from collections import namedtuple
from datetime import datetime, date, timedelta
from getpass import getpass
from os import environ as env
from os.path import dirname, realpath
from itertools import groupby

try:
    from tzlocal import get_localzone
except ImportError:
    print('you have to install tzlocal (pip install tzlocal)')
    sys.exit()

from wrappers.jira_client import JiraClient
from wrappers.gtimelog_parser import GtimelogParser
from wrappers.odoo_client import OdooClient
from wrappers.multi_log import MultiLog

DEFAULT_CONFIG_PATH = dirname(realpath(__file__)) + '/gtimelogrc'
DateWindow = namedtuple('DateWindow', 'start stop')

tz = get_localzone()
utcnow = datetime.now(tz)
tz_offset = utcnow.utcoffset().total_seconds()


class Utils:

    @staticmethod
    def current_weeknumber():
        return int(datetime.now().strftime("%W"))

    @staticmethod
    def current_year():
        return date.today().year

    @staticmethod
    def parse_week(args):
        """Parse week number and set week and year

        Use weeknumber as it is if positive
        if negative, get relative week from current one.
        """
        if args.week < 0:
            in_past = datetime.now() + timedelta(weeks=args.week)
            week = in_past.strftime("%W")
            week = int(week)
            year = in_past.year
        else:
            week = args.week
            year = args.year
        return week, year

    @staticmethod
    def date_range_for_week(weeknumber, yearnumber):
        year = yearnumber or date.today().year
        week = '%d %d 1' % (year, weeknumber)
        weekstart = datetime.strptime(week, "%Y %W %w")
        weekstop = weekstart + timedelta(days=6, hours=23, minutes=59,
                                         seconds=59)
        return weekstart, weekstop

    @staticmethod
    def ask_confirmation():
        print()
        confirm = input('Confirm? (y/N) ')
        return confirm.lower() in ('y', 'yes', 'sure')

    @staticmethod
    def parse_config(args):
        config_file = pathlib.Path(args.config).expanduser().resolve()
        if not config_file.exists():
            raise Exception(
                "Configuration file %s does not exist." % config_file)

        config = configparser.ConfigParser()
        config.optionxform = str  # do not lowercase the aliases section!
        config.read(config_file)

        if not config.has_section('gtimelog_exporter'):
            raise Exception(
                "Section [gtimelog_exporter] is not present "
                "in %s config file." % config_file)

        result = dict(config.items('gtimelog_exporter'))
        mandatory_fields = [
            'jira_url',
            'tempo_api',
            'tempo_user',
            'odoo_url',
            'odoo_db',
            'odoo_user'
        ]
        if len(set(mandatory_fields) - set(result.keys())) > 0:
            raise Exception(
                'Not all mandatory fields are present '
                'in %s config file.' % config_file)

        week, year = Utils.parse_week(args)
        result['date_window'] = DateWindow(
            *Utils.date_range_for_week(week, year)
        )
        result['tz_offset'] = tz_offset

        if config.has_section('gtimelog_exporter:aliases'):
            result['aliases'] = dict(config.items('gtimelog_exporter:aliases'))
        else:
            result['aliases'] = {}

        return result

    @classmethod
    def _report_log(cls, logs):
        for day, day_logs in groupby(logs, key=lambda e: e.date):
            day_logs = tuple(day_logs)  # we have to iterate twice
            day_duration = sum([d.duration for d in day_logs])
            print("  ", day, "-", MultiLog._human_duration(day_duration))
            for issue, issue_logs in groupby(day_logs, key=lambda e: e.issue):
                print("    ", issue)
                for log in issue_logs:
                    print("      ", log.human_duration, ":", log.comment)

    @classmethod
    def report(cls, to_create, to_delete, to_check, attendances):
        print("Jira Worklogs")
        print("=============")
        if to_create:
            print("Create")
            cls._report_log(to_create)

        if to_delete:
            print()
            print("Delete")
            cls._report_log(to_delete)

        if to_check:
            print()
            print("Not matching - TO CHECK")
            print("")
            for issue, reason in to_check.items():
                print("  ", issue, ':', reason)

        if not to_check and not to_delete and not to_create:
            print()
            print('All done, nothing to do.')

        print()
        print("Odoo Attendances")
        print("================")
        for day, day_attendances \
                in groupby(attendances, key=lambda e: e[0].date()):
            print("{}".format(day))
            for attendance in day_attendances:
                print("  {} → {}".format(
                    attendance[0].time(),
                    attendance[1] and attendance[1].time()
                ))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="gtimelog_exporter options")

    parser.add_argument('-c', '--config',
                        default=DEFAULT_CONFIG_PATH, type=str)
    parser.add_argument('-w', '--week',
                        default=Utils.current_weeknumber(), type=int)
    parser.add_argument('-y', '--year',
                        default=Utils.current_year(), type=int)
    parser.add_argument('--no-interactive', action='store_true')

    args = parser.parse_args()

    config = Utils.parse_config(args)

    odoo_password = tempo_password = env.get('ALL_PASSWORD')

    odoo_password = odoo_password or env.get('ODOO_PASSWORD')
    if not odoo_password:
        if args.no_interactive:
            raise Exception('Password missing in non-interactive, '
                            'set with ODOO_PASSWORD')
        odoo_password = getpass('Odoo password: ')

    tempo_password = tempo_password or env.get('TEMPO_PASSWORD')
    if not tempo_password:
        if args.no_interactive:
            raise Exception('Password missing in non-interactive, '
                            'set with TEMPO_PASSWORD')
        tempo_password = getpass('Tempo (Jira) password: ')

    config['odoo_password'] = odoo_password
    config['tempo_password'] = tempo_password

    not_before = datetime.strptime('2019-04-01', '%Y-%M-%d').date()
    if config['date_window'].start.date() < not_before:
        raise Exception('This script is not intended to manage attendences '
                        'prior to April 1st, 2019')

    jira = JiraClient(config)
    jira_logs = jira.get_worklogs(config['date_window'])

    gt_parser = GtimelogParser(config)
    attendances, gt_logs = gt_parser.get_entries(config['date_window'])

    to_create = []
    to_delete = []
    to_check = {}

    for l in jira_logs:
        if l not in gt_logs:
            to_delete.append(l)

    for l in gt_logs:
        if l not in jira_logs:
            to_create.append(l)

    # check issues exists
    issues = set([x.issue for x in to_create])
    for issue in issues:
        checked = jira.check_issue(issue)
        if not checked['ok']:
            to_check[issue] = checked['errors']

    # remove not matching
    to_create = [x for x in to_create if x.issue not in to_check]

    Utils.report(to_create, to_delete, to_check, attendances)

    if args.no_interactive or Utils.ask_confirmation():
        for l in to_create:
            jira.create_worklog(l)

        for l in to_delete:
            jira.delete_worklog(l)

        odoo = OdooClient(config)
        odoo.drop_attendances(config['date_window'])
        for attendance in attendances:
            odoo.create_attendance(attendance[0], attendance[1])
