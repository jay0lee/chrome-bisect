#!/usr/bin/env python3

''' wrapper for bisect-builds.py which simplifies option setting '''
import argparse
import codecs
import contextlib
from platform import system, machine
import os
import ssl
import sys
import urllib.request

import requests

import bisect_builds
from version import version as __version__
__author__ = "Jay Lee <jay0lee@gmail.com>"
__appname__ = "Chrome Bisect"


def unsecure_urllib_request_opener():
    ''' utility function that disables TLS verify '''
    urllib.request._opener = urllib.request.build_opener()
    for handler in urllib.request._opener.handlers:
        if isinstance(handler, urllib.request.HTTPSHandler):
            insecure_context = ssl.create_default_context()
            # Disable hostname verification
            insecure_context.check_hostname = False
            # Disable certificate verification
            insecure_context.verify_mode = ssl.CERT_NONE
            handler._context = insecure_context


@contextlib.contextmanager
def _patched_argv(argv):
    '''Temporarily replace sys.argv, restoring the original on exit.'''
    original = sys.argv
    sys.argv = argv
    try:
        yield
    finally:
        sys.argv = original


def get_relative_chrome_versions(minus=0, verify=True):
    '''Returns current Chrome stable milestone number minus value of minus.'''
    url = 'https://versionhistory.googleapis.com' \
          '/v1/chrome/platforms/all/channels/stable/versions/all/releases' \
          '?fields=releases%2Fversion%2CnextPageToken'
    resp = requests.get(url, verify=verify)
    resp.raise_for_status()
    versions = resp.json().get('releases')
    if not versions:
        print('ERROR: No release data returned from versionhistory API.')
        sys.exit(1)
    milestones = []
    for version in versions:
        ver = version.get('version')
        if ver:
            milestone = int(ver.split('.')[0])
            if milestone not in milestones:
                milestones.append(milestone)
    milestones.sort(reverse=True)
    if minus >= len(milestones):
        print(f'ERROR: Cannot go back {minus} milestones; only {len(milestones)} known.')
        sys.exit(1)
    return milestones[minus]


def detect_archive():
    '''returns an appropriate value for archive based on current OS and architecture.'''
    myos = system()
    mymachine = machine()
    match myos, mymachine:
      case 'Windows', 'ARM64':
        archive = 'win-arm64'
      case 'Windows', 'AMD64':
        archive = 'win64'
      case 'Linux', 'x86_64':
        archive = 'linux64'
      case 'Linux', 'aarch64':
        archive = 'linux-arm'
      case 'Darwin', 'arm64':
        archive = 'mac-arm'
      case 'Darwin', 'x86_64':
        archive = 'mac64'
      case _:
        print(f'ERROR: Could not auto-detect value for --archive for OS {myos} and machine {mymachine}. Try manually specifying --archive.')
        sys.exit(1)
    return archive


def _build_parser():
    '''Build argparse parser for chrome_bisect-specific arguments.'''
    parser = argparse.ArgumentParser(
        prog='chrome_bisect',
        description='Wrapper for bisect-builds.py with smart defaults.',
        add_help=False,  # Let --help pass through to bisect-builds.py
    )
    parser.add_argument('--version', action='store_true',
                        help='Show version info and exit.')
    parser.add_argument('--do-not-verify-tls', action='store_true',
                        help='Disable TLS certificate verification.')
    parser.add_argument('-a', '--archive', type=str, default=None,
                        help='Archive type (auto-detected if not set).')
    parser.add_argument('-g', '--good', type=str, default=None,
                        help='Known good revision (default: stable minus 6).')
    return parser


def add_default_chrome_args(args):
    '''Sets appropriate arguments that bisect-builds.py will pass to Chromium binaries.'''

    args.append('--enable-chrome-browser-cloud-management')
    return args


def main():
    '''Parse arguments, configure environment, and run bisect-builds.py.'''
    # Split at -- to separate bisect args from chrome args
    argv_rest = sys.argv[1:]
    if '--' in argv_rest:
        split_at = argv_rest.index('--')
        raw_bisect_args = argv_rest[:split_at]
        chrome_args = argv_rest[split_at:]  # includes the '--'
    else:
        raw_bisect_args = argv_rest
        chrome_args = ['--']

    parser = _build_parser()
    our_args, passthrough_args = parser.parse_known_args(raw_bisect_args)

    detected_archive = detect_archive()

    # Handle --version
    if our_args.version:
        print(f'{__appname__} {__version__}')
        print(f'Author: {__author__}')
        print(f'Detected --archive: {detected_archive}')
        sys.exit(0)

    # Handle TLS verification
    verify = not our_args.do_not_verify_tls
    if not verify:
        unsecure_urllib_request_opener()
        print('WARNING: TLS verify is turned off.')
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        roots_pem = os.path.join(script_dir, 'roots.pem')
        if not os.environ.get('REQUESTS_CA_BUNDLE'):
            os.environ['REQUESTS_CA_BUNDLE'] = roots_pem
        if not os.environ.get('SSL_CERT_FILE'):
            os.environ['SSL_CERT_FILE'] = roots_pem

    # Set API keys (public Chromium API keys, safe to embed)
    if not os.environ.get('GOOGLE_API_KEY'):
        os.environ['GOOGLE_API_KEY'] = codecs.decode('NVmnFlObSBm7wRPR5dUolxDHcnyXg_lUV4YKYTp', 'rot13')
    if not os.environ.get('GOOGLE_DEFAULT_CLIENT_SECRET'):
        os.environ['GOOGLE_DEFAULT_CLIENT_SECRET'] = codecs.decode('TBPFCK-LDdWORqtJDArsuKlwsQBXee5bY8W', 'rot13')
    if not os.environ.get('GOOGLE_DEFAULT_CLIENT_ID'):
        os.environ['GOOGLE_DEFAULT_CLIENT_ID'] = codecs.decode('933175750481-eo2epca4c5a4wnyueudoefv1nryusa8p.nccf.tbbtyrhfrepbagrag.pbz', 'rot13')

    # Build the arg list for bisect-builds.py
    bisect_args = list(passthrough_args)

    # If --help is requested, pass through without adding defaults
    if '-h' not in bisect_args and '--help' not in bisect_args:
        # Always include --verify-range and --use-local-cache
        for flag in ['--verify-range', '--use-local-cache']:
            if flag not in bisect_args:
                bisect_args.append(flag)

        # Apply --archive default
        bisect_args.extend(['--archive', our_args.archive or detected_archive])

        # Apply --good default
        if our_args.good:
            bisect_args.extend(['--good', our_args.good])
        else:
            good = get_relative_chrome_versions(6, verify=verify)
            bisect_args.extend(['--good', f'M{good}'])

    chrome_args = add_default_chrome_args(chrome_args)
    argv = [sys.argv[0]] + bisect_args + chrome_args
    print(f'running bisect-builds.py with options: {" ".join(argv[1:])}')
    with _patched_argv(argv):
        bisect_builds.main()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
