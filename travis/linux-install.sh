  export mypath="dist/chrome-bisect"
  rm -rf $mypath
  mkdir -p $mypath
  export mypath=$(readlink -e $mypath)
  $python -OO -m PyInstaller --clean --noupx --strip -F --distpath $mypath chrome-bisect.spec
  export me="${mypath}/chrome-bisect"
  export MYVERSION=`$me --version`
  cp LICENSE $mypath
  MY_ARCHIVE=chrome-bisect-$MYVERSION-$MYOS-$PLATFORM.tar.xz
  # tar will cd to dist and tar
  tar -C dist/ --create --file $MY_ARCHIVE --xz chrome-bisect
  echo "PyInstaller info:"
  du -h $me
  time $me version
  echo "My packages:"
  ls -l chrome-bisect-*.tar.xz
