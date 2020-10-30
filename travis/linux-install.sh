if [[ "$TRAVIS_JOB_NAME" == *"Testing" ]]; then
  export me="$python -m break19"
  export mypath=$(readlink -e .)
else
  export mypath="dist/break19"
  rm -rf $mypath
  mkdir -p $mypath
  export mypath=$(readlink -e $mypath)
  $python -OO -m PyInstaller --clean --noupx --strip -F --distpath $mypath break19.spec
  export me="${mypath}/break19"
  export MYVERSION=`$me --version`
  cp LICENSE $mypath
  MY_ARCHIVE=break19-$MYVERSION-$MYOS-$PLATFORM.tar.xz
  # tar will cd to dist and tar
  tar -C dist/ --create --file $MY_ARCHIVE --xz break19
  echo "PyInstaller info:"
  du -h $me
  time $me version
  echo "My packages:"
  ls -l break19-*.tar.xz
fi
