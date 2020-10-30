echo "MacOS Version Info According to Python:"
python -c "import platform; print(platform.mac_ver())"
export mypath=dist/chrome-bisect
rm -rf $mypath
$python -OO -m PyInstaller --clean --noupx --strip -F --distpath $mypath chrome-bisect.spec
export me="$mypath/chrome-bisect"
$me --version
export MYVERSION=`$me --version`
cp LICENSE $mypath
MACOSVERSION=$(defaults read loginwindow SystemVersionStampAsString)
MY_ARCHIVE=chrome-bisect-$MYVERSION-$MYOS-$PLATFORM-MacOS$MACOSVERSION.tar.xz
# tar will cd to dist/ and tar
tar -C dist/ --create --file $MY_ARCHIVE --xz chrome-bisect
