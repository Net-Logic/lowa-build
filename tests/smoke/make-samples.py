"""Create one small document per format in tests/smoke/samples/ with the host's desktop LibreOffice.
Usage: python3 tests/smoke/make-samples.py   (needs /usr/lib/libreoffice and python3-uno)"""
import os
import subprocess
import time

import uno
from com.sun.star.beans import PropertyValue

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'samples')
DOCS = [  # factory, extension, filter
    ('swriter', 'odt', 'writer8'), ('swriter', 'docx', 'MS Word 2007 XML'),
    ('scalc', 'ods', 'calc8'), ('scalc', 'xlsx', 'Calc MS Excel 2007 XML'),
    ('simpress', 'odp', 'impress8'), ('simpress', 'pptx', 'Impress MS PowerPoint 2007 XML'),
    ('sdraw', 'odg', 'draw8'),
]


def prop(name, value):
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def main():
    os.makedirs(OUT, exist_ok=True)
    office = subprocess.Popen(['soffice', '--headless', '--invisible', '--norestore',
                               '-env:UserInstallation=file:///tmp/lowa-samples-profile',
                               '--accept=socket,host=127.0.0.1,port=2083;urp;'])
    try:
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local)
        ctx = None
        for _ in range(60):
            try:
                ctx = resolver.resolve('uno:socket,host=127.0.0.1,port=2083;urp;StarOffice.ComponentContext')
                break
            except Exception:
                time.sleep(0.5)
        desktop = ctx.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', ctx)
        for factory, ext, filt in DOCS:
            doc = desktop.loadComponentFromURL('private:factory/' + factory, '_blank', 0, (prop('Hidden', True),))
            if factory == 'swriter':
                doc.getText().setString('Smoke test ' + ext)
            elif factory == 'scalc':
                doc.getSheets().getByIndex(0).getCellByPosition(0, 0).setString('Smoke test ' + ext)
            doc.storeToURL(uno.systemPathToFileUrl(os.path.join(OUT, 'sample.' + ext)), (prop('FilterName', filt),))
            doc.close(True)
            print('sample.' + ext)
    finally:
        office.terminate()


if __name__ == '__main__':
    main()
