#!/usr/bin/env python3
"""
Advanced CLI Tool for Code Snippet Manager
Features: Interactive commands, syntax highlighting, fuzzy search, Git integration
"""

import os
import sys
import json
import requests
import argparse
import subprocess
from typing import List, Dict, Optional, Any
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
import tempfile
import webbrowser

try:
    import click
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.syntax import Syntax
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.tree import Tree
    from rich.markdown import Markdown
    from fuzzywuzzy import fuzz, process
    import pyperclip
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("💡 Install with: pip install click rich requests fuzzywuzzy pyperclip")
    sys.exit(1)

# Initialize Rich console
console = Console()

@dataclass
class Config:
    """CLI Configuration"""
    api_base_url: str = "http://localhost:5000/api"
    auth_token: str = ""
    default_language: str = "auto"
    editor: str = os.environ.get('EDITOR', 'nano')
    sync_enabled: bool = True
    theme: str = "dark"

class APIClient:
    """Advanced API client with error handling and authentication"""
    
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {config.auth_token}',
            'Content-Type': 'application/json'
        })
    
    def request(self, method: str, endpoint: str, **kwargs) -> Dict[Any, Any]:
        """Make authenticated API request with error handling"""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Making API request...", total=None)
                
                response = self.session.request(
                    method, 
                    f"{self.config.api_base_url}{endpoint}",
                    timeout=30,
                    **kwargs
                )
                progress.update(task, completed=True)
                
            response.raise_for_status()
            return response.json() if response.content else {}
            
        except requests.exceptions.ConnectionError:
            console.print("❌ [red]Connection failed! Is the server running?[/red]")
            sys.exit(1)
        except requests.exceptions.HTTPError as e:
            console.print(f"❌ [red]API Error: {e.response.status_code} - {e.response.text}[/red]")
            sys.exit(1)
        except Exception as e:
            console.print(f"❌ [red]Unexpected error: {e}[/red]")
            sys.exit(1)

class SnippetManager:
    """Advanced snippet management with fuzzy search and Git integration"""
    
    def __init__(self, api_client: APIClient):
        self.api = api_client
        self.cache_file = Path.home() / '.snippet-manager' / 'cache.json'
        self.config_file = Path.home() / '.snippet-manager' / 'config.json'
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create necessary directories"""
        self.cache_file.parent.mkdir(exist_ok=True)
    
    def _get_cached_snippets(self) -> List[Dict]:
        """Get cached snippets for offline functionality"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    cache = json.load(f)
                    return cache.get('snippets', [])
            except:
                pass
        return []
    
    def _cache_snippets(self, snippets: List[Dict]):
        """Cache snippets for offline access"""
        cache_data = {
            'snippets': snippets,
            'last_updated': datetime.now().isoformat()
        }
        with open(self.cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)
    
    def create_snippet(self, title: str, content: str = None, language: str = None, 
                      tags: List[str] = None, collection: str = None, from_clipboard: bool = False):
        """Create a new snippet with advanced options"""
        
        if from_clipboard:
            try:
                content = pyperclip.paste()
                console.print("📋 [green]Content loaded from clipboard[/green]")
            except:
                console.print("❌ [red]Failed to read from clipboard[/red]")
                return
        
        if not content:
            # Open editor for content input
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as f:
                temp_file = f.name
            
            subprocess.run([config.editor, temp_file])
            
            with open(temp_file, 'r') as f:
                content = f.read().strip()
            
            os.unlink(temp_file)
            
            if not content:
                console.print("❌ [red]No content provided[/red]")
                return
        
        # Auto-detect language if not specified
        if not language or language == 'auto':
            language = self._detect_language(content)
        
        # Interactive tag input
        if not tags:
            tag_input = Prompt.ask("🏷️  Tags (comma-separated)", default="")
            tags = [tag.strip() for tag in tag_input.split(',') if tag.strip()]
        
        snippet_data = {
            'title': title,
            'content': content,
            'language': language,
            'tags': tags,
            'collection_id': collection,
            'created_via': 'cli'
        }
        
        try:
            result = self.api.request('POST', '/snippets', json=snippet_data)
            console.print(f"✅ [green]Snippet created successfully! ID: {result.get('id')}[/green]")
            
            # Show syntax-highlighted preview
            syntax = Syntax(content, language, theme="monokai", line_numbers=True)
            console.print(Panel(syntax, title=f"📝 {title}", border_style="green"))
            
        except Exception as e:
            console.print(f"❌ [red]Failed to create snippet: {e}[/red]")
    
    def search_snippets(self, query: str, language: str = None, tags: List[str] = None, 
                       fuzzy: bool = True, interactive: bool = True):
        """Advanced fuzzy search with interactive selection"""
        
        try:
            # Try API first, fall back to cache
            params = {'q': query}
            if language:
                params['language'] = language
            if tags:
                params['tags'] = ','.join(tags)
            
            results = self.api.request('GET', '/snippets/search', params=params)
            snippets = results.get('snippets', [])
            
        except:
            console.print("🔄 [yellow]Using cached data (offline mode)[/yellow]")
            snippets = self._get_cached_snippets()
            
            if fuzzy and query:
                # Fuzzy search on cached data
                snippet_texts = [f"{s['title']} {s.get('content', '')}" for s in snippets]
                matches = process.extractBests(query, snippet_texts, score_cutoff=60)
                snippet_indices = [snippet_texts.index(match[0]) for match in matches]
                snippets = [snippets[i] for i in snippet_indices]
        
        if not snippets:
            console.print("🔍 [yellow]No snippets found[/yellow]")
            return
        
        if interactive:
            self._interactive_snippet_selector(snippets)
        else:
            self._display_snippet_table(snippets)
    
    def _interactive_snippet_selector(self, snippets: List[Dict]):
        """Interactive snippet selector with preview"""
        
        choices = []
        for i, snippet in enumerate(snippets):
            tags_str = ', '.join(snippet.get('tags', []))
            choice = f"{i+1:2d}. {snippet['title']} [{snippet.get('language', 'text')}] {tags_str}"
            choices.append(choice)
        
        console.print("\n🔍 [bold blue]Search Results:[/bold blue]")
        for choice in choices:
            console.print(f"   {choice}")
        
        while True:
            selection = Prompt.ask(
                "\n📋 Select snippet (number), 'q' to quit, or 'a' for actions",
                default="q"
            )
            
            if selection.lower() == 'q':
                break
            elif selection.lower() == 'a':
                self._snippet_actions_menu(snippets)
                continue
            
            try:
                idx = int(selection) - 1
                if 0 <= idx < len(snippets):
                    self._display_snippet_detail(snippets[idx])
                    self._snippet_action_prompt(snippets[idx])
                else:
                    console.print("❌ [red]Invalid selection[/red]")
            except ValueError:
                console.print("❌ [red]Please enter a valid number[/red]")
    
    def _display_snippet_detail(self, snippet: Dict):
        """Display detailed snippet view with syntax highlighting"""
        
        content = snippet.get('content', 'No content')
        language = snippet.get('language', 'text')
        
        # Create syntax-highlighted content
        syntax = Syntax(content, language, theme="monokai", line_numbers=True)
        
        # Create info table
        info_table = Table(show_header=False, box=None, padding=(0, 1))
        info_table.add_row("🏷️  Tags:", ', '.join(snippet.get('tags', [])) or 'None')
        info_table.add_row("📅 Created:", snippet.get('created_at', 'Unknown'))
        info_table.add_row("🌍 Language:", language)
        info_table.add_row("📊 ID:", str(snippet.get('id', 'Unknown')))
        
        # Display in panels
        console.print(Panel(info_table, title="ℹ️  Snippet Info", border_style="blue"))
        console.print(Panel(syntax, title=f"📝 {snippet['title']}", border_style="green"))
    
    def _snippet_action_prompt(self, snippet: Dict):
        """Prompt for snippet actions"""
        
        actions = {
            'c': ('📋 Copy to clipboard', self._copy_to_clipboard),
            'e': ('✏️  Edit snippet', self._edit_snippet),
            'd': ('🗑️  Delete snippet', self._delete_snippet),
            's': ('🔗 Share snippet', self._share_snippet),
            'o': ('🌐 Open in browser', self._open_in_browser),
            'x': ('📤 Export', self._export_snippet)
        }
        
        console.print("\n🎯 [bold]Available Actions:[/bold]")
        for key, (desc, _) in actions.items():
            console.print(f"   {key}: {desc}")
        
        action = Prompt.ask("Select action", default="", choices=list(actions.keys()) + [''])
        
        if action and action in actions:
            actions[action][1](snippet)
    
    def _copy_to_clipboard(self, snippet: Dict):
        """Copy snippet content to clipboard"""
        try:
            pyperclip.copy(snippet.get('content', ''))
            console.print("✅ [green]Copied to clipboard![/green]")
        except Exception as e:
            console.print(f"❌ [red]Failed to copy: {e}[/red]")
    
    def _edit_snippet(self, snippet: Dict):
        """Edit snippet in external editor"""
        with tempfile.NamedTemporaryFile(mode='w+', suffix=f".{snippet.get('language', 'txt')}", delete=False) as f:
            f.write(snippet.get('content', ''))
            temp_file = f.name
        
        subprocess.run([config.editor, temp_file])
        
        with open(temp_file, 'r') as f:
            new_content = f.read()
        
        os.unlink(temp_file)
        
        if new_content != snippet.get('content', ''):
            # Update via API
            try:
                update_data = {'content': new_content}
                self.api.request('PUT', f"/snippets/{snippet['id']}", json=update_data)
                console.print("✅ [green]Snippet updated successfully![/green]")
            except Exception as e:
                console.print(f"❌ [red]Failed to update: {e}[/red]")
    
    def _delete_snippet(self, snippet: Dict):
        """Delete snippet with confirmation"""
        if Confirm.ask(f"🗑️  Delete '{snippet['title']}'?", default=False):
            try:
                self.api.request('DELETE', f"/snippets/{snippet['id']}")
                console.print("✅ [green]Snippet deleted successfully![/green]")
            except Exception as e:
                console.print(f"❌ [red]Failed to delete: {e}[/red]")
    
    def _share_snippet(self, snippet: Dict):
        """Generate shareable link"""
        try:
            result = self.api.request('POST', f"/snippets/{snippet['id']}/share")
            share_url = result.get('share_url')
            console.print(f"🔗 [green]Share URL: {share_url}[/green]")
            
            if Confirm.ask("📋 Copy to clipboard?", default=True):
                pyperclip.copy(share_url)
                console.print("✅ [green]URL copied to clipboard![/green]")
                
        except Exception as e:
            console.print(f"❌ [red]Failed to generate share link: {e}[/red]")
    
    def _open_in_browser(self, snippet: Dict):
        """Open snippet in web dashboard"""
        url = f"{self.api.config.api_base_url.replace('/api', '')}/dashboard/snippets/{snippet['id']}"
        webbrowser.open(url)
        console.print("🌐 [green]Opened in browser![/green]")
    
    def _export_snippet(self, snippet: Dict):
        """Export snippet to file"""
        formats = {
            'md': 'Markdown',
            'json': 'JSON', 
            'txt': 'Plain Text'
        }
        
        format_key = Prompt.ask("📤 Export format", choices=list(formats.keys()), default="md")
        
        filename = f"{snippet['title'].replace(' ', '_')}.{format_key}"
        
        try:
            export_data = {'format': format_key}
            result = self.api.request('POST', f"/snippets/{snippet['id']}/export", json=export_data)
            
            with open(filename, 'w') as f:
                f.write(result.get('content', ''))
            
            console.print(f"✅ [green]Exported to {filename}[/green]")
            
        except Exception as e:
            console.print(f"❌ [red]Failed to export: {e}[/red]")
    
    def _detect_language(self, content: str) -> str:
        """Simple language detection based on content patterns"""
        patterns = {
            'python': ['def ', 'import ', 'from ', 'print(', '__name__'],
            'javascript': ['function', 'const ', 'let ', 'var ', 'console.log'],
            'html': ['<html', '<div', '<span', '<!DOCTYPE'],
            'css': ['{', '}', 'color:', 'background:', 'margin:'],
            'sql': ['SELECT', 'FROM', 'WHERE', 'INSERT', 'UPDATE'],
            'bash': ['#!/bin/bash', 'echo ', '&&', '||', 'grep'],
            'json': ['{', '":', '"}', '[', ']']
        }
        
        content_lower = content.lower()
        scores = {}
        
        for lang, keywords in patterns.items():
            score = sum(1 for keyword in keywords if keyword.lower() in content_lower)
            if score > 0:
                scores[lang] = score
        
        return max(scores, key=scores.get) if scores else 'text'
    
    def sync_from_git(self, repo_path: str = '.'):
        """Sync snippets from Git repository"""
        try:
            # Find code files in repo
            repo = Path(repo_path)
            code_files = []
            
            for ext in ['.py', '.js', '.html', '.css', '.sql', '.sh', '.json', '.md']:
                code_files.extend(repo.rglob(f'*{ext}'))
            
            console.print(f"🔍 Found {len(code_files)} code files")
            
            for file_path in code_files[:10]:  # Limit to avoid spam
                if file_path.stat().st_size < 10000:  # Skip large files
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    # Create snippet from file
                    title = f"{file_path.parent.name}/{file_path.name}"
                    language = file_path.suffix[1:] if file_path.suffix else 'text'
                    
                    snippet_data = {
                        'title': title,
                        'content': content,
                        'language': language,
                        'tags': ['git-sync', repo_path],
                        'source': str(file_path)
                    }
                    
                    try:
                        self.api.request('POST', '/snippets', json=snippet_data)
                        console.print(f"✅ Synced: {title}")
                    except:
                        console.print(f"⚠️  Skipped: {title}")
            
            console.print("🔄 [green]Git sync completed![/green]")
            
        except Exception as e:
            console.print(f"❌ [red]Git sync failed: {e}[/red]")

# Configuration management
def load_config() -> Config:
    """Load CLI configuration"""
    config_file = Path.home() / '.snippet-manager' / 'config.json'
    config = Config()
    
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                data = json.load(f)
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
        except:
            pass
    
    return config

def save_config(config: Config):
    """Save CLI configuration"""
    config_file = Path.home() / '.snippet-manager' / 'config.json'
    config_file.parent.mkdir(exist_ok=True)
    
    with open(config_file, 'w') as f:
        json.dump(config.__dict__, f, indent=2)

# CLI Commands
@click.group()
@click.pass_context
def cli(ctx):
    """🚀 Advanced Code Snippet Manager CLI"""
    ctx.ensure_object(dict)
    ctx.obj['config'] = load_config()
    ctx.obj['api'] = APIClient(ctx.obj['config'])
    ctx.obj['manager'] = SnippetManager(ctx.obj['api'])

@cli.command()
@click.argument('title')
@click.option('--content', '-c', help='Snippet content')
@click.option('--language', '-l', help='Programming language')
@click.option('--tags', '-t', help='Comma-separated tags')
@click.option('--clipboard', is_flag=True, help='Use clipboard content')
@click.pass_context
def create(ctx, title, content, language, tags, clipboard):
    """📝 Create a new snippet"""
    tag_list = [tag.strip() for tag in tags.split(',')] if tags else None
    ctx.obj['manager'].create_snippet(title, content, language, tag_list, from_clipboard=clipboard)

@cli.command()
@click.argument('query', required=False)
@click.option('--language', '-l', help='Filter by language')
@click.option('--tags', '-t', help='Filter by tags')
@click.option('--fuzzy/--exact', default=True, help='Use fuzzy search')
@click.pass_context
def search(ctx, query, language, tags, fuzzy):
    """🔍 Search snippets"""
    tag_list = [tag.strip() for tag in tags.split(',')] if tags else None
    ctx.obj['manager'].search_snippets(query or '', language, tag_list, fuzzy)

@cli.command()
@click.option('--repo-path', '-r', default='.', help='Git repository path')
@click.pass_context
def sync_git(ctx, repo_path):
    """🔄 Sync snippets from Git repository"""
    ctx.obj['manager'].sync_from_git(repo_path)

@cli.command()
@click.option('--server', '-s', help='API server URL')
@click.option('--token', '-t', help='Authentication token')
@click.option('--editor', '-e', help='Default editor')
@click.pass_context
def config_cmd(ctx, server, token, editor):
    """⚙️  Configure CLI settings"""
    config = ctx.obj['config']
    
    if server:
        config.api_base_url = server
    if token:
        config.auth_token = token
    if editor:
        config.editor = editor
    
    save_config(config)
    console.print("✅ [green]Configuration updated![/green]")

@cli.command()
@click.pass_context
def login(ctx):
    """🔐 Login to snippet manager"""
    email = Prompt.ask("📧 Email")
    password = Prompt.ask("🔒 Password", password=True)
    
    try:
        response = ctx.obj['api'].request('POST', '/auth/login', json={
            'email': email,
            'password': password
        })
        
        token = response.get('access_token')
        if token:
            ctx.obj['config'].auth_token = token
            save_config(ctx.obj['config'])
            console.print("✅ [green]Login successful![/green]")
        else:
            console.print("❌ [red]Login failed![/red]")
    except Exception as e:
        console.print(f"❌ [red]Login error: {e}[/red]")

@cli.command()
@click.pass_context
def status(ctx):
    """📊 Show CLI status and statistics"""
    
    # Create status table
    table = Table(title="🚀 Snippet Manager CLI Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    config = ctx.obj['config']
    table.add_row("API Server", config.api_base_url)
    table.add_row("Auth Status", "✅ Logged in" if config.auth_token else "❌ Not logged in")
    table.add_row("Editor", config.editor)
    table.add_row("Theme", config.theme)
    
    console.print(table)
    
    # Try to get user stats
    if config.auth_token:
        try:
            stats = ctx.obj['api'].request('GET', '/user/stats')
            console.print(f"\n📊 [bold]Your Statistics:[/bold]")
            console.print(f"   📝 Total Snippets: {stats.get('total_snippets', 0)}")
            console.print(f"   📁 Collections: {stats.get('total_collections', 0)}")
            console.print(f"   🏷️  Unique Tags: {stats.get('unique_tags', 0)}")
        except:
            console.print("\n⚠️  [yellow]Could not fetch statistics[/yellow]")

if __name__ == '__main__':
    try:
        # Load global config
        config = load_config()
        
        # Welcome message
        console.print(Panel.fit(
            "🚀 [bold blue]Code Snippet Manager CLI[/bold blue]\n"
            "Advanced command-line interface for managing code snippets",
            border_style="blue"
        ))
        
        cli()
        
    except KeyboardInterrupt:
        console.print("\n👋 [yellow]Goodbye![/yellow]")
    except Exception as e:
        console.print(f"💥 [red]Fatal error: {e}[/red]")
        sys.exit(1)