import json
import requests

from dateutil import parser

from .multi_log import MultiLog


class TempoClient(object):
    def __init__(self, config):
        self.jira_url = config.get('jira_url')
        self.tempo_api = config.get('tempo_api')
        self.tempo_user = config.get('tempo_user')
        self.tempo_password = config.get('tempo_password')
        self.session = self.init_session()

    def init_session(self):
        session = requests.Session()
        session.auth = (self.tempo_user, self.tempo_password)

        api = self.jira_url + 'rest/api/2'
        resp = session.get('%s/myself' % api)
        if resp.ok:
            return session
        elif resp.status_code == 401:
            raise Exception("Error: Incorrect password or username.")
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

    def get_worklogs(self, date_window):
        params = {
            'jira_url': self.jira_url,
            'tempo_api': self.tempo_api,
            'date_from': date_window.start.date().isoformat(),
            'date_to': date_window.stop.date().isoformat(),
            'tempo_user': self.tempo_user,
        }

        url = "{jira_url}{tempo_api}worklogs" \
              "?username={tempo_user}&dateFrom={date_from}&dateTo={date_to}"

        response = self.session.get(url.format(**params))

        if response.status_code == 200:
            entries = json.loads(response.text)
            worklogs = []

            for entry in entries:
                worklogs.append(
                    MultiLog(
                        entry['id'],
                        entry['issue']['key'],
                        entry['timeSpentSeconds'],
                        parser.parse(entry['dateStarted']).date(),
                        entry['comment']
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
        params = {
            'jira_url': self.jira_url,
            'tempo_api': self.tempo_api
        }
        url = "{jira_url}{tempo_api}worklogs/"

        values = {
            "issue": {
                "key": worklog.issue,
                "remainingEstimateSeconds": 0
            },
            "author": {
                "name": self.tempo_user
            },
            "comment": worklog.comment,
            "dateStarted": worklog.date.strftime('%Y-%m-%dT02:00:00.000+0000'),
            "timeSpentSeconds": worklog.duration
        }

        return self.session.post(
            url.format(**params),
            json=values,
            headers={"Content-Type": "application/json"}
        )

    def delete_worklog(self, worklog):
        params = {
            'jira_url': self.jira_url,
            'tempo_api': self.tempo_api,
            'id': worklog.id
        }
        url = "{jira_url}{tempo_api}worklogs/{id}/"
        return self.session.delete(url.format(**params))
