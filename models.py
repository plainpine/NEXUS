from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    age = db.Column(db.String(20))  # 10～20代, 30～40代, 50代以上
    gender = db.Column(db.String(10))

    # 得意科目 (1:得意, 2:対応可, 3:不得意)
    math = db.Column(db.Integer)
    english = db.Column(db.Integer)
    japanese = db.Column(db.Integer)
    science = db.Column(db.Integer)
    social = db.Column(db.Integer)

    # 希望する生徒の条件 (1:高, 2:中, 3:低)
    pref_gender = db.Column(db.String(10)) # 男, 女, 不問
    pref_mid1_priority = db.Column(db.Integer, default=2)
    pref_mid2_priority = db.Column(db.Integer, default=2)
    pref_mid3_priority = db.Column(db.Integer, default=2)

    attend = db.Column(db.Boolean, default=True)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    grade = db.Column(db.String(20)) # 中1, 中2, 中3
    gender = db.Column(db.String(10))
    
    # 当日行う学習科目
    subject1 = db.Column(db.String(20))
    subject2 = db.Column(db.String(20))

    # 希望する講師の条件 (1:高, 2:中, 3:低)
    pref_gender = db.Column(db.String(10)) # 男, 女, 不問
    pref_age1020_priority = db.Column(db.Integer, default=2)
    pref_age3040_priority = db.Column(db.Integer, default=2)
    pref_age50_priority = db.Column(db.Integer, default=2)

    attend = db.Column(db.Boolean, default=True)

class MatchResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher = db.Column(db.String(50))
    student = db.Column(db.String(50))
