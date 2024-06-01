"""
Parser class is a factory of parsers. It returns an oject based on the extension.

Task:
  -> Implement a proper design pattern
"""
from parse_file import ParseFile

class Parse():
    @classmethod
    def create_parser(cls, file_name, RecordQueue):
        return ParseFile(file_name, RecordQueue)

