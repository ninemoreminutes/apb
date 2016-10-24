# Python
import argparse
from ConfigParser import SafeConfigParser
import copy
import logging
import os
import re
import subprocess
import sys

# Setuptools/APB
try:
    import pkg_resources
    __version__ = pkg_resources.require('apb')[0].version
except:
    from apb import __version__

logger = logging.getLogger('apb')


class ExtendAction(argparse.Action):

    def __init__(self, option_strings, dest, **kwargs):
        super(ExtendAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if not getattr(namespace, self.dest, None):
            setattr(namespace, self.dest, [])
        getattr(namespace, self.dest).extend(values)


class APB(object):

    COMMAND = 'ansible-playbook'

    def __init__(self, argv=None):
        try:
            ap_version = subprocess.check_output([self.COMMAND, '--version'])
            ap_help = subprocess.check_output([self.COMMAND, '-h'])
        except OSError:
            logger.error('%s not found!', self.COMMAND)
            sys.exit(1)
        self.arg_parser = self._build_arg_parser(ap_version, ap_help)
        self.ns_default = self.arg_parser.parse_known_args([])[0]
        self.args = self.arg_parser.parse_args()
        print self.args
        self.cfg_parser = self._load_cfg_parser(self.args.apb_ini)
        self.configs = []
        for config in (self.args.configs or ['default']):
            config_ns = self._load_config(config)
            self.configs.append((config, config_ns))
            print config, config_ns

    def __call__(self):
        for config, config_ns in self.configs:
            cmd = self._build_cmd_from_config(config_ns)
            print config, cmd

            subprocess.call(cmd)

    def _build_arg_parser(self, ap_version, ap_help):
        '''
        Build an ArgumentParser instance with APB-specific options and options
        derived from ansible-playbook help.
        '''
        ap_short_version = ap_version.splitlines()[0].strip()
        version = '%(prog)s {} (using {})'.format(__version__, ap_short_version)
        usage = '%(prog)s [options] [cfg | cfg1+cfg2 | cfg+pb.yml | pb.yml ...]'
        arg_parser = argparse.ArgumentParser(usage=usage, add_help=False)

        apb_parser = arg_parser.add_argument_group('APB Options')
        apb_parser.add_argument(nargs='*', action=ExtendAction, dest='configs',
                                metavar='cfg', help='run ansible-playbook with '
                                'the options specified by config section "cfg"')
        apb_parser.add_argument(nargs='*', action=ExtendAction, dest='configs',
                                metavar='cfg1+cfg2', help='run ansible-playbook'
                                ' with the combined options of multiple config '
                                'sections')
        apb_parser.add_argument(nargs='*', action=ExtendAction, dest='configs',
                                metavar='cfg+pb.yml', help='run '
                                'ansible-playbook with the options specified by'
                                ' config section "cfg" using playbook "pb.yml"')
        apb_parser.add_argument(nargs='*', action=ExtendAction, dest='configs',
                                metavar='pb.yml', help='run '
                                'ansible-playbook using playbook "pb.yml"')
        apb_parser.add_argument('--apb-ini', metavar='APB_INI',
                                default='apb.ini', help='default apb config '
                                'file to read')
        apb_parser.add_argument('-h', '--help', action='help', help='show this '
                                'help message and exit')
        apb_parser.add_argument('--version', action='version', version=version)

        ap_opt_list = self._parse_ansible_playbook_help(ap_help)
        self.option_params = self._build_option_params(ap_opt_list)
        self._update_arg_parser_from_option_params(arg_parser, self.option_params)
        return arg_parser

    def _parse_ansible_playbook_help(self, ap_help):
        '''
        Parse the output of "ansible-playbook -h" and use it to generate a list
        of possible command line / config options.
        '''
        re_group = re.compile(r'^([A-Z][A-Za-z0-9 ]+?):$')
        re_short = re.compile(r'^-([A-Za-z0-9]),??$')
        re_long = re.compile(r'^--([A-Za-z0-9a-z_-]+?)(?:=([A-Z0-9_-]+?))??,??$')
        re_meta = re.compile(r'^([A-Z0-9_-]+?),$')
        all_opts = []
        current_opt = []

        for line in ap_help.splitlines():
            if not line.strip():
                if current_opt:
                    all_opts.append(current_opt)
                    current_opt = []
            elif line.lstrip().startswith('-'):
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
                        current_opt.append(('short', m_short.group(1)))
                    elif m_long:
                        if current_opt and not opt_found:
                            all_opts.append(current_opt)
                            current_opt = []
                        opt_found = True
                        current_opt.append(('long', m_long.group(1)))
                        if m_long.group(2):
                            current_opt.append(('meta', m_long.group(2)))
                    elif m_meta and current_opt and current_opt[-1][0] == 'short':
                        current_opt.append(('meta', m_meta.group(1)))
                    else:
                        current_opt.append(('doc', part))
            else:
                m_group = re_group.match(line.strip())
                if m_group:
                    if current_opt:
                        all_opts.append(current_opt)
                        current_opt = []
                    current_opt.append(('group', m_group.group(1)))
                elif line.startswith(' '):
                    for part in line.split():
                        current_opt.append(('doc', part))

        if current_opt:
            all_opts.append(current_opt)

        return all_opts

    def _build_option_params(self, ap_opt_list):
        '''
        Build list of tuples with option parameters: (args, kwargs, group_dict).
        '''
        option_params = []
        opt_group = {}

        for opt_data in ap_opt_list:
            opt_doc = ' '.join([x[1] for x in opt_data if x[0] == 'doc'])

            if 'group' in [x[0] for x in opt_data]:
                group_title = [x[1] for x in opt_data if x[0] == 'group'][0]
                if group_title == 'Options':
                    group_title = 'Ansible Playbook Options'
                opt_group = dict(group_title=group_title, group_desc=opt_doc)
                continue

            opt_args = []
            opt_kwargs = {}
            opt_kwargs['help'] = opt_doc
            for opt_type, opt_val in opt_data:
                if opt_type == 'short':
                    opt_args.append('-{}'.format(opt_val))
                elif opt_type == 'long':
                    opt_args.append('--{}'.format(opt_val))
                    if 'dest' not in opt_kwargs:
                        opt_kwargs['dest'] = opt_val.replace('-', '_')
                elif opt_type == 'meta':
                    opt_kwargs['metavar'] = opt_val
            if 'dest' not in opt_kwargs:
                for opt_type, opt_val in opt_data:
                    if opt_type == 'short':
                        opt_kwargs['dest'] = opt_val
                        break

            if opt_kwargs.get('dest', '') in {'forks', 'timeout'}:
                opt_kwargs['type'] = int
                opt_kwargs['default'] = None
            elif opt_kwargs.get('dest', '') in {'verbose'}:
                opt_kwargs['action'] = 'count'
                opt_kwargs['default'] = None
            elif opt_kwargs.get('dest', '') in {'extra_vars'}:
                opt_kwargs['type'] = list
                opt_kwargs['action'] = 'append'
                opt_kwargs['default'] = []
            elif not opt_kwargs.get('metavar', ''):
                if opt_kwargs.get('dest', '') in {'help', 'version'}:
                    opt_kwargs['action'] = opt_kwargs['dest']
                else:
                    opt_kwargs['action'] = 'store_true'
                    opt_kwargs['default'] = None
            else:
                opt_kwargs['type'] = str
                opt_kwargs['default'] = None

            option_params.append((opt_args, opt_kwargs, opt_group))

        return option_params

    def _update_arg_parser_from_option_params(self, arg_parser, option_params):
        '''
        Update arg parser from parsed ansible-playbook options.
        '''
        group_title = None
        parser = arg_parser
        for opt_args, opt_kwargs, opt_group in option_params:
            if opt_kwargs.get('dest', '') in {'help', 'version'}:
                continue
            if opt_group.get('group_title', None) != group_title:
                group_title = opt_group['group_title']
                group_desc = opt_group.get('group_desc', '') or None
                parser = arg_parser.add_argument_group(group_title, group_desc)
            parser.add_argument(*opt_args, **opt_kwargs)

    def _load_cfg_parser(self, filename='apb.ini'):
        '''
        Load config parser from specific INI filename.
        '''
        defaults = {}
        try:
            cfg_parser = SafeConfigParser(defaults, allow_no_value=True)
        except TypeError:
            cfg_parser = SafeConfigParser(defaults)
        cfg_parser.optionxform = str
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
            cfg_parser.readfp(open(found_filename, 'r'), found_filename)
        return cfg_parser

    def _remove_ns_defaults(self, ns, ns_default=None):
        '''
        Given a ns (argparse.Namespace), remove any items that are the same as
        the default.
        '''
        ns_default = ns_default or self.ns_default
        for attr in vars(ns).keys():
            if getattr(ns, attr) == getattr(ns_default, attr, None):
                delattr(ns, attr)
        return ns

    def _load_config(self, config):
        '''
        Load configuration based on the provided config sections and playbook
        names.
        '''
        logger.debug('loading configuration: %s', config)
        config_ns = argparse.Namespace()
        config_ns._playbooks = []
        config_ns._included = []
        config_ns._env = {}

        config_specs = config.split('+')
        if 'default' not in config_specs:
            config_specs.insert(0, 'default')
        for config_spec in config_specs:
            logger.debug('processing config spec: %s', config_spec)
            if config_spec.endswith('.yml') or config_spec.endswith('.yaml'):
                config_ns._playbooks.append(config_spec)
            else:
                config_ns = self._update_config_ns_from_section(config_ns, config_spec)

        args_ns = self._remove_ns_defaults(copy.deepcopy(self.args))
        for attr in vars(args_ns).keys():
            setattr(config_ns, attr, getattr(args_ns, attr))

        return config_ns

    def _update_config_ns_from_section(self, config_ns, section):
        '''
        Update a config ns from the values in a given section of the config
        file.
        '''
        logger.debug('loading config section: %s', section)
        if section in config_ns._included:
            return config_ns
        config_ns._included.append(section)
        for opt, val in self.cfg_parser.items(section):
            if opt == 'include':
                config_ns = self._update_config_ns_from_section(config_ns, val)
            elif opt == 'playbook':  # FIXME: playbook vs. playbooks?
                config_ns._playbooks.append(val)
            elif len(opt) > 1 and opt == opt.upper():
                config_ns._env[opt] = val or None
            else:
                if len(opt) == 1:
                    flag = '-{}'.format(opt)
                else:
                    flag = '--{}'.format(opt.replace('_', '-'))
                ns, extra = self.arg_parser.parse_known_args([flag, val])
                extra = extra + ns.configs
                ns.configs = []
                ns = self._remove_ns_defaults(ns)
                if not vars(ns) and extra:
                    logger.warning('skipping config item: %s', ' '.join(extra))
                for attr in vars(ns).keys():
                    if extra:
                        if attr in {'verbose'}:
                            attr_val = int(extra[0])
                        else:
                            attr_val = bool(str(extra[0]).strip() and str(extra[0]).strip().lower()[0] in ('1', 't', 'y'))
                    else:
                        attr_val = getattr(ns, attr) or None
                    setattr(config_ns, attr, attr_val)
        return config_ns

    def _build_cmd_from_config(self, config_ns):
        '''
        Build command-line arguments from given config namespace.
        '''
        cmd = [self.COMMAND]
        bool_flags = []
        for opt_args, opt_kwargs, opt_group in self.option_params:
            dest = opt_kwargs.get('dest', None)
            if not dest:
                continue
            val = getattr(config_ns, dest, None)
            if val is None:
                continue
            if not opt_args:
                continue
            flag = opt_args[0]
            action = opt_kwargs.get('action', 'store')
            if action == 'count':
                for x in xrange(val):
                    bool_flags.append(flag)
            elif action == 'store_true':
                if val:
                    bool_flags.append(flag)
            elif action == 'append':
                for v in val:
                    cmd.append(flag)
                    cmd.append(str(v))
            else:
                cmd.append(flag)
                cmd.append(str(val))
        if bool_flags:
            cmd.insert(1, '-{}'.format(''.join([flag.lstrip('-') for flag in bool_flags])))
        for playbook in getattr(config_ns, '_playbooks', []):
            cmd.append(playbook)
        return cmd

    def _build_env_from_config(self, config_ns):
        env = {}
        # FIXME
        return env


def main():
    logging.basicConfig(level=logging.DEBUG)
    apb = APB()
    apb()
