import re


class GCodeParser:
    def __init__(self, handlers=None):
        self.handlers = handlers or {}

    def parse_line(self, text, line_number):
        text = re.sub(r';.*$', '', text).strip()
        if text:
            tokens = text.split()
            if tokens:
                cmd = tokens[0]
                args = {'cmd': cmd}
                for token in tokens[1:]:
                    key = token[0].lower()
                    try:
                        value = float(token[1:])
                        args[key] = value
                    except ValueError:
                        pass
                handler = self.handlers.get(tokens[0], self.handlers.get('default'))
                if handler:
                    return handler(args, line_number)

    def parse(self, gcode):
        lines = gcode.split('\n')
        for i, line in enumerate(lines):
            if self.parse_line(line, i) is False:
                break