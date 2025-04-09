from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

# Initialize SQLAlchemy
db = SQLAlchemy()

class User(UserMixin, db.Model):
    """User model for authentication and collaboration."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    documents = db.relationship('Document', backref='owner', lazy=True, foreign_keys='Document.owner_id')
    collaborations = db.relationship('Collaboration', backref='user', lazy=True)
    annotations = db.relationship('Annotation', backref='user', lazy=True)
    chat_messages = db.relationship('ChatMessage', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Document(db.Model):
    """Document model for storing course outlines."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    file_path = db.Column(db.String(512), nullable=True)
    content_text = db.Column(db.Text, nullable=True)
    checklist_text = db.Column(db.Text, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    collaborations = db.relationship('Collaboration', backref='document', lazy=True, cascade='all, delete-orphan')
    annotations = db.relationship('Annotation', backref='document', lazy=True, cascade='all, delete-orphan')
    chat_messages = db.relationship('ChatMessage', backref='document', lazy=True, cascade='all, delete-orphan')
    analysis_result = db.relationship('AnalysisResult', backref='document', lazy=True, uselist=False, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Document {self.title}>'

class Collaboration(db.Model):
    """Collaboration model for managing document sharing."""
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    access_level = db.Column(db.String(20), default='viewer')  # viewer, annotator, editor
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('document_id', 'user_id', name='unique_document_user'),
    )
    
    def __repr__(self):
        return f'<Collaboration {self.user_id} on {self.document_id}>'

class Annotation(db.Model):
    """Annotation model for storing user annotations on documents."""
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    position = db.Column(db.Text, nullable=False)  # JSON string with selection positions
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Annotation {self.id} by {self.user_id}>'

class ChatMessage(db.Model):
    """Chat message model for real-time collaboration."""
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ChatMessage {self.id} by {self.user_id}>'

class AnalysisResult(db.Model):
    """Model for storing document analysis results."""
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False, unique=True)
    results_json = db.Column(db.Text, nullable=False)  # JSON string with analysis results
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<AnalysisResult for document {self.document_id}>'