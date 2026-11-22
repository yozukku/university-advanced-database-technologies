import contextlib
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue
from com.sun.star.connection import NoConnectException
from com.sun.star.lang import DisposedException


def option(name, value):
    result = PropertyValue()
    result.Name = name
    result.Value = value
    return result


def connect(pipe):
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    deadline = time.monotonic() + 120
    while True:
        try:
            context = resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
            return context.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", context)
        except NoConnectException:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.2)


def convert(desktop, source, docx, pdf):
    document = desktop.loadComponentFromURL(Path(source).as_uri(), "_blank", 0, (option("Hidden", True),))
    indexes = document.getDocumentIndexes()
    if indexes.getCount() == 0:
        sys.exit("Dokument nie ma spisu treści")
    for position in range(indexes.getCount()):
        indexes.getByIndex(position).update()
    tables = document.getTextTables()
    for position in range(tables.getCount()):
        rows = tables.getByIndex(position).getRows()
        for row in range(rows.getCount()):
            rows.getByIndex(row).setPropertyValue("IsSplitAllowed", False)
    document.storeToURL(Path(docx).as_uri(), (option("FilterName", "MS Word 2007 XML"),))
    document.storeToURL(Path(pdf).as_uri(), (option("FilterName", "writer_pdf_Export"),))
    document.close(True)


def main(source, docx, pdf):
    pipe = f"ztb-report-{os.getpid()}"
    with tempfile.TemporaryDirectory() as profile:
        office = subprocess.Popen(["soffice", "--headless", "--invisible", "--nologo", "--norestore", "--nodefault",
                                   f"--accept=pipe,name={pipe};urp;", f"-env:UserInstallation={Path(profile).as_uri()}"])
        try:
            desktop = connect(pipe)
            try:
                convert(desktop, source, docx, pdf)
            finally:
                with contextlib.suppress(DisposedException):
                    desktop.terminate()
            office.wait(60)
        finally:
            if office.poll() is None:
                office.kill()


if __name__ == "__main__":
    main(*sys.argv[1:])
