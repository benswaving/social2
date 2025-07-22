from flask import Blueprint, request, jsonify
from src.services.auth_service import token_required
from src.models.project import Project
from src.models.generated_content import GeneratedContent
from src.services.celery_service import generate_content_task
from src.models.user import db

content_bp = Blueprint('content', __name__)

@content_bp.route('/generate', methods=['POST'])
@token_required
def generate_content(current_user):
    data = request.get_json()
    project_id = data.get('project_id')
    project = Project.query.filter_by(id=project_id, user_id=current_user.id).first()

    if not project:
        return jsonify({'message': 'Project not found'}), 404

    task = generate_content_task.delay(project.id)

    return jsonify({'message': 'Content generation started', 'task_id': task.id}), 202

@content_bp.route('/projects/<project_id>/content', methods=['GET'])
@token_required
def get_project_content(current_user, project_id):
    project = Project.query.filter_by(id=project_id, user_id=current_user.id).first()

    if not project:
        return jsonify({'message': 'Project not found'}), 404

    contents = GeneratedContent.query.filter_by(project_id=project.id).order_by(GeneratedContent.created_at.desc()).all()
    
    # Always return a valid JSON response
    if not contents:
        return jsonify([]), 200

    return jsonify([c.to_dict() for c in contents]), 200

@content_bp.route('/projects', methods=['POST'])
@token_required
def create_project(current_user):
    data = request.get_json()
    new_project = Project(user_id=current_user.id, name=data.get('name'))
    db.session.add(new_project)
    db.session.commit()
    return jsonify(new_project.to_dict()), 201

@content_bp.route('/projects', methods=['GET'])
@token_required
def get_projects(current_user):
    projects = Project.query.filter_by(user_id=current_user.id).all()
    return jsonify([p.to_dict() for p in projects])
