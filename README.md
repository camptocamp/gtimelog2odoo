# GTimeLog Exporter

This helper is designed to push the attendances and worklogs from GTimeLog
respectively to Odoo and Jira.

## Usage

> usage: exporter.py [-h] [-c CONFIG] [-w WEEK] [-y YEAR] [--no-interactive]

* -c : Configuration file location (default: ./gtimelogrc)
* -w : Week number to synchronize (default: current week /!\ Python based)
* -y : Year of the week to synchronize (default: current year)
* --no-interactive : Do not prompt for passwords or confirmations

## Configuration file

By default, the script will look for the configuration file in the same folder as itself.
You can change the location with the parameter described above.

After getting the script, copy the file `gtimelogrc.example` to `gtimelogrc` and add your changes.

### Aliases

You can add as many aliases as you want in the corresponding configuration file section.
Each alias is a key/value combination:
> daily_alias = BSDEV-42

### Passwords

Upon script execution, you will be prompted for your Odoo and Jira passwords.

You can also use `ODOO_PASSWORD` and `TEMP_PASSWORD` environment variables to pass to the script.
If both passwords are the same, you can use the environment variable `ALL_PASSWORD`.
In case the flag non-interactive is set, it is mandatory to use environment variables.

## GTimeLog Entry Format

The script will parse GTimeLog entries with the following format:

> [Project|Alias:] [JiraTask] LogComment [| PersonalComment]

Where

* Project is used solely in GTimeLog to group the entries by project
* Alias is a task alias. It is mutually exclusive with JiraTask
* JiraTask is a Jira task key (e.g. BSABC-42)
* LogComment is the description of your work. It will be reported in Jira
* PersonalComment will be stripped from the entry before processing

### Examples

* Log work to task BSMP-42 with comment "Investigate Issue"
  > my_project: BSMP-42 Investigate issue | this customer drives me mad
* Log work to task aliased by `daily_alias` with comment "Daily Meeting"
  > daily_alias: Daily Meeting
* Log work to task BSXYZ-14 with comment "Entry without project". Entry will not be grouped in GTimeLog view
  > BSXYZ-14 Entry without project

## Roadmap

* Check if conflicting worklogs could be updated instead of deleting and recreating them
* Update the remaining estimate on the Jira task instead of setting it to 0
* Improve GTimeLog entry parsing
* Optimize logs aggregation
* Better error management
* Build a package
