"""
WebSocket sync routes for real-time snippet synchronization
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from flask_socketio import emit, join_room, leave_room, disconnect
from app import socketio, db
from app.models.snippet import Snippet
from app.models.collection import Collection
from app.websocket.events import SnippetEvents
from app.websocket.handlers import handle_snippet_save, handle_snippet_update, handle_snippet_delete
import json
import logging
from datetime import datetime, timedelta


sync_bp = Blueprint('sync', __name__, url_prefix='/api/sync')
logger = logging.getLogger(__name__)

# WebSocket event handlers
@socketio.on('connect', namespace='/sync')
def handle_connect():
    """Handle client connection to sync namespace"""
    if current_user.is_authenticated:
        join_room(f'user_{current_user.id}', namespace='/sync')
        emit('connected', {
            'status': 'success',
            'message': 'Connected to sync service',
            'user_id': current_user.id
        }, namespace='/sync')
        logger.info(f'User {current_user.id} connected to sync service')
    else:
        logger.warning('Unauthenticated user attempted to connect to sync service')
        disconnect()

@socketio.on('disconnect', namespace='/sync')
def handle_disconnect():
    """Handle client disconnection"""
    if current_user.is_authenticated:
        leave_room(f'user_{current_user.id}', namespace='/sync')
        logger.info(f'User {current_user.id} disconnected from sync service')

@socketio.on('snippet_save', namespace='/sync')
def handle_snippet_save_event(data):
    """Handle snippet save from extension"""
    if not current_user.is_authenticated:
        emit('error', {'message': 'Authentication required'}, namespace='/sync')
        return
    
    try:
        # Validate required fields
        required_fields = ['code', 'title']
        for field in required_fields:
            if field not in data:
                emit('error', {'message': f'Missing required field: {field}'}, namespace='/sync')
                return
        
        # Create new snippet
        snippet = Snippet(
            user_id=current_user.id,
            title=data['title'],
            code=data['code'],
            language=data.get('language', 'text'),
            source_url=data.get('source_url', ''),
            tags=data.get('tags', []),
            description=data.get('description', '')
        )
        
        db.session.add(snippet)
        db.session.commit()
        
        # Add to collection if specified
        if data.get('collection_id'):
            collection = Collection.query.filter_by(
                id=data['collection_id'],
                user_id=current_user.id
            ).first()
            if collection:
                collection.snippets.append(snippet)
                db.session.commit()
        
        # Emit success response
        snippet_data = {
            'id': snippet.id,
            'title': snippet.title,
            'code': snippet.code,
            'language': snippet.language,
            'source_url': snippet.source_url,
            'tags': snippet.tags,
            'description': snippet.description,
            'created_at': snippet.created_at.isoformat(),
            'updated_at': snippet.updated_at.isoformat()
        }
        
        emit('snippet_saved', {
            'status': 'success',
            'snippet': snippet_data
        }, namespace='/sync')
        
        # Broadcast to all user's connected clients
        emit('snippet_created', {
            'snippet': snippet_data
        }, room=f'user_{current_user.id}', namespace='/sync')
        
        logger.info(f'Snippet {snippet.id} saved for user {current_user.id}')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error saving snippet for user {current_user.id}: {str(e)}')
        emit('error', {
            'message': 'Failed to save snippet',
            'details': str(e)
        }, namespace='/sync')

@socketio.on('snippet_update', namespace='/sync')
def handle_snippet_update_event(data):
    """Handle snippet update from dashboard"""
    if not current_user.is_authenticated:
        emit('error', {'message': 'Authentication required'}, namespace='/sync')
        return
    
    try:
        snippet_id = data.get('id')
        if not snippet_id:
            emit('error', {'message': 'Snippet ID required'}, namespace='/sync')
            return
        
        snippet = Snippet.query.filter_by(
            id=snippet_id,
            user_id=current_user.id
        ).first()
        
        if not snippet:
            emit('error', {'message': 'Snippet not found'}, namespace='/sync')
            return
        
        # Update snippet fields
        updatable_fields = ['title', 'code', 'language', 'tags', 'description']
        for field in updatable_fields:
            if field in data:
                setattr(snippet, field, data[field])
        
        db.session.commit()
        
        # Prepare updated snippet data
        snippet_data = {
            'id': snippet.id,
            'title': snippet.title,
            'code': snippet.code,
            'language': snippet.language,
            'source_url': snippet.source_url,
            'tags': snippet.tags,
            'description': snippet.description,
            'created_at': snippet.created_at.isoformat(),
            'updated_at': snippet.updated_at.isoformat()
        }
        
        # Broadcast update to all user's connected clients
        emit('snippet_updated', {
            'snippet': snippet_data
        }, room=f'user_{current_user.id}', namespace='/sync')
        
        logger.info(f'Snippet {snippet.id} updated for user {current_user.id}')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error updating snippet for user {current_user.id}: {str(e)}')
        emit('error', {
            'message': 'Failed to update snippet',
            'details': str(e)
        }, namespace='/sync')

@socketio.on('snippet_delete', namespace='/sync')
def handle_snippet_delete_event(data):
    """Handle snippet deletion"""
    if not current_user.is_authenticated:
        emit('error', {'message': 'Authentication required'}, namespace='/sync')
        return
    
    try:
        snippet_id = data.get('id')
        if not snippet_id:
            emit('error', {'message': 'Snippet ID required'}, namespace='/sync')
            return
        
        snippet = Snippet.query.filter_by(
            id=snippet_id,
            user_id=current_user.id
        ).first()
        
        if not snippet:
            emit('error', {'message': 'Snippet not found'}, namespace='/sync')
            return
        
        db.session.delete(snippet)
        db.session.commit()
        
        # Broadcast deletion to all user's connected clients
        emit('snippet_deleted', {
            'snippet_id': snippet_id
        }, room=f'user_{current_user.id}', namespace='/sync')
        
        logger.info(f'Snippet {snippet_id} deleted for user {current_user.id}')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting snippet for user {current_user.id}: {str(e)}')
        emit('error', {
            'message': 'Failed to delete snippet',
            'details': str(e)
        }, namespace='/sync')

@socketio.on('sync_request', namespace='/sync')
def handle_sync_request(data):
    """Handle full sync request from extension"""
    if not current_user.is_authenticated:
        emit('error', {'message': 'Authentication required'}, namespace='/sync')
        return
    
    try:
        # Get last sync timestamp if provided
        last_sync = data.get('last_sync')
        
        # Query snippets
        query = Snippet.query.filter_by(user_id=current_user.id)
        if last_sync:
            from datetime import datetime
            last_sync_dt = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
            query = query.filter(Snippet.updated_at > last_sync_dt)
        
        snippets = query.order_by(Snippet.updated_at.desc()).limit(100).all()
        
        # Prepare snippet data
        snippets_data = []
        for snippet in snippets:
            snippets_data.append({
                'id': snippet.id,
                'title': snippet.title,
                'code': snippet.code,
                'language': snippet.language,
                'source_url': snippet.source_url,
                'tags': snippet.tags,
                'description': snippet.description,
                'created_at': snippet.created_at.isoformat(),
                'updated_at': snippet.updated_at.isoformat()
            })
        
        # Get collections
        collections = Collection.query.filter_by(user_id=current_user.id).all()
        collections_data = []
        for collection in collections:
            collections_data.append({
                'id': collection.id,
                'name': collection.name,
                'description': collection.description,
                'created_at': collection.created_at.isoformat(),
                'snippet_count': len(collection.snippets)
            })
        
        emit('sync_response', {
            'status': 'success',
            'snippets': snippets_data,
            'collections': collections_data,
            'sync_timestamp': datetime.utcnow().isoformat()
        }, namespace='/sync')
        
        logger.info(f'Sync completed for user {current_user.id}: {len(snippets_data)} snippets')
        
    except Exception as e:
        logger.error(f'Error during sync for user {current_user.id}: {str(e)}')
        emit('error', {
            'message': 'Sync failed',
            'details': str(e)
        }, namespace='/sync')

# REST API endpoints for sync status
@sync_bp.route('/status', methods=['GET'])
@login_required
def sync_status():
    """Get sync status for current user"""
    try:
        snippet_count = Snippet.query.filter_by(user_id=current_user.id).count()
        collection_count = Collection.query.filter_by(user_id=current_user.id).count()
        
        # Get last updated snippet
        last_snippet = Snippet.query.filter_by(user_id=current_user.id)\
            .order_by(Snippet.updated_at.desc()).first()
        
        last_sync = last_snippet.updated_at.isoformat() if last_snippet else None
        
        return jsonify({
            'status': 'success',
            'data': {
                'snippet_count': snippet_count,
                'collection_count': collection_count,
                'last_sync': last_sync,
                'user_id': current_user.id
            }
        })
    except Exception as e:
        logger.error(f'Error getting sync status for user {current_user.id}: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Failed to get sync status'
        }), 500

@sync_bp.route('/force-sync', methods=['POST'])
@login_required
def force_sync():
    """Force full sync for debugging purposes"""
    try:
        data = {
            'user_id': current_user.id,
            'force': True
        }
        
        # Emit sync request to all connected clients
        socketio.emit('force_sync', data, 
                     room=f'user_{current_user.id}', 
                     namespace='/sync')
        
        return jsonify({
            'status': 'success',
            'message': 'Force sync initiated'
        })
    except Exception as e:
        logger.error(f'Error initiating force sync for user {current_user.id}: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Failed to initiate force sync'
        }), 500

# Health check endpoint
@sync_bp.route('/health', methods=['GET'])
def health_check():
    """Health check for sync service"""
    return jsonify({
        'status': 'healthy',
        'service': 'sync',
        'timestamp': datetime.utcnow().isoformat()
    })


bp = sync_bp