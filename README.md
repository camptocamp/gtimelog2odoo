# GTimeLog Exporter

This helper is designed to push the attendances and worklogs from GTimeLog
respectively to Odoo and Jira.

## Usage

> usage: exporter.py [-h] [-c CONFIG] [-w WEEK] [-y YEAR] [--no-interactive]

* -c : Configuration file location (default: ./gtimelogrc)
* -w : Week number to synchronize (default: current week /!\ Python based)
* -y : Year of the week to synchronize (default: current year)
* --no-interactive : Do not prompt for passwords or confirmations

TIP: Week number can be a negative number like -1 to use previous week.
The year will be computed automatically based on current year.
-y parameter will be ignored.

For instance: if current week is the 1st of 2020 and you push -w 2
it will push week 51 of 2019.


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

TIP: copy `set_passwords.example` to `set_passwords` and modify it according to your LP passwords.
Then run it to set both passwords on the fly with:

```
. ./set_passwords
```

## GTimeLog Entry Format

The script will parse GTimeLog entries with the following format:

> [TASK|alias for a task]: description | comment

or if you want to keep the category for your own usage:

> category: [TASK|alias for a task] description | comment

Where

* "TASK" is the card ID on JIRA, eg: "BSMNT-1"
* "alias for a task" is an alias matching your alias configuration, eg: "mgmt" => BS-445
* "description" is what you have done
* (opt) "comment" will be stripped and won't be pushed to Tempo

if `line_format` is `categorized`
* (opt) "category" for instance a project name it won't be pushed

configuration option:


### Examples

* Log work to task BSMP-42 with description "Investigate Issue"
  > BSMP-42: Investigate issue
* Log work to task aliased by `daily` with description "Daily Meeting"
  > daily: Daily Meeting

## Roadmap

* FIX past week number handling: as of today you have to use week number -1
* Log warnings if an entry does not match a card on JIRA
* Check if conflicting worklogs could be updated instead of deleting and recreating them
* Update the remaining estimate on the Jira task instead of setting it to 0
* Improve GTimeLog entry parsing
* Optimize logs aggregation
* Better error management
* Build a package
