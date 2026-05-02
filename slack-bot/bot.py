import os
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

import slack_sdk
from slack_sdk.rtm_v2 import RTMClient
from slack_sdk.web import WebClient
from slack_sdk.errors import SlackApiError
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt.context import BoltContext
from slack_bolt.request import BoltRequest
from slack_bolt.response import BoltResponse

import requests
import re
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import TerminalFormatter
from pygments.util import ClassNotFound

from handlers import (
    SnippetSearchHandler,
    SnippetShareHandler,
    TeamCollaborationHandler,
    AnalyticsHandler
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CodeSnippetSlackBot:
    """
    Advanced Slack bot for Code Snippet Manager with modern features:
    - Real-time snippet sharing
    - Smart code detection and formatting
    - Team collaboration features
    - Analytics and insights
    - Interactive UI components
    """
    
    def __init__(self):
        # Initialize Slack app with modern features
        self.app = App(
            token=os.environ.get("SLACK_BOT_TOKEN"),
            signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
            process_before_response=True
        )
        
        # Initialize API client for backend communication
        self.api_base_url = os.environ.get("SNIPPET_API_URL", "http://localhost:5000")
        self.api_headers = {
            "Authorization": f"Bearer {os.environ.get('SNIPPET_API_TOKEN')}",
            "Content-Type": "application/json"
        }
        
        # Initialize handlers
        self.search_handler = SnippetSearchHandler(self.api_base_url, self.api_headers)
        self.share_handler = SnippetShareHandler(self.api_base_url, self.api_headers)
        self.collaboration_handler = TeamCollaborationHandler(self.api_base_url, self.api_headers)
        self.analytics_handler = AnalyticsHandler(self.api_base_url, self.api_headers)
        
        # Bot state management
        self.active_sessions: Dict[str, Dict] = {}
        self.user_preferences: Dict[str, Dict] = {}
        
        # Register all event listeners and slash commands
        self.register_listeners()
        
    def register_listeners(self):
        """Register all Slack event listeners and commands"""
        
        # Slash Commands
        self.app.command("/snippet-search")(self.handle_snippet_search)
        self.app.command("/snippet-save")(self.handle_snippet_save)
        self.app.command("/snippet-share")(self.handle_snippet_share)
        self.app.command("/snippet-collections")(self.handle_collections)
        self.app.command("/snippet-analytics")(self.handle_analytics)
        self.app.command("/snippet-help")(self.handle_help)
        
        # Message Events
        self.app.event("message")(self.handle_message)
        self.app.event("app_mention")(self.handle_mention)
        
        # Interactive Components
        self.app.action("snippet_action")(self.handle_snippet_action)
        self.app.action("search_snippet")(self.handle_search_action)
        self.app.action("save_snippet")(self.handle_save_action)
        self.app.action("share_snippet")(self.handle_share_action)
        self.app.action("collection_select")(self.handle_collection_select)
        
        # Modal Submissions
        self.app.view("snippet_save_modal")(self.handle_save_modal_submission)
        self.app.view("snippet_search_modal")(self.handle_search_modal_submission)
        self.app.view("collection_create_modal")(self.handle_collection_create_submission)
        
        # Shortcut handlers
        self.app.shortcut("quick_snippet_search")(self.handle_quick_search_shortcut)
        self.app.shortcut("save_snippet_shortcut")(self.handle_save_shortcut)

    async def handle_snippet_search(self, ack, body, client, logger):
        """Handle /snippet-search command with advanced search UI"""
        await ack()
        
        try:
            # Create modern search modal with filters
            search_modal = self.create_search_modal()
            
            await client.views_open(
                trigger_id=body["trigger_id"],
                view=search_modal
            )
            
        except Exception as e:
            logger.error(f"Error opening search modal: {e}")
            await self.send_error_message(client, body["channel_id"], "Failed to open search. Please try again.")

    async def handle_snippet_save(self, ack, body, client, logger):
        """Handle /snippet-save command with smart code detection"""
        await ack()
        
        try:
            # Get recent messages to detect code blocks
            channel_id = body["channel_id"]
            messages = await self.get_recent_messages(client, channel_id, limit=10)
            
            # Find code blocks in recent messages
            code_blocks = self.extract_code_blocks(messages)
            
            if code_blocks:
                # Show save modal with detected code
                save_modal = self.create_save_modal(code_blocks)
            else:
                # Show empty save modal
                save_modal = self.create_save_modal()
            
            await client.views_open(
                trigger_id=body["trigger_id"],
                view=save_modal
            )
            
        except Exception as e:
            logger.error(f"Error opening save modal: {e}")
            await self.send_error_message(client, body["channel_id"], "Failed to open save dialog. Please try again.")

    async def handle_snippet_share(self, ack, body, client, logger):
        """Handle /snippet-share command with team sharing features"""
        await ack()
        
        try:
            user_id = body["user_id"]
            team_id = body["team_id"]
            
            # Get user's snippets and collections
            snippets = await self.get_user_snippets(user_id, team_id)
            collections = await self.get_user_collections(user_id, team_id)
            
            if not snippets:
                await client.chat_postEphemeral(
                    channel=body["channel_id"],
                    user=user_id,
                    text="You don't have any snippets to share yet. Use `/snippet-save` to create your first snippet!"
                )
                return
            
            # Create interactive share interface
            share_blocks = self.create_share_interface(snippets, collections)
            
            await client.chat_postEphemeral(
                channel=body["channel_id"],
                user=user_id,
                blocks=share_blocks,
                text="Select a snippet to share with the team"
            )
            
        except Exception as e:
            logger.error(f"Error handling snippet share: {e}")
            await self.send_error_message(client, body["channel_id"], "Failed to load snippets for sharing.")

    async def handle_collections(self, ack, body, client, logger):
        """Handle /snippet-collections command with collection management"""
        await ack()
        
        try:
            user_id = body["user_id"]
            team_id = body["team_id"]
            
            collections = await self.get_user_collections(user_id, team_id)
            
            # Create collection management interface
            collection_blocks = self.create_collection_interface(collections)
            
            await client.chat_postEphemeral(
                channel=body["channel_id"],
                user=user_id,
                blocks=collection_blocks,
                text="Manage your snippet collections"
            )
            
        except Exception as e:
            logger.error(f"Error handling collections: {e}")
            await self.send_error_message(client, body["channel_id"], "Failed to load collections.")

    async def handle_analytics(self, ack, body, client, logger):
        """Handle /snippet-analytics command with usage insights"""
        await ack()
        
        try:
            user_id = body["user_id"]
            team_id = body["team_id"]
            
            # Get analytics data
            analytics = await self.analytics_handler.get_user_analytics(user_id, team_id)
            
            # Create beautiful analytics visualization
            analytics_blocks = self.create_analytics_interface(analytics)
            
            await client.chat_postEphemeral(
                channel=body["channel_id"],
                user=user_id,
                blocks=analytics_blocks,
                text="Your snippet usage analytics"
            )
            
        except Exception as e:
            logger.error(f"Error handling analytics: {e}")
            await self.send_error_message(client, body["channel_id"], "Failed to load analytics.")

    async def handle_message(self, event, client, logger):
        """Handle regular messages with smart code detection"""
        try:
            # Skip bot messages and empty messages
            if event.get("bot_id") or not event.get("text"):
                return
            
            message_text = event["text"]
            channel_id = event["channel"]
            user_id = event["user"]
            
            # Detect code blocks with triple backticks
            code_pattern = r'```(\w+)?\n(.*?)\n```'
            code_matches = re.findall(code_pattern, message_text, re.DOTALL)
            
            if code_matches:
                # Offer to save detected code as snippet
                await self.offer_code_save(client, channel_id, user_id, code_matches)
            
            # Check for snippet mentions (@snippet-bot search: python)
            mention_pattern = r'<@\w+>\s+(search|find|get):\s*(.+)'
            mention_match = re.search(mention_pattern, message_text)
            
            if mention_match:
                action = mention_match.group(1)
                query = mention_match.group(2).strip()
                
                if action in ['search', 'find', 'get']:
                    await self.handle_inline_search(client, channel_id, user_id, query)
                    
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def handle_mention(self, event, client, logger):
        """Handle @mentions with smart responses"""
        try:
            message_text = event["text"]
            channel_id = event["channel"]
            user_id = event["user"]
            
            # Parse mention intent
            if "help" in message_text.lower():
                await self.send_help_message(client, channel_id, user_id)
            elif "search" in message_text.lower():
                # Extract search query
                query = self.extract_search_query(message_text)
                if query:
                    await self.handle_inline_search(client, channel_id, user_id, query)
                else:
                    await self.prompt_search_query(client, channel_id, user_id)
            elif "analytics" in message_text.lower():
                await self.show_quick_analytics(client, channel_id, user_id)
            else:
                await self.send_smart_response(client, channel_id, user_id, message_text)
                
        except Exception as e:
            logger.error(f"Error handling mention: {e}")

    def create_search_modal(self):
        """Create modern search modal with advanced filters"""
        return {
            "type": "modal",
            "callback_id": "snippet_search_modal",
            "title": {
                "type": "plain_text",
                "text": "🔍 Search Snippets"
            },
            "submit": {
                "type": "plain_text",
                "text": "Search"
            },
            "close": {
                "type": "plain_text",
                "text": "Cancel"
            },
            "blocks": [
                {
                    "type": "input",
                    "block_id": "search_query",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "query",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Enter keywords, tags, or language..."
                        }
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Search Query"
                    }
                },
                {
                    "type": "section",
                    "block_id": "language_filter",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Language Filter:*"
                    },
                    "accessory": {
                        "type": "multi_static_select",
                        "action_id": "languages",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select languages..."
                        },
                        "options": [
                            {"text": {"type": "plain_text", "text": "Python"}, "value": "python"},
                            {"text": {"type": "plain_text", "text": "JavaScript"}, "value": "javascript"},
                            {"text": {"type": "plain_text", "text": "TypeScript"}, "value": "typescript"},
                            {"text": {"type": "plain_text", "text": "Java"}, "value": "java"},
                            {"text": {"type": "plain_text", "text": "C++"}, "value": "cpp"},
                            {"text": {"type": "plain_text", "text": "Go"}, "value": "go"},
                            {"text": {"type": "plain_text", "text": "Rust"}, "value": "rust"},
                            {"text": {"type": "plain_text", "text": "PHP"}, "value": "php"},
                            {"text": {"type": "plain_text", "text": "Ruby"}, "value": "ruby"},
                            {"text": {"type": "plain_text", "text": "Swift"}, "value": "swift"}
                        ]
                    }
                },
                {
                    "type": "section",
                    "block_id": "collection_filter",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Collection Filter:*"
                    },
                    "accessory": {
                        "type": "static_select",
                        "action_id": "collection",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "All collections"
                        },
                        "options": [
                            {"text": {"type": "plain_text", "text": "All Collections"}, "value": "all"},
                            {"text": {"type": "plain_text", "text": "My Snippets"}, "value": "personal"},
                            {"text": {"type": "plain_text", "text": "Team Shared"}, "value": "team"}
                        ]
                    }
                },
                {
                    "type": "section",
                    "block_id": "sort_order",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Sort by:*"
                    },
                    "accessory": {
                        "type": "static_select",
                        "action_id": "sort",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Most Recent"
                        },
                        "options": [
                            {"text": {"type": "plain_text", "text": "Most Recent"}, "value": "recent"},
                            {"text": {"type": "plain_text", "text": "Most Used"}, "value": "popular"},
                            {"text": {"type": "plain_text", "text": "Alphabetical"}, "value": "alphabetical"},
                            {"text": {"type": "plain_text", "text": "Relevance"}, "value": "relevance"}
                        ]
                    }
                }
            ]
        }

    def create_save_modal(self, code_blocks=None):
        """Create modern save modal with smart code detection"""
        blocks = [
            {
                "type": "input",
                "block_id": "snippet_title",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "title",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Enter a descriptive title..."
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "Snippet Title"
                }
            }
        ]
        
        # Add code input with pre-filled detected code
        if code_blocks:
            initial_code = f"```{code_blocks[0][0]}\n{code_blocks[0][1]}\n```"
            blocks.append({
                "type": "input",
                "block_id": "snippet_code",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "code",
                    "multiline": True,
                    "initial_value": initial_code,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Paste your code here..."
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "Code"
                }
            })
        else:
            blocks.append({
                "type": "input",
                "block_id": "snippet_code",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "code",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Paste your code here..."
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "Code"
                }
            })
        
        # Add additional fields
        blocks.extend([
            {
                "type": "input",
                "block_id": "snippet_description",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "description",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Describe what this code does..."
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "Description"
                },
                "optional": True
            },
            {
                "type": "input",
                "block_id": "snippet_tags",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "tags",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "react, hooks, api, database..."
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "Tags (comma-separated)"
                },
                "optional": True
            },
            {
                "type": "section",
                "block_id": "snippet_language",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Programming Language:*"
                },
                "accessory": {
                    "type": "static_select",
                    "action_id": "language",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Auto-detect"
                    },
                    "options": [
                        {"text": {"type": "plain_text", "text": "Auto-detect"}, "value": "auto"},
                        {"text": {"type": "plain_text", "text": "Python"}, "value": "python"},
                        {"text": {"type": "plain_text", "text": "JavaScript"}, "value": "javascript"},
                        {"text": {"type": "plain_text", "text": "TypeScript"}, "value": "typescript"},
                        {"text": {"type": "plain_text", "text": "Java"}, "value": "java"},
                        {"text": {"type": "plain_text", "text": "C++"}, "value": "cpp"},
                        {"text": {"type": "plain_text", "text": "Go"}, "value": "go"},
                        {"text": {"type": "plain_text", "text": "Rust"}, "value": "rust"},
                        {"text": {"type": "plain_text", "text": "HTML"}, "value": "html"},
                        {"text": {"type": "plain_text", "text": "CSS"}, "value": "css"}
                    ]
                }
            }
        ])
        
        return {
            "type": "modal",
            "callback_id": "snippet_save_modal",
            "title": {
                "type": "plain_text",
                "text": "💾 Save Snippet"
            },
            "submit": {
                "type": "plain_text",
                "text": "Save"
            },
            "close": {
                "type": "plain_text",
                "text": "Cancel"
            },
            "blocks": blocks
        }

    def create_share_interface(self, snippets, collections):
        """Create interactive snippet sharing interface"""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚀 Share Your Snippets"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Select a snippet to share with the team:"
                }
            },
            {
                "type": "divider"
            }
        ]
        
        # Group snippets by collection
        snippet_groups = {"uncategorized": []}
        for collection in collections:
            snippet_groups[collection["name"]] = []
        
        for snippet in snippets[:10]:  # Limit to 10 most recent
            collection_name = snippet.get("collection_name", "uncategorized")
            if collection_name not in snippet_groups:
                snippet_groups[collection_name] = []
            snippet_groups[collection_name].append(snippet)
        
        # Create blocks for each group
        for group_name, group_snippets in snippet_groups.items():
            if not group_snippets:
                continue
                
            # Group header
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📁 {group_name.title()}*"
                }
            })
            
            # Snippet buttons
            for snippet in group_snippets:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{snippet['title']}*\n`{snippet['language']}` • {len(snippet['code'].split('\\n'))} lines"
                    },
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Share"
                        },
                        "action_id": "share_snippet",
                        "value": str(snippet["id"]),
                        "style": "primary"
                    }
                })
        
        return blocks

    def create_analytics_interface(self, analytics):
        """Create beautiful analytics visualization"""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📊 Your Snippet Analytics"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Total Snippets:*\n{analytics.get('total_snippets', 0)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Times Used:*\n{analytics.get('total_usage', 0)}"
                    },
                    {
                        "type": "mrkdwn", 
                        "text": f"*Collections:*\n{analytics.get('collections_count', 0)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Shared Snippets:*\n{analytics.get('shared_count', 0)}"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🔥 Most Used Languages:*"
                }
            }
        ]
        
        # Add language usage chart
        for lang_data in analytics.get('top_languages', [])[:5]:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"`{lang_data['language']}` {'█' * int(lang_data['percentage'] / 5)} {lang_data['percentage']}%"
                }
            })
        
        return blocks

    async def get_user_snippets(self, user_id: str, team_id: str) -> List[Dict]:
        """Fetch user snippets from API"""
        try:
            response = requests.get(
                f"{self.api_base_url}/api/snippets",
                headers=self.api_headers,
                params={"user_id": user_id, "team_id": team_id}
            )
            if response.status_code == 200:
                return response.json().get("snippets", [])
        except Exception as e:
            logger.error(f"Error fetching snippets: {e}")
        return []

    async def get_user_collections(self, user_id: str, team_id: str) -> List[Dict]:
        """Fetch user collections from API"""
        try:
            response = requests.get(
                f"{self.api_base_url}/api/collections",
                headers=self.api_headers,
                params={"user_id": user_id, "team_id": team_id}
            )
            if response.status_code == 200:
                return response.json().get("collections", [])
        except Exception as e:
            logger.error(f"Error fetching collections: {e}")
        return []

    def extract_code_blocks(self, messages: List[Dict]) -> List[tuple]:
        """Extract code blocks from messages"""
        code_blocks = []
        for message in messages:
            text = message.get("text", "")
            # Find code blocks with backticks
            pattern = r'```(\w+)?\n(.*?)\n```'
            matches = re.findall(pattern, text, re.DOTALL)
            code_blocks.extend(matches)
        return code_blocks

    async def send_error_message(self, client, channel_id: str, message: str):
        """Send formatted error message"""
        await client.chat_postMessage(
            channel=channel_id,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"❌ *Error:* {message}"
                    }
                }
            ]
        )

    def start(self):
        """Start the Slack bot"""
        handler = SocketModeHandler(self.app, os.environ["SLACK_APP_TOKEN"])
        logger.info("🤖 Code Snippet Slack Bot is starting...")
        handler.start()

if __name__ == "__main__":
    bot = CodeSnippetSlackBot()
    bot.start()
                    