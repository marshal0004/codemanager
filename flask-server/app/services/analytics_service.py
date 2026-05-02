"""
Advanced Analytics Service for Code Snippet Manager
Provides comprehensive usage statistics, insights, and performance metrics
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter
import json
import statistics
from sqlalchemy import func, desc, and_, or_
from sqlalchemy.orm import sessionmaker
# ADD THIS IMPORT
from app.models.activity import Activity


class AnalyticsService:
    """Modern analytics service with comprehensive insights and real-time metrics"""

    def __init__(self, db_session):
        self.db = db_session
        self.cache_duration = timedelta(minutes=15)
        self._cache = {}

    def get_user_dashboard_analytics(
        self, user_id: str, days: int = 30
    ) -> Dict[str, Any]:
        """Generate comprehensive dashboard analytics for a user"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        analytics = {
            "overview": self._get_user_overview(user_id, start_date, end_date),
            "usage_patterns": self._get_usage_patterns(user_id, start_date, end_date),
            "snippet_insights": self._get_snippet_insights(
                user_id, start_date, end_date
            ),
            "productivity_metrics": self._get_productivity_metrics(
                user_id, start_date, end_date
            ),
            "trending_data": self._get_trending_data(user_id, start_date, end_date),
            "language_breakdown": self._get_language_breakdown(user_id),
            "collection_analytics": self._get_collection_analytics(user_id),
            "recommendations": self._generate_user_recommendations(user_id),
            "generated_at": datetime.utcnow().isoformat(),
            "period": f"Last {days} days",
        }

        return analytics

    def _get_user_overview(
        self, user_id: str, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Get high-level user statistics"""
        from app.models.snippet import Snippet
        from app.models.collection import Collection

        # Total counts
        total_snippets = (
            self.db.query(Snippet).filter(Snippet.user_id == user_id).count()
        )
        total_collections = (
            self.db.query(Collection).filter(Collection.user_id == user_id).count()
        )

        # Recent activity
        new_snippets = (
            self.db.query(Snippet)
            .filter(and_(Snippet.user_id == user_id, Snippet.created_at >= start_date))
            .count()
        )

        # Usage statistics
        total_snippet_views = (
            self.db.query(func.sum(Snippet.view_count))
            .filter(Snippet.user_id == user_id)
            .scalar()
            or 0
        )

        total_snippet_usage = (
            self.db.query(func.sum(Snippet.usage_count))
            .filter(Snippet.user_id == user_id)
            .scalar()
            or 0
        )

        # Growth metrics
        previous_period_start = start_date - (end_date - start_date)
        previous_snippets = (
            self.db.query(Snippet)
            .filter(
                and_(
                    Snippet.user_id == user_id,
                    Snippet.created_at >= previous_period_start,
                    Snippet.created_at < start_date,
                )
            )
            .count()
        )

        growth_rate = 0
        if previous_snippets > 0:
            growth_rate = ((new_snippets - previous_snippets) / previous_snippets) * 100

        return {
            "totals": {
                "snippets": total_snippets,
                "collections": total_collections,
                "snippet_views": total_snippet_views,
                "snippet_usage": total_snippet_usage,
            },
            "recent_activity": {
                "new_snippets": new_snippets,
                "growth_rate": round(growth_rate, 2),
                "avg_snippets_per_day": round(
                    new_snippets / max((end_date - start_date).days, 1), 2
                ),
            },
            "efficiency_score": self._calculate_efficiency_score(
                user_id, start_date, end_date
            ),
        }



    
    def get_team_dashboard_analytics(self, team_id: str, days: int = 30) -> Dict[str, Any]:
        """Generate comprehensive team analytics with real activity data"""
        try:
            from app.models.team import Team
            from app.models.team_member import TeamMember
            from app.models.snippet import Snippet
            from app.models.collection import Collection
            
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get team
            team = self.db.query(Team).filter(Team.id == team_id).first()
            if not team:
                return {"error": "Team not found"}
                
            # Get team members
            members = self.db.query(TeamMember).filter(
                TeamMember.team_id == team_id,
                TeamMember.is_active == True
            ).all()
            
            # GET REAL ACTIVITY DATA
            activities = Activity.get_team_activities(team_id=team_id, limit=100)
            activity_stats = Activity.get_activity_stats(team_id=team_id, days=days)
            
            # Calculate analytics from real data
            analytics = {
                "overview": {
                    "team_name": team.name,
                    "member_count": len(members),
                    "total_activities": activity_stats['total_activities'],
                    "active_members": len(set(a.user_id for a in activities[:20])),
                },
                "activity_metrics": {
                    "activities_this_period": activity_stats['total_activities'],
                    "by_category": activity_stats['by_category'],
                    "by_type": activity_stats['by_type'],
                    "daily_breakdown": activity_stats['by_day'],
                },
                "recent_activities": [activity.to_dict() for activity in activities[:10]],
                "most_active_members": activity_stats['most_active_users'],
                "collaboration_score": self._calculate_collaboration_score(activities),
                "generated_at": datetime.utcnow().isoformat(),
                "period_days": days
            }
            
            print(f"✅ TEAM ANALYTICS: Generated with {len(activities)} real activities")
            return analytics
            
        except Exception as e:
            print(f"❌ TEAM ANALYTICS ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": f"Analytics generation failed: {str(e)}"}

    def _calculate_collaboration_score(self, activities):
        """Calculate collaboration score based on real activity data"""
        if not activities:
            return 0
        
        collaboration_activities = [
            'member_joined', 'snippet_shared', 'collection_shared', 
            'comment_added', 'snippet_edited', 'chat_message_sent'
        ]
        
        collab_count = sum(1 for a in activities if a.action_type in collaboration_activities)
        return min(100, (collab_count / len(activities)) * 100)


    def _get_most_active_member(self, members, start_date):
        """Get most active team member"""
        try:
            most_active = max(members, key=lambda m: m.activity_summary.get('snippets_created', 0) if m.activity_summary else 0)
            return {
                "user_id": most_active.user_id,
                "activity_score": most_active.activity_summary.get('collaboration_score', 0) if most_active.activity_summary else 0
            }
        except:
            return {"user_id": None, "activity_score": 0}

    def _get_team_language_breakdown(self, snippets):
        """Get language breakdown for team"""
        from collections import Counter
        languages = Counter([s.language for s in snippets if s.language])
        return dict(languages.most_common(10))

    def _get_team_daily_activity(self, snippets, start_date, end_date):
        """Get daily activity breakdown"""
        daily_activity = {}
        current_date = start_date.date()
        
        while current_date <= end_date.date():
            day_snippets = [s for s in snippets if s.created_at.date() == current_date]
            daily_activity[current_date.isoformat()] = len(day_snippets)
            current_date += timedelta(days=1)
            
        return daily_activity

    def _calculate_team_collaboration_score(self, members):
        """Calculate team collaboration score"""
        if not members:
            return 0
            
        total_score = sum([
            m.activity_summary.get('collaboration_score', 0) if m.activity_summary else 0 
            for m in members
        ])
        
        return round(total_score / len(members), 2)    

    def _get_usage_patterns(
        self, user_id: str, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Analyze user usage patterns and behavior"""
        from app.models.snippet import Snippet

        # Time-based analysis
        snippets = (
            self.db.query(Snippet)
            .filter(and_(Snippet.user_id == user_id, Snippet.created_at >= start_date))
            .all()
        )

        # Hour of day analysis
        hourly_activity = defaultdict(int)
        daily_activity = defaultdict(int)

        for snippet in snippets:
            hour = snippet.created_at.hour
            day = snippet.created_at.strftime("%A")
            hourly_activity[hour] += 1
            daily_activity[day] += 1

        # Peak activity times
        peak_hour = (
            max(hourly_activity.items(), key=lambda x: x[1])
            if hourly_activity
            else (12, 0)
        )
        peak_day = (
            max(daily_activity.items(), key=lambda x: x[1])
            if daily_activity
            else ("Monday", 0)
        )

        # Activity timeline for charts
        timeline_data = self._generate_activity_timeline(snippets, start_date, end_date)

        return {
            "peak_times": {
                "peak_hour": f"{peak_hour[0]:02d}:00",
                "peak_day": peak_day[0],
                "peak_hour_count": peak_hour[1],
                "peak_day_count": peak_day[1],
            },
            "hourly_distribution": dict(hourly_activity),
            "daily_distribution": dict(daily_activity),
            "timeline": timeline_data,
            "activity_score": self._calculate_activity_score(
                hourly_activity, daily_activity
            ),
        }

    def _get_snippet_insights(
        self, user_id: str, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Get detailed snippet analytics and insights"""
        from app.models.snippet import Snippet

        snippets = self.db.query(Snippet).filter(Snippet.user_id == user_id).all()

        if not snippets:
            return {"message": "No snippets found for analysis"}

        # Performance metrics
        most_used = sorted(snippets, key=lambda s: s.usage_count or 0, reverse=True)[:5]
        most_viewed = sorted(snippets, key=lambda s: s.view_count or 0, reverse=True)[
            :5
        ]
        recent_snippets = sorted(
            [s for s in snippets if s.created_at >= start_date],
            key=lambda s: s.created_at,
            reverse=True,
        )[:5]

        # Content analysis
        avg_snippet_length = statistics.mean(
            [len(s.content) for s in snippets if s.content]
        )
        total_lines_of_code = sum(
            [len(s.content.splitlines()) for s in snippets if s.content]
        )

        # Tag analysis
        all_tags = []
        for snippet in snippets:
            if snippet.tags:
                all_tags.extend(snippet.tags)

        tag_frequency = Counter(all_tags)
        popular_tags = tag_frequency.most_common(10)

        return {
            "performance": {
                "most_used_snippets": [
                    {
                        "id": s.id,
                        "title": s.title,
                        "usage_count": s.usage_count or 0,
                        "language": s.language,
                    }
                    for s in most_used
                ],
                "most_viewed_snippets": [
                    {
                        "id": s.id,
                        "title": s.title,
                        "view_count": s.view_count or 0,
                        "language": s.language,
                    }
                    for s in most_viewed
                ],
            },
            "content_metrics": {
                "avg_snippet_length": round(avg_snippet_length, 2),
                "total_lines_of_code": total_lines_of_code,
                "avg_lines_per_snippet": round(total_lines_of_code / len(snippets), 2),
            },
            "tagging": {
                "total_tags": len(set(all_tags)),
                "popular_tags": popular_tags,
                "avg_tags_per_snippet": round(len(all_tags) / len(snippets), 2),
            },
            "recent_activity": [
                {
                    "id": s.id,
                    "title": s.title,
                    "created_at": s.created_at.isoformat(),
                    "language": s.language,
                }
                for s in recent_snippets
            ],
        }

    def _get_productivity_metrics(
        self, user_id: str, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Calculate productivity and efficiency metrics"""
        from app.models.snippet import Snippet

        snippets = (
            self.db.query(Snippet)
            .filter(and_(Snippet.user_id == user_id, Snippet.created_at >= start_date))
            .all()
        )

        if not snippets:
            return {"message": "Insufficient data for productivity analysis"}

        days_active = len(set(s.created_at.date() for s in snippets))
        total_days = (end_date - start_date).days

        # Calculate various productivity metrics
        snippets_per_active_day = len(snippets) / max(days_active, 1)
        consistency_score = (days_active / max(total_days, 1)) * 100

        # Quality metrics (based on usage and length)
        quality_scores = []
        for snippet in snippets:
            # Simple quality score based on usage, length, and tags
            usage_score = min((snippet.usage_count or 0) * 10, 50)
            length_score = min(len(snippet.content) / 10, 30) if snippet.content else 0
            tag_score = min(len(snippet.tags or []) * 5, 20)
            quality_scores.append(usage_score + length_score + tag_score)

        avg_quality_score = statistics.mean(quality_scores) if quality_scores else 0

        # Streak calculation
        current_streak, longest_streak = self._calculate_activity_streaks(snippets)

        return {
            "efficiency": {
                "snippets_per_day": round(snippets_per_active_day, 2),
                "consistency_score": round(consistency_score, 2),
                "days_active": days_active,
                "activity_percentage": round(
                    (days_active / max(total_days, 1)) * 100, 2
                ),
            },
            "quality": {
                "avg_quality_score": round(avg_quality_score, 2),
                "high_quality_snippets": len([s for s in quality_scores if s >= 70]),
                "improvement_suggestions": self._get_quality_suggestions(snippets),
            },
            "streaks": {
                "current_streak": current_streak,
                "longest_streak": longest_streak,
                "streak_status": "active" if current_streak > 0 else "broken",
            },
        }

    def _get_trending_data(
        self, user_id: str, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Get trending languages, tags, and patterns"""
        from app.models.snippet import Snippet

        snippets = (
            self.db.query(Snippet)
            .filter(and_(Snippet.user_id == user_id, Snippet.created_at >= start_date))
            .all()
        )

        # Language trends
        language_counts = Counter([s.language for s in snippets if s.language])
        trending_languages = language_counts.most_common(5)

        # Tag trends
        all_tags = []
        for snippet in snippets:
            if snippet.tags:
                all_tags.extend(snippet.tags)

        tag_trends = Counter(all_tags).most_common(10)

        # Weekly trends
        weekly_data = self._get_weekly_trends(snippets, start_date, end_date)

        return {
            "languages": {
                "trending": trending_languages,
                "total_languages": len(language_counts),
            },
            "tags": {
                "trending": tag_trends,
                "emerging_tags": self._find_emerging_tags(snippets, start_date),
            },
            "weekly_trends": weekly_data,
            "growth_indicators": self._calculate_growth_indicators(snippets),
        }

    def _get_language_breakdown(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive language usage breakdown"""
        from app.models.snippet import Snippet

        snippets = self.db.query(Snippet).filter(Snippet.user_id == user_id).all()

        language_stats = defaultdict(
            lambda: {
                "count": 0,
                "total_lines": 0,
                "avg_length": 0,
                "usage_count": 0,
                "view_count": 0,
            }
        )

        for snippet in snippets:
            lang = snippet.language or "unknown"
            language_stats[lang]["count"] += 1

            if snippet.content:
                lines = len(snippet.content.splitlines())
                language_stats[lang]["total_lines"] += lines

            language_stats[lang]["usage_count"] += snippet.usage_count or 0
            language_stats[lang]["view_count"] += snippet.view_count or 0

        # Calculate averages and percentages
        total_snippets = len(snippets)
        for lang, stats in language_stats.items():
            stats["percentage"] = round((stats["count"] / total_snippets) * 100, 2)
            stats["avg_lines"] = round(stats["total_lines"] / stats["count"], 2)

        # Sort by count
        sorted_languages = sorted(
            language_stats.items(), key=lambda x: x[1]["count"], reverse=True
        )

        return {
            "breakdown": dict(sorted_languages),
            "total_languages": len(language_stats),
            "most_used": sorted_languages[0][0] if sorted_languages else "None",
            "diversity_score": self._calculate_language_diversity(language_stats),
        }

    def _get_collection_analytics(self, user_id: str) -> Dict[str, Any]:
        """Analyze collection usage and organization"""
        from app.models.collection import Collection
        from app.models.snippet import Snippet

        collections = (
            self.db.query(Collection).filter(Collection.user_id == user_id).all()
        )

        if not collections:
            return {"message": "No collections found"}

        collection_stats = []
        for collection in collections:
            snippet_count = (
                self.db.query(Snippet)
                .filter(Snippet.collection_id == collection.id)
                .count()
            )

            collection_stats.append(
                {
                    "id": collection.id,
                    "name": collection.name,
                    "snippet_count": snippet_count,
                    "created_at": collection.created_at.isoformat(),
                    "is_shared": getattr(collection, "is_shared", False),
                }
            )

        # Sort by snippet count
        collection_stats.sort(key=lambda x: x["snippet_count"], reverse=True)

        # Calculate metrics
        total_snippets_in_collections = sum(
            c["snippet_count"] for c in collection_stats
        )
        total_snippets = (
            self.db.query(Snippet).filter(Snippet.user_id == user_id).count()
        )
        organization_rate = (
            total_snippets_in_collections / max(total_snippets, 1)
        ) * 100

        return {
            "collections": collection_stats,
            "metrics": {
                "total_collections": len(collections),
                "avg_snippets_per_collection": round(
                    total_snippets_in_collections / len(collections), 2
                ),
                "organization_rate": round(organization_rate, 2),
                "largest_collection": collection_stats[0] if collection_stats else None,
            },
        }

    def _generate_user_recommendations(self, user_id: str) -> List[Dict[str, Any]]:
        """Generate personalized recommendations for the user"""
        from app.models.snippet import Snippet
        from app.models.collection import Collection

        recommendations = []

        # Check organization
        total_snippets = (
            self.db.query(Snippet).filter(Snippet.user_id == user_id).count()
        )
        collections_count = (
            self.db.query(Collection).filter(Collection.user_id == user_id).count()
        )

        if total_snippets > 10 and collections_count == 0:
            recommendations.append(
                {
                    "type": "organization",
                    "title": "Create Collections",
                    "description": f"You have {total_snippets} snippets but no collections. Organize them for better management.",
                    "action": "create_collection",
                    "priority": "high",
                }
            )

        # Check tagging
        untagged_snippets = (
            self.db.query(Snippet)
            .filter(
                and_(
                    Snippet.user_id == user_id,
                    or_(Snippet.tags == None, Snippet.tags == []),
                )
            )
            .count()
        )

        if untagged_snippets > total_snippets * 0.5:  # More than 50% untagged
            recommendations.append(
                {
                    "type": "tagging",
                    "title": "Add Tags to Snippets",
                    "description": f"{untagged_snippets} snippets are missing tags. Tags help with organization and search.",
                    "action": "add_tags",
                    "priority": "medium",
                }
            )

        # Check activity
        recent_activity = (
            self.db.query(Snippet)
            .filter(
                and_(
                    Snippet.user_id == user_id,
                    Snippet.created_at >= datetime.utcnow() - timedelta(days=7),
                )
            )
            .count()
        )

        if recent_activity == 0 and total_snippets > 0:
            recommendations.append(
                {
                    "type": "engagement",
                    "title": "Stay Active",
                    "description": "No recent activity detected. Regular snippet creation improves productivity.",
                    "action": "create_snippet",
                    "priority": "low",
                }
            )

        # Check for duplicate detection opportunity
        if total_snippets > 20:
            recommendations.append(
                {
                    "type": "optimization",
                    "title": "Check for Duplicates",
                    "description": "With many snippets, you might have duplicates. Run duplicate detection to clean up.",
                    "action": "run_duplicate_check",
                    "priority": "medium",
                }
            )

        return recommendations

    def _calculate_efficiency_score(
        self, user_id: str, start_date: datetime, end_date: datetime
    ) -> float:
        """Calculate overall user efficiency score (0-100)"""
        from app.models.snippet import Snippet
        from app.models.collection import Collection

        score = 0

        # Activity score (30 points)
        recent_snippets = (
            self.db.query(Snippet)
            .filter(and_(Snippet.user_id == user_id, Snippet.created_at >= start_date))
            .count()
        )

        days = (end_date - start_date).days
        activity_score = min((recent_snippets / max(days, 1)) * 10, 30)
        score += activity_score

        # Organization score (25 points)
        total_snippets = (
            self.db.query(Snippet).filter(Snippet.user_id == user_id).count()
        )
        collections = (
            self.db.query(Collection).filter(Collection.user_id == user_id).count()
        )

        if total_snippets > 0:
            org_ratio = min(
                collections / (total_snippets / 5), 1
            )  # 1 collection per 5 snippets is optimal
            organization_score = org_ratio * 25
            score += organization_score

        # Usage score (25 points)
        total_usage = (
            self.db.query(func.sum(Snippet.usage_count))
            .filter(Snippet.user_id == user_id)
            .scalar()
            or 0
        )

        if total_snippets > 0:
            usage_ratio = min(total_usage / total_snippets, 10) / 10  # Normalize to 0-1
            usage_score = usage_ratio * 25
            score += usage_score

        # Quality score (20 points)
        tagged_snippets = (
            self.db.query(Snippet)
            .filter(
                and_(
                    Snippet.user_id == user_id, Snippet.tags != None, Snippet.tags != []
                )
            )
            .count()
        )

        if total_snippets > 0:
            tagging_ratio = tagged_snippets / total_snippets
            quality_score = tagging_ratio * 20
            score += quality_score

        return min(round(score, 2), 100)

    def _generate_activity_timeline(
        self, snippets: List, start_date: datetime, end_date: datetime
    ) -> List[Dict]:
        """Generate timeline data for activity charts"""
        timeline = []
        current_date = start_date.date()
        end_date_only = end_date.date()

        while current_date <= end_date_only:
            day_snippets = [s for s in snippets if s.created_at.date() == current_date]
            timeline.append(
                {
                    "date": current_date.isoformat(),
                    "count": len(day_snippets),
                    "languages": list(
                        set(s.language for s in day_snippets if s.language)
                    ),
                }
            )
            current_date += timedelta(days=1)

        return timeline

    def _calculate_activity_score(
        self, hourly_activity: Dict, daily_activity: Dict
    ) -> float:
        """Calculate activity consistency score"""
        if not hourly_activity and not daily_activity:
            return 0.0

        # Measure distribution spread (lower is more consistent)
        hourly_values = list(hourly_activity.values())
        daily_values = list(daily_activity.values())

        hourly_std = statistics.stdev(hourly_values) if len(hourly_values) > 1 else 0
        daily_std = statistics.stdev(daily_values) if len(daily_values) > 1 else 0

        # Convert to consistency score (0-100, higher is more consistent)
        max_hourly = max(hourly_values) if hourly_values else 1
        max_daily = max(daily_values) if daily_values else 1

        hourly_consistency = max(0, 100 - (hourly_std / max_hourly * 100))
        daily_consistency = max(0, 100 - (daily_std / max_daily * 100))

        return round((hourly_consistency + daily_consistency) / 2, 2)

    def _calculate_activity_streaks(self, snippets: List) -> Tuple[int, int]:
        """Calculate current and longest activity streaks"""
        if not snippets:
            return 0, 0

        # Group by date
        snippet_dates = sorted(set(s.created_at.date() for s in snippets))

        current_streak = 0
        longest_streak = 0
        temp_streak = 1

        today = datetime.utcnow().date()

        # Calculate longest streak
        for i in range(1, len(snippet_dates)):
            if snippet_dates[i] - snippet_dates[i - 1] == timedelta(days=1):
                temp_streak += 1
            else:
                longest_streak = max(longest_streak, temp_streak)
                temp_streak = 1

        longest_streak = max(longest_streak, temp_streak)

        # Calculate current streak (working backwards from today)
        for i in range(len(snippet_dates) - 1, -1, -1):
            expected_date = today - timedelta(days=current_streak)
            if snippet_dates[i] == expected_date:
                current_streak += 1
            else:
                break

        return current_streak, longest_streak

    def _get_quality_suggestions(self, snippets: List) -> List[str]:
        """Generate quality improvement suggestions"""
        suggestions = []

        untagged_count = len([s for s in snippets if not s.tags])
        if untagged_count > 0:
            suggestions.append(
                f"Add tags to {untagged_count} snippets for better organization"
            )

        short_snippets = len([s for s in snippets if s.content and len(s.content) < 50])
        if short_snippets > len(snippets) * 0.3:
            suggestions.append(
                "Consider adding more detailed descriptions to short snippets"
            )

        unused_snippets = len([s for s in snippets if (s.usage_count or 0) == 0])
        if unused_snippets > 0:
            suggestions.append(
                f"Review {unused_snippets} unused snippets - archive or improve them"
            )

        return suggestions or ["Your snippets are well-maintained!"]

    def _get_weekly_trends(
        self, snippets: List, start_date: datetime, end_date: datetime
    ) -> List[Dict]:
        """Calculate weekly trending data"""
        weeks = []
        current_week_start = start_date

        while current_week_start < end_date:
            week_end = min(current_week_start + timedelta(days=7), end_date)
            week_snippets = [
                s for s in snippets if current_week_start <= s.created_at < week_end
            ]

            weeks.append(
                {
                    "week_start": current_week_start.isoformat(),
                    "week_end": week_end.isoformat(),
                    "snippet_count": len(week_snippets),
                    "languages": Counter(
                        [s.language for s in week_snippets if s.language]
                    ),
                }
            )

            current_week_start = week_end

        return weeks

    def _find_emerging_tags(self, snippets: List, start_date: datetime) -> List[str]:
        """Find tags that are trending upward"""
        recent_snippets = [s for s in snippets if s.created_at >= start_date]
        older_snippets = [s for s in snippets if s.created_at < start_date]

        recent_tags = Counter()
        older_tags = Counter()

        for snippet in recent_snippets:
            if snippet.tags:
                recent_tags.update(snippet.tags)

        for snippet in older_snippets:
            if snippet.tags:
                older_tags.update(snippet.tags)

        # Find tags with increased usage
        emerging = []
        for tag, recent_count in recent_tags.items():
            older_count = older_tags.get(tag, 0)
            if recent_count > older_count * 1.5:  # 50% increase threshold
                emerging.append(tag)

        return emerging[:5]  # Top 5 emerging tags

    def _calculate_growth_indicators(self, snippets: List) -> Dict[str, Any]:
        """Calculate various growth indicators"""
        if len(snippets) < 2:
            return {"message": "Insufficient data for growth analysis"}

        # Sort by creation date
        sorted_snippets = sorted(snippets, key=lambda s: s.created_at)

        # Calculate weekly growth
        first_week = sorted_snippets[0].created_at
        last_week = sorted_snippets[-1].created_at

        total_weeks = max(1, (last_week - first_week).days / 7)
        weekly_growth_rate = len(snippets) / total_weeks

        # Language diversity growth
        languages_over_time = []
        unique_languages = set()

        for snippet in sorted_snippets:
            if snippet.language:
                unique_languages.add(snippet.language)
            languages_over_time.append(len(unique_languages))

        language_growth = len(unique_languages)

        return {
            "weekly_snippet_rate": round(weekly_growth_rate, 2),
            "language_diversity_growth": language_growth,
            "total_growth_period_weeks": round(total_weeks, 1),
            "acceleration": self._calculate_acceleration(sorted_snippets),
        }

    def _calculate_acceleration(self, sorted_snippets: List) -> str:
        """Calculate if snippet creation is accelerating or decelerating"""
        if len(sorted_snippets) < 6:
            return "insufficient_data"

        # Compare first half vs second half
        mid_point = len(sorted_snippets) // 2
        first_half = sorted_snippets[:mid_point]
        second_half = sorted_snippets[mid_point:]

        first_half_days = (
            first_half[-1].created_at - first_half[0].created_at
        ).days or 1
        second_half_days = (
            second_half[-1].created_at - second_half[0].created_at
        ).days or 1

        first_half_rate = len(first_half) / first_half_days
        second_half_rate = len(second_half) / second_half_days

        if second_half_rate > first_half_rate * 1.2:
            return "accelerating"
        elif second_half_rate < first_half_rate * 0.8:
            return "decelerating"
        else:
            return "steady"

    def _calculate_language_diversity(self, language_stats: Dict) -> float:
        """Calculate language diversity score using Shannon diversity index"""
        if not language_stats:
            return 0.0

        total_snippets = sum(stats["count"] for stats in language_stats.values())
        if total_snippets == 0:
            return 0.0

        diversity = 0
        for stats in language_stats.values():
            proportion = stats["count"] / total_snippets
            if proportion > 0:
                diversity -= proportion * (proportion**0.5)  # Simplified Shannon index

        # Normalize to 0-100 scale
        max_diversity = len(language_stats) ** 0.5
        return round((diversity / max_diversity) * 100, 2) if max_diversity > 0 else 0.0

    def get_system_analytics(self) -> Dict[str, Any]:
        """Get system-wide analytics for admin dashboard"""
        from app.models.user import User
        from app.models.snippet import Snippet
        from app.models.collection import Collection

        total_users = self.db.query(User).count()
        total_snippets = self.db.query(Snippet).count()
        total_collections = self.db.query(Collection).count()

        # Active users (created snippet in last 30 days)
        active_users = (
            self.db.query(User)
            .join(Snippet)
            .filter(Snippet.created_at >= datetime.utcnow() - timedelta(days=30))
            .distinct()
            .count()
        )

        # Popular languages
        language_stats = (
            self.db.query(Snippet.language, func.count(Snippet.id))
            .group_by(Snippet.language)
            .order_by(desc(func.count(Snippet.id)))
            .limit(10)
            .all()
        )

        return {
            "overview": {
                "total_users": total_users,
                "total_snippets": total_snippets,
                "total_collections": total_collections,
                "active_users": active_users,
                "activity_rate": round((active_users / max(total_users, 1)) * 100, 2),
            },
            "popular_languages": [
                {"language": lang, "count": count} for lang, count in language_stats
            ],
            "generated_at": datetime.utcnow().isoformat(),
        }
