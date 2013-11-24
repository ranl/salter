Salter
======

```bash
salt-run salter.go /srv/salt/base/deploy_my_app.salter
```

/srv/salt/base/deploy_my_app.salter
```yaml
Ping All Minions:
  ping:
    tgt: '*'

Salt Sync All Data:
  module:
    func: saltutil.sync_all
    tgt: '*'
    timeout: 999

Update Mine System:
  module:
    func: mine.update
    tgt: '*'
    timeout: 999

Common State:
  state:
    state: common
    tgt: 'kernel:Linux'
    expr_form: grain
    timeout: 999

Build Windows Repository:
  winrepo_genrepo

Deploy Application:
  state:
    state: myapp
    tgt: 'roles:app-server'
    expr_form: grain
    timeout: 9999
```

SaltStack Runner - aggregates salt commands within a single runner 

This runner is used as a deployment/orchestration tool.
it will access a state-like files (not the same syntax) that will specify what states/modules/runners to execute,
and make sure that they are apllied correctly.

There is no jinja rendering at the moment and no require/watch options,
the order of the functions will be as stated in the salter file


Dependencies
============
The salt-master should have a salt-minion daemon installed
The mine system should be configured on all the minions
salt >= 0.17
if you are running salt 0.17.0 or 0.17.1 update your mine module https://github.com/saltstack/salt/issues/8144

Why do I need this
==================
this solves the same problems that the state.over runner is solving: ordering states executions

make sure all the minions returned something:

salt publish the commands to the minions in an asynchronous fashion
so you don't always get the response back from all the minions, depending on how much timeout you've specified.
when salter publish a state / module the returned data will be crossed reference with the mine system to check that all the minion returned somehing.
if it was a state, it will also check if any minion returned a False state.
in case of any error the runner will stop immediately

Disclaimer
==========
This is still under development so there could be bugs
Please let me know on any bugs / improvements you have in mind
