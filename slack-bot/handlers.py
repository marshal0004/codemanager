"""
Slack Bot Event Handlers
Handles Slack events for team snippet sharing and collaboration
"""

import logging
from flask import current_app
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from app.models.snippet import Snippet
from app.models.collection import Collection
from app.models.team import Team
from app.models.user import User
from app.services.notification_service import NotificationService
from app.utils.helpers import format_code_block, truncate_text
import json
import re

logger = logging.getLogger(__name__)


class SlackEventHandler:
    def __init__(self, slack_client: WebClient):
        self.client = slack_client
        self.notification_service = NotificationService()

    def handle_app_mention(self, event, say):
        """Handle @snippet_bot mentions in channels"""
        try:
            user_id = event.get("user")
            channel_id = event.get("channel")
            text = event.get("text", "").lower()

            # Get user info from Slack
            slack_user = self.client.users_info(user=user_id)
            email = slack_user["user"].get("profile", {}).get("email")

            if not email:
                say(
                    "❌ Unable to find your account. Please ensure your Slack email matches your snippet manager account."
                )
                return

            # Find user in our system
            user = User.query.filter_by(email=email).first()
            if not user:
                say(
                    "❌ No snippet manager account found for your email. Please sign up first!"
                )
                return

            # Parse command
            if "search" in text:
                self._handle_search_command(text, user, say)
            elif "share" in text:
                self._handle_share_command(text, user, channel_id, say)
            elif "create" in text:
                self._handle_create_command(text, user, say)
            elif "list" in text:
                self._handle_list_command(user, say)
            else:
                self._show_help(say)

        except SlackApiError as e:
            logger.error(f"Slack API error: {e}")
            say("❌ Something went wrong. Please try again later.")
        except Exception as e:
            logger.error(f"Error handling app mention: {e}")
            say("❌ An error occurred while processing your request.")

    def handle_message(self, event, say):
        """Handle direct messages to the bot"""
        try:
            if event.get("channel_type") != "im":
                return

            user_id = event.get("user")
            text = event.get("text", "").strip()

            # Get user info
            slack_user = self.client.users_info(user=user_id)
            email = slack_user["user"].get("profile", {}).get("email")

            if not email:
                say(
                    "❌ Unable to find your account. Please ensure your Slack email matches your snippet manager account."
                )
                return

            user = User.query.filter_by(email=email).first()
            if not user:
                say(
                    "👋 Welcome! It looks like you don't have a snippet manager account yet. Please sign up at our web dashboard first!"
                )
                return

            # Handle code snippet detection
            if self._contains_code(text):
                self._handle_code_snippet(text, user, say)
            else:
                self._show_help(say)

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            say("❌ An error occurred while processing your message.")

    def handle_slash_command(self, command, ack, say):
        """Handle /snippet slash commands"""
        ack()

        try:
            user_id = command.get("user_id")
            text = command.get("text", "").strip()
            channel_id = command.get("channel_id")

            # Get user info
            slack_user = self.client.users_info(user=user_id)
            email = slack_user["user"].get("profile", {}).get("email")

            if not email:
                say("❌ Unable to find your account.")
                return

            user = User.query.filter_by(email=email).first()
            if not user:
                say("❌ No account found. Please sign up first!")
                return

            if not text:
                self._show_help(say)
                return

            parts = text.split(" ", 1)
            action = parts[0].lower()

            if action == "search":
                query = parts[1] if len(parts) > 1 else ""
                self._handle_search_command(query, user, say)
            elif action == "share":
                snippet_id = parts[1] if len(parts) > 1 else ""
                self._handle_share_command(snippet_id, user, channel_id, say)
            elif action == "recent":
                self._handle_recent_command(user, say)
            else:
                self._show_help(say)

        except Exception as e:
            logger.error(f"Error handling slash command: {e}")
            say("❌ An error occurred while processing your command.")

    def _handle_search_command(self, query, user, say):
        """Search for snippets"""
        if not query or len(query.strip()) < 2:
            say("🔍 Please provide a search query. Example: `search python function`")
            return

        # Extract actual search term
        search_term = query.replace("search", "").strip()

        # Search user's snippets
        snippets = (
            Snippet.query.filter(
                Snippet.user_id == user.id,
                Snippet.title.contains(search_term)
                | Snippet.content.contains(search_term)
                | Snippet.tags.contains(search_term),
            )
            .limit(5)
            .all()
        )

        if not snippets:
            say(f"🔍 No snippets found for '{search_term}'")
            return

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🔍 *Found {len(snippets)} snippet(s) for '{search_term}'*",
                },
            },
            {"type": "divider"},
        ]

        for snippet in snippets:
            truncated_content = truncate_text(snippet.content, 200)

            blocks.extend(
                [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{snippet.title}*\n`{snippet.language}` • {snippet.tags}\n```{truncated_content}```",
                        },
                        "accessory": {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Share"},
                            "value": str(snippet.id),
                            "action_id": f"share_snippet_{snippet.id}",
                        },
                    }
                ]
            )

        say(blocks=blocks)

    def _handle_share_command(self, snippet_ref, user, channel_id, say):
        """Share a snippet to the channel"""
        # Extract snippet ID from command
        snippet_id = re.search(r"\d+", snippet_ref)
        if not snippet_id:
            say("❌ Please provide a valid snippet ID. Example: `share 123`")
            return

        snippet = Snippet.query.filter_by(
            id=int(snippet_id.group()), user_id=user.id
        ).first()

        if not snippet:
            say("❌ Snippet not found or you don't have permission to access it.")
            return

        # Share to channel
        self._share_snippet_to_channel(snippet, channel_id, user)
        say(f"✅ Shared snippet '{snippet.title}' to the channel!")

    def _handle_create_command(self, text, user, say):
        """Handle quick snippet creation"""
        say(
            {
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "📝 *Quick Snippet Creation*\nSend me your code in the next message and I'll help you save it!",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "💡 *Tip:* Use code blocks (```) for better formatting",
                        },
                    },
                ]
            }
        )

    def _handle_list_command(self, user, say):
        """List recent snippets"""
        snippets = (
            Snippet.query.filter_by(user_id=user.id)
            .order_by(Snippet.created_at.desc())
            .limit(10)
            .all()
        )

        if not snippets:
            say("📝 You don't have any snippets yet. Create your first one!")
            return

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📋 *Your Recent Snippets* ({len(snippets)})",
                },
            },
            {"type": "divider"},
        ]

        for snippet in snippets:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{snippet.title}*\n`{snippet.language}` • Created {snippet.created_at.strftime('%m/%d/%Y')}",
                    },
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Share"},
                        "value": str(snippet.id),
                        "action_id": f"share_snippet_{snippet.id}",
                    },
                }
            )

        say(blocks=blocks)

    def _handle_recent_command(self, user, say):
        """Show recent snippets with quick actions"""
        self._handle_list_command(user, say)

    def _handle_code_snippet(self, text, user, say):
        """Process and save code snippet from message"""
        # Extract code blocks
        code_blocks = re.findall(r"```(\w+)?\n(.*?)\n```", text, re.DOTALL)

        if not code_blocks:
            # Try to detect code without markdown
            if any(
                keyword in text.lower()
                for keyword in [
                    "def ",
                    "function",
                    "class ",
                    "import ",
                    "const ",
                    "var ",
                ]
            ):
                say(
                    {
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "🤖 I detected some code! Would you like me to save it as a snippet?",
                                },
                            },
                            {
                                "type": "actions",
                                "elements": [
                                    {
                                        "type": "button",
                                        "text": {
                                            "type": "plain_text",
                                            "text": "✅ Yes, save it",
                                        },
                                        "style": "primary",
                                        "value": text,
                                        "action_id": "save_code_snippet",
                                    },
                                    {
                                        "type": "button",
                                        "text": {
                                            "type": "plain_text",
                                            "text": "❌ No, thanks",
                                        },
                                        "action_id": "dismiss_code",
                                    },
                                ],
                            },
                        ]
                    }
                )
            else:
                self._show_help(say)
            return

        # Process the first code block
        language, code = code_blocks[0]
        language = language or "text"

        # Create snippet
        title = f"Slack Snippet - {language.title()}"

        say(
            {
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"💾 *Save this {language} snippet?*\n```{code[:200]}{'...' if len(code) > 200 else ''}```",
                        },
                    },
                    {
                        "type": "input",
                        "element": {
                            "type": "plain_text_input",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Enter snippet title...",
                            },
                            "initial_value": title,
                        },
                        "label": {"type": "plain_text", "text": "Title"},
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "💾 Save Snippet",
                                },
                                "style": "primary",
                                "value": json.dumps(
                                    {"code": code, "language": language}
                                ),
                                "action_id": "confirm_save_snippet",
                            }
                        ],
                    },
                ]
            }
        )

    def _share_snippet_to_channel(self, snippet, channel_id, user):
        """Share snippet to Slack channel"""
        try:
            formatted_code = format_code_block(snippet.content, snippet.language)

            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"📋 *{snippet.title}*\nShared by <@{user.slack_user_id}>",
                    },
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"```{formatted_code}```"},
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"`{snippet.language}` • {snippet.tags or 'No tags'} • Created {snippet.created_at.strftime('%m/%d/%Y')}",
                        }
                    ],
                },
            ]

            self.client.chat_postMessage(channel=channel_id, blocks=blocks)

            # Log activity
            self.notification_service.create_notification(
                user_id=snippet.user_id,
                title="Snippet Shared",
                message=f"Your snippet '{snippet.title}' was shared to Slack",
                type="share",
            )

        except SlackApiError as e:
            logger.error(f"Error sharing snippet to channel: {e}")
            raise

    def _contains_code(self, text):
        """Detect if message contains code"""
        code_indicators = [
            "```",
            "def ",
            "function",
            "class ",
            "import ",
            "const ",
            "var ",
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "CREATE TABLE",
            "#!/bin/",
            "if __name__",
            "public static void",
            "console.log",
        ]

        return any(indicator in text for indicator in code_indicators)

    def _show_help(self, say):
        """Show help message with available commands"""
        say(
            {
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "🤖 *Snippet Manager Bot - Available Commands*",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*🔍 Search Snippets*\n`@snippet search python function`\n`/snippet search react hooks`",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*📤 Share Snippet*\n`@snippet share 123`\n`/snippet share 456`",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*📋 List Recent*\n`@snippet list`\n`/snippet recent`",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*💾 Quick Save*\nJust send me code blocks:\n```python\ndef hello():\n    print('Hello World')\n```",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": "💡 *Tip:* You can also DM me directly for a more private experience!",
                            }
                        ],
                    },
                ]
            }
        )


# Button interaction handlers
class SlackInteractionHandler:
    def __init__(self, slack_client: WebClient):
        self.client = slack_client

    def handle_button_click(self, ack, body, say):
        """Handle button interactions"""
        ack()

        try:
            action = body["actions"][0]
            action_id = action["action_id"]
            user_id = body["user"]["id"]

            if action_id.startswith("share_snippet_"):
                snippet_id = action["value"]
                self._handle_share_button(snippet_id, user_id, body, say)
            elif action_id == "save_code_snippet":
                code = action["value"]
                self._handle_save_button(code, user_id, say)
            elif action_id == "dismiss_code":
                say("👍 No problem! Let me know if you need anything else.")

        except Exception as e:
            logger.error(f"Error handling button click: {e}")
            say("❌ Something went wrong. Please try again.")

    def _handle_share_button(self, snippet_id, slack_user_id, body, say):
        """Handle snippet share button click"""
        # Implementation for sharing snippet
        pass

    def _handle_save_button(self, code, slack_user_id, say):
        """Handle save snippet button click"""
        # Implementation for saving snippet
        pass
