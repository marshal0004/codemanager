"""
Advanced Snippet Comparison Service
Provides diff functionality, similarity detection, and code analysis
"""

import difflib
import re
import hashlib
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import ast
import tokenize
import io
from collections import Counter


class ComparisonService:
    """Modern snippet comparison with advanced diff and analysis features"""

    def __init__(self):
        self.similarity_threshold = 0.7
        self.language_patterns = {
            "python": r"(def\s+\w+|class\s+\w+|import\s+\w+)",
            "javascript": r"(function\s+\w+|const\s+\w+|let\s+\w+|var\s+\w+)",
            "java": r"(public\s+class|private\s+\w+|public\s+\w+)",
            "css": r"(\.\w+\s*{|#\w+\s*{|\w+\s*{)",
            "html": r"(<\w+|<\/\w+)",
            "sql": r"(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER)",
        }

    def compare_snippets(self, snippet1: Dict, snippet2: Dict) -> Dict[str, Any]:
        """
        Comprehensive snippet comparison with multiple analysis methods
        """
        try:
            content1 = snippet1.get("content", "")
            content2 = snippet2.get("content", "")

            # Generate unified diff
            diff_html = self._generate_html_diff(content1, content2)

            # Calculate similarity metrics
            similarity = self._calculate_similarity(content1, content2)

            # Analyze structural differences
            structure_analysis = self._analyze_structure(
                content1, content2, snippet1.get("language"), snippet2.get("language")
            )

            # Performance metrics
            metrics = self._compare_metrics(snippet1, snippet2)

            return {
                "comparison_id": self._generate_comparison_id(
                    snippet1["id"], snippet2["id"]
                ),
                "snippets": {
                    "source": {
                        "id": snippet1["id"],
                        "title": snippet1.get("title", "Untitled"),
                        "language": snippet1.get("language", "text"),
                        "created_at": snippet1.get("created_at"),
                        "lines": len(content1.splitlines()),
                    },
                    "target": {
                        "id": snippet2["id"],
                        "title": snippet2.get("title", "Untitled"),
                        "language": snippet2.get("language", "text"),
                        "created_at": snippet2.get("created_at"),
                        "lines": len(content2.splitlines()),
                    },
                },
                "diff": {
                    "html": diff_html,
                    "stats": self._get_diff_stats(content1, content2),
                },
                "similarity": similarity,
                "structure_analysis": structure_analysis,
                "metrics": metrics,
                "recommendations": self._generate_recommendations(
                    similarity, structure_analysis
                ),
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {
                "error": f"Comparison failed: {str(e)}",
                "generated_at": datetime.utcnow().isoformat(),
            }

    def _generate_html_diff(self, content1: str, content2: str) -> str:
        """Generate modern HTML diff with syntax highlighting support"""
        differ = difflib.HtmlDiff(wrapcolumn=80)

        lines1 = content1.splitlines()
        lines2 = content2.splitlines()

        diff_html = differ.make_file(
            lines1,
            lines2,
            fromdesc="Original Version",
            todesc="Compared Version",
            context=True,
            numlines=3,
        )

        # Enhance with modern styling classes
        enhanced_html = self._enhance_diff_styling(diff_html)

        return enhanced_html

    def _enhance_diff_styling(self, html: str) -> str:
        """Add modern CSS classes for better styling"""
        enhancements = {
            "diff_header": "diff-header bg-gray-100 dark:bg-gray-800 p-2 rounded-t",
            "diff_next": "diff-nav inline-flex items-center px-3 py-1 bg-blue-500 text-white rounded",
            "diff_add": "diff-add bg-green-50 dark:bg-green-900/20 border-l-4 border-green-500",
            "diff_chg": "diff-change bg-yellow-50 dark:bg-yellow-900/20 border-l-4 border-yellow-500",
            "diff_sub": "diff-delete bg-red-50 dark:bg-red-900/20 border-l-4 border-red-500",
        }

        for old_class, new_class in enhancements.items():
            html = html.replace(f'class="{old_class}"', f'class="{new_class}"')

        return html

    def _calculate_similarity(self, content1: str, content2: str) -> Dict[str, float]:
        """Calculate multiple similarity metrics"""
        # Sequence similarity
        seq_similarity = difflib.SequenceMatcher(None, content1, content2).ratio()

        # Token-based similarity
        tokens1 = set(re.findall(r"\w+", content1.lower()))
        tokens2 = set(re.findall(r"\w+", content2.lower()))

        if tokens1 or tokens2:
            token_similarity = len(tokens1 & tokens2) / len(tokens1 | tokens2)
        else:
            token_similarity = 1.0 if not tokens1 and not tokens2 else 0.0

        # Line-based similarity
        lines1 = set(line.strip() for line in content1.splitlines() if line.strip())
        lines2 = set(line.strip() for line in content2.splitlines() if line.strip())

        if lines1 or lines2:
            line_similarity = len(lines1 & lines2) / len(lines1 | lines2)
        else:
            line_similarity = 1.0 if not lines1 and not lines2 else 0.0

        # Overall similarity (weighted average)
        overall = seq_similarity * 0.5 + token_similarity * 0.3 + line_similarity * 0.2

        return {
            "overall": round(overall, 3),
            "sequence": round(seq_similarity, 3),
            "tokens": round(token_similarity, 3),
            "lines": round(line_similarity, 3),
            "rating": self._get_similarity_rating(overall),
        }

    def _get_similarity_rating(self, similarity: float) -> str:
        """Convert similarity score to human-readable rating"""
        if similarity >= 0.9:
            return "Nearly Identical"
        elif similarity >= 0.7:
            return "Very Similar"
        elif similarity >= 0.5:
            return "Moderately Similar"
        elif similarity >= 0.3:
            return "Somewhat Similar"
        else:
            return "Very Different"

    def _analyze_structure(
        self, content1: str, content2: str, lang1: str, lang2: str
    ) -> Dict[str, Any]:
        """Analyze structural differences between code snippets"""
        analysis = {
            "language_match": lang1 == lang2 if lang1 and lang2 else None,
            "complexity_comparison": self._compare_complexity(content1, content2),
            "pattern_analysis": {},
            "function_analysis": {},
        }

        if lang1 and lang1 in self.language_patterns:
            pattern1 = re.findall(
                self.language_patterns[lang1], content1, re.IGNORECASE
            )
            pattern2 = re.findall(
                self.language_patterns[lang2 or lang1], content2, re.IGNORECASE
            )

            analysis["pattern_analysis"] = {
                "source_patterns": len(pattern1),
                "target_patterns": len(pattern2),
                "common_patterns": len(set(pattern1) & set(pattern2)),
                "pattern_similarity": len(set(pattern1) & set(pattern2))
                / max(len(set(pattern1) | set(pattern2)), 1),
            }

        # Function/method analysis
        if lang1 in ["python", "javascript", "java"]:
            analysis["function_analysis"] = self._analyze_functions(
                content1, content2, lang1
            )

        return analysis

    def _compare_complexity(self, content1: str, content2: str) -> Dict[str, Any]:
        """Compare code complexity metrics"""

        def calculate_complexity(content: str) -> Dict[str, int]:
            lines = content.splitlines()
            return {
                "total_lines": len(lines),
                "code_lines": len(
                    [l for l in lines if l.strip() and not l.strip().startswith("#")]
                ),
                "blank_lines": len([l for l in lines if not l.strip()]),
                "comment_lines": len([l for l in lines if l.strip().startswith("#")]),
                "indentation_levels": max(
                    [len(l) - len(l.lstrip()) for l in lines] + [0]
                ),
                "characters": len(content),
                "words": len(re.findall(r"\w+", content)),
            }

        comp1 = calculate_complexity(content1)
        comp2 = calculate_complexity(content2)

        return {
            "source": comp1,
            "target": comp2,
            "difference": {
                "lines": comp2["total_lines"] - comp1["total_lines"],
                "complexity": comp2["indentation_levels"] - comp1["indentation_levels"],
                "size_change": comp2["characters"] - comp1["characters"],
            },
        }

    def _analyze_functions(
        self, content1: str, content2: str, language: str
    ) -> Dict[str, Any]:
        """Analyze function/method differences"""
        if language == "python":
            funcs1 = re.findall(r"def\s+(\w+)", content1)
            funcs2 = re.findall(r"def\s+(\w+)", content2)
        elif language == "javascript":
            funcs1 = re.findall(r"function\s+(\w+)|(\w+)\s*=\s*function", content1)
            funcs2 = re.findall(r"function\s+(\w+)|(\w+)\s*=\s*function", content2)
            funcs1 = [f[0] or f[1] for f in funcs1]
            funcs2 = [f[0] or f[1] for f in funcs2]
        else:
            return {}

        return {
            "source_functions": funcs1,
            "target_functions": funcs2,
            "added_functions": list(set(funcs2) - set(funcs1)),
            "removed_functions": list(set(funcs1) - set(funcs2)),
            "common_functions": list(set(funcs1) & set(funcs2)),
        }

    def _get_diff_stats(self, content1: str, content2: str) -> Dict[str, int]:
        """Calculate diff statistics"""
        lines1 = content1.splitlines()
        lines2 = content2.splitlines()

        matcher = difflib.SequenceMatcher(None, lines1, lines2)
        stats = {"added": 0, "deleted": 0, "modified": 0, "unchanged": 0}

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "replace":
                stats["modified"] += max(i2 - i1, j2 - j1)
            elif tag == "delete":
                stats["deleted"] += i2 - i1
            elif tag == "insert":
                stats["added"] += j2 - j1
            elif tag == "equal":
                stats["unchanged"] += i2 - i1

        return stats

    def _compare_metrics(self, snippet1: Dict, snippet2: Dict) -> Dict[str, Any]:
        """Compare snippet performance and usage metrics"""
        return {
            "performance": {
                "size_comparison": {
                    "source_size": len(snippet1.get("content", "")),
                    "target_size": len(snippet2.get("content", "")),
                    "size_diff": len(snippet2.get("content", ""))
                    - len(snippet1.get("content", "")),
                },
                "readability": {
                    "source_score": self._calculate_readability_score(
                        snippet1.get("content", "")
                    ),
                    "target_score": self._calculate_readability_score(
                        snippet2.get("content", "")
                    ),
                },
            },
            "usage": {
                "source_usage": snippet1.get("usage_count", 0),
                "target_usage": snippet2.get("usage_count", 0),
                "popularity_diff": snippet2.get("usage_count", 0)
                - snippet1.get("usage_count", 0),
            },
        }

    def _calculate_readability_score(self, content: str) -> float:
        """Calculate code readability score (0-100)"""
        if not content.strip():
            return 0.0

        lines = content.splitlines()
        total_lines = len(lines)

        # Factors that affect readability
        comment_ratio = len([l for l in lines if l.strip().startswith("#")]) / max(
            total_lines, 1
        )
        blank_line_ratio = len([l for l in lines if not l.strip()]) / max(
            total_lines, 1
        )
        avg_line_length = sum(len(line) for line in lines) / max(total_lines, 1)

        # Calculate score (simplified algorithm)
        score = 50  # Base score
        score += comment_ratio * 20  # Good comments increase score
        score += min(blank_line_ratio * 15, 10)  # Some blank lines are good
        score -= max(0, (avg_line_length - 80) * 0.2)  # Penalize very long lines

        return max(0, min(100, score))

    def _generate_recommendations(self, similarity: Dict, structure: Dict) -> List[str]:
        """Generate actionable recommendations based on comparison"""
        recommendations = []

        if similarity["overall"] > 0.8:
            recommendations.append(
                "These snippets are very similar. Consider merging them or creating a reusable function."
            )

        if (
            structure.get("complexity_comparison", {})
            .get("difference", {})
            .get("complexity", 0)
            > 3
        ):
            recommendations.append(
                "Target snippet has higher complexity. Consider refactoring for better maintainability."
            )

        if not structure.get("language_match", True):
            recommendations.append(
                "Different languages detected. Consider creating language-specific versions."
            )

        pattern_sim = structure.get("pattern_analysis", {}).get("pattern_similarity", 0)
        if pattern_sim < 0.3:
            recommendations.append(
                "Different coding patterns detected. Review for consistency with your coding standards."
            )

        return recommendations or ["No specific recommendations at this time."]

    def _generate_comparison_id(self, id1: str, id2: str) -> str:
        """Generate unique comparison ID"""
        combined = f"{id1}:{id2}:{datetime.utcnow().timestamp()}"
        return hashlib.md5(combined.encode()).hexdigest()[:12]

    def find_similar_snippets(
        self, target_snippet: Dict, all_snippets: List[Dict], limit: int = 10
    ) -> List[Dict]:
        """Find snippets similar to the target snippet"""
        similar_snippets = []
        target_content = target_snippet.get("content", "")

        for snippet in all_snippets:
            if snippet["id"] == target_snippet["id"]:
                continue

            similarity = self._calculate_similarity(
                target_content, snippet.get("content", "")
            )

            if similarity["overall"] >= self.similarity_threshold:
                similar_snippets.append(
                    {
                        "snippet": snippet,
                        "similarity": similarity,
                        "match_type": (
                            "high" if similarity["overall"] >= 0.9 else "medium"
                        ),
                    }
                )

        # Sort by similarity and return top results
        similar_snippets.sort(key=lambda x: x["similarity"]["overall"], reverse=True)
        return similar_snippets[:limit]

    def batch_compare(self, snippets: List[Dict]) -> Dict[str, Any]:
        """Compare multiple snippets and find duplicates/similarities"""
        results = {
            "total_comparisons": 0,
            "duplicates": [],
            "similar_groups": [],
            "unique_snippets": [],
        }

        n = len(snippets)
        similarity_matrix = {}

        # Generate all pairwise comparisons
        for i in range(n):
            for j in range(i + 1, n):
                comparison = self.compare_snippets(snippets[i], snippets[j])
                results["total_comparisons"] += 1

                similarity_score = comparison["similarity"]["overall"]
                pair_key = f"{snippets[i]['id']}:{snippets[j]['id']}"
                similarity_matrix[pair_key] = similarity_score

                if similarity_score >= 0.95:
                    results["duplicates"].append(
                        {
                            "snippets": [snippets[i]["id"], snippets[j]["id"]],
                            "similarity": similarity_score,
                        }
                    )
                elif similarity_score >= 0.7:
                    results["similar_groups"].append(
                        {
                            "snippets": [snippets[i]["id"], snippets[j]["id"]],
                            "similarity": similarity_score,
                        }
                    )

        # Find unique snippets (those with low similarity to all others)
        for snippet in snippets:
            max_similarity = 0
            for pair_key, similarity in similarity_matrix.items():
                if snippet["id"] in pair_key:
                    max_similarity = max(max_similarity, similarity)

            if max_similarity < 0.3:
                results["unique_snippets"].append(snippet["id"])

        return results
