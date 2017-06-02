import sys
import os
import time
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler
from watchdog.events import FileSystemEventHandler
from lxml import etree

from xmljson import badgerfish as bf

import json

class XMLObserver(FileSystemEventHandler):

    def __init__(self, path='.'):
        super(XMLObserver, self).__init__()

        self.path = path

    def dispatch(self, event):

        schema_file_name = os.path.join(self.path, 'schema.xsd')
        with open(schema_file_name, 'r') as schema_file:
            schema = schema_file.read()

        schema_root = etree.XML(schema)
        schema = etree.XMLSchema(schema_root)

        section_file_name = os.path.join(self.path, 'sample-section.xml')
        with open(section_file_name, 'r') as section_file:
            sample_section = section_file.read()

        parser = etree.XMLParser(schema = schema)

        try:
            root = etree.fromstring(sample_section, parser)

            print json.dumps(bf.data(root))
        except etree.XMLSyntaxError, e:
            print 'ERROR'

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else '.'

    print "Watching %s for changes" % path

    event_handler = XMLObserver(path = path)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
