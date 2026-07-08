#!/usr/bin/env python3

''' wrapper for bisect-builds.py which simplifies option setting '''
import codecs
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


def _arg_present(args, *flags):
    '''Check if any of the given flags are present in args.'''
    return any(arg.split('=')[0] in flags for arg in args)


def add_default_args(args, verify=True):
    '''Sets appropriate default arguments for bisect-builds.py.'''
    
    detected_archive = detect_archive()

    if '--version' in args:
        print(f'{__appname__} {__version__}')
        print(f'Author: {__author__}')
        print(f'Detected --archive: {detected_archive}')
        sys.exit(0)

    # return --help quick
    if '--help' in args or '-h' in args:
        return args

    # always add --verify-range and --use-local-cache
    for def_arg in ['--verify-range', '--use-local-cache']:
        if def_arg not in args:
            args.append(def_arg)

    # if --archive is not set detect an appropriate value to set
    if not _arg_present(args, '-a', '--archive'):
        args.extend(['--archive', detected_archive])

    # if --good is not set set to Chrome stable milestone - 6
    if not _arg_present(args, '-g', '--good'):
        good = get_relative_chrome_versions(6, verify=verify)
        good_milestone = f'M{good}'
        args.extend(['--good', good_milestone])

    return args

def add_default_chrome_args(args):
    '''Sets appropriate arguments that bisect-builds.py will pass to Chromium binaries.'''

    args.append('--enable-chrome-browser-cloud-management')
    return args
    
def main():
    '''Parse arguments, configure environment, and run bisect-builds.py.'''
    if '--' in sys.argv:
        split_at = sys.argv.index('--')
        bisect_args = sys.argv[:split_at]
        chrome_args = sys.argv[split_at:]
    else:
        bisect_args = sys.argv
        chrome_args = ['--']
    verify = True
    if '--do-not-verify-tls' in bisect_args:
        unsecure_urllib_request_opener()
        verify = False
        bisect_args.remove('--do-not-verify-tls')
        print('WARNING: TLS verify is turned off.')
    if verify:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        roots_pem = os.path.join(script_dir, 'roots.pem')
        if not os.environ.get('REQUESTS_CA_BUNDLE'):
            os.environ['REQUESTS_CA_BUNDLE'] = roots_pem
        if not os.environ.get('SSL_CERT_FILE'):
            os.environ['SSL_CERT_FILE'] = roots_pem
    
    # secret, not really secret
    if not os.environ.get('GOOGLE_API_KEY'):
        os.environ['GOOGLE_API_KEY'] = codecs.decode('NVmnFlObSBm7wRPR5dUolxDHcnyXg_lUV4YKYTp', 'rot13')
    if not os.environ.get('GOOGLE_DEFAULT_CLIENT_SECRET'):
        os.environ['GOOGLE_DEFAULT_CLIENT_SECRET'] = codecs.decode('TBPFCK-LDdWORqtJDArsuKlwsQBXee5bY8W', 'rot13')
    if not os.environ.get('GOOGLE_DEFAULT_CLIENT_ID'):
        os.environ['GOOGLE_DEFAULT_CLIENT_ID'] = codecs.decode('933175750481-eo2epca4c5a4wnyueudoefv1nryusa8p.nccf.tbbtyrhfrepbagrag.pbz', 'rot13')
    bisect_args = add_default_args(bisect_args, verify=verify)
    chrome_args = add_default_chrome_args(chrome_args)
    sys.argv = bisect_args + chrome_args
    print(f'running bisect-builds.py with options: {" ".join(sys.argv[1:])}')
    bisect_builds.main()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
