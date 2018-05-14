# -*- mode: python -*-
a = Analysis(['chrome-bisect.py'],
             pathex=['C:\\Users\\jlee\\Documents\\GitHub\\GAM'],
             hiddenimports=[],
             hookspath=None,
             excludes=['_tkinter'],
             runtime_hooks=None)
for d in a.datas:
    if 'pyconfig' in d[0]:
        a.datas.remove(d)
        break
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='chrome-bisect.exe',
          debug=False,
          strip=None,
          upx=False,
          console=True )
