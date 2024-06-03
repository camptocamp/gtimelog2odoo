from datetime import timedelta
from urllib.parse import urlparse

import odoorpc


class OdooClient(object):
    def __init__(self, config):
        self.client = odoorpc.ODOO(
            host=urlparse(config.get("odoo_url", "")).netloc,
            protocol=config.get("odoo_protocol"),
            port=config.get("odoo_port"),
        )
        self.client.login(
            db=config.get("odoo_db"),
            login=config.get("odoo_user"),
            password=config.get("odoo_password"),
        )
        self.tz_offset = config.get("tz_offset")
        self._attendance_default = None
        self._uid = self._get_uid()

    def _get_uid(self):
        return self.client.env.uid

    def _attendance_defaults(self):
        if self._attendance_default is None:
            self._attendance_default = self.client.env["hr.attendance"].default_get(
                ["employee_id"]
            )
        return self._attendance_default

    def drop_attendances(self, date_window):
        employee_id = self._attendance_defaults()["employee_id"]
        attendance_ids = self.client.env["hr.attendance"].search(
            [
                ("employee_id", "=", employee_id),
                ("check_in", ">=", date_window.start.isoformat()),
                "|",
                ("check_out", "<=", date_window.stop.isoformat()),
                ("check_out", "=", None),
            ]
        )
        # TODO: we should avoid deletion of all records when not required.
        # If they have not changed, it's pointless to do it.
        error_removing_all = False
        if attendance_ids:
            try:
                self.client.env["hr.attendance"].unlink(attendance_ids)
            except odoorpc.error.RPCError:
                error_removing_all = True
        if error_removing_all:
            for attendance_id in attendance_ids:
                try:
                    self.client.env["hr.attendance"].unlink(attendance_id)
                except odoorpc.error.RPCError:
                    pass
            print(
                "Some Odoo attendances could not be updated, invoicing period probably closed !"
            )

    def create_attendance(self, check_in, check_out):
        delta = timedelta(seconds=self.tz_offset)
        values = {
            "employee_id": self._attendance_defaults()["employee_id"],
            "check_in": (check_in - delta).strftime("%Y-%m-%d %H:%M:%S"),
            "check_out": (
                check_out and (check_out - delta).strftime("%Y-%m-%d %H:%M:%S")
            ),
        }
        try:
            self.client.env["hr.attendance"].create(values)
        except odoorpc.error.RPCError:
            print(
                "Error updating attendance for {} to {}".format(
                    values["check_in"], values["check_out"]
                )
            )
