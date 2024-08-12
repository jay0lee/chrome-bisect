#!/usr/bin/env python3

''' wrapper for bisect-builds.py which simplifies option setting '''
from platform import system, machine
import os
import sys

import requests

import bisect_builds


def get_relative_chrome_versions(minus=0):
    ''' returns current Chrome stable milestone number minus value of minus'''
    url = 'https://versionhistory.googleapis.com' \
          '/v1/chrome/platforms/all/channels/stable/versions/all/releases' \
          '?fields=releases%2Fversion%2CnextPageToken'
    resp = requests.get(url)
    versions = resp.json().get('releases')
    milestones = []
    for version in versions:
        ver = version.get('version')
        if ver:
            milestone = int(ver.split('.')[0])
            if milestone not in milestones:
                milestones.append(milestone)
    milestones.sort(reverse=True)
    return milestones[minus]

def detect_archive():
    '''returns an appropriate value for archive based on current OS and architecture.'''
    myos = system()
    sixty_four = sys.maxsize > 2**32
    mymachine = machine()
    archive = None
    if myos == 'Windows':
        if sixty_four:
            archive = 'win64'
        else:
            archive = 'win'
    elif myos == 'Linux':
        if sixty_four:
            archive = 'linux64'
        else:
            archive = 'linux'
    elif myos == 'Darwin':
        if mymachine == 'arm64':
            archive = 'mac-arm'
        elif mymachine == 'x86_64':
            archive = 'mac64'
    if not archive:
        print('Could not auto-detect value for --archive. ' \
              f'OS: {myos}, 64-bit: {sixty_four}, machine: {mymachine}')
        sys.exit(1)
    return archive


def add_default_args(args):
    '''sets appropriate default arguments for bisect-builds.py'''
    # return --help quick
    if '--help' in args or '-h' in args:
        return args

    # always add --verify-range and --use-local-cache
    for def_arg in ['--verify-range', '--use-local-cache']:
        if def_arg not in args:
            args.append(def_arg)

    # if --archive is not set detect an appropriate value to set
    archive_set = False
    for arg in list(args):
        arg = arg.split('=')[0]
        if arg in ['-a', '--archive']:
            archive_set = True
    if not archive_set:
        archive = detect_archive()
        args.extend(['--archive', archive])

    # if --good is not set set to Chrome stable milestone - 6
    good_set = False
    for arg in list(args):
        arg = arg.split('=')[0]
        if arg in ['-g', '--good']:
            good_set = True
    if not good_set:
        good = get_relative_chrome_versions(6)
        good_milestone = f'M{good}'
        args.extend(['--good', good_milestone])

    return args

def main():
    '''main screen turn on'''
    if '--' in sys.argv:
        split_at = sys.argv.index('--')
        bisect_args = sys.argv[:split_at]
        chrome_args = sys.argv[split_at:]
    else:
        bisect_args = sys.argv
        chrome_args = []
    os.environ['REQUESTS_CA_BUNDLE'] = 'roots.pem'
    os.environ['SSL_CERT_FILE'] = 'roots.pem'    
    bisect_args = add_default_args(bisect_args)
    sys.argv = bisect_args + chrome_args
    print(f'running bisect-builds.py with options: {" ".join(sys.argv[1:])}')
    bisect_builds.main()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
