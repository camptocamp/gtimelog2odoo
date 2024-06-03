class MultiLog:

    def __init__(self, _id, issue, duration, date, comment):
        self.id = int(_id) if _id else None
        self.issue = issue
        self.duration = duration
        self.date = date
        self.comment = comment

    __slots__ = ("id", "issue", "duration", "date", "comment")

    def _asdict(self):
        return {k: getattr(self, k) for k in ("issue", "duration", "date", "comment")}

    def __eq__(self, other):
        d1 = self._asdict()
        d2 = other._asdict()
        return d1 == d2

    @property
    def human_duration(self):
        return self._human_duration(self.duration)

    @classmethod
    def _human_duration(cls, duration):
        hours = minutes = 0
        if duration:
            hours = int(duration // 3600)
            minutes = int(duration % 3600 / 60)
        return "{}h {:02}m".format(hours, minutes)

    @property
    def jira_ref(self):
        # When loaded from gtimelog we don't have the ID
        if self.id:
            return self.id
        return self.issue
