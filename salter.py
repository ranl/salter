'''
 Salter Runner
----------------

This runner is used as a deployment/orchestration tool.
it will access a state-like files that will specify what states/modules/runners to publish
and make sures that they are executed apllied correctly
The salt-master should have a salt-minion daemon installed and running for the mine system

 salter files examples
-----------------------

Ping All Minions:
  ping:
    tgt: '*'

Salt Sync All Data:
  module:
    func: saltutil.sync_all
    tgt: '*'
    timeout: 999

Common State:
  state:
    state: common.vmware
    tgt: 'kernel:Linux'
    expr_form: grain
    timeout: 999

Build Windows Repository:
  winrepo_genrepo
'''

# Python std libs
import logging
import sys
import types

# Salt libs
import salt.client
import salt.runner
import salt.utils
import salt.output.highstate
import salt.renderers.yaml
from salt.exceptions import SaltSystemExit

# Logger
log = logging.getLogger(__name__)


###############
### Private ###
###############

class _nullOut():
    '''
    Auxilary class to disable stdout
    '''
    def write(self, s):
        pass


def _render(filename):
    '''
    Render a salter file
    '''
    
    with open( filename, 'r' ) as f:
        return salt.renderers.yaml.render(f)


def _validateNonZeroDiscovery(minions, ret):
    '''
    Validate that we've discovered at least 1 minion
    '''
    
    log.info('discovered the minions: {0}'.format(minions))
    if not minions:
        ret['result'] = False
        ret['comment'] = 'discovered 0 minions'
        return False
    return True


def _checkStateReturn(cmdret, minions):
    '''
    Parse a return states run on the minion
    '''
    
    ret = {
        'errors' : {},
        'no_returns': [],
        'returned_empty': [],
    }
    
    for minion in minions:
        try:
            if isinstance(cmdret[minion], str):
                ret['empty'].append(minion)
                continue
            elif isinstance(cmdret[minion], list):
                if not ret['errors'][minion]:
                    ret['errors'][minion] = []
                ret['errors'][minion].append(cmdret[minion])
                continue
            for st in cmdret[minion]:
                if not cmdret[minion][st]['result']:
                    if not ret['errors'][minion]:
                        ret['errors'][minion] = []
                    ret['errors'][minion].append(st)
        except KeyError:
            ret['returned_empty'].append(minion)
    
    return ret


def _discoverMinions(tgt, expr_form='glob'):
    '''
    Return a set of minion via the mine system
    '''

    minions = salt.client.Caller().sminion.functions['mine.get'](tgt, 'test.ping', expr_form)
    return list(set(minions.keys()))


def _genValidFunctions():
    '''
    Return a hashmap of valid salter functions
    '''
    
    ret = {}
    for key in globals():
        if type(globals()[key]) == types.FunctionType and \
                not key.startswith('_') and \
                key != 'go':
            ret[key] = globals()[key]
    return ret


def _printHeader(string, color='BLUE', prefix='Executing Stage:'):
    '''
    Print Header
    '''

    h = '*********************************'
    print '{0}{1}{2}'.format(
        salt.utils.get_colors()[color],
        '*'*len(string) + '*'*len(prefix) + '*'*len(h),
        salt.utils.get_colors()['ENDC']
    )
    print '{0}*************** {3} {1} ***************{2}'.format(
        salt.utils.get_colors()[color],
        string,
        salt.utils.get_colors()['ENDC'],
        prefix,
    )
    print '{0}{1}{2}'.format(
        salt.utils.get_colors()[color],
        '*'*len(string) + '*'*len(prefix) + '*'*len(h),
        salt.utils.get_colors()['ENDC']
    )


def _printStage(ret):
    '''
    Print the current stage to the console
    '''

    color = salt.utils.get_colors()['GREEN']
    if not ret['result']:
        color = salt.utils.get_colors()['RED_BOLD']
    else:
        for k in ret['changes']:
            if ret['changes'][k]:
                color = salt.utils.get_colors()['CYAN']
                break

    print '{0}Stage: {1}{2}'.format(color, ret['name'], salt.utils.get_colors()['ENDC'])
    print '{0}  Result: {1}{2}'.format(color, ret['result'], salt.utils.get_colors()['ENDC'])
    print '{0}  Comment: {1}{2}'.format(color, ret['comment'], salt.utils.get_colors()['ENDC'])
    if ret['changes'] and ret['changes'].keys()[0] == 'state':
        for host in ret['changes']['state']:
            salt.output.display_output({host: ret['changes']['state'][host]}, 'highstate', opts=__opts__)
    else:
        print '{0}  Changes: {1}{2}'.format(color, ret['changes'], salt.utils.get_colors()['ENDC'])
    print


def _printSummary(rets):
    '''
    Print a small summary in the end of the stages
    '''

    color = 'LIGHT_GREEN'
    if not rets[-1]['result']:
        color = 'RED_BOLD'

    _printHeader('Salter is done !', color, '')
    stagesToPrint = '{0}Stages: \n{1}'.format(salt.utils.get_colors()['LIGHT_GREEN'], salt.utils.get_colors()['ENDC'])
    for stage in rets:
        color = salt.utils.get_colors()['LIGHT_GREEN']
        if not stage['result']:
            color = salt.utils.get_colors()['RED_BOLD']
        stagesToPrint += '{0}  {1} {2}\n'.format(
            color,
            stage['name'],
            salt.utils.get_colors()['ENDC']
        )
    print stagesToPrint


def _execStage(stage, conf, functions):
    '''
    Execute a stage and return it's result
    '''
    
    if not isinstance(conf, dict):
        conf = {conf: {}}
    funcName = conf.keys()[0]
    args = conf[funcName]

    if funcName in functions:
        origStdOut = sys.stdout
        sys.stdout = _nullOut()
        ret = functions[funcName](stage, **args)
        sys.stdout = origStdOut
    else:
        ret = {'name': stage,
               'result': False,
               'changes': {},
               'comment': '{0} is not a valid Salter function'.format(funcName)}

    return ret


##############
### Public ###
##############


def _endFuncFromCli(ret):
    '''
    When a salter function ends from a cli
    this function deals with printing and exit status
    '''
    
    _printStage(ret)
    if not ret['result']:
        raise SaltSystemExit('Error')


##############
### PUBLIC ###
##############
        
def ping(name, tgt, timeout=None, expr_form='glob', cli=True):
    '''
    Make sure all the named minions are connected

    Example::

        check.alive.all:
          ping:
            - name: 'roles:webserver'
            - expr_form: grain

    CLI Examples:

    .. code-block:: bash

        salt-run salter.ping 'alias name' \* 10
        salt-run salter.ping 'alias name' 'roles:web-server' cmd.run '["service tomcat status"]' expr_form=grain
    '''
    
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}
    
    # discover targeted minions
    minions = _discoverMinions(tgt, expr_form)
    _validateNonZeroDiscovery(minions, ret)
    if not ret['result']:
        return ret

    # ping'em !
    ret['comment'] = ''
    cmdret = salt.client.LocalClient().cmd(tgt, 'test.ping', [], timeout, expr_form)
    ret['changes'] = {'ping': {}}
    ret['changes']['ping'].update({'alive': cmdret.keys()})

    # verify that all the minion returned
    no_return = list(set(minions) - set(ret['changes']['ping']['alive']))
    if no_return:
        ret['result'] = False
        ret['changes']['ping'].update({'dead': no_return})
        ret['comment'] = 'the following minions are dead {0}'.format(no_return)

    if cli:
        _endFuncFromCli(ret)
    return ret


def module(name, tgt, func, args=[], timeout=None, expr_form='glob', cli=True):
    '''
    Execute a module on the targeted minions

    Salter Example::

        test.ping.everyone:
          module:
            - name: test.ping
            - tgt: '*'

    CLI Examples:

    .. code-block:: bash

        salt-run salter.module 'alias name' \* cmd.run '["ls -l"]' 10
        salt-run salter.module 'alias name' 'roles:web-server' cmd.run '["service tomcat status"]' expr_form=grain
    '''
    
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    # discover targeted minions
    minions = _discoverMinions(tgt, expr_form)
    if not _validateNonZeroDiscovery(minions, ret):
        return ret

    # execute the module
    cmdret = salt.client.LocalClient().cmd(tgt, func, args, timeout, expr_form)
    ret['changes'] = cmdret

    # verify that all the minion returned
    no_return = list(set(minions) - set(cmdret.keys()))
    if no_return:
        ret['result'] = False
        ret['comment'] = 'the following minions did not return: {0}'.format(no_return)

    if cli:
        _endFuncFromCli(ret)
    return ret


def state(name, tgt, state, timeout=None, expr_form='glob', cli=True):
    '''
    Execute a module on the targeted minions

    Salter Example::

        common:
          state:
            - tgt: '*'

    CLI Examples:

    .. code-block:: bash

        salt-run salter.state 'alias name' \* common 10
        salt-run salter.state 'alias name' 'roles:web-server' tomcat 999 expr_form=grain
    '''
    
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    # discover targeted minions
    minions = _discoverMinions(tgt, expr_form)
    if not _validateNonZeroDiscovery(minions, ret):
        return ret

    # apply the state
    cmdret = salt.client.LocalClient().cmd(tgt, 'state.sls', [state], timeout, expr_form)
    ret['changes'] = {'state': cmdret}
    ret['comment'] = ''

    # verify that all the minion returned and all is True
    ret_err  =_checkStateReturn(cmdret, minions)

    if ret_err['errors']:
        ret['result'] = False
        ret['changes'].update({'errors': ret_err['errors']})
        ret['comment'] = 'the following minions had Flase states: {0}'.format(ret_err['errors'].keys())
    if ret_err['returned_empty']:
        ret['result'] = False
        ret['changes'].update({'empty': ret_err['returned_empty']})
        if ret['comment']:
            ret['comment'] += '\n'
        ret['comment'] = 'the following minions had returned but without state data: {0}'.format(ret_err['returned_empty'])
    if ret_err['no_returns']:
        ret['result'] = False
        ret['changes'].update({'no_returns': ret_err['no_returns']})
        if ret['comment']:
            ret['comment'] += '\n'
        ret['comment'] += 'the following minions did not return: {0}'.format(ret_err['no_returns'])

    if cli:
        _endFuncFromCli(ret)
    return ret

  
def winrepo_genrepo(name, cli=True):
    '''
    Execute the winrepo.genrepo runner

    Salter Example::
        
        init.winrepo:
          winrepo_genrep

    CLI Examples:

    .. code-block:: bash

        salt-run salter.winrepo_genrepo
    '''
    
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    pillar = salt.client.Caller().sminion.functions['pillar.data']()
    runner = salt.runner.RunnerClient(pillar['master'])
    ret['changes'] = {'winrepo': runner.cmd('winrepo.genrepo', [])}
    if not ret['changes']:
        ret['result'] = False
        ret['comment'] = 'winrepo returned empty !'

    if cli:
        _endFuncFromCli(ret)
    return ret


def go(fn, out=True):
    '''
    Execute the salter file
    
    CLI Examples:

    .. code-block:: bash

        salt-run salter.go /path/to/file.salter
        salt-run salter.go /path/to/file.salter False
    '''
    
    functions = _genValidFunctions()
    data = _render(fn)
    error = False
    
    rets = []
    for stage in data:
        conf = data[stage]
        if not isinstance(conf, dict):
            conf = {conf: {}}
        conf[conf.keys()[0]].update({'cli': False})
        if out:
            _printHeader(stage)
        ret = _execStage(stage, conf, functions)
        if out:
            _printStage(ret)
        rets.append(ret)
        if not ret['result']:
            error = True
            break
    
    if out:
        _printSummary(rets)
    if error:
        raise SaltSystemExit('Error')
    
    return rets
