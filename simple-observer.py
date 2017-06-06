import sys
import os
import time
from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler
from watchdog.events import FileSystemEventHandler
from lxml import etree
from collections import Counter

import json

from xmljson import XMLData

class ZyBooksConvention(XMLData):
    '''Converts between XML and data using a modification of the BadgerFish convention'''

    def __init__(self, **kwargs):
        super(ZyBooksConvention, self).__init__(attr_prefix='@', text_content='$', **kwargs)

    def data(self, root):
        '''Convert etree.Element into a dictionary'''

        value = self.dict()
        children = [node for node in root if isinstance(node.tag, basestring)]
        for attr, attrval in root.attrib.items():
            attr = attr if self.attr_prefix is None else self.attr_prefix + attr
            value[attr] = self._fromstring(attrval)

        # Check for mixed content
        has_children = len(children) > 0
        root_has_text = root.text is not None and root.text.strip()
        child_has_tail = any(child.tail is not None and child.tail.strip() for child in children)
        has_mixed_content = has_children and (root_has_text or child_has_tail)
        mixed_content_key = '#'

        # If the element doesn't have mixed content, just execute the BadgerFish convention
        if not has_mixed_content:
            if root.text and self.text_content is not None:
                text = root.text.strip()
                if text:
                    if self.simple_text and len(children) == len(root.attrib) == 0:
                        value = self._fromstring(text)
                    else:
                        value[self.text_content] = self._fromstring(text)
            count = Counter(child.tag for child in children)
            for child in children:
                if count[child.tag] == 1:
                    value.update(self.data(child))
                else:
                    result = value.setdefault(child.tag, self.list())
                    result += self.data(child).values()

        # Otherwise, if the element has mixed content, add individual text content and children to a list
        else:
            value[mixed_content_key] = list()
            root_text = root.text.strip() if root.text is not None else None

            # Append root text
            if root_text:
                value[mixed_content_key].append({self.text_content: root.text})

            # Append children and tails
            for child in children:
                value[mixed_content_key].append(self.data(child))

                child_tail = child.tail.strip() if child.tail is not None else None
                if child_tail:
                    value[mixed_content_key].append({self.text_content: child.tail})

        return self.dict([(root.tag, value)])

xmljson_convention = ZyBooksConvention()

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

            print json.dumps(xmljson_convention.data(root))
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
