rm -rf chrome-bisect
rm -rf build
rm -rf dist
rm -rf chrome-bisect-$1-macos.tar.xz

/Library/Frameworks/Python.framework/Versions/2.7/bin/pyinstaller --clean -F --distpath=chrome-bisect macos.spec
cp LICENSE chrome-bisect

tar cfJ chrome-bisect-$1-macos.tar.xz chrome-bisect/ 
