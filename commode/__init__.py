
from pathlib import Path
from commode.file_entry import FileEntry
from commode.server import Server
import click
from commode import common
from commode.common import bail, warn
from commode.exceptions import Error


def run():
    try:
        cli()  #pylint: disable=no-value-for-parameter
    except Error as e:
        bail(e)
    except KeyboardInterrupt:
        print('Keyboard interrupt. Stopping.')


@click.group()
@click.option('-v', '--verbose', is_flag=True, help='Be verbose.')
@click.option('-q', '--quiet', is_flag=True, help='Be quiet.')
@click.option('--debug', is_flag=True, help='Run with debugging information.')
@click.option('--trace', is_flag=True, help='Run with debugging and trace information.')
@click.option('--log-out', 'logout', type=click.File('w'), help='Redirect log output to file.')
@click.option('--log-err', 'logerr', type=click.File('w'), help='Redirect log error output to file.')
@click.option('--log-err2out', 'err2out', is_flag=True, help='Write log errors to normal log output.')
def cli(verbose, quiet, debug, trace, logout, logerr, err2out):  # pylint: disable=too-many-arguments
    'Commode - client for the Cabinet file server.'
    common.DEBUG = debug
    common.QUIET = quiet
    common.VERBOSE = verbose
    common.TRACE = trace
    common.LOGOUT = logout
    common.LOGERR = common.LOGOUT if err2out else logerr

    # Server password are stored in plain text in config file - should warn user if 
    # other users are able to read the config file
    if common.CONFIG_FILE.stat().st_mode & 0o044:
        warn(f'config file ({common.CONFIG_FILE}) is readable by group and others')

    # Setup from config
    cfg = common.CONFIG
    if (addr := cfg.get('server', 'address', fallback=None)):
        scheme = cfg.get('server', 'scheme', fallback='https')
        common.SERVER = Server(address=addr, scheme=scheme)
    else:
        warn(f'server address is not configured. Run: `commode config --server-address <addr>`')


@cli.command()
@click.option('--server-address', help='Set the address of target Cabinet server')
@click.option('--user', help='Set username for server authentication')
@click.option('--password', help='Set password for server authentication')
def config(server_address, user, password):
    """Configure the client. When no option is provided the current config is printed."""
    cfg = common.CONFIG

    # Prepare config sections
    if 'server' not in cfg:
        cfg.add_section('server')

    if server_address:
        from urllib.parse import urlparse
        url = urlparse(server_address)
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


################################################################################
#                                                                              #
# Files interface
#                                                                              #
################################################################################

@cli.command()
@click.argument('file')
def download(file: str):
    'Download a file from the server'
    with common.SERVER:
        f = FileEntry(file)
        txt = f.content()
    print(txt)


@cli.command()
@click.argument('srcfile')
@click.argument('dstfile')
def upload(srcfile: str, dstfile: str):
    'Upload a file to the server'
    try:
        text = Path(srcfile).read_text()
    except FileNotFoundError:
        bail(f'source file not found: {srcfile}')
    with common.SERVER:
        f = FileEntry(dstfile)
        f.update(text)


@cli.command()
@click.argument('file')
def delete(file: str):
    'Delete a file on the server'
    with common.SERVER:
        f = FileEntry(file)
        f.delete()


################################################################################
#                                                                              #
# Directory interface
#                                                                              #
################################################################################

@cli.command()
@click.argument('path', required=False, default='')
def ls(path: str):
    'List directory content on the server'
    with common.SERVER as srv:
        content = srv.get_dir(path)
    print('\n'.join(sorted(content)))


@cli.command()
@click.argument('path')
def mkdir(path: str):
    'Create a directory on the server'
    with common.SERVER as srv:
        srv.put_dir(path)


@cli.command()
@click.argument('path')
def rmdir(path: str):
    'Remove a directory on the server'
    with common.SERVER as srv:
        srv.delete_dir(path)


################################################################################
#                                                                              #
# Boilerplates interface
#                                                                              #
################################################################################

@cli.command()
def boilerplates():
    'List all boilerplates on the server'
    # TODO: boilerplates


@cli.group()
def boilerplate():
    'Manage boilerplates'


@boilerplate.command()
@click.argument('name')
def download(name: str):
    'Download a boilerplate'
    # TODO: download boilerplate


@boilerplate.command()
@click.argument('name')
def upload(name: str):
    'Upload a boilerplate to the server.'
    # TODO: upload boilerplate


@boilerplate.command()
@click.argument('name')
def delete(name: str):
    'Delete a boilerplate on the server.'
    # TODO: Delete server
