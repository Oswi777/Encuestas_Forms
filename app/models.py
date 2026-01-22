import secrets
from datetime import datetime
from sqlalchemy import Index
from .extensions import db

class Area(db.Model):
    __tablename__ = 'areas'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Survey(db.Model):
    __tablename__ = 'surveys'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(60), nullable=False, default='GENERAL')
    # JSON schema for the template
    schema_json = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class Campaign(db.Model):
    __tablename__ = 'campaigns'
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(32), unique=True, nullable=False, index=True)
    survey_id = db.Column(db.Integer, db.ForeignKey('surveys.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    # Snapshot of survey schema + metadata at creation time
    snapshot_json = db.Column(db.JSON, nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    start_at = db.Column(db.DateTime)
    end_at = db.Column(db.DateTime)
    require_area = db.Column(db.Boolean, default=True, nullable=False)
    require_shift = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    survey = db.relationship('Survey')

    @staticmethod
    def new_token() -> str:
        return secrets.token_urlsafe(16)[:24]

class Response(db.Model):
    __tablename__ = 'responses'
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=False, index=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    lang = db.Column(db.String(8), default='es', nullable=False)
    area_id = db.Column(db.Integer, db.ForeignKey('areas.id'))
    shift = db.Column(db.String(16))

    wants_followup = db.Column(db.Boolean, default=False, nullable=False)
    contact_name = db.Column(db.String(200))
    employee_no = db.Column(db.String(50))

    # raw answers payload to keep schema flexible
    answers_json = db.Column(db.JSON, nullable=False, default=dict)
    user_agent = db.Column(db.String(300))
    source = db.Column(db.String(20), default='kiosko')  # kiosko|link

    campaign = db.relationship('Campaign')
    area = db.relationship('Area')

Index('ix_responses_campaign_date', Response.campaign_id, Response.submitted_at)
