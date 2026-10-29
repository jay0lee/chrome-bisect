#!/usr/bin/env python3

''' wrapper for bisect-builds.py which simplifies option setting '''
import argparse
import codecs
import contextlib
import json
from platform import system, machine
import os
import ssl
import sys
import urllib.request

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


def get_relative_chrome_versions(minus=0):
    '''Returns current Chrome stable milestone number minus value of minus.'''
    url = 'https://versionhistory.googleapis.com' \
          '/v1/chrome/platforms/all/channels/stable/versions/all/releases' \
          '?fields=releases%2Fversion%2CnextPageToken'
    resp = urllib.request.urlopen(url)
    versions = json.loads(resp.read()).get('releases')
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


def _fetch_json(url, timeout=15):
    '''Fetch JSON from a URL, returning None on failure.'''
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
        return json.loads(resp.read())
    except Exception as e:
        print(f'WARNING: API request failed for {url}: {e}')
        return None


def _get_version_for_milestone(milestone_num):
    '''Use the versionhistory API to find a release version for a milestone.

    Returns a base version string like "139.0.7258.0" or None.
    Searches across stable, beta, dev, and canary channels.
    '''
    channels = ['stable', 'beta', 'dev', 'canary']
    for channel in channels:
        url = (
            'https://versionhistory.googleapis.com'
            f'/v1/chrome/platforms/all/channels/{channel}/versions/all/releases'
            f'?filter=version%3E{milestone_num},version%3C{milestone_num + 1}'
            '&fields=releases%2Fversion&pageSize=1'
        )
        data = _fetch_json(url)
        if data:
            releases = data.get('releases', [])
            if releases:
                ver = releases[0].get('version', '')
                # Convert to base version (e.g. 139.0.7258.158 -> 139.0.7258.0)
                parts = ver.split('.')
                if len(parts) == 4:
                    return f'{parts[0]}.{parts[1]}.{parts[2]}.0'
    return None


def resolve_milestone(milestone_str):
    '''Resolve a milestone string like "M139" or "m139" to a commit position.

    Uses multiple strategies with fallbacks to handle intermittent API issues
    with the chromiumdash.appspot.com App Engine app:

    Strategy 1: Bulk-fetch all milestones from chromiumdash (one request,
                more reliable than per-milestone queries).
    Strategy 2: Use versionhistory API to find a version string for the
                milestone, then use chromiumdash fetch_version to resolve
                the commit position (different endpoint, more reliable).
    Strategy 3: Direct per-milestone query to chromiumdash (original method,
                prone to latency spikes and timeouts).

    Returns the commit position as a string, or None if all strategies fail.
    '''
    if not (milestone_str[:1].upper() == 'M' and milestone_str[1:].isdigit()):
        return None  # Not a milestone string
    milestone_num = int(milestone_str[1:])

    # Strategy 1: Bulk fetch all milestones (one request, avoids the
    # per-milestone endpoint that has latency spikes up to 15+ seconds).
    data = _fetch_json(
        'https://chromiumdash.appspot.com/fetch_milestones', timeout=15
    )
    if data:
        for m in data:
            if (m and isinstance(m, dict)
                    and m.get('milestone') == milestone_num
                    and m.get('chromium_main_branch_position')):
                pos = m['chromium_main_branch_position']
                print(f'Resolved M{milestone_num} to commit position {pos}'
                      ' (via chromiumdash bulk milestones)')
                return str(pos)

    # Strategy 2: Use versionhistory to find a version, then fetch_version
    # to get the commit position. These are separate services and may be
    # available when the milestones endpoint is not.
    print(f'WARNING: Bulk milestones lookup failed for M{milestone_num},'
          ' trying versionhistory fallback...')
    base_version = _get_version_for_milestone(milestone_num)
    if base_version:
        ver_data = _fetch_json(
            f'https://chromiumdash.appspot.com/fetch_version'
            f'?version={base_version}',
            timeout=15,
        )
        if ver_data and ver_data.get('chromium_main_branch_position'):
            pos = ver_data['chromium_main_branch_position']
            print(f'Resolved M{milestone_num} to commit position {pos}'
                  f' (via versionhistory {base_version})')
            return str(pos)

    # Strategy 3: Direct per-milestone query (original method, last resort).
    print(f'WARNING: Versionhistory fallback failed for M{milestone_num},'
          ' trying direct milestone lookup...')
    data = _fetch_json(
        f'https://chromiumdash.appspot.com/fetch_milestones'
        f'?mstone={milestone_num}',
        timeout=30,  # generous timeout since this endpoint can be slow
    )
    if data:
        for m in data:
            if (m and isinstance(m, dict)
                    and m.get('milestone') == milestone_num
                    and m.get('chromium_main_branch_position')):
                pos = m['chromium_main_branch_position']
                print(f'Resolved M{milestone_num} to commit position {pos}'
                      ' (via chromiumdash direct)')
                return str(pos)

    return None


def _looks_like_milestone(value):
    '''Check if a value looks like a Chrome milestone rather than a commit position.

    Accepts formats like "M139", "m139", or bare "139". Bare numbers are
    treated as milestones when they fall in the plausible milestone range
    (1-999). Chrome commit positions are always >= ~40000, so there is no
    ambiguity. This avoids the common user mistake of typing "--good 139"
    when they mean "--good M139".
    '''
    if not value:
        return False
    # Explicit M/m prefix — always a milestone
    if len(value) > 1 and value[0].upper() == 'M' and value[1:].isdigit():
        return int(value[1:]) >= 1
    # Bare number in the milestone range (1-999)
    # Commit positions for even the earliest snapshot builds are > 40000,
    # and milestones have never exceeded ~200, so there is zero overlap.
    if value.isdigit() and 1 <= int(value) <= 999:
        return True
    return False


def _normalize_milestone_str(value):
    '''Normalize a milestone-like value to "M<number>" form.

    Handles "M139", "m139", and bare "139" inputs.
    '''
    if value[0].upper() == 'M' and value[1:].isdigit():
        return value  # Already in M-prefix form
    # Bare number
    return f'M{value}'


def resolve_milestone_arg(value):
    '''Resolve a --good or --bad value, converting milestones to positions.

    Accepts milestones in any common format:
      - "M139" or "m139" (explicit milestone prefix)
      - "139" (bare number — treated as milestone when <= 999, since commit
        positions are always >= ~40000)

    Non-milestone values (version strings like "139.0.7258.0", large commit
    positions like "1477651") are returned unchanged for bisect-builds.py.
    '''
    if _looks_like_milestone(value):
        milestone_str = _normalize_milestone_str(value)
        milestone_num = milestone_str[1:]
        # Let the user know we're interpreting their input as a milestone
        if value.isdigit():
            print(f'Interpreting "{value}" as Chrome milestone M{milestone_num}'
                  f' (use a commit position > 999 for raw revisions)')
        position = resolve_milestone(milestone_str)
        if position:
            return position
        print(f'ERROR: Could not resolve milestone M{milestone_num} to a'
              f' commit position.')
        print(f'All API strategies failed. You can try:')
        print(f'  1. Running again (may be a transient API issue)')
        print(f'  2. Looking up the position manually at:')
        print(f'     https://chromiumdash.appspot.com/fetch_milestones'
              f'?mstone={milestone_num}')
        print(f'  3. Specifying a numeric commit position directly')
        sys.exit(1)
    return value


def show_milestone_map():
    '''Display a mapping of recent Chrome milestones to commit positions.

    Fetches the current stable milestone from versionhistory, then attempts
    to resolve each milestone from the past ~4 years using all three API
    strategies. Reports successes, failures, and which strategy was used.
    '''
    # Determine the range: current stable back ~4 years (~52 releases)
    print('Fetching current stable milestone from versionhistory API...')
    try:
        current_stable = get_relative_chrome_versions(0)
    except SystemExit:
        print('ERROR: Could not determine current stable milestone.')
        return
    oldest = max(current_stable - 52, 1)
    print(f'Current stable: M{current_stable}')
    print(f'Showing milestones M{oldest} through M{current_stable}'
          f' (~4 years)\n')

    # Strategy 1: Try bulk fetch first (cheapest, one request)
    print('Fetching bulk milestone data from chromiumdash...')
    bulk_data = _fetch_json(
        'https://chromiumdash.appspot.com/fetch_milestones', timeout=15
    )
    bulk_map = {}
    if bulk_data:
        for m in bulk_data:
            if m and isinstance(m, dict) and m.get('milestone'):
                bulk_map[m['milestone']] = m.get('chromium_main_branch_position')
        print(f'  Bulk API returned {len(bulk_map)} milestones.\n')
    else:
        print('  WARNING: Bulk API failed.\n')

    # Print header
    print(f'{"Milestone":<12} {"Position":<12} {"Status"}')
    print(f'{"---------":<12} {"--------":<12} {"------"}')

    ok_count = 0
    fail_count = 0

    for ms in range(oldest, current_stable + 1):
        label = f'M{ms}'

        # Check bulk data first
        if ms in bulk_map and bulk_map[ms]:
            pos = bulk_map[ms]
            print(f'{label:<12} {pos:<12} OK')
            ok_count += 1
            continue

        # Bulk didn't have it — try the fallback strategies silently
        # Strategy 2: versionhistory + fetch_version
        pos = None
        error_detail = None
        base_version = None
        try:
            base_version = _get_version_for_milestone(ms)
        except Exception as e:
            error_detail = f'versionhistory lookup error: {e}'

        if base_version:
            ver_data = _fetch_json(
                f'https://chromiumdash.appspot.com/fetch_version'
                f'?version={base_version}',
                timeout=15,
            )
            if ver_data and ver_data.get('chromium_main_branch_position'):
                pos = ver_data['chromium_main_branch_position']
                print(f'{label:<12} {pos:<12} OK (via fallback)')
                ok_count += 1
                continue
            elif ver_data:
                error_detail = (f'fetch_version returned null position for'
                                f' {base_version}')
            else:
                error_detail = (f'fetch_version failed for {base_version}')

        # Strategy 3: Direct per-milestone query
        direct_data = _fetch_json(
            f'https://chromiumdash.appspot.com/fetch_milestones?mstone={ms}',
            timeout=30,
        )
        if direct_data:
            for m in direct_data:
                if (m and isinstance(m, dict)
                        and m.get('milestone') == ms
                        and m.get('chromium_main_branch_position')):
                    pos = m['chromium_main_branch_position']
                    print(f'{label:<12} {pos:<12} OK (via fallback)')
                    ok_count += 1
                    break
            else:
                if ms in bulk_map and bulk_map[ms] is None:
                    error_detail = 'chromium_main_branch_position is null' \
                                   ' (milestone not yet branched?)'
                elif not error_detail:
                    error_detail = 'no valid data in API response'
                print(f'{label:<12} {"—":<12} FAILED: {error_detail}')
                fail_count += 1
        else:
            if not error_detail:
                error_detail = 'all API endpoints failed or timed out'
            print(f'{label:<12} {"—":<12} FAILED: {error_detail}')
            fail_count += 1

    print(f'\n{ok_count} milestones resolved successfully, '
          f'{fail_count} failed.')
    if fail_count:
        print('Failed milestones may not yet be branched (future milestones)'
              ' or may be too old for the API.')


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
    parser.add_argument('--show-milestones', action='store_true',
                        help='Show milestone-to-commit-position map and exit.')
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
        # In a PyInstaller bundle, __file__ points to a temp extraction dir
        # but roots.pem is alongside the executable in --onedir mode.
        if getattr(sys, 'frozen', False):
            script_dir = os.path.dirname(sys.executable)
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
        roots_pem = os.path.join(script_dir, 'roots.pem')
        # Explicitly configure urllib to use the bundled CA bundle.
        # The SSL_CERT_FILE env var alone isn't sufficient in
        # PyInstaller-bundled builds with custom OpenSSL.
        secure_context = ssl.create_default_context(cafile=roots_pem)
        https_handler = urllib.request.HTTPSHandler(context=secure_context)
        urllib.request._opener = urllib.request.build_opener(https_handler)
        # Also set SSL_CERT_FILE as a fallback for bisect_builds.py
        if not os.environ.get('SSL_CERT_FILE'):
            os.environ['SSL_CERT_FILE'] = roots_pem

    # Handle --show-milestones (after TLS setup so API calls work)
    if our_args.show_milestones:
        show_milestone_map()
        sys.exit(0)

    # Set API keys (public Chromium API keys, safe to embed)
    if not os.environ.get('GOOGLE_API_KEY'):
        os.environ['GOOGLE_API_KEY'] = codecs.decode('NVmnFlObSBm7wRPR5dUolxDHcnyXg_lUV4YKYTp', 'rot13')
    if not os.environ.get('GOOGLE_DEFAULT_CLIENT_SECRET'):
        os.environ['GOOGLE_DEFAULT_CLIENT_SECRET'] = codecs.decode('TBPFCK-LDdWORqtJDArsuKlwsQBXee5bY8W', 'rot13')
    if not os.environ.get('GOOGLE_DEFAULT_CLIENT_ID'):
        os.environ['GOOGLE_DEFAULT_CLIENT_ID'] = codecs.decode('933175750481-eo2epca4c5a4wnyueudoefv1nryusa8p.nccf.tbbtyrhfrepbagrag.pbz', 'rot13')

    # Build the arg list for bisect-builds.py
    bisect_args = list(passthrough_args)

    # If --help is requested, show our own options first, then pass through
    # to bisect-builds.py for its full help.
    if '-h' in bisect_args or '--help' in bisect_args:
        print(f'{__appname__} - wrapper for bisect-builds.py with smart defaults.\n')
        print('Chrome Bisect options (in addition to bisect-builds.py options below):')
        print(f'  {"--version":<25} Show version info and exit.')
        print(f'  {"--show-milestones":<25} Show milestone-to-commit-position map')
        print(f'  {"":25} for the last ~4 years and exit.')
        print(f'  {"--do-not-verify-tls":<25} Disable TLS certificate verification.')
        print(f'  {"-g, --good REVISION":<25} Known good revision. Accepts milestone')
        print(f'  {"":25} (M139, m139, or bare 139), version')
        print(f'  {"":25} string, or commit position.')
        print(f'  {"":25} Default: current stable minus 6.')
        print(f'  {"-a, --archive ARCHIVE":<25} Archive type (auto-detected if omitted).')
        print()
        print('Defaults applied automatically: --verify-range --use-local-cache')
        print(f'  --archive {detected_archive} (auto-detected)')
        print()
        print('-' * 72)
        print('bisect-builds.py options:')
        print('-' * 72)
    else:
        # Always include --verify-range and --use-local-cache
        for flag in ['--verify-range', '--use-local-cache']:
            if flag not in bisect_args:
                bisect_args.append(flag)

        # Apply --archive default
        bisect_args.extend(['--archive', our_args.archive or detected_archive])

        # Apply --good default
        if our_args.good:
            bisect_args.extend(['--good', resolve_milestone_arg(our_args.good)])
        else:
            good = get_relative_chrome_versions(6)
            bisect_args.extend(['--good', resolve_milestone_arg(f'M{good}')])

        # Resolve any milestone values in passthrough args (e.g. --bad M141
        # or --bad 141)
        for i, arg in enumerate(bisect_args):
            if (i > 0 and bisect_args[i - 1] in ('-b', '--bad')
                    and _looks_like_milestone(arg)):
                bisect_args[i] = resolve_milestone_arg(arg)

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
