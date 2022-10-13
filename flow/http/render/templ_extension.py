from jinja2.ext import Extension
from jinja2 import nodes
from abc import abstractmethod


class BaseExtension(Extension):
    """
    Base extension class. All extensions should inherit from it.
    """

    # Extensiom name.
    tags = []

    def parse(self, parser):
        lineno = parser.stream.expect(f'name:{self.tags[0]}').lineno
        parse_expression = [parser.parse_expression()]
        if parser.stream.skip_if("comma"):
            parse_expression.append(parser.parse_expression())
        #else:
        #    parse_expression.append(nodes.Const(None))
        call = self.call_method('handler', parse_expression, lineno=lineno)
        return nodes.Output([nodes.MarkSafe(call)]).set_lineno(lineno)

    @abstractmethod
    def handler(self) -> str:
        """
        Extension handler.
        """
        pass

