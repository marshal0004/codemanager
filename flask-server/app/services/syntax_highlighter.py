"""
Syntax Highlighter Service
Provides server-side syntax highlighting using Pygments library
"""

from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer, get_all_lexers

from pygments.formatters import HtmlFormatter
from pygments.formatters.other import (
    RawTokenFormatter,
)  # Use this instead of JsonFormatter
from pygments.util import ClassNotFound
from pygments.styles import get_all_styles, get_style_by_name
import re
import json
from typing import Dict, List, Optional, Tuple


class SyntaxHighlighter:
    """Server-side syntax highlighting service"""

    def __init__(self):
        self.supported_languages = self._get_supported_languages()
        self.default_style = "default"
        self.available_styles = list(get_all_styles())

    def _get_supported_languages(self) -> Dict[str, List[str]]:
        """Get all supported languages and their aliases"""
        languages = {}
        for name, aliases, filenames, mimetypes in get_all_lexers():
            if aliases:
                languages[aliases[0]] = {
                    "name": name,
                    "aliases": aliases,
                    "filenames": filenames,
                    "mimetypes": mimetypes,
                }
        return languages

    def highlight_code(
        self,
        code: str,
        language: str = None,
        style: str = None,
        output_format: str = "html",
    ) -> Dict:
        """
        Highlight code with specified language and style

        Args:
            code: Source code to highlight
            language: Programming language (auto-detect if None)
            style: Highlighting style (default if None)
            output_format: Output format ('html', 'json', 'terminal')

        Returns:
            Dict with highlighted code and metadata
        """
        try:
            # Get lexer
            if language:
                try:
                    lexer = get_lexer_by_name(language)
                    detected_language = language
                except ClassNotFound:
                    lexer = guess_lexer(code)
                    detected_language = lexer.aliases[0] if lexer.aliases else "text"
            else:
                lexer = guess_lexer(code)
                detected_language = lexer.aliases[0] if lexer.aliases else "text"

            # Set style
            style_name = style or self.default_style
            if style_name not in self.available_styles:
                style_name = self.default_style

            # Get formatter
            if output_format == "html":
                formatter = HtmlFormatter(
                    style=style_name,
                    linenos=True,
                    cssclass="highlight",
                    linenostart=1,
                    hl_lines=[],
                    noclasses=False,
                )
            elif output_format == "json":
                formatter = RawTokenFormatter(style=style_name)
            else:
                formatter = HtmlFormatter(style=style_name, noclasses=True)

            # Highlight code
            highlighted = highlight(code, lexer, formatter)

            # Get CSS for HTML format
            css = ""
            if output_format == "html":
                css = formatter.get_style_defs(".highlight")

            return {
                "success": True,
                "highlighted_code": highlighted,
                "css": css,
                "detected_language": detected_language,
                "style_used": style_name,
                "line_count": len(code.split("\n")),
                "character_count": len(code),
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "highlighted_code": f"<pre><code>{code}</code></pre>",
                "css": "",
                "detected_language": "text",
                "style_used": style_name,
                "line_count": len(code.split("\n")),
                "character_count": len(code),
            }

    def get_language_info(self, language: str) -> Optional[Dict]:
        """Get information about a specific language"""
        return self.supported_languages.get(language)

    def search_languages(self, query: str) -> List[Dict]:
        """Search for languages by name or alias"""
        query = query.lower()
        results = []

        for alias, info in self.supported_languages.items():
            if (
                query in alias.lower()
                or query in info["name"].lower()
                or any(query in a.lower() for a in info["aliases"])
            ):
                results.append(
                    {"alias": alias, "name": info["name"], "aliases": info["aliases"]}
                )

        return results[:20]  # Limit results

    def validate_language(self, language: str) -> bool:
        """Check if language is supported"""
        try:
            get_lexer_by_name(language)
            return True
        except ClassNotFound:
            return False

    def get_css_for_style(self, style: str = None) -> str:
        """Get CSS for a specific style"""
        style_name = style or self.default_style
        if style_name not in self.available_styles:
            style_name = self.default_style

        formatter = HtmlFormatter(style=style_name, cssclass="highlight")
        return formatter.get_style_defs(".highlight")

    def preview_styles(self, code: str, language: str = None) -> Dict[str, str]:
        """Generate preview of code in different styles"""
        previews = {}
        sample_styles = [
            "default",
            "github",
            "monokai",
            "solarized-dark",
            "solarized-light",
            "vim",
            "vs",
            "xcode",
        ]

        for style in sample_styles:
            if style in self.available_styles:
                result = self.highlight_code(code, language, style, "html")
                if result["success"]:
                    previews[style] = result["highlighted_code"]

        return previews

    def extract_functions_classes(self, code: str, language: str) -> List[Dict]:
        """Extract function and class definitions from code"""
        definitions = []

        try:
            # Language-specific patterns
            patterns = {
                "python": [
                    (r"^def\s+(\w+)\s*\([^)]*\):", "function"),
                    (r"^class\s+(\w+)(?:\([^)]*\))?:", "class"),
                    (r"^async\s+def\s+(\w+)\s*\([^)]*\):", "async_function"),
                ],
                "javascript": [
                    (r"function\s+(\w+)\s*\([^)]*\)", "function"),
                    (
                        r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>)",
                        "function",
                    ),
                    (r"class\s+(\w+)", "class"),
                    (r"(\w+)\s*:\s*(?:async\s+)?function", "method"),
                ],
                "java": [
                    (
                        r"(?:public|private|protected)?\s*(?:static\s+)?(?:void|int|String|boolean|\w+)\s+(\w+)\s*\([^)]*\)",
                        "method",
                    ),
                    (r"(?:public|private|protected)?\s*class\s+(\w+)", "class"),
                    (r"(?:public|private|protected)?\s*interface\s+(\w+)", "interface"),
                ],
                "cpp": [
                    (r"(?:\w+\s+)*(\w+)\s*\([^)]*\)\s*{", "function"),
                    (r"class\s+(\w+)", "class"),
                    (r"struct\s+(\w+)", "struct"),
                ],
            }

            lang_patterns = patterns.get(language.lower(), [])
            lines = code.split("\n")

            for i, line in enumerate(lines, 1):
                line = line.strip()
                for pattern, def_type in lang_patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        definitions.append(
                            {
                                "name": match.group(1),
                                "type": def_type,
                                "line": i,
                                "definition": line,
                            }
                        )

        except Exception as e:
            pass  # Return empty list on error

        return definitions

    def get_supported_languages_list(self) -> List[Dict]:
        """Get list of all supported languages"""
        return [
            {
                "alias": alias,
                "name": info["name"],
                "aliases": info["aliases"],
                "filenames": info["filenames"][:5],  # Limit filenames
            }
            for alias, info in self.supported_languages.items()
        ]

    def get_available_styles(self) -> List[str]:
        """Get list of available highlighting styles"""
        return self.available_styles

    def batch_highlight(self, snippets: List[Dict]) -> List[Dict]:
        """Highlight multiple code snippets"""
        results = []

        for snippet in snippets:
            code = snippet.get("code", "")
            language = snippet.get("language")
            style = snippet.get("style")

            result = self.highlight_code(code, language, style)
            result["snippet_id"] = snippet.get("id")
            results.append(result)

        return results


# Global instance
syntax_highlighter = SyntaxHighlighter()
