"""
Advanced Snippet Search Engine Service
Provides powerful search functionality with full-text search, filtering, and ranking
"""

from flask import current_app
from sqlalchemy import or_, and_, func, text
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
import re
from typing import List, Dict, Any, Optional, Tuple
import json

from ..models.snippet import Snippet
from ..models.collection import Collection
from ..models.user import User
from app.extensions import db


class SearchEngine:
    """Advanced search engine for code snippets"""

    def __init__(self):
        self.operators = {"AND": and_, "OR": or_, "NOT": lambda x: ~x}

    def search_snippets(
        self,
        query: str,
        user_id: int,
        filters: Dict[str, Any] = None,
        sort_by: str = "relevance",
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        """
        Advanced snippet search with multiple filters and ranking

        Args:
            query: Search query string
            user_id: User performing the search
            filters: Additional filters (language, tags, date_range, etc.)
            sort_by: Sort method (relevance, date, title, usage)
            page: Page number for pagination
            per_page: Results per page

        Returns:
            Dict containing search results and metadata
        """

        # Start with base query
        base_query = db.session.query(Snippet).filter(
            or_(Snippet.user_id == user_id, Snippet.is_public == True)
        )

        # Apply text search
        if query and query.strip():
            search_conditions = self._build_search_conditions(query)
            base_query = base_query.filter(search_conditions)

        # Apply filters
        if filters:
            base_query = self._apply_filters(base_query, filters)

        # Apply sorting
        base_query = self._apply_sorting(base_query, sort_by, query)

        # Get total count before pagination
        total_count = base_query.count()

        # Apply pagination
        results = base_query.offset((page - 1) * per_page).limit(per_page).all()

        # Calculate relevance scores if sorting by relevance
        if sort_by == "relevance" and query:
            results = self._calculate_relevance_scores(results, query)

        # Prepare response
        return {
            "results": [self._serialize_snippet(snippet) for snippet in results],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "pages": (total_count + per_page - 1) // per_page,
            },
            "query": query,
            "filters": filters or {},
            "sort_by": sort_by,
            "search_time": datetime.utcnow().isoformat(),
        }

    def _build_search_conditions(self, query: str):
        """Build search conditions from query string"""

        # Parse search query for special operators
        parsed_query = self._parse_query(query)

        conditions = []

        for term in parsed_query["terms"]:
            # Search in multiple fields with different weights
            term_conditions = or_(
                Snippet.title.ilike(f"%{term}%"),
                Snippet.description.ilike(f"%{term}%"),
                Snippet.code_content.ilike(f"%{term}%"),
                Snippet.tags.ilike(f"%{term}%"),
                Snippet.filename.ilike(f"%{term}%"),
            )
            conditions.append(term_conditions)

        # Handle phrase searches
        for phrase in parsed_query["phrases"]:
            phrase_conditions = or_(
                Snippet.title.ilike(f"%{phrase}%"),
                Snippet.description.ilike(f"%{phrase}%"),
                Snippet.code_content.ilike(f"%{phrase}%"),
            )
            conditions.append(phrase_conditions)

        # Combine conditions
        if conditions:
            return and_(*conditions) if len(conditions) > 1 else conditions[0]

        return True  # Return all if no conditions

    
        

    def _parse_query(self, query: str) -> Dict[str, List[str]]:
        """Parse search query for terms and phrases"""

        # Extract phrases in quotes
        phrases = re.findall(r'"([^"]*)"', query)

        # Remove phrases from query and extract individual terms
        query_without_phrases = re.sub(r'"[^"]*"', "", query)
        terms = [term.strip() for term in query_without_phrases.split() if term.strip()]

        return {"terms": terms, "phrases": phrases}

    def _apply_filters(self, query, filters: Dict[str, Any]):
        """Apply various filters to the search query"""

        # Language filter
        if filters.get("language"):
            languages = (
                filters["language"]
                if isinstance(filters["language"], list)
                else [filters["language"]]
            )
            query = query.filter(Snippet.language.in_(languages))

        # Tags filter
        if filters.get("tags"):
            tags = (
                filters["tags"]
                if isinstance(filters["tags"], list)
                else [filters["tags"]]
            )
            for tag in tags:
                query = query.filter(Snippet.tags.ilike(f"%{tag}%"))

        # Date range filter
        if filters.get("date_from"):
            date_from = datetime.fromisoformat(
                filters["date_from"].replace("Z", "+00:00")
            )
            query = query.filter(Snippet.created_at >= date_from)

        if filters.get("date_to"):
            date_to = datetime.fromisoformat(filters["date_to"].replace("Z", "+00:00"))
            query = query.filter(Snippet.created_at <= date_to)

        # Collection filter
        if filters.get("collection_id"):
            query = query.filter(Snippet.collection_id == filters["collection_id"])

        # Source filter (where snippet was captured from)
        if filters.get("source"):
            query = query.filter(Snippet.source_url.ilike(f'%{filters["source"]}%'))

        # Privacy filter
        if filters.get("is_public") is not None:
            query = query.filter(Snippet.is_public == filters["is_public"])

        # File extension filter
        if filters.get("file_extension"):
            extensions = (
                filters["file_extension"]
                if isinstance(filters["file_extension"], list)
                else [filters["file_extension"]]
            )
            conditions = []
            for ext in extensions:
                conditions.append(Snippet.filename.ilike(f"%.{ext}"))
            query = query.filter(or_(*conditions))

        # Minimum lines of code filter
        if filters.get("min_lines"):
            query = query.filter(Snippet.lines_of_code >= filters["min_lines"])

        # Maximum lines of code filter
        if filters.get("max_lines"):
            query = query.filter(Snippet.lines_of_code <= filters["max_lines"])

        return query

    def _apply_sorting(self, query, sort_by: str, search_query: str = None):
        """Apply sorting to the query"""

        if sort_by == "date":
            return query.order_by(Snippet.created_at.desc())
        elif sort_by == "title":
            return query.order_by(Snippet.title.asc())
        elif sort_by == "usage":
            return query.order_by(Snippet.usage_count.desc())
        elif sort_by == "lines":
            return query.order_by(Snippet.lines_of_code.desc())
        elif sort_by == "language":
            return query.order_by(Snippet.language.asc())
        elif sort_by == "relevance" and search_query:
            # For relevance, we'll calculate scores after fetching
            return query.order_by(Snippet.updated_at.desc())  # Temporary order
        else:
            # Default: most recently updated
            return query.order_by(Snippet.updated_at.desc())

    def _calculate_relevance_scores(
        self, snippets: List[Snippet], query: str
    ) -> List[Snippet]:
        """Calculate relevance scores and sort by them"""

        query_terms = query.lower().split()

        def calculate_score(snippet):
            score = 0
            title_lower = (snippet.title or "").lower()
            desc_lower = (snippet.description or "").lower()
            code_lower = (snippet.code_content or "").lower()
            tags_lower = (snippet.tags or "").lower()

            for term in query_terms:
                # Title matches (highest weight)
                if term in title_lower:
                    score += 10

                # Description matches
                if term in desc_lower:
                    score += 5

                # Tag matches
                if term in tags_lower:
                    score += 7

                # Code content matches
                if term in code_lower:
                    score += 3

                # Exact title match bonus
                if term == title_lower:
                    score += 15

            # Boost score for frequently used snippets
            score += min(snippet.usage_count or 0, 20) * 0.1

            # Boost score for recently updated snippets
            days_old = (datetime.utcnow() - snippet.updated_at).days
            if days_old < 7:
                score += 2
            elif days_old < 30:
                score += 1

            return score

        # Sort by calculated relevance score
        return sorted(snippets, key=calculate_score, reverse=True)

    def _serialize_snippet(self, snippet: Snippet) -> Dict[str, Any]:
        """Serialize snippet for search results"""
        return {
            "id": snippet.id,
            "title": snippet.title,
            "description": snippet.description,
            "language": snippet.language,
            "tags": snippet.tags.split(",") if snippet.tags else [],
            "filename": snippet.filename,
            "lines_of_code": snippet.lines_of_code,
            "created_at": snippet.created_at.isoformat(),
            "updated_at": snippet.updated_at.isoformat(),
            "usage_count": snippet.usage_count,
            "is_public": snippet.is_public,
            "source_url": snippet.source_url,
            "preview": (
                snippet.code_content[:200] + "..."
                if len(snippet.code_content or "") > 200
                else snippet.code_content
            ),
        }

    def get_search_suggestions(
        self, query: str, user_id: int, limit: int = 10
    ) -> List[str]:
        """Get search suggestions based on partial query"""

        if not query or len(query) < 2:
            return []

        # Get suggestions from titles
        title_suggestions = (
            db.session.query(Snippet.title)
            .filter(
                and_(
                    or_(Snippet.user_id == user_id, Snippet.is_public == True),
                    Snippet.title.ilike(f"%{query}%"),
                )
            )
            .limit(limit // 2)
            .all()
        )

        # Get suggestions from tags
        tag_suggestions = (
            db.session.query(Snippet.tags)
            .filter(
                and_(
                    or_(Snippet.user_id == user_id, Snippet.is_public == True),
                    Snippet.tags.ilike(f"%{query}%"),
                )
            )
            .limit(limit // 2)
            .all()
        )

        suggestions = []

        # Process titles
        for (title,) in title_suggestions:
            if title and query.lower() in title.lower():
                suggestions.append(title)

        # Process tags
        for (tags,) in tag_suggestions:
            if tags:
                tag_list = [tag.strip() for tag in tags.split(",")]
                for tag in tag_list:
                    if query.lower() in tag.lower() and tag not in suggestions:
                        suggestions.append(tag)

        return suggestions[:limit]

    def get_popular_searches(
        self, user_id: int, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get popular search terms for the user"""

        # This would typically come from a search_history table
        # For now, return popular tags and languages

        popular_languages = (
            db.session.query(Snippet.language, func.count(Snippet.id).label("count"))
            .filter(or_(Snippet.user_id == user_id, Snippet.is_public == True))
            .group_by(Snippet.language)
            .order_by(func.count(Snippet.id).desc())
            .limit(limit // 2)
            .all()
        )

        # Get popular tags
        all_tags = (
            db.session.query(Snippet.tags)
            .filter(
                and_(
                    Snippet.tags.isnot(None),
                    or_(Snippet.user_id == user_id, Snippet.is_public == True),
                )
            )
            .all()
        )

        tag_counts = {}
        for (tags,) in all_tags:
            if tags:
                for tag in tags.split(","):
                    tag = tag.strip()
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

        popular_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[
            : limit // 2
        ]

        results = []

        # Add languages
        for lang, count in popular_languages:
            if lang:
                results.append({"term": lang, "type": "language", "count": count})

        # Add tags
        for tag, count in popular_tags:
            results.append({"term": tag, "type": "tag", "count": count})

        return results[:limit]

    def get_search_analytics(self, user_id: int) -> Dict[str, Any]:
        """Get search and usage analytics for user"""

        # Total snippets
        total_snippets = (
            db.session.query(Snippet).filter(Snippet.user_id == user_id).count()
        )

        # Snippets by language
        language_stats = (
            db.session.query(Snippet.language, func.count(Snippet.id).label("count"))
            .filter(Snippet.user_id == user_id)
            .group_by(Snippet.language)
            .all()
        )

        # Most used snippets
        most_used = (
            db.session.query(Snippet)
            .filter(Snippet.user_id == user_id)
            .order_by(Snippet.usage_count.desc())
            .limit(10)
            .all()
        )

        # Recent activity
        recent_snippets = (
            db.session.query(Snippet)
            .filter(
                and_(
                    Snippet.user_id == user_id,
                    Snippet.created_at >= datetime.utcnow() - timedelta(days=30),
                )
            )
            .count()
        )

        return {
            "total_snippets": total_snippets,
            "languages": [
                {"language": lang, "count": count} for lang, count in language_stats
            ],
            "most_used": [self._serialize_snippet(snippet) for snippet in most_used],
            "recent_activity": recent_snippets,
            "generated_at": datetime.utcnow().isoformat(),
        }


# Initialize the search engine
search_engine = SearchEngine()
def search_snippets(query, user_id):
    """
    Simple search function for backward compatibility

    Args:
        query: Search query string
        user_id: ID of the user whose snippets to search

    Returns:
        List of matching snippet dictionaries
    """
    # Use the search engine instance
    result = search_engine.search_snippets(
        query=query,
        user_id=user_id,
        filters=None,
        sort_by="relevance",
        page=1,
        per_page=100,  # Get more results for simple search
    )

    # Return just the results array for backward compatibility
    return result["results"]
