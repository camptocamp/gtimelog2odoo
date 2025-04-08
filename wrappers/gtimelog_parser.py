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
        if self.line_format == 'categorized':
            self.line_format_str = "category: task description | comment"
            self.delimiter = " "
        else:
            self.line_format_str = "task: description | comment"
            self.delimiter = ":"

    def skip_entry(self, entry):
        if '**' in entry:
            return True
        if entry.strip() in ('arrive', 'arrived', 'start'):
            return True
        return False

    def get_entries(self, date_window):
        window = self.timelog.window_for(date_window.start, date_window.stop)

        worklogs = []
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
                description
            ))

        # Dangling attendance for today except friday
        if attendances:
            today = attendances[-1][1].date() == date.today()
            friday = attendances[-1][1].weekday() == 4
            if today and not friday:
                attendances[-1] = (attendances[-1][0], None)

        return attendances, worklogs
