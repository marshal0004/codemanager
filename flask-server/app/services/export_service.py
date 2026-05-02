"""
Export Service for Code Snippets
Supports multiple export formats: JSON, Markdown, HTML, PDF, GitHub Gist, etc.
"""

import json
import zipfile
import io
import base64
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from flask import current_app, render_template_string
import requests
from jinja2 import Template

from ..models.snippet import Snippet
from ..models.collection import Collection
from ..models.user import User
from app.extensions import db


class ExportService:
    """Service for exporting snippets in various formats"""

    def __init__(self):
        self.supported_formats = [
            "json",
            "markdown",
            "html",
            "csv",
            "txt",
            "zip",
            "gist",
            "pastebin",
            "hastebin",
        ]

    def export_snippets(
        self,
        snippet_ids: List[int],
        format_type: str,
        user_id: int,
        options: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Export snippets in specified format

        Args:
            snippet_ids: List of snippet IDs to export
            format_type: Export format (json, markdown, html, etc.)
            user_id: User performing the export
            options: Additional export options

        Returns:
            Dict containing export data and metadata
        """

        if format_type not in self.supported_formats:
            raise ValueError(f"Unsupported format: {format_type}")

        # Fetch snippets
        snippets = (
            db.session.query(Snippet)
            .filter(Snippet.id.in_(snippet_ids), Snippet.user_id == user_id)
            .all()
        )

        if not snippets:
            raise ValueError("No snippets found or access denied")

        # Route to appropriate export method
        export_methods = {
            "json": self._export_json,
            "markdown": self._export_markdown,
            "html": self._export_html,
            "csv": self._export_csv,
            "txt": self._export_txt,
            "zip": self._export_zip,
            "gist": self._export_github_gist,
            "pastebin": self._export_pastebin,
            "hastebin": self._export_hastebin,
        }

        return export_methods[format_type](snippets, options or {})

    def export_collections(
        self,
        collection_ids: List[int],
        format_type: str,
        user_id: int,
        options: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Export multiple collections"""
        
        if format_type not in self.supported_formats:
            raise ValueError(f"Unsupported format: {format_type}")
        
        # Fetch collections
        collections = (
            db.session.query(Collection)
            .filter(Collection.id.in_(collection_ids), Collection.user_id == user_id)
            .all()
        )
        
        if not collections:
            raise ValueError("No collections found or access denied")
        
        # Get all snippets from all collections
        all_snippets = []
        collections_metadata = []
        
        for collection in collections:
            snippets = (
                db.session.query(Snippet)
                .filter(Snippet.collection_id == collection.id, Snippet.user_id == user_id)
                .all()
            )
            all_snippets.extend(snippets)
            
            collections_metadata.append({
                "id": collection.id,
                "name": collection.name,
                "description": collection.description,
                "created_at": collection.created_at.isoformat(),
                "updated_at": collection.updated_at.isoformat(),
                "snippets_count": len(snippets)
            })
        
        # Add collections metadata to options
        options = options or {}
        options["collections"] = collections_metadata
        options["multiple_collections"] = True
        
        return self.export_snippets(
            [s.id for s in all_snippets], format_type, user_id, options
        )

    def _export_json(
        self, snippets: List[Snippet], options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Export as JSON format"""

        export_data = {
            "metadata": {
                "exported_at": datetime.utcnow().isoformat(),
                "format": "json",
                "version": "1.0",
                "total_snippets": len(snippets),
                "collection": options.get("collection"),
            },
            "snippets": [],
        }

        for snippet in snippets:
            snippet_data = {
                "id": snippet.id,
                "title": snippet.title,
                "description": snippet.description,
                "code_content": snippet.code_content,
                "language": snippet.language,
                "filename": snippet.filename,
                "tags": snippet.tags.split(",") if snippet.tags else [],
                "source_url": snippet.source_url,
                "lines_of_code": snippet.lines_of_code,
                "created_at": snippet.created_at.isoformat(),
                "updated_at": snippet.updated_at.isoformat(),
                "usage_count": snippet.usage_count,
                "is_public": snippet.is_public,
            }

            # Include version history if requested
            if options.get("include_versions") and hasattr(snippet, "versions"):
                snippet_data["versions"] = [
                    {
                        "version": v.version_number,
                        "content": v.content,
                        "created_at": v.created_at.isoformat(),
                        "changes_summary": v.changes_summary,
                    }
                    for v in snippet.versions
                ]

            export_data["snippets"].append(snippet_data)

        return {
            "content": json.dumps(export_data, indent=2),
            "filename": f'snippets_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
            "content_type": "application/json",
            "size": len(json.dumps(export_data)),
        }

    def _export_markdown(
        self, snippets: List[Snippet], options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Export as Markdown format"""

        md_template = """# Code Snippets Export

**Exported on:** {{ exported_at }}  
**Total Snippets:** {{ total_snippets }}  
{% if collection %}**Collection:** {{ collection.name }}{% endif %}

---

{% for snippet in snippets %}
## {{ snippet.title }}

{% if snippet.description %}
**Description:** {{ snippet.description }}
{% endif %}

**Language:** {{ snippet.language }}  
{% if snippet.filename %}**Filename:** {{ snippet.filename }}{% endif %}
{% if snippet.tags %}**Tags:** {{ snippet.tags }}{% endif %}
{% if snippet.source_url %}**Source:** {{ snippet.source_url }}{% endif %}

```{{ snippet.language or 'text' }}
{{ snippet.code_content }}
```

**Created:** {{ snippet.created_at }}  
**Updated:** {{ snippet.updated_at }}  
**Usage Count:** {{ snippet.usage_count }}

---

{% endfor %}

*Generated by Code Snippet Manager*
"""

        template = Template(md_template)
        content = template.render(
            exported_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            total_snippets=len(snippets),
            collection=options.get("collection"),
            snippets=[
                {
                    "title": s.title,
                    "description": s.description,
                    "code_content": s.code_content,
                    "language": s.language,
                    "filename": s.filename,
                    "tags": s.tags,
                    "source_url": s.source_url,
                    "created_at": s.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "updated_at": s.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "usage_count": s.usage_count or 0,
                }
                for s in snippets
            ],
        )

        return {
            "content": content,
            "filename": f'snippets_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.md',
            "content_type": "text/markdown",
            "size": len(content.encode("utf-8")),
        }

    def _export_html(
        self, snippets: List[Snippet], options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Export as HTML format"""

        html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Code Snippets Export</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism.min.css">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; }
        .header { border-bottom: 2px solid #eee; padding-bottom: 20px; margin-bottom: 30px; }
        .snippet { margin-bottom: 40px; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }
        .snippet-header { background: #f8f9fa; padding: 15px; border-bottom: 1px solid #ddd; }
        .snippet-title { margin: 0; color: #333; }
        .snippet-meta { color: #666; font-size: 0.9em; margin-top: 5px; }
        .snippet-content { padding: 0; }
        .snippet-description { padding: 15px; background: #fafafa; font-style: italic; }
        pre { margin: 0 !important; }
        .tags { display: inline-flex; gap: 5px; margin-top: 10px; }
        .tag { background: #007bff; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; }
        .footer { margin-top: 50px; text-align: center; color: #666; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Code Snippets Export</h1>
        <p><strong>Exported:</strong> {{ exported_at }}</p>
        <p><strong>Total Snippets:</strong> {{ total_snippets }}</p>
        {% if collection %}<p><strong>Collection:</strong> {{ collection.name }}</p>{% endif %}
    </div>
    
    {% for snippet in snippets %}
    <div class="snippet">
        <div class="snippet-header">
            <h2 class="snippet-title">{{ snippet.title }}</h2>
            <div class="snippet-meta">
                <strong>Language:</strong> {{ snippet.language }} | 
                <strong>Created:</strong> {{ snippet.created_at }} | 
                <strong>Usage:</strong> {{ snippet.usage_count }} times
                {% if snippet.filename %} | <strong>File:</strong> {{ snippet.filename }}{% endif %}
            </div>
            {% if snippet.tags %}
            <div class="tags">
                {% for tag in snippet.tags.split(',') %}
                <span class="tag">{{ tag.strip() }}</span>
                {% endfor %}
            </div>
            {% endif %}
        </div>
        {% if snippet.description %}
        <div class="snippet-description">{{ snippet.description }}</div>
        {% endif %}
        <div class="snippet-content">
            <pre><code class="language-{{ snippet.language or 'text' }}">{{ snippet.code_content }}</code></pre>
        </div>
    </div>
    {% endfor %}
    
    <div class="footer">
        <p>Generated by Code Snippet Manager on {{ exported_at }}</p>
    </div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-core.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/autoloader/prism-autoloader.min.js"></script>
</body>
</html>"""

        template = Template(html_template)
        content = template.render(
            exported_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            total_snippets=len(snippets),
            collection=options.get("collection"),
            snippets=snippets,
        )

        return {
            "content": content,
            "filename": f'snippets_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html',
            "content_type": "text/html",
            "size": len(content.encode("utf-8")),
        }

    def _export_csv(
        self, snippets: List[Snippet], options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Export as CSV format"""

        import csv

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            [
                "ID",
                "Title",
                "Description",
                "Language",
                "Filename",
                "Tags",
                "Lines of Code",
                "Created At",
                "Updated At",
                "Usage Count",
                "Is Public",
                "Source URL",
            ]
        )

        # Data rows
        for snippet in snippets:
            writer.writerow(
                [
                    snippet.id,
                    snippet.title,
                    snippet.description or "",
                    snippet.language or "",
                    snippet.filename or "",
                    snippet.tags or "",
                    snippet.lines_of_code or 0,
                    snippet.created_at.isoformat(),
                    snippet.updated_at.isoformat(),
                    snippet.usage_count or 0,
                    snippet.is_public,
                    snippet.source_url or "",
                ]
            )

        content = output.getvalue()
        output.close()

        return {
            "content": content,
            "filename": f'snippets_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            "content_type": "text/csv",
            "size": len(content.encode("utf-8")),
        }

    def _export_txt(
        self, snippets: List[Snippet], options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Export as plain text format"""

        content_lines = [
            f"CODE SNIPPETS EXPORT",
            f"Generated on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Total snippets: {len(snippets)}",
            "=" * 60,
            "",
        ]

        for i, snippet in enumerate(snippets, 1):
            content_lines.extend(
                [
                    f"{i}. {snippet.title}",
                    f"   Language: {snippet.language or 'Unknown'}",
                    f"   Created: {snippet.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
                    f"   Tags: {snippet.tags or 'None'}",
                    f"   Description: {snippet.description or 'No description'}",
                    "",
                    "   Code:",
                    "   " + "-" * 50,
                    "",
                ]
            )

            # Add code content with indentation
            code_lines = (
                snippet.code_content.split("\n") if snippet.code_content else [""]
            )
            for line in code_lines:
                content_lines.append(f"   {line}")

            content_lines.extend(["", "   " + "-" * 50, "", ""])

        content = "\n".join(content_lines)

        return {
            "content": content,
            "filename": f'snippets_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt',
            "content_type": "text/plain",
            "size": len(content.encode("utf-8")),
        }

    def _export_zip(
        self, snippets: List[Snippet], options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Export as ZIP archive with individual files"""

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # Add README file
            readme_content = f"""Code Snippets Export
=====================

Exported on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
Total snippets: {len(snippets)}
Export format: Individual files in ZIP archive

Files included:
"""

            file_extensions = {
                "python": "py",
                "javascript": "js",
                "typescript": "ts",
                "html": "html",
                "css": "css",
                "java": "java",
                "cpp": "cpp",
                "c": "c",
                "csharp": "cs",
                "php": "php",
                "ruby": "rb",
                "go": "go",
                "rust": "rs",
                "kotlin": "kt",
                "swift": "swift",
                "sql": "sql",
                "bash": "sh",
                "powershell": "ps1",
                "json": "json",
                "xml": "xml",
                "yaml": "yml",
            }

            # Add individual snippet files
            for i, snippet in enumerate(snippets, 1):
                # Determine file extension
                lang = snippet.language.lower() if snippet.language else "txt"
                ext = file_extensions.get(lang, "txt")

                # Create safe filename
                safe_title = "".join(
                    c for c in snippet.title if c.isalnum() or c in (" ", "-", "_")
                ).strip()
                safe_title = safe_title.replace(" ", "_")[:50]  # Limit length

                filename = f"{i:03d}_{safe_title}.{ext}"

                # File content with metadata header
                file_content = f"""/*
 * Title: {snippet.title}
 * Description: {snippet.description or 'No description'}
 * Language: {snippet.language or 'Unknown'}
 * Created: {snippet.created_at.strftime('%Y-%m-%d %H:%M:%S')}
 * Tags: {snippet.tags or 'None'}
 * Usage Count: {snippet.usage_count or 0}
 */

{snippet.code_content or ''}"""

                zip_file.writestr(filename, file_content)
                readme_content += f"- {filename}\n"

            # Add README
            zip_file.writestr("README.txt", readme_content)

            # Add JSON export for metadata
            json_export = self._export_json(snippets, options)
            zip_file.writestr("metadata.json", json_export["content"])

        zip_buffer.seek(0)
        zip_content = zip_buffer.getvalue()

        return {
            "content": base64.b64encode(zip_content).decode("utf-8"),
            "filename": f'snippets_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip',
            "content_type": "application/zip",
            "size": len(zip_content),
            "encoding": "base64",
        }

    def _export_github_gist(
        self, snippets: List[Snippet], options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Export to GitHub Gist"""

        github_token = options.get("github_token")
        if not github_token:
            raise ValueError("GitHub token required for Gist export")

        # Prepare files for Gist
        files = {}

        if len(snippets) == 1:
            # Single snippet
            snippet = snippets[0]
            filename = snippet.filename or f"{snippet.title.replace(' ', '_')}.txt"
            files[filename] = {"content": snippet.code_content or ""}
            description = snippet.description or snippet.title
        else:
            # Multiple snippets
            for i, snippet in enumerate(snippets, 1):
                ext = self._get_file_extension(snippet.language)
                safe_title = "".join(
                    c for c in snippet.title if c.isalnum() or c in (" ", "-", "_")
                ).strip()
                filename = f"{i:02d}_{safe_title.replace(' ', '_')}.{ext}"

                files[filename] = {
                    "content": f"// {snippet.title}\n// {snippet.description or 'No description'}\n\n{snippet.code_content or ''}"
                }

            description = f"Code Snippets Export - {len(snippets)} snippets"

        # Create Gist payload
        gist_data = {
            "description": description,
            "public": options.get("public", False),
            "files": files,
        }

        # Make API request
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        try:
            response = requests.post(
                "https://api.github.com/gists",
                headers=headers,
                json=gist_data,
                timeout=30,
            )
            response.raise_for_status()

            gist_info = response.json()

            return {
                "success": True,
                "gist_id": gist_info["id"],
                "gist_url": gist_info["html_url"],
                "api_url": gist_info["url"],
                "created_at": gist_info["created_at"],
                "public": gist_info["public"],
                "files_count": len(files),
            }

        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Failed to create Gist: {str(e)}"}

    def _export_pastebin(
        self, snippets: List[Snippet], options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Export to Pastebin"""

        api_key = options.get("pastebin_api_key") or current_app.config.get(
            "PASTEBIN_API_KEY"
        )
        if not api_key:
            raise ValueError("Pastebin API key required")

        # Combine snippets into single paste
        content_parts = []
        for snippet in snippets:
            content_parts.append(f"// {snippet.title}")
            if snippet.description:
                content_parts.append(f"// {snippet.description}")
            content_parts.append(f"// Language: {snippet.language or 'Unknown'}")
            content_parts.append("")
            content_parts.append(snippet.code_content or "")
            content_parts.append("")
            content_parts.append("-" * 50)
            content_parts.append("")

        paste_content = "\n".join(content_parts)

        # Pastebin API parameters
        data = {
            "api_dev_key": api_key,
            "api_option": "paste",
            "api_paste_code": paste_content,
            "api_paste_name": options.get(
                "title", f"Code Snippets Export - {len(snippets)} snippets"
            ),
            "api_paste_expire_date": options.get("expire", "1M"),  # 1 month
            "api_paste_private": "1" if options.get("private", True) else "0",
            "api_paste_format": "text",
        }

        try:
            response = requests.post(
                "https://pastebin.com/api/api_post.php", data=data, timeout=30
            )

            if response.text.startswith("https://pastebin.com/"):
                return {
                    "success": True,
                    "paste_url": response.text.strip(),
                    "snippets_count": len(snippets),
                }
            else:
                return {"success": False, "error": response.text}

        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Failed to create paste: {str(e)}"}

    def _export_hastebin(
        self, snippets: List[Snippet], options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Export to Hastebin"""

        # Combine snippets
        content_parts = []
        for snippet in snippets:
            content_parts.append(f"// {snippet.title}")
            if snippet.description:
                content_parts.append(f"// {snippet.description}")
            content_parts.append("")
            content_parts.append(snippet.code_content or "")
            content_parts.append("")
            content_parts.append("-" * 40)
            content_parts.append("")

        paste_content = "\n".join(content_parts)

        hastebin_url = options.get("hastebin_url", "https://hastebin.com")

        try:
            response = requests.post(
                f"{hastebin_url}/documents", data=paste_content, timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                paste_url = f"{hastebin_url}/{result['key']}"

                return {
                    "success": True,
                    "paste_url": paste_url,
                    "key": result["key"],
                    "snippets_count": len(snippets),
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                }

        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Failed to create paste: {str(e)}"}

    def _get_file_extension(self, language: str) -> str:
        """Get appropriate file extension for language"""

        extensions = {
            "python": "py",
            "javascript": "js",
            "typescript": "ts",
            "html": "html",
            "css": "css",
            "java": "java",
            "cpp": "cpp",
            "c": "c",
            "csharp": "cs",
            "php": "php",
            "ruby": "rb",
            "go": "go",
            "rust": "rs",
            "kotlin": "kt",
            "swift": "swift",
            "sql": "sql",
            "bash": "sh",
            "powershell": "ps1",
            "json": "json",
            "xml": "xml",
            "yaml": "yml",
            "markdown": "md",
            "dockerfile": "dockerfile",
        }

        return extensions.get(language.lower() if language else "", "txt")

    def get_export_options(self, format_type: str) -> Dict[str, Any]:
        """Get available options for specific export format"""

        base_options = {
            "include_metadata": {
                "type": "boolean",
                "default": True,
                "description": "Include creation date, tags, and other metadata",
            },
            "include_versions": {
                "type": "boolean",
                "default": False,
                "description": "Include version history (if available)",
            },
        }

        format_specific = {
            "json": {
                "pretty_print": {
                    "type": "boolean",
                    "default": True,
                    "description": "Format JSON with indentation",
                }
            },
            "html": {
                "syntax_highlighting": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include syntax highlighting CSS/JS",
                },
                "theme": {
                    "type": "select",
                    "options": ["default", "dark", "github", "monokai"],
                    "default": "default",
                    "description": "Color theme for syntax highlighting",
                },
            },
            "gist": {
                "github_token": {
                    "type": "string",
                    "required": True,
                    "description": "GitHub personal access token",
                },
                "public": {
                    "type": "boolean",
                    "default": False,
                    "description": "Make Gist public",
                },
            },
            "pastebin": {
                "pastebin_api_key": {
                    "type": "string",
                    "required": True,
                    "description": "Pastebin API key",
                },
                "expire": {
                    "type": "select",
                    "options": ["N", "10M", "1H", "1D", "1W", "2W", "1M", "6M", "1Y"],
                    "default": "1M",
                    "description": "Paste expiration time",
                },
                "private": {
                    "type": "boolean",
                    "default": True,
                    "description": "Make paste private",
                },
            },
        }

        options = base_options.copy()
        if format_type in format_specific:
            options.update(format_specific[format_type])

        return options


# Initialize the export service
export_service = ExportService()
# Initialize the export service
export_service = ExportService()


# Standalone function for backward compatibility
def export_snippets(snippets, format_type="json"):
    """
    Export snippets in specified format (backward compatibility wrapper)

    Args:
        snippets: List of Snippet objects
        format_type: Export format (json, markdown, html, etc.)

    Returns:
        Export data based on format
    """
    # Extract snippet IDs
    snippet_ids = [s.id for s in snippets]

    # Get user_id from first snippet (assuming all belong to same user)
    user_id = snippets[0].user_id if snippets else None

    if not user_id:
        raise ValueError("Cannot determine user_id from snippets")

    # Use the export service
    result = export_service.export_snippets(
        snippet_ids=snippet_ids, format_type=format_type, user_id=user_id, options={}
    )

    # For backward compatibility, return just the content for simple formats
    if format_type in ["json", "markdown", "txt", "csv", "html"]:
        return result.get("content", result)

    return result


def export_collections(collection_ids, format_type="json", user_id=None, options=None):
    """
    Export multiple collections in specified format (standalone function)

    Args:
        collection_ids: List of collection IDs to export
        format_type: Export format (json, markdown, html, etc.)
        user_id: User ID performing the export
        options: Additional export options

    Returns:
        Export data based on format
    """
    if not user_id:
        raise ValueError("user_id is required for export_collections")

    # Use the export service
    result = export_service.export_collections(
        collection_ids=collection_ids,
        format_type=format_type,
        user_id=user_id,
        options=options or {},
    )

    # For backward compatibility, return just the content for simple formats
    if format_type in ["json", "markdown", "txt", "csv", "html"]:
        return result.get("content", result)

    return result
