import os
import sys

# Append root directory to sys.path so app, pdf_parser, etc. can be imported cleanly
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app

# Vercel serverless WSGI handler
app.debug = False
