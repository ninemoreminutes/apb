# Python
import optparse
import re
import subprocess
import sys

# Setuptools/APB
try:
    import pkg_resources
    __version__ = pkg_resources.require('apb')[0].version
except:
    from apb import __version__

# APB
from .config import load_config, update_opts_from_config


def parse_ansible_playbook_help(help_text):
    '''
    Parse the output of "ansible-playbook -h" and use it to generate list of
    possible command line / config options.
    '''
    # Parse lines output from help.
    re_short = re.compile(r'^-([A-Za-z0-9]),??$')
    re_long = re.compile(r'^--([A-Za-z0-9a-z_-]+?)(?:=([A-Z0-9_-]+?))??$')
    re_meta = re.compile(r'^([A-Z0-9_-]+?),$')
    all_opts = []
    current_opt = []
    for line in help_text.splitlines():
        if line.lstrip().startswith('-'):
            opt_found = False
            for n, part in enumerate(line.split()):
                m_short = re_short.match(part)
                m_long = re_long.match(part)
                m_meta = re_meta.match(part)
                if m_short:
                    if current_opt and not opt_found:
                        all_opts.append(current_opt)
                        current_opt = []
                    opt_found = True
                    current_opt.append(('short', m_short.groups()[0]))
                elif m_long:
                    if current_opt and not opt_found:
                        all_opts.append(current_opt)
                        current_opt = []
                    opt_found = True
                    current_opt.append(('long', m_long.groups()[0]))
                    if m_long.groups()[1]:
                        current_opt.append(('meta', m_long.groups()[1]))
                elif m_meta and current_opt and current_opt[-1][0] == 'short':
                    current_opt.append(('meta', m_meta.groups()[0]))
                else:
                    current_opt.append(('doc', part))
        elif line.startswith(' '):
            for part in line.split():
                current_opt.append(('doc', part))
    if current_opt:
        all_opts.append(current_opt)
    
    # Build list of dicts with option parameters.
    opts = []
    for opt_data in all_opts:
        opt_dict = dict(opt_data)
        opt_dict['doc'] = ' '.join([x[1] for x in opt_data if x[0] == 'doc'])
        if opt_dict.get('long', '') in ('version',):
            continue
        elif opt_dict.get('long', '') in ('forks', 'timeout'):
            opt_dict['type'] = int
        elif opt_dict.get('long', '') in ('extra-vars',):
            opt_dict['type'] = list
        elif not opt_dict.get('meta', ''):
            opt_dict['type'] = bool
        else:
            opt_dict['type'] = str
        opts.append(opt_dict)
    return opts


def update_parser_from_options(parser, options):
    '''
    Update option parser from parsed ansible-playbook options.
    '''
    for opt in options:
        opt_args = []
        opt_kwargs = {}
        if 'short' in opt:
            opt_args.append('-%s' % opt['short'])
        if 'long' in opt:
            opt_args.append('--%s' % opt['long'])
            opt_kwargs['dest'] = opt['long'].replace('-', '_')
        if 'doc' in opt:
            opt_kwargs['help'] = opt['doc']
        if 'meta' in opt:
            opt_kwargs['metavar'] = opt['meta']
        if opt['type'] is bool:
            if opt.get('long', '') in ('help', 'version'):
                opt_kwargs['action'] = opt['long']
            else:
                opt_kwargs['action'] = 'store_true'
                opt_kwargs['default'] = False
        elif opt['type'] is int:
            opt_kwargs['type'] = int
        elif opt['type'] is list:
            opt_kwargs['action'] = 'append'
            opt_kwargs['default'] = []
        parser.add_option(*opt_args, **opt_kwargs)


def main():
    try:
        ap_version = subprocess.check_output(['ansible-playbook', '--version'])
        ap_help = subprocess.check_output(['ansible-playbook', '-h'])
    except OSError:
        print >> sys.stderr, 'ansible-playbook not found!'
        sys.exit(1)
    opts = parse_ansible_playbook_help(ap_help)
    ap_version = ap_version.splitlines()[0].strip()
    version = '%%prog %s (using %s)' % (__version__, ap_version)
    usage = '%prog [options] [cmd | cmd1+cmd2 | cmd+site.yml | site.yml ...]'
    description = ''
    parser = optparse.OptionParser(usage=usage, description=description,
                                   version=version, add_help_option=False)
    update_parser_from_options(parser, opts)
    options, args = parser.parse_args()
    cfg = load_config('apb.ini')
    
    #print cfg.sections()
    #print options, args
    #print type(options), dir(options)
    opts2 = {}
    for arg in args:
        cmds = arg.split('+')
        opts2 = update_opts_from_config(cfg, opts, section='default')
        for cmd in cmds:
            if cmd.endswith('.yml') or cmd.endswith('.yaml'):
                #print 'playbook', cmd
                opts2 = update_opts_from_config(cfg, opts, opts2, optsdict={'playbook': cmd})
            else:
                #print 'section', cmd
                opts2 = update_opts_from_config(cfg, opts, opts2, section=cmd)
        opts2 = update_opts_from_config(cfg, opts, opts2, optsdict=vars(options))
    
    for k,v in opts2.items():
        print k, '=', v


    
    #subprocess.call(["ansible-playbook", "-h"])


