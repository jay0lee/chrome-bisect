echo "compiling with pyinstaller..."
export mypath="dist/chrome-bisect"
rm -rf $mypath
mkdir -p $mypath
export mypath=$(readlink -e $mypath)
pyinstaller --clean --noupx -F --distpath $mypath chrome-bisect.spec
export me="${mypath}/chrome-bisect"
echo "running compiled..."
$me --version
export MYVERSION=`$me --version`
cp LICENSE $mypath
MY_ARCHIVE=chrome-bisect-$MYVERSION-$MYOS-$PLATFORM.zip
/c/Program\ Files/7-Zip/7z.exe a -tzip $MY_ARCHIVE $mypath -xr!.svn

echo "Running WIX candle $WIX_BITS..."
/c/Program\ Files\ \(x86\)/WiX\ Toolset\ v3.11/bin/candle.exe -arch $WIX_BITS chrome-bisect.wxs
echo "Done with WIX candle..."
echo "Running WIX light..."
/c/Program\ Files\ \(x86\)/WiX\ Toolset\ v3.11/bin/light.exe -ext /c/Program\ Files\ \(x86\)/WiX\ Toolset\ v3.11/bin/WixUIExtension.dll chrome-bisect.wixobj -o chrome-bisect-$MYVERSION-$MYOS-$PLATFORM.msi || true;
echo "Done with WIX light..."
rm *.wixpdb
