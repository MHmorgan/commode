
import json
from logging.config import fileConfig
import os
import shelve
from pathlib import Path

import click
from click import echo, secho

from commode import common
from commode.common import bail, debug, err, verbose, warn, info
from commode.server import Server

version = '2.0.0'


def run():
    from .exceptions import Error
    from .server import Unauthorized
    try:
        cli()  # pylint: disable=no-value-for-parameter
    except Unauthorized as e:
        bail(f'{str(e).strip()} (have you forgotten to configure username and password? See: `commode config --help`)')
    except Error as e:
        bail(e)
    except KeyboardInterrupt:
        print('Keyboard interrupt. Stopping.')


@click.group()
@click.option('-v', '--verbose', is_flag=True, help='Be verbose.')
@click.option('-q', '--quiet', is_flag=True, help='Be quiet.')
@click.option('--debug', is_flag=True, help='Run with debugging information.')
@click.version_option(version)
@click.pass_context
def cli(ctx, verbose, quiet, debug):  # pylint: disable=too-many-arguments
    'Commode - client for the Cabinet file server.'
    common.DEBUG = debug
    common.QUIET = quiet
    common.VERBOSE = verbose

    # Server password are stored in plain text in config file - should warn user if
    # other users are able to read the config file
    if common.CONFIG_FILE.stat().st_mode & 0o044:
        warn(f'config file ({common.CONFIG_FILE}) is readable by group and others')

    # TODO: Pass the server as a click object to sub commands
    # Setup server session from config
    cfg = common.CONFIG
    if (addr := cfg.get('server', 'address', fallback=None)):
        scheme = cfg.get('server', 'scheme', fallback='https')
        ctx.obj = Server(address=addr, scheme=scheme)


@cli.command()
@click.option('--server-address', help='Set the address of target Cabinet server')
@click.option('--user', help='Set username for server authentication')
@click.option('--password', help='Set password for server authentication')
def config(server_address, user, password):
    '''Configure the client. When no option is provided the current config is printed.'''
    cfg = common.CONFIG
    
    # Prepare config sections
    if 'server' not in cfg:
        cfg.add_section('server')

    if server_address:
        if not server_address.startswith('http'):
            bail('Server address should be an URL starting with http or https')
        from urllib.parse import urlparse
        url = urlparse(server_address)
        debug(f'Parsed server url: {url}')
        cfg.set('server', 'address', url.netloc)
        cfg.set('server', 'scheme', url.scheme or 'https')
    if user:
        cfg.set('server', 'user', user)
    if password:
        cfg.set('server', 'password', password)

    if server_address or user or password:
        common.write_config()
    else:
        print(common.CONFIG_FILE.read_text(), end='')


@cli.command()
def migrate():
    '''Migrate between different commode versions.'''
    from shutil import copy

    #
    # Migrate config file
    #
    old_cfg = Path.home() / '.config/commode.cfg'
    new_cfg = common.CONFIG_FILE
    if old_cfg.exists():
        info(f'Migrating old config file: {old_cfg} → {new_cfg}')
        if new_cfg.exists():
            bck = new_cfg.with_name('commode.cfg~')
            info(f'Creating backup of existing config: {bck}')
            new_cfg.rename(bck)
        copy(old_cfg, new_cfg)


def pass_server(f):
    '''Decorator for commands that requires a server object.
    This will perform some sanity checks for the server.
    '''
    from functools import update_wrapper

    @click.pass_context
    def new_func(ctx, *args, **kwargs):
        srv: Server = ctx.obj
        if not srv:
            bail(f'server is not properly configured. Please run: `commode config --server-address <addr>`')
        return ctx.invoke(f, srv, *args, **kwargs)

    return update_wrapper(new_func, f)


################################################################################
#                                                                              #
# Files interface
#                                                                              #
################################################################################

@cli.command()
@click.argument('file')
@pass_server
def download(srv: Server, file: str):
    '''Download a file from the server'''
    with srv:
        f = srv.get_file(file)
    echo(f.text, nl=False)


@cli.command()
@click.argument('srcfile')
@click.argument('dstfile')
@pass_server
def upload(srv: Server, srcfile: str, dstfile: str):
    '''Upload a file to the server'''
    try:
        text = Path(srcfile).read_text()
    except FileNotFoundError:
        bail(f'source file not found: {srcfile}')
    with srv:
        srv.put_file(dstfile, text)


@cli.command()
@click.argument('file')
@pass_server
def delete(srv: Server, file: str):
    '''Delete a file on the server'''
    with srv:
        srv.delete_file(file)


################################################################################
#                                                                              #
# Directory interface
#                                                                              #
################################################################################

@cli.command()
@click.argument('path', required=False, default='')
@click.option('-d', '--directories', is_flag=True, help='Only list directories.')
@click.option('-f', '--files', is_flag=True, help='Only list files.')
@pass_server
def ls(srv: Server, path: str, directories: bool, files: bool):
    '''List directory content on the server'''
    with srv:
        content = srv.get_dir(path)
    if directories:
        content = [d for d in content if d.endswith('/')]
    if files:
        content = [f for f in content if not f.endswith('/')]
    # The content is sorted from the server with directories
    # first, then files.
    echo('\n'.join(content))


@cli.command()
@click.argument('path')
@pass_server
def mkdir(srv: Server, path: str):
    '''Create a directory on the server'''
    with srv:
        srv.put_dir(path)


@cli.command()
@click.argument('path')
@pass_server
def rmdir(srv: Server, path: str):
    '''Remove a directory on the server'''
    with srv:
        srv.delete_dir(path)


################################################################################
#                                                                              #
# Boilerplates interface
#                                                                              #
################################################################################

@cli.command()
@pass_server
def boilerplates(srv: Server):
    '''List all boilerplates on the server'''
    with srv:
        names = srv.get_boilerplate_names()
    echo('\n'.join(sorted(names)))


@cli.group()
def boilerplate():
    '''Manage boilerplates.
    
    A boilerplate is a json object which maps client file paths to
    server file paths:

    \b
        {
            "$HOME/.vimrc" : "linuxconfig/vimrc",
            "$HOME/.aliases" : "linuxconfig/aliases"
        }

    The client file path may contain environment variables, which will
    be expanded when installing a boilerplate with the `boilerplate install`
    command.

    Any file used in a boilerplate may be a jinja template - when installing
    a boilerplate all files are passed through the jinja template rendering.
    '''


@boilerplate.command()
@click.argument('name')
@pass_server
def download(srv: Server, name: str):
    '''Download a boilerplate'''
    with srv:
        bp = srv.get_boilerplate(name)
    echo(json.dumps(bp.files, indent=4))


@boilerplate.command()
@click.argument('name')
@click.argument('location', default='.', type=click.Path(exists=True, file_okay=False, writable=True))
@click.option('-f', '--force', is_flag=True, help='Overwrite any existing files during installation.')
@pass_server
def install(srv: Server, name: str, location: str, force: bool):
    '''Install a boilerplate, downloading and installing all files in
    the boilerplate.
    '''
    from .exceptions import Error
    os.chdir(location)
    with srv:
        bp = srv.get_boilerplate(name)

        def prep(path, name):
            verbose(f'Preparing file {path}')
            assert isinstance(path, Path)
            if path.exists() and not force:
                warn(f'file already exists: {path} (use --force to overwrite)')
                return
            elif not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
            file = srv.get_file(name)
            text = render_template(file.name, file.text)
            return (path, text)

        # Render all templates before writing files to catch any errors
        # before installing any files.
        for path, text in [pair for p, n in bp.substituted_files if (pair := prep(p, n))]:
            info(f'Installing {path}')
            path.write_text(text)


@boilerplate.command()
@click.argument('srcfile', type=click.File())
@click.argument('name')
@click.option('--upload-all', is_flag=True, help='Upload all files referenced by the boilerplate before uploading the boilerplate itself.')
@click.option('--upload-missing', is_flag=True, help='Upload any files referenced by the boilerplate but missing on the server.')
@pass_server
def upload(srv: Server, srcfile, name: str, upload_all: bool, upload_missing: bool):
    '''Upload a boilerplate to the server.
    The boilerplate is read from a local file (SRCFILE) which must be a correctly
    formatted JSON boilerplate object.

    When uploading a boilerplate all files referenced in the boilerplate must
    exist on the server. The --upload-files option may be used to automatically
    upload all files referenced in the boilerplate.
    '''
    from .types import Boilerplate
    from .server import NotFound
    #
    # Decode boilerplate json
    #
    try:
        files = json.load(srcfile)
    except json.JSONDecodeError as e:
        bail(f'invalid JSON in source file: {e}')
    bp = Boilerplate(name, files)
    bp.verify()
    #
    # Upload boilerplate and optionally its files
    #
    with srv:
        if upload_all or upload_missing:
            for src, dst in bp.substituted_files:
                if upload_missing:
                    try:
                        srv.get_file(dst)
                    except NotFound:
                        pass
                    else:
                        verbose(f'File already exists: {dst}')
                        continue
                verbose(f'Uploading file: {src} → {dst}')
                try:
                    text = Path(src).read_text()
                except FileNotFoundError:
                    bail(f'File not found: {src}')
                srv.put_file(dst, text)
        verbose(f'Uploading boilerplate {name}…')
        srv.put_boilerplate(name, files)


@boilerplate.command()
@click.argument('name')
@pass_server
def delete(srv: Server, name: str):
    'Delete a boilerplate on the server.'
    with srv:
        verbose(f'Deleting boilerplate {name}…')
        srv.delete_boilerplate(name)


################################################################################
#                                                                              #
# Cache handling
#                                                                              #
################################################################################

@cli.group()
def cache():
    '''Inspect and manage cached files and boilerplates.'''


@cache.command()
def files():
    '''List all cached files with last modified timestamp and ETAG'''
    with common.file_cache() as cache:
        # max() requires at least 1 item
        if len(cache) == 0:
            return
        w = max(len(name) for name in cache)
        for file in sorted(cache):
            etag, mod, _ = cache[file]
            print(f'{file:<{w}}\t{mod}\t{etag}')


@cache.command()
def boilerplates():
    '''List all cached boilerplates with last modified timestamp and ETAG'''
    with common.boilerplate_cache() as cache:
        # max() requires at least 1 item
        if len(cache) == 0:
            return
        w = max(len(name) for name in cache)
        for bp in sorted(cache):
            etag, mod, _ = cache[bp]
            print(f'{bp:<{w}}\t{mod}\t{etag}')


@cache.command()
def clear():
    '''Clear entire cache, both for boilerplates and files'''
    with common.file_cache() as cache:
        cache.clear()
    with common.boilerplate_cache() as cache:
        cache.clear()


################################################################################
#                                                                              #
# Template
#                                                                              #
################################################################################

class TemplateEnv(dict):
    '''Helper class for working with environment variables in Jinja templates.
    Used to track which environment variables were accessed in a template,
    and catch any missing variables.
    '''
    def __init__(self, template_name: str, variable_name: str):
        from os import environ
        super().__init__(environ)
        self.tname = template_name
        self.vname = variable_name

    def __getitem__(self, key: str) -> str:
        from .common import Error
        try:
            return super().__getitem__(key)
        except KeyError:
            raise Error(f'Variable referenced in template "{self.tname}" missing: {self.vname}.{key}')

def render_template(name: str, text: str) -> str:
    '''Render the given text as a jinja template'''
    from os import environ
    from jinja2 import Template
    context = {
        'ENV': TemplateEnv(name, 'ENV'),
    }
    return Template(text).render(context)
