"""Проверить ограничения оформления Python из страницы 5 задания."""

import ast
from io import StringIO
from pathlib import Path
import tokenize

from radon.complexity import cc_visit
from radon.visitors import Class, Function


MAX_FILE_LINES = 1000
MAX_LINE_LENGTH = 80
MAX_FUNCTION_LINES = 40
MAX_ARGUMENTS = 7
MAX_COMPLEXITY = 10


def inspect_function(node):
    """Проверить длину функции и число всех объявленных аргументов."""
    errors = []
    if node.end_lineno - node.lineno + 1 > MAX_FUNCTION_LINES:
        errors.append(f"{node.name}: function exceeds 40 lines")
    arguments = node.args
    count = len(arguments.posonlyargs + arguments.args + arguments.kwonlyargs)
    count += bool(arguments.vararg) + bool(arguments.kwarg)
    if count > MAX_ARGUMENTS:
        errors.append(f"{node.name}: more than 7 arguments")
    return errors


def inspect_ast(source):
    """Проверить функции и числовые литералы в выражениях сравнения."""
    errors = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            errors.extend(inspect_function(node))
        if isinstance(node, ast.Compare):
            operands = [node.left] + node.comparators
            for operand in operands:
                if isinstance(operand, ast.Constant):
                    value = operand.value
                    if isinstance(value, (int, float)) and value not in {0, 1}:
                        errors.append(
                            f"line {node.lineno}: numeric comparison")
    return errors


def inspect_complexity(source):
    """Ограничить цикломатическую сложность каждой функции значением 10."""
    errors = []
    for block in cc_visit(source):
        functions = block.methods if isinstance(block, Class) else [block]
        for function in functions:
            if isinstance(function, Function):
                if function.complexity > MAX_COMPLEXITY:
                    errors.append(f"{function.name}: complexity exceeds 10")
    return errors


def inspect_file(path):
    """Проверить размеры файла, отсутствие комментариев и его AST."""
    source = path.read_text("utf-8")
    lines = source.splitlines()
    errors = []
    if len(lines) > MAX_FILE_LINES:
        errors.append("more than 1000 lines")
    if any(len(line) > MAX_LINE_LENGTH for line in lines):
        errors.append("line exceeds 80 characters")
    tokens = tokenize.generate_tokens(StringIO(source).readline)
    if any(token.type == tokenize.COMMENT for token in tokens):
        errors.append("comments outside docstrings")
    return errors + inspect_ast(source) + inspect_complexity(source)


def main():
    """Проверить все собственные файлы проекта и вернуть код проверки."""
    paths = [path for folder in ("src", "tests", "examples", "tools")
             for path in Path(folder).rglob("*.py")]
    errors = [f"{path}: {error}" for path in paths
              for error in inspect_file(path)]
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"OK: {len(paths)} Python files; "
          "limits 1000/80/40/7, complexity <=10")


if __name__ == "__main__":
    main()
