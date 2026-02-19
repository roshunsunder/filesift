"""Per-language regex extractors for structural code analysis."""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Tuple

EXT_TO_LANGUAGE: Dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".swift": "swift",
    ".html": "html",
    ".css": "css",
    ".txt": "text",
    ".md": "markdown",
    ".rst": "text",
    ".log": "text",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".xml": "xml",
    ".csv": "csv",
    ".toml": "toml",
    ".ini": "config",
    ".conf": "config",
    ".cfg": "config",
    ".properties": "config",
    ".env": "config",
}

SUPPORTED_EXTENSIONS = set(EXT_TO_LANGUAGE.keys())


@dataclass
class ExtractionResult:
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    comments: List[str] = field(default_factory=list)


def detect_language(extension: str) -> str:
    return EXT_TO_LANGUAGE.get(extension.lower(), "unknown")


# ---------- Python ----------

def _extract_python(content: str) -> ExtractionResult:
    imports = []
    for m in re.finditer(r"^\s*import\s+([\w.]+)", content, re.MULTILINE):
        imports.append(m.group(1))
    for m in re.finditer(r"^\s*from\s+([\w.]+)\s+import", content, re.MULTILINE):
        imports.append(m.group(1))

    functions = [m.group(1) for m in re.finditer(r"^\s*def\s+(\w+)\s*\(", content, re.MULTILINE)]
    classes = [m.group(1) for m in re.finditer(r"^\s*class\s+(\w+)", content, re.MULTILINE)]

    exports = []
    match = re.search(r"^__all__\s*=\s*\[([^\]]*)\]", content, re.MULTILINE)
    if match:
        exports = [s.strip().strip("'\"") for s in match.group(1).split(",") if s.strip()]

    comments = []
    for m in re.finditer(r'"""(.*?)"""', content, re.DOTALL):
        text = m.group(1).strip()
        if text:
            comments.append(text[:200])
    for m in re.finditer(r"'''(.*?)'''", content, re.DOTALL):
        text = m.group(1).strip()
        if text:
            comments.append(text[:200])
    for m in re.finditer(r"^\s*#\s*(.+)$", content, re.MULTILINE):
        text = m.group(1).strip()
        if text and not text.startswith("!"):
            comments.append(text[:200])

    return ExtractionResult(imports=imports, exports=exports, functions=functions, classes=classes, comments=comments)


# ---------- JavaScript / TypeScript ----------

def _extract_javascript(content: str) -> ExtractionResult:
    imports = []
    for m in re.finditer(r"""import\s+.*?\s+from\s+['"]([^'"]+)['"]""", content):
        imports.append(m.group(1))
    for m in re.finditer(r"""require\(\s*['"]([^'"]+)['"]\s*\)""", content):
        imports.append(m.group(1))

    functions = []
    for m in re.finditer(r"function\s+(\w+)\s*\(", content):
        functions.append(m.group(1))
    # Arrow functions: const/let/var name = (...) => or name = async (...) =>
    for m in re.finditer(r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(?", content):
        # Only count if followed by arrow somewhere nearby
        start = m.end()
        snippet = content[start:start + 100]
        if "=>" in snippet:
            functions.append(m.group(1))
    # Method shorthand in objects/classes: name(...) {
    for m in re.finditer(r"^\s+(\w+)\s*\([^)]*\)\s*\{", content, re.MULTILINE):
        name = m.group(1)
        if name not in ("if", "for", "while", "switch", "catch", "constructor"):
            functions.append(name)

    classes = [m.group(1) for m in re.finditer(r"class\s+(\w+)", content)]

    exports = []
    for m in re.finditer(r"export\s+(?:default\s+)?(?:class|function|const|let|var)\s+(\w+)", content):
        exports.append(m.group(1))
    for m in re.finditer(r"module\.exports\s*=\s*(\w+)", content):
        exports.append(m.group(1))

    comments = _extract_c_style_comments(content)

    return ExtractionResult(imports=imports, exports=exports, functions=functions, classes=classes, comments=comments)


# ---------- Java ----------

def _extract_java(content: str) -> ExtractionResult:
    imports = [m.group(1) for m in re.finditer(r"^\s*import\s+([\w.]+);", content, re.MULTILINE)]

    functions = []
    # Method signatures: access modifier + optional static/final + return type + name(
    for m in re.finditer(
        r"(?:public|private|protected)\s+(?:static\s+)?(?:final\s+)?(?:[\w<>\[\]]+)\s+(\w+)\s*\(",
        content,
    ):
        name = m.group(1)
        if name not in ("if", "for", "while", "switch", "catch"):
            functions.append(name)

    classes = []
    for m in re.finditer(r"(?:public\s+)?(?:abstract\s+)?(?:class|interface|enum)\s+(\w+)", content):
        classes.append(m.group(1))

    exports = []  # Java doesn't have a direct export mechanism
    comments = _extract_c_style_comments(content)

    return ExtractionResult(imports=imports, exports=exports, functions=functions, classes=classes, comments=comments)


# ---------- Go ----------

def _extract_go(content: str) -> ExtractionResult:
    imports = []
    # Single import
    for m in re.finditer(r'^\s*import\s+"([^"]+)"', content, re.MULTILINE):
        imports.append(m.group(1))
    # Block import
    for m in re.finditer(r"import\s*\((.*?)\)", content, re.DOTALL):
        for line in m.group(1).splitlines():
            pkg = line.strip().strip('"')
            if pkg:
                imports.append(pkg)

    functions = [m.group(1) for m in re.finditer(r"^func\s+(?:\([^)]*\)\s+)?(\w+)\s*\(", content, re.MULTILINE)]

    classes = []
    for m in re.finditer(r"^type\s+(\w+)\s+struct\b", content, re.MULTILINE):
        classes.append(m.group(1))
    for m in re.finditer(r"^type\s+(\w+)\s+interface\b", content, re.MULTILINE):
        classes.append(m.group(1))

    exports = [name for name in functions + classes if name and name[0].isupper()]
    comments = _extract_c_style_comments(content)

    return ExtractionResult(imports=imports, exports=exports, functions=functions, classes=classes, comments=comments)


# ---------- Rust ----------

def _extract_rust(content: str) -> ExtractionResult:
    imports = [m.group(1) for m in re.finditer(r"^\s*use\s+([\w:]+)", content, re.MULTILINE)]

    functions = [m.group(1) for m in re.finditer(r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*[<(]", content, re.MULTILINE)]

    classes = []
    for m in re.finditer(r"^\s*(?:pub\s+)?struct\s+(\w+)", content, re.MULTILINE):
        classes.append(m.group(1))
    for m in re.finditer(r"^\s*(?:pub\s+)?enum\s+(\w+)", content, re.MULTILINE):
        classes.append(m.group(1))
    for m in re.finditer(r"^\s*(?:pub\s+)?trait\s+(\w+)", content, re.MULTILINE):
        classes.append(m.group(1))
    for m in re.finditer(r"^\s*impl\s+(\w+)", content, re.MULTILINE):
        if m.group(1) not in classes:
            classes.append(m.group(1))

    exports = [m.group(1) for m in re.finditer(r"^\s*pub\s+(?:fn|struct|enum|trait|mod|const|static|type)\s+(\w+)", content, re.MULTILINE)]

    comments = []
    for m in re.finditer(r"^\s*///\s*(.+)$", content, re.MULTILINE):
        comments.append(m.group(1).strip()[:200])
    comments.extend(_extract_c_style_comments(content))

    return ExtractionResult(imports=imports, exports=exports, functions=functions, classes=classes, comments=comments)


# ---------- C / C++ ----------

def _extract_c(content: str) -> ExtractionResult:
    imports = []
    for m in re.finditer(r'^\s*#include\s*[<"]([^>"]+)[>"]', content, re.MULTILINE):
        imports.append(m.group(1))

    functions = []
    # Heuristic: type name( at start of line, not inside a class
    for m in re.finditer(r"^(?:[\w*&:]+\s+)+(\w+)\s*\([^)]*\)\s*\{", content, re.MULTILINE):
        name = m.group(1)
        if name not in ("if", "for", "while", "switch", "catch", "return"):
            functions.append(name)

    classes = []
    for m in re.finditer(r"^\s*(?:class|struct)\s+(\w+)", content, re.MULTILINE):
        classes.append(m.group(1))

    comments = _extract_c_style_comments(content)

    return ExtractionResult(imports=imports, functions=functions, classes=classes, comments=comments)


# ---------- Ruby ----------

def _extract_ruby(content: str) -> ExtractionResult:
    imports = []
    for m in re.finditer(r"""^\s*require(?:_relative)?\s+['"]([^'"]+)['"]""", content, re.MULTILINE):
        imports.append(m.group(1))

    functions = [m.group(1) for m in re.finditer(r"^\s*def\s+(\w+)", content, re.MULTILINE)]

    classes = []
    for m in re.finditer(r"^\s*class\s+(\w+)", content, re.MULTILINE):
        classes.append(m.group(1))
    for m in re.finditer(r"^\s*module\s+(\w+)", content, re.MULTILINE):
        classes.append(m.group(1))

    comments = [m.group(1).strip()[:200] for m in re.finditer(r"^\s*#\s*(.+)$", content, re.MULTILINE)]

    return ExtractionResult(imports=imports, functions=functions, classes=classes, comments=comments)


# ---------- PHP ----------

def _extract_php(content: str) -> ExtractionResult:
    imports = []
    for m in re.finditer(r"""^\s*use\s+([\w\\]+)""", content, re.MULTILINE):
        imports.append(m.group(1))
    for m in re.finditer(r"""^\s*(?:require|include)(?:_once)?\s+['"]([^'"]+)['"]""", content, re.MULTILINE):
        imports.append(m.group(1))

    functions = [m.group(1) for m in re.finditer(r"function\s+(\w+)\s*\(", content)]
    classes = [m.group(1) for m in re.finditer(r"(?:class|interface|trait)\s+(\w+)", content)]

    comments = _extract_c_style_comments(content)

    return ExtractionResult(imports=imports, functions=functions, classes=classes, comments=comments)


# ---------- C# ----------

def _extract_csharp(content: str) -> ExtractionResult:
    imports = [m.group(1) for m in re.finditer(r"^\s*using\s+([\w.]+)\s*;", content, re.MULTILINE)]

    functions = []
    for m in re.finditer(
        r"(?:public|private|protected|internal)\s+(?:static\s+)?(?:async\s+)?(?:[\w<>\[\]]+)\s+(\w+)\s*\(",
        content,
    ):
        name = m.group(1)
        if name not in ("if", "for", "while", "switch", "catch"):
            functions.append(name)

    classes = []
    for m in re.finditer(r"(?:public\s+)?(?:abstract\s+)?(?:static\s+)?(?:class|interface|struct|enum)\s+(\w+)", content):
        classes.append(m.group(1))

    comments = _extract_c_style_comments(content)

    return ExtractionResult(imports=imports, functions=functions, classes=classes, comments=comments)


# ---------- Shared helpers ----------

def _extract_c_style_comments(content: str) -> List[str]:
    """Extract // and /* */ comments."""
    comments = []
    for m in re.finditer(r"//\s*(.+)$", content, re.MULTILINE):
        text = m.group(1).strip()
        if text:
            comments.append(text[:200])
    for m in re.finditer(r"/\*\s*(.*?)\s*\*/", content, re.DOTALL):
        text = m.group(1).strip()
        if text:
            comments.append(text[:200])
    return comments


def _extract_generic(content: str) -> ExtractionResult:
    """Fallback extractor — returns empty structured fields."""
    return ExtractionResult()


# ---------- Registry ----------

_EXTRACTORS: Dict[str, Callable[[str], ExtractionResult]] = {
    "python": _extract_python,
    "javascript": _extract_javascript,
    "typescript": _extract_javascript,  # TS is close enough to JS for regex extraction
    "java": _extract_java,
    "go": _extract_go,
    "rust": _extract_rust,
    "c": _extract_c,
    "cpp": _extract_c,
    "ruby": _extract_ruby,
    "php": _extract_php,
    "csharp": _extract_csharp,
}


def extract(language: str, content: str) -> ExtractionResult:
    """Run the appropriate extractor for the given language.

    Returns an ExtractionResult (possibly empty for unsupported languages).
    """
    extractor = _EXTRACTORS.get(language, _extract_generic)
    return extractor(content)
