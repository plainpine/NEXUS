from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# 組織
class Organization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

# 会場
class Venue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    organization = db.relationship('Organization', backref='venues')

# イベントと会場の中間テーブル
event_venue = db.Table('event_venue',
    db.Column('event_id', db.Integer, db.ForeignKey('event.id'), primary_key=True),
    db.Column('venue_id', db.Integer, db.ForeignKey('venue.id'), primary_key=True)
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(50), nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_super_admin = db.Column(db.Boolean, default=False)
    is_org_admin = db.Column(db.Boolean, default=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)
    organization = db.relationship('Organization', backref='users')

    teacher_record = db.relationship('Teacher', back_populates='user', uselist=False)
    student_record = db.relationship('Student', back_populates='user', uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user = db.relationship('User', back_populates='teacher_record')
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    organization = db.relationship('Organization')
    default_venue_id = db.Column(db.Integer, db.ForeignKey('venue.id'), nullable=True)
    default_venue = db.relationship('Venue')
    name = db.Column(db.String(50), nullable=False)
    age = db.Column(db.String(20))
    gender = db.Column(db.String(10))
    math = db.Column(db.Integer)
    english = db.Column(db.Integer)
    japanese = db.Column(db.Integer)
    science = db.Column(db.Integer)
    social = db.Column(db.Integer)
    subject1 = db.Column(db.String(20), default='なし')
    subject2 = db.Column(db.String(20), default='なし')
    pref_gender = db.Column(db.String(10))
    pref_mid1_priority = db.Column(db.Integer, default=2)
    pref_mid2_priority = db.Column(db.Integer, default=2)
    pref_mid3_priority = db.Column(db.Integer, default=2)
    attend = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            "name": self.name,
            "username": self.user.username if self.user else None,
            "age": self.age,
            "gender": self.gender,
            "math": self.math,
            "english": self.english,
            "japanese": self.japanese,
            "science": self.science,
            "social": self.social,
            "pref_gender": self.pref_gender,
            "pref_mid1_priority": self.pref_mid1_priority,
            "pref_mid2_priority": self.pref_mid2_priority,
            "pref_mid3_priority": self.pref_mid3_priority,
            "attend": self.attend
        }

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    user = db.relationship('User', back_populates='student_record')
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    organization = db.relationship('Organization')
    default_venue_id = db.Column(db.Integer, db.ForeignKey('venue.id'), nullable=True)
    default_venue = db.relationship('Venue')
    name = db.Column(db.String(50), nullable=False)
    grade = db.Column(db.String(20))
    gender = db.Column(db.String(10))
    subject1 = db.Column(db.String(20))
    subject2 = db.Column(db.String(20))
    pref_gender = db.Column(db.String(10))
    pref_age1020_priority = db.Column(db.Integer, default=2)
    pref_age3040_priority = db.Column(db.Integer, default=2)
    pref_age50_priority = db.Column(db.Integer, default=2)
    attend = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            "name": self.name,
            "username": self.user.username if self.user else None,
            "grade": self.grade,
            "gender": self.gender,
            "pref_gender": self.pref_gender,
            "pref_age1020_priority": self.pref_age1020_priority,
            "pref_age3040_priority": self.pref_age3040_priority,
            "pref_age50_priority": self.pref_age50_priority,
            "attend": self.attend
        }

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    organization = db.relationship('Organization')
    venues = db.relationship('Venue', secondary=event_venue, backref='events')
    teacher_start = db.Column(db.String(5), nullable=False)
    teacher_end = db.Column(db.String(5), nullable=False)
    student_start = db.Column(db.String(5), nullable=False)
    student_end = db.Column(db.String(5), nullable=False)
    publish_to = db.Column(db.String(20), default='両方')
    status = db.Column(db.String(20), default='公開前')

class Config(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(255), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), primary_key=True)

class EventAttendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    venue_id = db.Column(db.Integer, db.ForeignKey('venue.id'), nullable=True) # マッチング時に必要
    attend = db.Column(db.Boolean, default=False)
    subject1 = db.Column(db.String(20))
    subject2 = db.Column(db.String(20))
    achievement = db.Column(db.Integer) # 1-4
    compatibility = db.Column(db.Integer) # 1-4
    updated_by = db.Column(db.String(10)) # 'user' or 'admin'

class MatchResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    venue_id = db.Column(db.Integer, db.ForeignKey('venue.id'), nullable=False)
    # 同名講師を区別するため、講師IDも保存する。
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=True)
    # 同名生徒を区別するため、生徒IDも保存する。
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=True)
    teacher = db.Column(db.String(50))
    student = db.Column(db.String(50))

class AdjustedMatch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    venue_id = db.Column(db.Integer, db.ForeignKey('venue.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    teacher = db.Column(db.String(50))
    student = db.Column(db.String(50))
