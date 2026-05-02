"""
Snippet Analyzer Service
Provides language detection, auto-tagging, and code analysis
"""

import re
import hashlib
from typing import Dict, List, Optional, Set, Tuple
from collections import Counter
import keyword
from pygments.lexers import guess_lexer, get_lexer_by_name
from pygments.util import ClassNotFound

class SnippetAnalyzer:
    """Analyzes code snippets for language detection and auto-tagging"""

    def __init__(self):
        self.language_keywords = self._initialize_language_keywords()
        self.framework_patterns = self._initialize_framework_patterns()
        self.common_tags = self._initialize_common_tags()

    def _initialize_language_keywords(self) -> Dict[str, Set[str]]:
        """Initialize language-specific keywords for better detection"""
        return {
            'python': {
                'def', 'class', 'import', 'from', 'if', 'elif', 'else', 'for', 'while',
                'try', 'except', 'finally', 'with', 'as', 'lambda', 'yield', 'async',
                'await', 'nonlocal', 'global', '__init__', 'self', 'None', 'True', 'False'
            },
            'javascript': {
                'function', 'var', 'let', 'const', 'if', 'else', 'for', 'while', 'do',
                'switch', 'case', 'break', 'continue', 'return', 'try', 'catch', 'finally',
                'async', 'await', 'class', 'extends', 'constructor', 'this', 'null', 'undefined'
            },
            'java': {
                'public', 'private', 'protected', 'static', 'final', 'abstract', 'class',
                'interface', 'extends', 'implements', 'import', 'package', 'if', 'else',
                'for', 'while', 'do', 'switch', 'case', 'break', 'continue', 'return',
                'try', 'catch', 'finally', 'throw', 'throws', 'new', 'this', 'super'
            },
            'cpp': {
                'include', 'using', 'namespace', 'class', 'struct', 'public', 'private',
                'protected', 'virtual', 'static', 'const', 'if', 'else', 'for', 'while',
                'do', 'switch', 'case', 'break', 'continue', 'return', 'try', 'catch',
                'throw', 'new', 'delete', 'this', 'nullptr'
            },
            'csharp': {
                'using', 'namespace', 'class', 'struct', 'interface', 'public', 'private',
                'protected', 'internal', 'static', 'readonly', 'const', 'if', 'else',
                'for', 'foreach', 'while', 'do', 'switch', 'case', 'break', 'continue',
                'return', 'try', 'catch', 'finally', 'throw', 'new', 'this', 'base'
            },
            'go': {
                'package', 'import', 'func', 'var', 'const', 'type', 'struct', 'interface',
                'if', 'else', 'for', 'range', 'switch', 'case', 'break', 'continue',
                'return', 'defer', 'go', 'chan', 'select', 'nil'
            },
            'rust': {
                'fn', 'let', 'mut', 'const', 'static', 'struct', 'enum', 'impl', 'trait',
                'use', 'mod', 'pub', 'crate', 'if', 'else', 'match', 'for', 'while',
                'loop', 'break', 'continue', 'return', 'Some', 'None', 'Ok', 'Err'
            }
        }

    def _initialize_framework_patterns(self) -> Dict[str, List[str]]:
        """Initialize framework and library detection patterns"""
        return {
            'react': [
                r'import\s+.*from\s+[\'"]react[\'"]',
                r'useState|useEffect|useContext',
                r'<\w+.*?/?>|<\/\w+>',
                r'jsx|tsx',
                r'ReactDOM\.render'
            ],
            'vue': [
                r'<template>|<script>|<style>',
                r'v-if|v-for|v-model|v-show',
                r'@click|@submit|@change',
                r'{{.*?}}',
                r'Vue\.component|new Vue'
            ],
            'angular': [
                r'@Component|@Injectable|@NgModule',
                r'\*ngFor|\*ngIf|ngModel',
                r'import.*@angular',
                r'\[\(.*?\)\]|\(.*?\)=',
                r'constructor.*inject'
            ],
            'django': [
                r'from django\..*import',
                r'models\.Model|forms\.Form',
                r'def get|def post|def put|def delete',
                r'HttpResponse|JsonResponse',
                r'{% .*? %}|{{ .*? }}'
            ],
            'flask': [
                r'from flask import',
                r'@app\.route|@bp\.route',
                r'Flask\(__name__\)',
                r'request\.|session\.',
                r'render_template|jsonify'
            ],
            'express': [
                r'require\([\'"]express[\'"]\)',
                r'app\.get|app\.post|app\.put|app\.delete',
                r'req\.|res\.',
                r'express\.Router\(\)',
                r'middleware'
            ],
            'spring': [
                r'@RestController|@Controller',
                r'@RequestMapping|@GetMapping|@PostMapping',
                r'@Autowired|@Service|@Repository',
                r'import org\.springframework',
                r'ResponseEntity'
            ]
        }

    def _initialize_common_tags(self) -> Dict[str, List[str]]:
        """Initialize common programming tags"""
        return {
            'algorithm': ['sort', 'search', 'binary', 'recursion', 'dynamic', 'graph', 'tree'],
            'data-structure': ['array', 'list', 'dict', 'map', 'set', 'stack', 'queue', 'heap'],
            'web-development': ['html', 'css', 'javascript', 'http', 'api', 'rest', 'ajax'],
            'database': ['sql', 'query', 'select', 'insert', 'update', 'delete', 'join'],
            'authentication': ['login', 'password', 'token', 'jwt', 'auth', 'session', 'oauth'],
            'testing': ['test', 'mock', 'assert', 'unittest', 'jest', 'pytest', 'spec'],
            'async': ['async', 'await', 'promise', 'callback', 'thread', 'concurrent'],
            'utility': ['helper', 'util', 'config', 'settings', 'common', 'shared'],
            'error-handling': ['try', 'catch', 'exception', 'error', 'throw', 'handle']
        }

    def analyze_snippet(self, code: str, filename: str = None, 
                       provided_language: str = None) -> Dict:
        """
        Comprehensive analysis of a code snippet
        
        Args:
            code: Source code to analyze
            filename: Optional filename for extension-based detection
            provided_language: Optional language hint
        
        Returns:
            Dict with analysis results
        """
        # Basic metrics
        lines = code.split('\n')
        line_count = len(lines)
        char_count = len(code)
        non_empty_lines = len([line for line in lines if line.strip()])

        # Language detection
        language_info = self.detect_language(code, filename, provided_language)

        # Generate tags
        auto_tags = self.generate_auto_tags(code, language_info['detected_language'])

        # Complexity analysis
        complexity = self.analyze_complexity(code, language_info['detected_language'])

        # Extract important elements
        functions = self.extract_functions(code, language_info['detected_language'])
        imports = self.extract_imports(code, language_info['detected_language'])

        # Security analysis
        security_issues = self.analyze_security(code, language_info['detected_language'])

        # Generate hash for duplicate detection
        content_hash = self.generate_content_hash(code)

        # Framework detection
        frameworks = self.detect_frameworks(code)

        return {
            'language': language_info,
            'metrics': {
                'line_count': line_count,
                'character_count': char_count,
                'non_empty_lines': non_empty_lines,
                'blank_lines': line_count - non_empty_lines,
                'avg_line_length': char_count / line_count if line_count > 0 else 0
            },
            'auto_tags': auto_tags,
            'complexity': complexity,
            'functions': functions,
            'imports': imports,
            'frameworks': frameworks,
            'security_issues': security_issues,
            'content_hash': content_hash,
            'analysis_timestamp': None  # Will be set by the service layer
        }

    def detect_language(self, code: str, filename: str = None, 
                       hint: str = None) -> Dict:
        """Detect programming language with multiple strategies"""
        confidence_scores = {}
        detected_language = 'text'

        # Strategy 1: Use provided hint
        if hint:
            try:
                get_lexer_by_name(hint)
                confidence_scores['hint'] = 0.9
                detected_language = hint
            except ClassNotFound:
                pass

        # Strategy 2: Filename extension
        if filename:
            ext_lang = self._detect_by_extension(filename)
            if ext_lang:
                confidence_scores['extension'] = 0.8
                if not hint or confidence_scores.get('hint', 0) < 0.8:
                    detected_language = ext_lang

        # Strategy 3: Pygments guess_lexer
        try:
            lexer = guess_lexer(code)
            if lexer.aliases:
                pygments_lang = lexer.aliases[0]
                confidence_scores['pygments'] = 0.7
                if not hint and not filename:
                    detected_language = pygments_lang
        except:
            pass

        # Strategy 4: Keyword analysis
        keyword_results = self._analyze_keywords(code)
        if keyword_results:
            lang, score = keyword_results
            confidence_scores['keywords'] = score
            if score > max(confidence_scores.values()) * 0.8:
                detected_language = lang

        return {
            'detected_language': detected_language,
            'confidence_scores': confidence_scores,
            'alternatives': list(confidence_scores.keys())
        }

    def _detect_by_extension(self, filename: str) -> Optional[str]:
        """Detect language by file extension"""
        extensions = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.java': 'java', '.cpp': 'cpp', '.c': 'c', '.cs': 'csharp',
            '.php': 'php', '.rb': 'ruby', '.go': 'go', '.rs': 'rust',
            '.html': 'html', '.css': 'css', '.sql': 'sql', '.sh': 'bash',
            '.json': 'json', '.xml': 'xml', '.yaml': 'yaml', '.yml': 'yaml'
        }

        for ext, lang in extensions.items():
            if filename.lower().endswith(ext):
                return lang
        return None

    def _analyze_keywords(self, code: str) -> Optional[Tuple[str, float]]:
        """Analyze code for language-specific keywords"""
        code_lower = code.lower()
        language_scores = {}

        for language, keywords in self.language_keywords.items():
            score = 0
            total_keywords = len(keywords)

            for keyword in keywords:
                # Count keyword occurrences with word boundaries
                pattern = r'\b' + re.escape(keyword) + r'\b'
                matches = len(re.findall(pattern, code_lower))
                if matches > 0:
                    score += min(matches, 3)  # Cap at 3 occurrences per keyword

            # Normalize score
            language_scores[language] = score / total_keywords

        if language_scores:
            best_language = max(language_scores, key=language_scores.get)
            best_score = language_scores[best_language]

            if best_score > 0.1:  # Minimum threshold
                return best_language, best_score

        return None

    def generate_auto_tags(self, code: str, language: str) -> List[str]:
        """Generate automatic tags based on code content"""
        tags = set()
        code_lower = code.lower()

        # Add language tag
        if language and language != 'text':
            tags.add(language)

        # Analyze for common patterns
        for tag_category, patterns in self.common_tags.items():
            for pattern in patterns:
                if pattern in code_lower:
                    tags.add(tag_category)
                    break

        # Specific pattern matching
        patterns = {
            "crud": [
                r"create|insert",
                r"read|select|get",
                r"update|modify",
                r"delete|remove",
            ],
            "api": [r"@app\.route|@api|endpoint|/api/"],
            "class-based": [r"class\s+\w+", r"__init__|constructor"],
            "functional": [r"def\s+\w+|function\s+\w+"],
            "recursive": [r"def\s+\w+.*:\s*.*\w+\(", r"function\s+\w+.*{\s*.*\w+\("],
            "file-io": [r"open\(|read\(|write\(|close\("],
            "networking": [r"http|https|socket|request|response"],
            "regex": [r"re\.|RegExp|\/.*\/[gimuy]*"],
            "json": [r"json\.|JSON\.|parse|stringify"],
            "config": [r"config|settings|env|environment"],
        }

        for tag, regex_patterns in patterns.items():
            for pattern in regex_patterns:
                if re.search(pattern, code, re.IGNORECASE):
                    tags.add(tag)
                    break

        return sorted(list(tags))

    def analyze_complexity(self, code: str, language: str) -> Dict:
        """Analyze code complexity"""
        lines = code.split('\n')
        complexity_indicators = {
            'cyclomatic_complexity': 1,  # Base complexity
            'nesting_depth': 0,
            'function_count': 0,
            'class_count': 0,
            'comment_ratio': 0
        }

        current_depth = 0
        max_depth = 0
        comment_lines = 0

        for line in lines:
            stripped = line.strip()

            # Count indentation depth (approximate)
            if stripped:
                depth = len(line) - len(line.lstrip())
                current_depth = depth // 4  # Assuming 4-space indentation
                max_depth = max(max_depth, current_depth)

            # Count complexity indicators
            if re.search(r'\b(if|elif|else|for|while|switch|case|catch|except)\b', stripped, re.IGNORECASE):
                complexity_indicators['cyclomatic_complexity'] += 1

            # Count functions and classes
            if re.search(r'\b(def|function|class)\s+\w+', stripped, re.IGNORECASE):
                if 'class' in stripped.lower():
                    complexity_indicators['class_count'] += 1
                else:
                    complexity_indicators['function_count'] += 1

            # Count comments
            if (stripped.startswith('#') or stripped.startswith('//') or 
                stripped.startswith('/*') or stripped.startswith('*')):
                comment_lines += 1

        complexity_indicators['nesting_depth'] = max_depth
        complexity_indicators['comment_ratio'] = comment_lines / len(lines) if lines else 0

        # Calculate overall complexity score
        score = (
            complexity_indicators['cyclomatic_complexity'] * 0.4 +
            complexity_indicators['nesting_depth'] * 0.3 +
            complexity_indicators['function_count'] * 0.1 +
            complexity_indicators['class_count'] * 0.2
        )

        complexity_indicators['overall_score'] = score
        complexity_indicators['complexity_level'] = (
            'low' if score < 10 else
            'medium' if score < 25 else
            'high'
        )

        return complexity_indicators

    def extract_functions(self, code: str, language: str) -> List[Dict]:
        """Extract function definitions from code"""
        functions = []
        lines = code.split('\n')

        patterns = {
            'python': r'^def\s+(\w+)\s*\([^)]*\):',
            'javascript': r'function\s+(\w+)\s*\([^)]*\)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>)',
            'java': r'(?:public|private|protected)?\s*(?:static\s+)?(?:void|int|String|boolean|\w+)\s+(\w+)\s*\([^)]*\)',
            'cpp': r'(?:\w+\s+)*(\w+)\s*\([^)]*\)\s*{',
            'csharp': r'(?:public|private|protected|internal)?\s*(?:static\s+)?(?:void|int|string|bool|\w+)\s+(\w+)\s*\([^)]*\)'
        }

        pattern = patterns.get(language.lower())
        if not pattern:
            return functions

        for i, line in enumerate(lines, 1):
            match = re.search(pattern, line.strip(), re.IGNORECASE)
            if match:
                func_name = match.group(1) or match.group(2) if match.lastindex > 1 else match.group(1)
                if func_name:
                    functions.append({
                        'name': func_name,
                        'line': i,
                        'definition': line.strip()
                    })

        return functions

    def extract_imports(self, code: str, language: str) -> List[str]:
        """Extract import statements from code"""
        imports = []
        lines = code.split('\n')

        patterns = {
            'python': [r'^import\s+(.+)', r'^from\s+(.+?)\s+import'],
            'javascript': [r'import\s+.+\s+from\s+[\'"](.+)[\'"]', r'require\([\'"](.+)[\'"]\)'],
            'java': [r'^import\s+(.+);'],
            'cpp': [r'^#include\s*[<"](.+)[>"]'],
            'csharp': [r'^using\s+(.+);']
        }

        lang_patterns = patterns.get(language.lower(), [])

        for line in lines:
            stripped = line.strip()
            for pattern in lang_patterns:
                match = re.search(pattern, stripped)
                if match:
                    imports.append(match.group(1))
                    break

        return imports

    def detect_frameworks(self, code: str) -> List[str]:
        """Detect frameworks and libraries used in code"""
        detected_frameworks = []
        code_lower = code.lower()

        for framework, patterns in self.framework_patterns.items():
            for pattern in patterns:
                if re.search(pattern, code, re.IGNORECASE):
                    detected_frameworks.append(framework)
                    break

        return detected_frameworks

    def analyze_security(self, code: str, language: str) -> List[Dict]:
        """Basic security issue detection"""
        issues = []

        # Common security anti-patterns
        security_patterns = [
            {
                'pattern': r'password\s*=\s*[\'"][^\'"]*[\'"]',
                'issue': 'Hardcoded password',
                'severity': 'high'
            },
            {
                'pattern': r'api_key\s*=\s*[\'"][^\'"]*[\'"]',
                'issue': 'Hardcoded API key',
                'severity': 'high'
            },
            {
                'pattern': r'secret\s*=\s*[\'"][^\'"]*[\'"]',
                'issue': 'Hardcoded secret',
                'severity': 'high'
            },
            {
                'pattern': r'eval\s*\(',
                'issue': 'Use of eval() function',
                'severity': 'medium'
            },
            {
                'pattern': r'exec\s*\(',
                'issue': 'Use of exec() function',
                'severity': 'medium'
            },
            {
                'pattern': r'innerHTML\s*=',
                'issue': 'Potential XSS via innerHTML',
                'severity': 'medium'
            },
            {
                'pattern': r'document\.write\s*\(',
                'issue': 'Use of document.write',
                'severity': 'low'
            },
            {
                'pattern': r'SELECT\s+.*\s+WHERE\s+.*\+',
                'issue': 'Potential SQL injection',
                'severity': 'high'
            }
        ]

        for pattern_info in security_patterns:
            matches = re.finditer(pattern_info['pattern'], code, re.IGNORECASE)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                issues.append({
                    'issue': pattern_info['issue'],
                    'severity': pattern_info['severity'],
                    'line': line_num,
                    'code_snippet': match.group(0)
                })

        return issues

    def generate_content_hash(self, code: str) -> str:
        """Generate hash for duplicate detection"""
        # Normalize code by removing whitespace and comments for better duplicate detection
        normalized_code = re.sub(r'\s+', ' ', code.strip())
        normalized_code = re.sub(r'#.*', '', normalized_code, flags=re.MULTILINE)   # Python comments
        normalized_code = re.sub(r'//.*', '', normalized_code, flags=re.MULTILINE)  # JS/Java comments
        normalized_code = re.sub(r'/\*.*?\*/', '', normalized_code, flags=re.DOTALL)  # Block comments

        return hashlib.md5(normalized_code.encode()).hexdigest()

    def compare_snippets(self, snippet1: str, snippet2: str) -> Dict:
        """Compare two snippets for similarity"""
        hash1 = self.generate_content_hash(snippet1)
        hash2 = self.generate_content_hash(snippet2)

        # Exact match
        if hash1 == hash2:
            return {
                'similarity': 1.0,
                'type': 'exact_match',
                'details': 'Identical code after normalization'
            }

        # Line-by-line similarity
        lines1 = set(line.strip() for line in snippet1.split('\n') if line.strip())
        lines2 = set(line.strip() for line in snippet2.split('\n') if line.strip())

        if not lines1 or not lines2:
            return {'similarity': 0.0, 'type': 'no_comparison', 'details': 'Empty snippets'}

        intersection = lines1.intersection(lines2)
        union = lines1.union(lines2)

        jaccard_similarity = len(intersection) / len(union) if union else 0

        similarity_type = (
            'high_similarity' if jaccard_similarity > 0.8 else
            'medium_similarity' if jaccard_similarity > 0.5 else
            'low_similarity'
        )

        return {
            'similarity': jaccard_similarity,
            'type': similarity_type,
            'details': f'Jaccard similarity: {jaccard_similarity:.2f}',
            'common_lines': len(intersection),
            'total_unique_lines': len(union)
        }

    def suggest_improvements(self, code: str, language: str) -> List[Dict]:
        """Suggest code improvements"""
        suggestions = []

        # General suggestions based on patterns
        improvement_patterns = [
            {
                "pattern": r"def\s+\w+\([^)]*\):\s*",
                "suggestion": "Consider adding docstrings to functions",
                "type": "documentation",
            },
            {
                "pattern": r"class\s+\w+.*:\s*",
                "suggestion": "Consider adding class docstrings",
                "type": "documentation",
            },
            {
                "pattern": r"except:\s*",
                "suggestion": "Avoid bare except clauses, specify exception types",
                "type": "error_handling",
            },
            {
                "pattern": r"print\s*\(",
                "suggestion": "Consider using logging instead of print statements",
                "type": "best_practice",
            },
            {
                "pattern": r"var\s+",
                "suggestion": "Consider using let or const instead of var",
                "type": "best_practice",
            },
        ]

        for pattern_info in improvement_patterns:
            if re.search(pattern_info['pattern'], code, re.IGNORECASE):
                suggestions.append({
                    'type': pattern_info['type'],
                    'suggestion': pattern_info['suggestion'],
                    'priority': 'medium'
                })

        # Complexity-based suggestions
        complexity = self.analyze_complexity(code, language)
        if complexity['cyclomatic_complexity'] > 15:
            suggestions.append({
                'type': 'refactoring',
                'suggestion': 'Consider breaking down complex functions',
                'priority': 'high'
            })

        if complexity['nesting_depth'] > 4:
            suggestions.append({
                'type': 'refactoring',
                'suggestion': 'Consider reducing nesting depth',
                'priority': 'medium'
            })

        return suggestions

    def extract_metadata(self, code: str, language: str) -> Dict:
        """Extract additional metadata from code"""
        metadata = {
            'author': None,
            'version': None,
            'description': None,
            'license': None,
            'created_date': None,
            'modified_date': None
        }

        # Look for common metadata patterns in comments
        metadata_patterns = {
            'author': r'@author\s+(.+)|Author:\s*(.+)|Created by:\s*(.+)',
            'version': r'@version\s+(.+)|Version:\s*(.+)',
            'description': r'@description\s+(.+)|Description:\s*(.+)',
            'license': r'@license\s+(.+)|License:\s*(.+)',
            'created_date': r'@created\s+(.+)|Created:\s*(.+)',
            'modified_date': r'@modified\s+(.+)|Modified:\s*(.+)|Last updated:\s*(.+)'
        }

        for key, pattern in metadata_patterns.items():
            match = re.search(pattern, code, re.IGNORECASE)
            if match:
                # Get the first non-empty group
                for group in match.groups():
                    if group and group.strip():
                        metadata[key] = group.strip()
                        break

        return metadata

    def get_language_statistics(self) -> Dict:
        """Get statistics about supported languages"""
        return {
            'total_languages': len(self.language_keywords),
            'supported_languages': list(self.language_keywords.keys()),
            'supported_frameworks': list(self.framework_patterns.keys()),
            'tag_categories': list(self.common_tags.keys())
        }

# Global instance
snippet_analyzer = SnippetAnalyzer()
# Add these at the bottom of snippet_analyzer.py, after the SnippetAnalyzer class

# Create a global instance
snippet_analyzer = SnippetAnalyzer()


# Standalone functions for backward compatibility
def detect_language(code):
    """Standalone function for language detection"""
    result = snippet_analyzer.detect_language(code)
    return result["detected_language"]


def generate_tags(code, language, title=""):
    """Standalone function for tag generation"""
    # First get auto tags from the analyzer
    auto_tags = snippet_analyzer.generate_auto_tags(code, language)

    # Add title-based tags if provided
    if title:
        title_words = title.lower().split()
        for word in title_words:
            if len(word) > 3 and word not in ["function", "class", "method", "example"]:
                auto_tags.append(word)

    # Remove duplicates and return
    return list(dict.fromkeys(auto_tags))[:10]
