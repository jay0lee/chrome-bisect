echo "MacOS Version Info According to Python:"
python -c "import platform; print(platform.mac_ver())"
export mypath=dist/break19
rm -rf $mypath
$python -OO -m PyInstaller --clean --noupx --strip -F --distpath $mypath break19.spec
export me="$mypath/break19"
$me --version
export MYVERSION=`$me --version`
cp LICENSE $mypath
MACOSVERSION=$(defaults read loginwindow SystemVersionStampAsString)
MY_ARCHIVE=break19-$MYVERSION-$MYOS-$PLATFORM-MacOS$MACOSVERSION.tar.xz
# tar will cd to dist/ and tar
tar -C dist/ --create --file $MY_ARCHIVE --xz break19
