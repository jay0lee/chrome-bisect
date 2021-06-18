#!/usr/bin/env python3

''' wrapper for bisect-builds.py which simplifies option setting '''
from platform import system, machine
import sys

import requests

import bisect_builds

override_milestones = {
        'M88': '843830'
        }

def get_relative_chrome_versions(minus=0):
    url = 'https://versionhistory.googleapis.com/v1/chrome/platforms/all/channels/stable/versions/all/releases?fields=releases%2Fversion%2CnextPageToken'
    resp = requests.get(url)
    versions = resp.json().get('releases')
    milestones = []
    for v in versions:
        ver = v.get('version')
        if ver:
            m = int(ver.split('.')[0])
            if m not in milestones:
                milestones.append(m)
    milestones.sort(reverse=True)
    return milestones[minus]

def add_default_args(args):
    # return --help quick
    if '--help' in args or '-h' in args:
        return args
    
    # always add --verify-range and --use-local-cache
    for def_arg in ['--verify-range', '--use-local-cache']:
        if def_arg not in args:
            args.append(def_arg)

    archive_set = False
    for arg in list(args):
        arg = arg.split('=')[0]
        if arg == '-a' or arg == '--archive':
            archive_set = True
    if not archive_set:
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
            print(f'Could not auto-detect value for --archive. OS: {myos}, 64-bit: {sixty_four}, machine: {mymachine}')
            sys.exit(1)
        args.extend(['--archive', archive])
    good_set = False
    for arg in list(args):
        arg = arg.split('=')[0]
        if arg == '-g' or arg == '--good':
            good_set = True
    if not good_set:
        good = get_relative_chrome_versions(6)
        good_milestone = f'M{good}'
        args.extend(['--good', good_milestone])
    # fix milestones with bad build results
    for i in range(0, len(args) - 1):
        args[i] = override_milestones.get(args[i].upper(), args[i])
    return args

def main():
    if '--' in sys.argv:
        split_at = sys.argv.index('--')
        bisect_args = sys.argv[:split_at]
        chrome_args = sys.argv[split_at:]
    else:
        bisect_args = sys.argv
        chrome_args = []
    bisect_args = add_default_args(bisect_args)
    sys.argv = bisect_args + chrome_args
    print(f'running bisect-builds.py with options: {" ".join(sys.argv[1:])}')
    bisect_builds.main()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
