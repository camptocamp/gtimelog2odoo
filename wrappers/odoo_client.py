import erppeek

from datetime import timedelta


class OdooClient(object):
    def __init__(self, config):
        self.client = erppeek.Client(
            config.get('odoo_url'),
            db=config.get('odoo_db'),
            user=config.get('odoo_user'),
            password=config.get('odoo_password')
        )
        self.tz_offset = config.get('tz_offset')
        self._attendance_default = None
        self._uid = self._get_uid()

    def _get_uid(self):
        cache_key = (self.client._server, self.client._db, self.client.user)
        return self.client._login.cache[cache_key][0]

    def _attendance_defaults(self):
        if self._attendance_default is None:
            self._attendance_default = self.client.HrAttendance.default_get(
                ["employee_id"]
            )
        return self._attendance_default

    def drop_attendances(self, date_window):
        employee_id = self._attendance_defaults()['employee_id']
        attendance_ids = self.client.HrAttendance.search(
            ['&', ('employee_id', '=', employee_id),
             '&', ('check_in', '>=', date_window.start.isoformat()),
             '|', ('check_out', '<=', date_window.stop.isoformat()),
             ('check_out', '=', None)
             ]
        )
        if attendance_ids:
            self.client.HrAttendance.unlink(attendance_ids)

    def create_attendance(self, check_in, check_out):
        delta = timedelta(seconds=self.tz_offset)
        values = {
            'employee_id': self._attendance_defaults()['employee_id'],
            'check_in': (check_in - delta).strftime('%Y-%m-%d %H:%M:%S'),
            'check_out': (check_out and
                          (check_out - delta).strftime('%Y-%m-%d %H:%M:%S'))
        }
        self.client.HrAttendance.create(values)
