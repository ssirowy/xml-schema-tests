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

    def __init__(self, path='.', write_path=None):
        super(XMLObserver, self).__init__()

        self.path = path
        self.write_path = write_path

    def parse_chapter(self):
        '''
        Returns a list of dictionaries with section xml file names.
        '''

        schema_file_name = os.path.join(self.path, 'chapter-schema.xsd')
        with open(schema_file_name, 'r') as schema_file:
            schema = schema_file.read()

        schema_root = etree.XML(schema)
        schema = etree.XMLSchema(schema_root)

        chapter_file_name = os.path.join(self.path, 'chapter1/chapter.xml')
        with open(chapter_file_name, 'r') as chapter_file:
            chapter1 = chapter_file.read()

        parser = etree.XMLParser(schema = schema)
        sections = []

        try:
            root = etree.fromstring(chapter1, parser)
            json_val = xmljson_convention.data(root)
            json_sections = json_val['chapter']['sections']['section']

            if type(json_sections) is not list:
                sections.append(json_sections)
            else:
                sections.extend(json_sections)

            #print(json.dumps(sections))
        except etree.XMLSyntaxError, e:
            print 'ERROR parsing chapter'
            print e
            return None

        return sections

    def parse_section(self, xml_filename):
        '''
        Validates a section's xml file and returns a JSON representation.
        '''

        json_section = None
        schema_file_name = os.path.join(self.path, 'section-schema.xsd')
        with open(schema_file_name, 'r') as schema_file:
            schema = schema_file.read()

        schema_root = etree.XML(schema)
        schema = etree.XMLSchema(schema_root)

        section_file_name = os.path.join(self.path, 'chapter1', xml_filename)

        if os.path.isfile(section_file_name):
            with open(section_file_name, 'r') as section_file:
                sample_section = section_file.read()

            parser = etree.XMLParser(schema = schema)

            try:
                root = etree.fromstring(sample_section, parser)
                json_section = xmljson_convention.data(root)['section']

                #print(json.dumps(json_section))
            except etree.XMLSyntaxError, e:
                print 'ERROR parsing section file: %s' %xml_filename
                print e

                return None

        else:
            print 'ERROR: file %s does not exist' % xml_filename

        return json_section

    def dispatch(self, event):

        # Get a list of section files from a chapter's xml
        section_files = self.parse_chapter()

        if not section_files:
            return

        sections = []
        error = False

        # Validate each of the section xml files and add corresponding JSON list
        for section_file in section_files:
            section = self.parse_section(section_file['@file'].strip())

            if section is not None:
                sections.append(section)
            else:
                error = True
                break

        # Write data to file
        if not error:
            output_str = 'export default function fetchSectionData() { return %s; }' % json.dumps(sections)
            if self.write_path:
                with open(self.write_path, 'w') as output_file:
                    output_file.write(output_str)

            print output_str





if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else '.'

    write_path = sys.argv[2] if len(sys.argv) > 2 else None

    print "Watching %s for changes" % path

    event_handler = XMLObserver(path = path, write_path = write_path)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
