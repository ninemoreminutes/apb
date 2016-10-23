# Python
from ConfigParser import SafeConfigParser
import os


def load_config(filename='apb.ini'):
    '''
    '''
    defaults = {'command': 'ansible-playbook'}
    try:
        cfg = SafeConfigParser(defaults, allow_no_value=True)
    except TypeError:
        cfg = SafeConfigParser(defaults)
    cfg.optionxform = str
    found_filename = None
    if filename == os.path.basename(filename):
        base_filename = filename
        cwd = os.getcwd()
        while cwd:
            filename = os.path.join(cwd, base_filename)
            if os.path.exists(filename):
                found_filename = filename
                break
            if os.path.dirname(cwd) == cwd:
                break
            cwd = os.path.dirname(cwd)
    else:
        found_filename = filename
    if found_filename:
        cfg.readfp(open(found_filename, 'r'), found_filename)
    return cfg

def update_opts_from_config(cfg, optlist, opts=None, section=None, optsdict=None):
    opts = opts or {}
    
    optlist2 = {
        'command': {},
        'playbook': {},
    }
    for opt in optlist:
        if opt['type'] is list or opt['type'] is str:
            func = lambda x: str(x or '')
        elif opt['type'] is int:
            func = lambda x: int(x or 0)
        elif opt['type'] is bool:
            func = lambda x: bool(str(x).strip()) and bool(str(x).strip().lower()[0] in ('1', 't', 'y'))
        else:
            func = opt['type']
        opt_key = opt.get('long', opt.get('short', '')).replace('-', '_')
        if 'short' in opt:
            optlist2[opt['short']] = {'key': opt_key, 'func': func}
        if 'long' in opt:
            optlist2[opt['long']] = {'key': opt_key, 'func': func}
            if '-' in opt['long']:
                optlist2[opt['long'].replace('-', '_')] = {'key': opt_key, 'func': func}
    
    items = []
    if section:
        if 'included_sections' not in opts:
            opts['included_sections'] = []
        if section not in opts['included_sections']:
            items.extend(cfg.items(section))
            opts['included_sections'].append(section)
    if optsdict:
        items.extend(optsdict.items())
    if 'include' in dict(items):
        update_opts_from_config(cfg, optlist, opts, section=dict(items)['include'])
    for k,v in items:
        #print 'update', k, v
        if k in optlist2:
            key = optlist2[k].get('key', k)
            func = optlist2[k].get('func', str)
            #print key, func, v
            opts[key] = func(v)
        elif len(k) > 1 and k == k.upper():
            if 'env' not in opts:
                opts['env'] = {}
            opts['env'][k] = v
        elif k == 'include':
            pass
        else:
            print 'ignoring option', k
            

    return opts
