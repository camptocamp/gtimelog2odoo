#!/usr/bin/env python3

import argparse
import sys
import configparser

from collections import namedtuple
from datetime import datetime, date, timedelta
from getpass import getpass
from itertools import groupby
from os import getenv
from pathlib import Path

try:
    from tzlocal import get_localzone
except ImportError:
    print('you have to install tzlocal (pip install tzlocal)')
    sys.exit()

from wrappers.jira_client import JiraClient
from wrappers.gtimelog_parser import GtimelogParser
from wrappers.odoo_client import OdooClient
from wrappers.multi_log import MultiLog

DEFAULT_CONFIG_PATH = Path(__file__).parent / 'gtimelogrc'
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
    def ask_submit_timesheet():
        print()
        confirm = input('Submit timesheet? (Y/n)')
        return confirm.lower() in ('y', 'yes', 'sure', '')

    @staticmethod
    def select_reviewer(reviewers):
        print()
        input_message = "Choose a reviewer:\n"
        user_input = "0"
        for index, rev_data in reviewers.items():
            input_message += f'[{index}] {rev_data["name"]}\n'
        input_message += "Your choice: "
        while user_input not in reviewers:
            user_input = input(input_message)
        return reviewers[user_input]

    @staticmethod
    def request_comment():
        print()
        return input('Enter any comment needed for timesheet submission:')

    @staticmethod
    def parse_config(args):
        config_file = Path(args.config).expanduser().resolve()
        if not config_file.exists():
            raise Exception(f"Configuration file {config_file} does not exist.")

        config = configparser.ConfigParser()
        config.optionxform = str  # do not lowercase the aliases section!
        config.read(config_file)

        if not config.has_section('gtimelog_exporter'):
            raise Exception(
                "Section [gtimelog_exporter] is not present "
                f"in {config_file} config file.")

        result = dict(config.items('gtimelog_exporter'))
        mandatory_fields = [
            'jira_url',
            'tempo_url',
            'jira_account_email',
        ]

        if not (args.no_attendance or result.get('no_attendance')):
            mandatory_fields.extend(['odoo_url', 'odoo_db', 'odoo_user'])
        if any(fld not in result for fld in mandatory_fields):
            raise Exception(
                'Not all mandatory fields are present '
                f"in {config_file} config file.")

        week, year = Utils.parse_week(args)
        result['date_window'] = DateWindow(*Utils.date_range_for_week(week, year))
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
            day_duration = sum(d.duration for d in day_logs)
            print("  ", day, "-", MultiLog._human_duration(day_duration))
            for issue, issue_logs in groupby(day_logs, key=lambda e: e.issue):
                print("    ", issue)
                for log in issue_logs:
                    print("      ", log.human_duration, ":", log.comment)

    @classmethod
    def report(cls, to_create, to_delete, to_check, attendances=None):
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
            for reason, logs in to_check.items():
                print("  ", reason, ':', ', '.join(log.issue for log in logs))

        if attendances is not None:
            print()
            print("Odoo Attendances")
            print("================")
            for day, day_attendances in groupby(attendances, key=lambda e: e[0].date()):
                print("{}".format(day))
                for attendance in day_attendances:
                    print("  {} → {}".format(
                        attendance[0].time(),
                        attendance[1] and attendance[1].time()
                    ))


def get_odoo_conf(config):
    odoo_config = config.copy()
    odoo_password = getenv('ODOO_PASSWORD')
    if not odoo_password:
        if args.no_interactive:
            raise Exception('Password missing in non-interactive, '
                            'set with ODOO_PASSWORD')
        odoo_password = getpass('Odoo password: ')
    odoo_config['odoo_password'] = odoo_password
    return odoo_config


def main():
    # 1. Configure
    parser = argparse.ArgumentParser(description="gtimelog_exporter options")

    parser.add_argument('-c', '--config',
                        default=DEFAULT_CONFIG_PATH, type=str)
    parser.add_argument('-w', '--week',
                        default=Utils.current_weeknumber(), type=int)
    parser.add_argument('-y', '--year',
                        default=Utils.current_year(), type=int)
    parser.add_argument('--no-interactive', action='store_true')
    parser.add_argument('--no-attendance', action='store_true')
    parser.add_argument('--submit', action='store_true')
    parser.add_argument('--select-reviewer', default=False, action='store_true')
    parser.add_argument('-r', '--repair-estimate',
                        default=False,
                        action='store_true',
                        help='The script will attempt to update the "Remaining Estimate", default is False')

    args = parser.parse_args()
    config = Utils.parse_config(args)

    no_attendance = args.no_attendance or config.get('no_attendance')
    do_submit = args.submit
    repair_estimate = args.repair_estimate

    if no_attendance:
        odoo_conf = {}
        print()
        print('`--no-attendance` flag is ON -> Skipping Odoo attendances')
        print()
    else:
        odoo_conf = get_odoo_conf(config)

    jira_api_token = getenv('JIRA_API_TOKEN')
    tempo_api_token = getenv('TEMPO_API_TOKEN')

    if not jira_api_token:
        if args.no_interactive:
            raise Exception('Token missing in non-interactive, '
                            'set with JIRA_API_TOKEN')
        jira_api_token = getpass('Jira API token: ')

    if not tempo_api_token:
        if args.no_interactive:
            raise Exception('Token missing in non-interactive, '
                            'set with TEMPO_API_TOKEN')
        tempo_api_token = getpass('Tempo API token: ')

    config['jira_api_token'] = jira_api_token
    config['tempo_api_token'] = tempo_api_token

    # 2. Collect worklogs (TEMPO API) and link to issues (JIRA API)
    jira = JiraClient(config)
    jira_logs = jira.get_worklogs(config['date_window'])
    jira_logs, jira_errors = jira.populate_issue_field(jira_logs)

    # 3. Collect GTimelog entries
    gt_parser = GtimelogParser(config)
    attendances, gt_logs = gt_parser.get_entries(config['date_window'])
    gt_logs, gt_errors = jira.populate_issue_field(gt_logs)

    to_create = []
    to_delete = []

    for log in jira_logs:
        if log not in gt_logs:
            to_delete.append(log)

    for log in gt_logs:
        if log not in jira_logs:
            to_create.append(log)

    Utils.report(to_create, to_delete, gt_errors, attendances if not no_attendance else None)

    nothing_to_do = not (gt_errors or to_delete or to_create)
    if nothing_to_do:
        print()
        print('All done, nothing to do.')

    # 4. Create worklogs (TEMPO API) and repair (JIRA API) and create attendances (Odoo API)
    confirmed = not nothing_to_do and Utils.ask_confirmation()

    if args.no_interactive or confirmed:
        for log in to_create:
            jira.create_worklog(log)

        for log in to_delete:
            jira.delete_worklog(log)

        if repair_estimate:
            # Get a unique list of all the issues impacted
            to_repair = set([log.issue for log in to_create] + [log.issue for log in to_delete])
            for i in to_repair:
                try:
                    jira.repair_estimate(i)
                except Exception as e:
                    print(e)

        if not no_attendance:
            odoo = OdooClient(odoo_conf)
            odoo.drop_attendances(config['date_window'])
            for attendance in attendances:
                odoo.create_attendance(attendance[0], attendance[1])

    # 5. Submit Timesheet (TEMPO API)
    ts_state = jira.get_timesheet_state(config['date_window'])
    submit = False
    if ts_state == "OPEN" and do_submit:
        submit = Utils.ask_submit_timesheet()
    if submit:
        cfg_reviewer_key = "tempo_reviewer_id"
        select_reviewer = args.select_reviewer
        reviewer = config.get(cfg_reviewer_key)
        if not reviewer or select_reviewer:
            reviewers = jira.get_reviewers()
            selected = Utils.select_reviewer(reviewers)
            reviewer = selected.get("accountId")
            print()
            print("Please add following line to your gtimelogrc (in gtimelog_exporter section) to avoid having to select a reviewer the next time:\n")
            print(f"{cfg_reviewer_key} = {reviewer}")
        comment = Utils.request_comment()
        res = jira.submit_timesheet(config['date_window'], reviewer, comment=comment)
        if res:
            print("Your Timesheet was submitted successfully")


if __name__ == "__main__":
    main()
