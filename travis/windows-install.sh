echo "compiling with pyinstaller..."
export mypath="dist/chrome-bisect"
rm -rf $mypath
mkdir -p $mypath
export mypath=$(readlink -e $mypath)
pyinstaller --clean --noupx -F --distpath $mypath chrome-bisect.spec
export me="${mypath}/chrome-bisect"
echo "running compiled..."
$me --version
export MYVERSION=`$me --short-version`
cp LICENSE $mypath
MY_ARCHIVE=chrome-bisect-$MYVERSION-$MYOS-$PLATFORM.zip
/c/Program\ Files/7-Zip/7z.exe a -tzip $MY_ARCHIVE $mypath -xr!.svn
