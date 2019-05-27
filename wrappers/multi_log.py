from collections import namedtuple


class MultiLog(namedtuple('MultiLog', 'id issue duration date comment')):

    def __eq__(self, other):
        d1 = self._asdict()
        del d1['id']
        d2 = other._asdict()
        del d2['id']
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
        return '{}h {:02}m'.format(hours, minutes)
