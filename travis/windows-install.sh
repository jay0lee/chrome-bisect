echo "compiling with pyinstaller..."
export mypath="dist/break19"
rm -rf $mypath
mkdir -p $mypath
export mypath=$(readlink -e $mypath)
pyinstaller --clean --noupx -F --distpath $mypath break19.spec
export me="${mypath}/break19"
echo "running compiled..."
$me --version
export MYVERSION=`$me --version`
cp LICENSE $mypath
MY_ARCHIVE=break19-$MYVERSION-$MYOS-$PLATFORM.zip
/c/Program\ Files/7-Zip/7z.exe a -tzip $MY_ARCHIVE $mypath -xr!.svn

echo "Running WIX candle $WIX_BITS..."
/c/Program\ Files\ \(x86\)/WiX\ Toolset\ v3.11/bin/candle.exe -arch $WIX_BITS break19.wxs
echo "Done with WIX candle..."
echo "Running WIX light..."
/c/Program\ Files\ \(x86\)/WiX\ Toolset\ v3.11/bin/light.exe -ext /c/Program\ Files\ \(x86\)/WiX\ Toolset\ v3.11/bin/WixUIExtension.dll break19.wixobj -o break19-$MYVERSION-$MYOS-$PLATFORM.msi || true;
echo "Done with WIX light..."
rm *.wixpdb
