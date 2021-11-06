"""
Run the KGTK-Browser Flask server
Open a browser window with the kgtk-browser location

Optional params:
    - hostname (--host)
    - port number (-p, --port)
    - kgtk browser config file (-c, --config)
    - kgtk browser flask app file (-a, --app)

Example usage:
    kgtk browser --host 0.0.0.0 --port 1234 --app flask_app.py --config config.py
"""

from argparse import Namespace, SUPPRESS
import typing

from kgtk.cli_argparse import KGTKArgumentParser, KGTKFiles


# Define the name of the command and its alias.
BROWSER_COMMAND: str = "browser"
BROWSE_COMMAND: str = "browse"


def parser():
    return {
        'aliases': [ BROWSE_COMMAND ],
        'help': 'Run the KGTK-Browser Flask app.',
        'description': 'Open a new browser with the KGTK-Browser app running.',
    }


def add_arguments_extended(parser: KGTKArgumentParser, parsed_shared_args: Namespace):
    """
    Parse arguments
    Args:
        parser (argparse.ArgumentParser)
    """
    from kgtk.utils.argparsehelpers import optional_bool

    # These special shared aruments inticate whether the `--expert` option
    # was supplied and the command name that was used.
    _expert: bool = parsed_shared_args._expert
    _command: str = parsed_shared_args._command

    # This helper function makes it easy to suppress options from
    # The help message.  The options are still there, and initialize
    # what they need to initialize.
    def h(msg: str)->str:
        if _expert:
            return msg
        else:
            return SUPPRESS

    # KGTK Browser hostname
    parser.add_argument(
        '--host',
        dest="kgtk_browser_host",
        help="Hostname used to launch flask server, defaults to localhost",
        default="localhost",
    )

    # KGTK Browser port number
    parser.add_argument(
        '-p', '--port',
        dest="kgtk_browser_port",
        help="Port number used to launch flask server, defaults to 5000",
        default="5000",
    )

    # KGTK Browser configuration file
    parser.add_argument(
        '-c', '--config',
        dest="kgtk_browser_config",
        help="KGTK Browser configuration file, defaults to `kgtk_browser_config.py`",
        default="kgtk_browser_config.py",
    )

    # KGTK Browser application file
    parser.add_argument(
        '-a', '--app',
        dest="kgtk_browser_app",
        help="KGTK Browser flask application file, defaults to `kgtk_browser_app.py`",
        default="kgtk_browser_app.py",
    )


def run(
        kgtk_browser_host: str = 'localhost',
        kgtk_browser_port: str = '5000',
        kgtk_browser_config: str = 'kgtk_browser_config.py',
        kgtk_browser_app: str = 'kgtk_browser_app.py',

        errors_to_stdout: bool = False,
        errors_to_stderr: bool = True,
        show_options: bool = False,
        verbose: bool = False,
        very_verbose: bool = False,

        **kwargs # Whatever KgtkFileOptions and KgtkValueOptions want.
)->int:
    # import modules locally
    from pathlib import Path
    import simplejson as json
    import webbrowser
    import threading
    import os, sys
    import typing

    from kgtk.exceptions import KGTKException

    # Select where to send error messages, defaulting to stderr.
    error_file: typing.TextIO = sys.stdout if errors_to_stdout else sys.stderr

    # Show the final option structures for debugging and documentation.
    if show_options:
        print("--input-file=%s" % repr(str(input_file_path)), file=error_file, flush=True)
        print("--output-file=%s" % repr(str(output_file_path)), file=error_file, flush=True)

        idbuilder_options.show(out=error_file)
        print("=======", file=error_file, flush=True)

    try:

        # Set the flask app and configuration file settings
        os.environ["FLASK_APP"] = kgtk_browser_app
        os.environ["KGTK_BROWSER_CONFIG"] = kgtk_browser_config

        # Open the default web browser at the kgtk-browser location
        url = "http://{}:{}/browser".format(kgtk_browser_host, kgtk_browser_port)
        threading.Timer(2.5, lambda: webbrowser.open(url)).start()

        # Run flask app using the selected host and port
        os.system(
            "flask run --host {} --port {}".format(
                kgtk_browser_host,
                kgtk_browser_port,
            )
        )

        return 0

    except SystemExit as e:
        raise KGTKException("Exit requested")
    except Exception as e:
        raise KGTKException(str(e))
