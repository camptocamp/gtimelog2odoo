try:
    from gtimelog.settings import Settings
    from gtimelog.timelog import TimeLog
except ImportError:
    print('you have to install gtimelog first (pip install gtimelog)')
    raise

import re
import collections

from datetime import date

from .multi_log import MultiLog


def groupby(seq, key=lambda x: x):
    seq = list(seq)
    indexes = collections.defaultdict(list)
    for i, elem in enumerate(seq):
        indexes[key(elem)].append(i)
    for k, idxs in indexes.items():
        yield k, (seq[i] for i in idxs)


class GtimelogParser(object):
    def __init__(self, config):
        self.settings = Settings()
        self.timelog = TimeLog(self.settings.get_timelog_file(),
                               self.settings.virtual_midnight)
        self.aliases = config.get('aliases', {})
        self.entry_re = re.compile(
            r"(?:(?P<project>[a-z_-]*?): )?"
            r"(?:(?P<issue>[A-Z0-9]*?-[0-9]*?) )?"
            r"(?P<comment>.+)"
        )

    def get_entries(self, date_window, consolidate=True):
        window = self.timelog.window_for(date_window.start, date_window.stop)

        worklogs = []
        attendances = []
        for start, stop, duration, tags, entry in window.all_entries():
            if '**' in entry:
                continue
            if attendances and attendances[-1][1] == start:
                attendances[-1] = (attendances[-1][0], stop)
            else:
                attendances += [(start, stop)]
            entry = entry.split('|')[0].strip()
            matches = self.entry_re.match(entry)
            if matches:
                issue = matches.group('issue')
                if not issue:
                    #  Issue not in entry, check for alias
                    project = matches.group('project')
                    if project in self.aliases:
                        issue = self.aliases[project]
                    else:
                        continue
                comment = matches.group('comment')
                worklogs.append(MultiLog(
                    None,
                    issue,
                    int(duration.total_seconds()),
                    start.date(),
                    comment
                ))
            elif entry:
                print('Cannot parse entry "%s"' % entry)

        # Dangling attendance for today
        if attendances and attendances[-1][1].date() == date.today():
            attendances[-1] = (attendances[-1][0], None)

        if consolidate:
            consolidated = []
            for day, day_logs in groupby(worklogs, key=lambda e: e.date):
                for issue, issue_logs \
                        in groupby(day_logs, key=lambda e: e.issue):
                    for comment, comment_logs \
                            in groupby(issue_logs, key=lambda e: e.comment):
                        total = sum([l.duration for l in comment_logs])
                        consolidated.append(
                            MultiLog(None, issue, total, day, comment)
                        )
            return attendances, consolidated

        return attendances, worklogs
