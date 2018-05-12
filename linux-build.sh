rm -rf chrome-bisect
rm -rf build
rm -rf dist
rm -rf chrome-bisect-$1-linux-$(arch).tar.xz

export LD_LIBRARY_PATH=/usr/local/lib
pyinstaller --clean -F --distpath=chrome-bisect linux.spec
cp LICENSE chrome-bisect

tar cfJ chrome-bisect-$1-linux-$(arch).tar.xz chrome-bisect/
