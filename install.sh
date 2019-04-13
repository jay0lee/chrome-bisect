#!/usr/bin/env bash

usage()
{
cat << EOF
Chrome Bisect Installation Script.

OPTIONS:
   -h      show help.
   -d      Directory where chrome-bisect folder will be installed. Default is \$HOME/bin/
   -a      Architecture to install (i386, x86_64, arm). Default is to detect your arch with "uname -m".
   -o      OS we are running (linux, osx). Default is to detect your OS with "uname -s".
   -l      Just upgrade Chrome Bisect to latest version. Skips project creation and auth.
   -p      Profile update (true, false). Should script add chrome-bisect command to environment. Default is true.
   -v      Version to install (latest, prerelease, draft, 3.8, etc). Default is latest.
EOF
}

target_dir="$HOME/bin"
cbarch=$(uname -m)
cbos=$(uname -s)
update_profile=true
upgrade_only=false
cbversion="latest"
while getopts "hd:a:o:lp:v:" OPTION
do
     case $OPTION in
         h) usage; exit;;
         d) target_dir="$OPTARG";;
         a) cbarch="$OPTARG";;
         o) cbos="$OPTARG";;
         l) upgrade_only=true;;
         p) update_profile="$OPTARG";;
         v) cbversion="$OPTARG";;
         ?) usage; exit;;
     esac
done

# remove possible / from end of target_dir
target_dir=${target_dir%/}

update_profile() {
	[ -f "$1" ] || return 1
	grep -F "$alias_line" "$1" > /dev/null 2>&1
	if [ $? -ne 0 ]; then
                echo_yellow "Adding chrome-bisect alias to profile file $1."
		echo -e "\n$alias_line" >> "$1"
        else
          echo_yellow "chrome-bisect alias already exists in profile file $1. Skipping add."
	fi
}

echo_red()
{
echo -e "\x1B[1;31m$1"
echo -e '\x1B[0m'
}

echo_green()
{
echo -e "\x1B[1;32m$1"
echo -e '\x1B[0m'
}

echo_yellow()
{
echo -e "\x1B[1;33m$1"
echo -e '\x1B[0m'
}

case $cbos in
  [lL]inux)
    cbos="linux"
    case $cbarch in
      x86_64) cbfile="linux.tar.xz";;
      i?86) cbfile="linux.tar.xz";;
      arm*) cbfile="linux-armv7l.tar.xz";;
      *)
        echo_red "ERROR: this installer currently only supports i386, x86_64 and arm Linux. Looks like you're running on $cbarch. Exiting."
        exit
    esac
    ;;
  [Mm]ac[Oo][sS]|[Dd]arwin)
    osver=$(sw_vers -productVersion | awk -F'.' '{print $2}')
    if (( $osver < 10 )); then
      echo_red "ERROR: Chrome Bisect currently requires MacOS 10.10 or newer. You are running MacOS 10.$osver. Please upgrade." 
      exit
    else
      echo_green "Good, you're running MacOS 10.$osver..."
    fi
    cbos="osx"
    cbfile="osx.tar.xz"
    ;;
  *)
    echo_red "Sorry, this installer currently only supports Linux and MacOS. Looks like you're runnning on $cbos. Exiting."
    exit
    ;;
esac

if [ "$cbversion" == "latest" -o "$cbversion" == "prerelease" -o "$cbversion" == "draft" ]; then
  release_url="https://api.github.com/repos/jay0lee/chrome-bisect/releases"
else
  release_url="https://api.github.com/repos/jay0lee/chrome-bisect/releases/tags/v$cbversion"
fi

echo_yellow "Checking GitHub URL $release_url for $cbversion Chrome Bisect release..."
release_json=$(curl -s $release_url 2>&1 /dev/null)

echo_yellow "Getting file and download URL..."
# Python is sadly the nearest to universal way to safely handle JSON with Bash
# At least this code should be compatible with just about any Python version ever
# unlike Chrome Bisect itself. If some users don't have Python we can try grep / sed / etc
# but that gets really ugly
pycode="import json
import sys

attrib = sys.argv[1]
cbversion = sys.argv[2]

release = json.load(sys.stdin)
if type(release) is list:
  for a_release in release:
    if a_release['prerelease'] and cbversion != 'prerelease':
      continue
    elif a_release['draft'] and cbversion != 'draft':
      continue
    release = a_release
    break
for asset in release['assets']:
  if asset[sys.argv[1]].endswith('$cbfile'):
    print(asset[sys.argv[1]])
    break"

pycmd="python"
$pycmd -V >/dev/null 2>&1
rc=$?
if (( $rc != 0 )); then
  pycmd="python3"
fi
$pycmd -V >/dev/null 2>&1
rc=$?
if (( $rc != 0 )); then
  echo_red "ERROR: No version of python installed."
  exit
fi

browser_download_url=$(echo "$release_json" | $pycmd -c "$pycode" browser_download_url $cbversion)
name=$(echo "$release_json" | $pycmd -c "$pycode" name $cbversion)
# Temp dir for archive
temp_archive_dir=$(mktemp -d 2>/dev/null || mktemp -d -t 'mytmpdir')
echo_yellow "Downloading file $name from $browser_download_url to $temp_archive_dir."
# Save archive to temp w/o losing our path
(cd $temp_archive_dir && curl -O -L $browser_download_url)

mkdir -p "$target_dir"

echo_yellow "Extracting archive to $target_dir"
tar xf $temp_archive_dir/$name -C "$target_dir"
rc=$?
if (( $rc != 0 )); then
  echo_red "ERROR: extracting the Chrome Bisect archive with tar failed with error $rc. Exiting."
  exit
else
  echo_green "Finished extracting Chrome Bisect archive."
fi

if [ "$upgrade_only" = true ]; then
  echo_green "Here's information about your Chrome Bisect upgrade:"
  "$target_dir/chrome-bisect/chrome-bisect" --version
  rc=$?
  if (( $rc != 0 )); then
    echo_red "ERROR: Failed running Chrome Bisect for the first time with $rc. Please report this error to Chrome Bisect GitHub issues. Exiting."
    exit
  fi
  echo_green "Chrome Bisect upgrade complete!"
  exit
fi

# Update profile to add chrome-bisect command
if [ "$update_profile" = true ]; then
  alias_line="chrome-bisect() { \"$target_dir/chrome-bisect/chrome-bisect\" \"\$@\" ; }"
  if [ "$cbos" == "linux" ]; then
    update_profile "$HOME/.bashrc" || update_profile "$HOME/.bash_profile"
  elif [ "$cbos" == "osx" ]; then
    update_profile "$HOME/.profile" || update_profile "$HOME/.bash_profile"
  fi
else
  echo_yellow "skipping profile update."
fi

echo_green "Here's information about your new Chrome Bisect installation:"
"$target_dir/chrome-bisect/chrome-bisect" --version
rc=$?
if (( $rc != 0 )); then
  echo_red "ERROR: Failed running Chrome Bisect for the first time with $rc. Please report this error to Chrome Bisect GitHub issues. Exiting."
  exit
fi

echo_green "Chrome Bisect installation and setup complete!"
if [ "$update_profile" = true ]; then
  echo_green "Please restart your terminal shell or to get started right away run:\n\n$alias_line"
fi

# Clean up after ourselves even if we are killed with CTRL-C
trap "rm -rf $temp_archive_dir" EXIT
