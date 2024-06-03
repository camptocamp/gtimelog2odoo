# Quick migration guide to cloud instance


## Get a JIRA token

Account -> Security -> Tokens

## Get a Tempo token

Apps -> Tempo -> Api integration (left menu) -> new token


## LastPass and set_passwords

Add those keys as entries on you LP then login using lastpass cli and run

```
    lpass ls|grep token
```

where "token" is something that matches the name of your tokens' entries.

Get the IDs of the entries and modify your `set_passwords` like

```
    export JIRA_API_TOKEN=$(lpass show XXXXXXX -p)
    export TEMPO_API_TOKEN=$(lpass show XXXXXXX -p)
```

replacing XXX w/ your IDs.

Run `. ./set_passwords`.


## Config

Modify your `gtimelogrc` like

```
    jira_url = https://camptocamp.atlassian.net/
    tempo_url = https://api.tempo.io/4/
    jira_account_email = me.work@camptocamp.com
```
## Update gtimelog2odoo

```
    git pull gtimelog2odoo
    pip install odoorpc
```

Now you are ready to go! :)
