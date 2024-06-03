import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import urljoin

from dateutil import parser
from collections import defaultdict

from .multi_log import MultiLog


class JiraClient(object):
    @staticmethod
    def convert_seconds_to_jira_time(seconds):
        weeks, remainder = divmod(seconds, 5 * 8 * 3600)
        days, remainder = divmod(seconds, 8 * 3600)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)

        jira_time = []
        if weeks > 0:
            jira_time.append(f"{weeks}w")
        if days > 0:
            jira_time.append(f"{days}d")
        if hours > 0:
            jira_time.append(f"{hours}h")
        if minutes > 0:
            jira_time.append(f"{minutes}m")

        return " ".join(jira_time) if jira_time else "0s"

    def __init__(self, config: dict):
        self.jira_url = config.get('jira_url')
        self.tempo_url = config.get('tempo_url')
        self.jira_api_token = config.get('jira_api_token')
        self.tempo_api_token = config.get('tempo_api_token')
        self.jira_account_email = config.get('jira_account_email')
        self.jira_session, self.account_id = self.init_jira_session()
        self.tempo_session = self.init_tempo_session()
        self.worklog_url = urljoin(self.tempo_url, f'worklogs/user/{self.account_id}')
        self.worklog_create_url = urljoin(self.tempo_url, 'worklogs')

    def init_jira_session(self):
        session = requests.Session()
        session.headers.update({
            "Accept": "application/json",
        })
        session.auth = HTTPBasicAuth(
            self.jira_account_email,
            self.jira_api_token
        )
        resp = session.get(urljoin(self.jira_url, 'rest/api/3/myself'))
        if resp.status_code == 200:
            return session, resp.json()["accountId"]
        elif resp.status_code == 401:
            raise Exception("Error: Jira authentication failed.")
        elif resp.status_code == 403:
            raise Exception(
                "Jira credentials seems to be correct, but this user does "
                "not have permission to log in.\nTry to log in via browser, "
                "maybe you need to answer a security question: %s" %
                self.jira_url
            )
        else:
            raise Exception(
                "Something went wrong,"
                " Jira gave %s status code." % resp.status_code
            )

    def init_tempo_session(self):
        session = requests.Session()
        session.headers.update({
            "Accept": "application/json",
            "Authorization": f"Bearer {self.tempo_api_token}"
        })
        return session

    def get_issue(self, issue, fields="*all"):
        url = urljoin(self.jira_url, f'rest/api/latest/issue/{issue}')
        return self.jira_session.get(url, params={"fields": fields})

    def get_worklogs(self, date_window):
        url = self.worklog_url
        response = self.tempo_session.get(
            url,
            params={
                "from": date_window.start.date().isoformat(),
                "to": date_window.stop.date().isoformat(),
                "offset": 0,
                "limit": 9999
            }
        )
        if response.status_code == 200:
            entries = response.json()["results"]
            worklogs = []
            for entry in entries:
                worklogs.append(
                    MultiLog(
                        entry['issue']['id'],
                        None,  # Populated later
                        entry['timeSpentSeconds'],
                        parser.parse(entry['startDate']).date(),
                        entry['description']
                    )
                )

            return worklogs
        else:
            raise Exception(
                'Error when requesting Jira: {code} {error}'.format(
                    code=response.status_code,
                    error=response.text
                ))

    def create_worklog(self, worklog):
        values = {
            "issueId": worklog.id,
            "authorAccountId": self.account_id,
            "description": worklog.comment,
            "startDate": worklog.date.strftime('%Y-%m-%d'),
            "startTime": "02:00:00",
            "timeSpentSeconds": worklog.duration
        }

        return self.tempo_session.post(
            self.worklog_create_url,
            json=values,
        )

    def delete_worklog(self, worklog):
        url = urljoin(self.worklog_url, worklog.id)
        return self.tempo_session.delete(url)

    def populate_issue_field(self, logs):
        new_logs = []
        errors = defaultdict(list)
        for log in logs:
            res = self.get_issue(log.jira_ref, "id,key")
            if res.status_code == 200:
                data = res.json()
                # Ensure both keys are properly set
                # as this log entry can come from gtimelog (no id)
                # or from tempo api (no key)
                log.id = data["id"]
                log.issue = data["key"]
                new_logs.append(log)
            else:
                errors[res.reason].append(log)

        return new_logs, errors

    def repair_estimate(self, issue):
        response = self.get_issue(issue)
        if not response.ok:
            raise Exception(f"Cannot fetch information for issue: {issue}")
        try:
            timetracking = response.json()['fields']['timetracking']
            original_estimate_s = timetracking['originalEstimateSeconds']
            original_estimate = timetracking['originalEstimate']
            timespent_s = timetracking['timeSpentSeconds']
            diff_o_e_vs_t_s = original_estimate_s - timespent_s
            remaining_estimate_s = diff_o_e_vs_t_s if diff_o_e_vs_t_s >= 0 else 0

            payload = {
                "fields": {
                    "timetracking": {
                        "originalEstimate": original_estimate,
                        "originalEstimateSeconds" : original_estimate_s,
                        "remainingEstimateSeconds": remaining_estimate_s,
                        "remainingEstimate": self.convert_seconds_to_jira_time(remaining_estimate_s),
                    }
                }
            }
            url = urljoin(self.jira_url, f"/rest/api/latest/issue/{issue}")
            put_response = self.jira_session.put(url, json=payload)
        except KeyError as e:
            raise Exception(f"repair_estimate: impossible to edit remaining estimate for {issue}. Check permissions and jira workflow. Maybe the `originalEstimate` field is not editable.")
