import pprint

try:
    from gtimelog.settings import Settings
    from gtimelog.timelog import TimeLog
except ImportError:
    print('you have to install gtimelog first (pip install gtimelog)')
    raise

from datetime import date

from .multi_log import MultiLog


class GtimelogParser(object):

    def __init__(self, config):
        self.settings = Settings()
        self.timelog = TimeLog(self.settings.get_timelog_file(),
                               self.settings.virtual_midnight)
        self.aliases = config.get('aliases', {})
        self.line_format = config.get('line_format', '')
        self.dispatch_blacklist_prefixes = self.parse_dispatch_blacklist_prefixes(config)
        if self.line_format == 'categorized':
            self.line_format_str = "category: task description | comment"
            self.delimiter = " "
        else:
            self.line_format_str = "task: description | comment"
            self.delimiter = ":"

    def parse_dispatch_blacklist_prefixes(self, config):
        prefixes = config.get('dispatch_blacklist_prefixes', "").split(",")
        # Cleanup in case of spaces
        return [
            prefix.strip() for prefix in prefixes
            if prefix.strip()
        ]

    def skip_entry(self, entry):
        if '**' in entry:
            return True
        if entry.strip() in ('arrive', 'arrived', 'start'):
            return True
        return False

    def is_dispatch_entry(self, entry):
        """Returns whether or not this entry is a dispatch"""
        return '++' in entry

    def is_dispatch_entry_blacklisted(self, entry):
        """Returns whether or not this entry will not be considered during
        dispatch"""
        if not self.dispatch_blacklist_prefixes:
            return False
        issue, description = self.get_issue_description(entry)
        return any([
            issue.startswith(ref)
            for ref in self.dispatch_blacklist_prefixes
        ])

    def get_entries_to_dispatch(self, window):
        """Returns non internal nor dispatchable nor skippable entries"""
        return [
            entry
            for start, stop, duration, tags, entry in window.all_entries()
            if not (
                self.skip_entry(entry)
                or self.is_dispatch_entry(entry)
                or self.is_dispatch_entry_blacklisted(entry)
            )
        ]

    def get_duration_to_dispatch(self, window):
        """Returns the time to dispatch to entries
        i.e. total amount of dispatchable entries divided byt the quantity of
        entries to dispatch
        """
        entries_to_dispatch = self.get_entries_to_dispatch(window)
        durations = [
            int(duration.total_seconds())
            for start, stop, duration, tags, entry in window.all_entries()
            if self.is_dispatch_entry(entry)
        ]
        total_duration = sum(durations)
        return total_duration / len(entries_to_dispatch)

    def get_issue_description(self, entry):
        # remove comments
        line = entry.split('|')[0]
        try:
            # remove category
            if self.line_format == 'categorized':
                # category is optional
                if ':' in line:
                    line = line.split(':', 1)[1].strip()
            issue, description = [
                x.strip() for x in line.split(self.delimiter, 1)
                if x.strip()
            ]
        except ValueError:
            print(
                'Entry must be in the format `{}`. '
                'Got '.format(self.line_format_str), entry
            )
            return

        # no matter what we find as `issue`:
        # if we have an alias override it takes precedence
        if issue in self.aliases:
            issue = self.aliases[issue]
        return issue, description

    def dispatch_entries(self, window):
        entries_to_dispatch = self.get_entries_to_dispatch(window)
        duration_to_dispatch = self.get_duration_to_dispatch(window)

        entries_to_return = []
        for start, stop, duration, tags, entry in window.all_entries():
            if self.skip_entry(entry):
                continue

            issue, description = self.get_issue_description(entry)

            dispatched_duration = int(duration.total_seconds())
            # Apply dispatch to dispatchable entries only
            if entry in entries_to_dispatch:
                dispatched_duration = (
                        int(duration.total_seconds()) + duration_to_dispatch
                )
            log_entry = MultiLog(
                None,
                issue,
                dispatched_duration,
                start.date(),
                start.time(),
                description
            )
            if not self.is_dispatch_entry(entry):
                entries_to_return.append(log_entry)
        return entries_to_return

    def get_entries(self, date_window):
        window = self.timelog.window_for(date_window.start, date_window.stop)

        worklogs = self.dispatch_entries(window)
        dispatchlogs = []
        attendances = []

        for start, stop, duration, tags, entry in window.all_entries():
            if self.skip_entry(entry):
                continue
            if attendances and attendances[-1][1] == start:
                attendances[-1] = (attendances[-1][0], stop)
            else:
                attendances += [(start, stop)]
            # remove comments
            line = entry.split('|')[0]
            try:
                # remove category
                if self.line_format == 'categorized':
                    # category is optional
                    if ':' in line:
                        line = line.split(':', 1)[1].strip()
                issue, description = [
                    x.strip() for x in line.split(self.delimiter, 1)
                    if x.strip()
                ]
            except ValueError:
                print(
                    'Entry must be in the format `{}`. '
                    'Got '.format(self.line_format_str), entry
                )
                continue

            # no matter what we find as `issue`:
            # if we have an alias override it takes precedence
            if issue in self.aliases:
                issue = self.aliases[issue]
            worklogs.append(MultiLog(
                None,
                issue,
                int(duration.total_seconds()),
                start.date(),
                start.time(),
                description
            ))

        # Dangling attendance for today
        if attendances and attendances[-1][1].date() == date.today():
            attendances[-1] = (attendances[-1][0], None)

        return attendances, worklogs, dispatchlogs
