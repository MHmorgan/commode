
import click
from . import common
from .common import Error, bail, ctx


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


@cli.command()
@click.option('--server-address')
@click.option('--user')
@click.option('--password')
def config(server_address, user, password):
    'Configure the client'
    # TODO: Configure the client


################################################################################
#                                                                              #
# Files interface
#                                                                              #
################################################################################

@cli.command()
@click.argument('file')
def download(file: str):
    'Download a file from the server'
    # TODO: Download file


@cli.command()
@click.argument('srcfile')
@click.argument('dstfile')
def upload(srcfile: str, dstfile: str):
    'Upload a file to the server'
    # TODO: Upload a file


@cli.command()
@click.argument('file')
def delete(file: str):
    'Delete a file on the server'
    # TODO: Delete a file


################################################################################
#                                                                              #
# Directory interface
#                                                                              #
################################################################################

@cli.command()
@click.argument('path')
def ls(path: str):
    'List directory content on the server'
    # TODO: ls


@cli.command()
@click.argument('path')
def mkdir(path: str):
    'Create a directory on the server'
    # TODO: mkdir


@cli.command()
@click.argument('path')
def rmdir(path: str):
    'Remove a directory on the server'
    # TODO: rmdir


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
