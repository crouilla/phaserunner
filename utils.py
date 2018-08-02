#/usr/local/bin python
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging

try:
    from xml.etree import cElementTree as ET
except:
    from xml.etree import ElementTree as ET
from xml.dom import minidom

def configure_log(level=None, name=None):
    """Configure log parameters. Borrowed from harness logmod.py to keep consistent format,
       but made local to allow for easy modification and dereferencing"""
    if level is None:
        level = logging.INFO
    lgr = logging.getLogger(__name__)
    lgr.setLevel(level)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s      %(levelname)s      %(message)s", "%Y:%m:%dT%H:%M:%S")
    console_handler.setFormatter(formatter)
    lgr.addHandler(console_handler)
    return lgr
    
def prettify_xml(node):
    """Return a pretty-printed XML string for the pass ElementTree node"""
    rough_string = '<?xml version="1.0" encoding="UTF-8"?>'
    rough_string += ET.tostring(node, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return "\n".join([line for line in reparsed.toprettyxml(indent=' '*4).split("\n") if line.strip()])
