#!/usr/bin/python3
"""Fixture controller: keep the real Qt D-Bus owner alive between commands."""
from importlib.machinery import SourceFileLoader
import json
import os
import sys
from PySide6.QtCore import QCoreApplication

app = QCoreApplication(sys.argv)
pdf = SourceFileLoader("pdf_fixture", os.environ["MONET_PDF_HELPER"]).load_module()
for line in sys.stdin:
    try:
        request = json.loads(line)
        if "armed" in request:
            result = pdf.arm(request["pid"], request["id"], request["armed"])
        else:
            result = pdf.departure(request["pid"], request["id"], request["window"])
        print(json.dumps({"result": result}), flush=True)
    except Exception as error:
        print(json.dumps({"error": str(error)}), flush=True)
