import erppeek

from datetime import timedelta
from xmlrpc.client import Fault


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
        # TODO: we should avoid deletion of all records when not required.
        # If they have not changed, it's pointless to do it.
        error_removing_all = False
        if attendance_ids:
            try:
                self.client.HrAttendance.unlink(attendance_ids)
            except Fault:
                error_removing_all = True
        if error_removing_all:
            for attendance_id in attendance_ids:
                try:
                    self.client.HrAttendance.unlink(attendance_id)
                except Fault:
                    pass
            print('Some Odoo attendances could not be updated, invoicing period probably closed !')

    def create_attendance(self, check_in, check_out):
        delta = timedelta(seconds=self.tz_offset)
        values = {
            'employee_id': self._attendance_defaults()['employee_id'],
            'check_in': (check_in - delta).strftime('%Y-%m-%d %H:%M:%S'),
            'check_out': (check_out and
                          (check_out - delta).strftime('%Y-%m-%d %H:%M:%S'))
        }
        try:
            self.client.HrAttendance.create(values)
        except Fault:
            print("Error updating attendance for {} to {}".format(
                values['check_in'], values['check_out'])
            )
