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

    def get_entries(self, date_window):
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
            try:
                issue, description = [
                    x.strip() for x in entry.split(':') if x.strip()
                ]
            except ValueError:
                print(
                    'Entry must be in the format `task: description`. '
                    'Got ', entry
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

        # Dangling attendance for today
        if attendances and attendances[-1][1].date() == date.today():
            attendances[-1] = (attendances[-1][0], None)

        return attendances, worklogs
