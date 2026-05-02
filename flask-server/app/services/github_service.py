# flask-server/app/services/github_service.py
import requests
import base64
import json
from typing import Dict, List, Optional, Tuple
from flask import current_app
from datetime import datetime
import os


class GitHubService:
    """GitHub integration service for snippet management"""

    def __init__(self):
        self.api_base = "https://api.github.com"
        self.client_id = current_app.config.get("GITHUB_CLIENT_ID")
        self.client_secret = current_app.config.get("GITHUB_CLIENT_SECRET")

    def get_oauth_url(self, state: str) -> str:
        """Generate GitHub OAuth authorization URL"""
        return (
            f"https://github.com/login/oauth/authorize"
            f"?client_id={self.client_id}"
            f"&redirect_uri={current_app.config.get('GITHUB_REDIRECT_URI')}"
            f"&scope=repo,gist"
            f"&state={state}"
        )

    def exchange_code_for_token(self, code: str) -> Optional[str]:
        """Exchange OAuth code for access token"""
        try:
            response = requests.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                },
                headers={"Accept": "application/json"},
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("access_token")
            return None
        except Exception as e:
            current_app.logger.error(f"GitHub token exchange error: {str(e)}")
            return None

    def get_user_info(self, access_token: str) -> Optional[Dict]:
        """Get GitHub user information"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            }

            response = requests.get(f"{self.api_base}/user", headers=headers)

            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            current_app.logger.error(f"GitHub user info error: {str(e)}")
            return None

    def get_user_repositories(
        self, access_token: str, per_page: int = 30
    ) -> List[Dict]:
        """Get user's repositories"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            }

            response = requests.get(
                f"{self.api_base}/user/repos",
                headers=headers,
                params={"sort": "updated", "per_page": per_page, "type": "owner"},
            )

            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            current_app.logger.error(f"GitHub repositories error: {str(e)}")
            return []

    def create_gist(
        self,
        access_token: str,
        snippets: List[Dict],
        description: str = "",
        public: bool = False,
    ) -> Optional[Dict]:
        """Create a GitHub Gist from snippets"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            }

            files = {}
            for snippet in snippets:
                filename = self._generate_filename(snippet)
                files[filename] = {"content": snippet["content"]}

            data = {
                "description": description or "Code snippets from Snippet Manager",
                "public": public,
                "files": files,
            }

            response = requests.post(
                f"{self.api_base}/gists", headers=headers, json=data
            )

            if response.status_code == 201:
                return response.json()
            return None
        except Exception as e:
            current_app.logger.error(f"GitHub gist creation error: {str(e)}")
            return None

    def save_snippet_to_repo(
        self, access_token: str, repo_name: str, snippet: Dict, branch: str = "main"
    ) -> Optional[Dict]:
        """Save snippet to a specific repository"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            }

            # Get user info for repo path
            user_info = self.get_user_info(access_token)
            if not user_info:
                return None

            username = user_info["login"]
            filename = self._generate_filename(snippet)
            file_path = f"snippets/{filename}"

            # Check if file exists
            existing_file = self._get_file_content(
                access_token, username, repo_name, file_path, branch
            )

            # Prepare commit data
            content_encoded = base64.b64encode(snippet["content"].encode()).decode()

            commit_data = {
                "message": f"Add snippet: {snippet.get('title', 'Untitled')}",
                "content": content_encoded,
                "branch": branch,
            }

            if existing_file:
                commit_data["sha"] = existing_file["sha"]
                commit_data["message"] = (
                    f"Update snippet: {snippet.get('title', 'Untitled')}"
                )

            # Commit to repository
            response = requests.put(
                f"{self.api_base}/repos/{username}/{repo_name}/contents/{file_path}",
                headers=headers,
                json=commit_data,
            )

            if response.status_code in [200, 201]:
                return response.json()
            return None
        except Exception as e:
            current_app.logger.error(f"GitHub repo save error: {str(e)}")
            return None

    def create_repository(
        self,
        access_token: str,
        repo_name: str,
        description: str = "",
        private: bool = True,
    ) -> Optional[Dict]:
        """Create a new repository for snippets"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            }

            data = {
                "name": repo_name,
                "description": description or "Code snippets repository",
                "private": private,
                "auto_init": True,
                "gitignore_template": "Python",
            }

            response = requests.post(
                f"{self.api_base}/user/repos", headers=headers, json=data
            )

            if response.status_code == 201:
                return response.json()
            return None
        except Exception as e:
            current_app.logger.error(f"GitHub repo creation error: {str(e)}")
            return None

    def sync_snippets_to_repo(
        self,
        access_token: str,
        repo_name: str,
        snippets: List[Dict],
        branch: str = "main",
    ) -> Dict:
        """Bulk sync multiple snippets to repository"""
        results = {"success": [], "failed": [], "total": len(snippets)}

        for snippet in snippets:
            try:
                result = self.save_snippet_to_repo(
                    access_token, repo_name, snippet, branch
                )

                if result:
                    results["success"].append(
                        {
                            "snippet_id": snippet.get("id"),
                            "title": snippet.get("title"),
                            "github_url": result.get("content", {}).get("html_url"),
                        }
                    )
                else:
                    results["failed"].append(
                        {
                            "snippet_id": snippet.get("id"),
                            "title": snippet.get("title"),
                            "error": "Upload failed",
                        }
                    )
            except Exception as e:
                results["failed"].append(
                    {
                        "snippet_id": snippet.get("id"),
                        "title": snippet.get("title"),
                        "error": str(e),
                    }
                )

        return results

    def import_gist(self, access_token: str, gist_id: str) -> Optional[List[Dict]]:
        """Import snippets from a GitHub Gist"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            }

            response = requests.get(f"{self.api_base}/gists/{gist_id}", headers=headers)

            if response.status_code == 200:
                gist = response.json()
                snippets = []

                for filename, file_data in gist["files"].items():
                    snippet = {
                        "title": filename,
                        "content": file_data["content"],
                        "language": self._detect_language_from_filename(filename),
                        "source": "github_gist",
                        "external_id": gist_id,
                        "tags": ["imported", "github"],
                        "created_at": gist["created_at"],
                        "updated_at": gist["updated_at"],
                    }
                    snippets.append(snippet)

                return snippets
            return None
        except Exception as e:
            current_app.logger.error(f"GitHub gist import error: {str(e)}")
            return None

    def get_user_gists(self, access_token: str, per_page: int = 30) -> List[Dict]:
        """Get user's gists"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            }

            response = requests.get(
                f"{self.api_base}/gists", headers=headers, params={"per_page": per_page}
            )

            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            current_app.logger.error(f"GitHub gists error: {str(e)}")
            return []

    def validate_token(self, access_token: str) -> bool:
        """Validate GitHub access token"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            }

            response = requests.get(f"{self.api_base}/user", headers=headers)
            return response.status_code == 200
        except Exception:
            return False

    def _get_file_content(
        self,
        access_token: str,
        username: str,
        repo_name: str,
        file_path: str,
        branch: str,
    ) -> Optional[Dict]:
        """Get existing file content from repository"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            }

            response = requests.get(
                f"{self.api_base}/repos/{username}/{repo_name}/contents/{file_path}",
                headers=headers,
                params={"ref": branch},
            )

            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None

    def _generate_filename(self, snippet: Dict) -> str:
        """Generate appropriate filename for snippet"""
        title = snippet.get("title", "untitled")
        language = snippet.get("language", "").lower()

        # Clean title for filename
        clean_title = "".join(
            c for c in title if c.isalnum() or c in (" ", "-", "_")
        ).strip()
        clean_title = clean_title.replace(" ", "_")

        # Add appropriate extension
        extensions = {
            "python": ".py",
            "javascript": ".js",
            "typescript": ".ts",
            "java": ".java",
            "cpp": ".cpp",
            "c": ".c",
            "csharp": ".cs",
            "php": ".php",
            "ruby": ".rb",
            "go": ".go",
            "rust": ".rs",
            "html": ".html",
            "css": ".css",
            "scss": ".scss",
            "sql": ".sql",
            "bash": ".sh",
            "powershell": ".ps1",
            "json": ".json",
            "yaml": ".yml",
            "xml": ".xml",
            "markdown": ".md",
        }

        extension = extensions.get(language, ".txt")
        return f"{clean_title}{extension}"

    def _detect_language_from_filename(self, filename: str) -> str:
        """Detect programming language from filename"""
        extension = os.path.splitext(filename)[1].lower()

        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".cs": "csharp",
            ".php": "php",
            ".rb": "ruby",
            ".go": "go",
            ".rs": "rust",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".sql": "sql",
            ".sh": "bash",
            ".ps1": "powershell",
            ".json": "json",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".xml": "xml",
            ".md": "markdown",
        }

        return language_map.get(extension, "text")
