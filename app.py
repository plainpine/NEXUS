from flask import Flask, render_template, request, redirect, url_for, session, abort, flash, jsonify
import json
from functools import wraps
from datetime import datetime
from sqlalchemy import inspect, text
from models import db, Teacher, Student, MatchResult, AdjustedMatch, User, Event, Config, EventAttendance, Organization, Venue, TeacherEvaluation, StudentEvaluation
from matching import simulated_annealing
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = "secret"

# 初期化
db.init_app(app)

with app.app_context():
    inspector = inspect(db.engine)
    if 'match_result' in inspector.get_table_names():
        columns = {column['name'] for column in inspector.get_columns('match_result')}
        missing_columns = {
            'teacher_id': 'ALTER TABLE match_result ADD COLUMN teacher_id INTEGER',
            'student_id': 'ALTER TABLE match_result ADD COLUMN student_id INTEGER',
        }
        for column_name, alter_statement in missing_columns.items():
            if column_name not in columns:
                db.session.execute(text(alter_statement))
        if any(column_name not in columns for column_name in missing_columns):
            db.session.commit()

# ログインチェックデコレータ
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# 組織チェックデコレータ
def organization_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        user = User.query.get(session['user_id'])
        
        # 組織情報を必ずセット
        session['organization_id'] = user.organization_id
        session['org_name'] = user.organization.name
            
        return f(*args, **kwargs)
    return decorated_function

# 管理者チェックデコレータ
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# 講師エクスポート
@app.route('/teachers/export', methods=['GET'])
@login_required
@organization_required
def teachers_export():
    org_id = session['organization_id']
    teachers = Teacher.query.filter_by(organization_id=org_id).all()
    data = [t.to_dict() for t in teachers]
    response = jsonify(data)
    response.headers['Content-Disposition'] = 'attachment; filename=teachers.json'
    return response

# 講師インポート
@app.route('/teachers/import', methods=['POST'])
@login_required
@organization_required
def teachers_import():
    file = request.files['file']
    if not file:
        return "ファイルがありません", 400
    
    data = json.load(file)
    org_id = session['organization_id']
    
    for item in data:
        # 重複チェック: 同じ組織内で氏名が同じならスキップ
        if Teacher.query.filter_by(name=item['name'], organization_id=org_id).first():
            continue
            
        teacher = Teacher(
            name=item['name'],
            age=item.get('age'),
            gender=item.get('gender'),
            math=item.get('math', 3),
            english=item.get('english', 3),
            japanese=item.get('japanese', 3),
            science=item.get('science', 3),
            social=item.get('social', 3),
            subject1=item.get('subject1', 'なし'),
            subject2=item.get('subject2', 'なし'),
            pref_gender=item.get('pref_gender'),
            pref_mid1_priority=item.get('pref_mid1_priority', 2),
            pref_mid2_priority=item.get('pref_mid2_priority', 2),
            pref_mid3_priority=item.get('pref_mid3_priority', 2),
            attend=item.get('attend', False),
            organization_id=org_id
        )
        
        # ユーザ作成
        username = item.get('username')
        if username:
            user = User(username=username, name=item['name'], organization_id=org_id)
            user.set_password("password") # 初期パスワード
            db.session.add(user)
            db.session.flush()
            teacher.user_id = user.id
            
        db.session.add(teacher)
    db.session.commit()
    flash('講師情報をインポートしました')
    return redirect(url_for('teachers'))

# 生徒エクスポート
@app.route('/students/export', methods=['GET'])
@login_required
@organization_required
def students_export():
    org_id = session['organization_id']
    students = Student.query.filter_by(organization_id=org_id).all()
    data = [s.to_dict() for s in students]
    response = jsonify(data)
    response.headers['Content-Disposition'] = 'attachment; filename=students.json'
    return response

# 生徒インポート
@app.route('/students/import', methods=['POST'])
@login_required
@organization_required
def students_import():
    file = request.files['file']
    if not file:
        return "ファイルがありません", 400
    
    data = json.load(file)
    org_id = session['organization_id']
    
    for item in data:
        # 重複チェック: 同じ組織内で氏名が同じならスキップ
        if Student.query.filter_by(name=item['name'], organization_id=org_id).first():
            continue
            
        student = Student(
            name=item['name'],
            grade=item.get('grade'),
            gender=item.get('gender'),
            subject1=item.get('subject1', 'なし'),
            subject2=item.get('subject2', 'なし'),
            pref_gender=item.get('pref_gender'),
            pref_age1020_priority=item.get('pref_age1020_priority', 2),
            pref_age3040_priority=item.get('pref_age3040_priority', 2),
            pref_age50_priority=item.get('pref_age50_priority', 2),
            attend=item.get('attend', False),
            organization_id=org_id
        )
        
        # ユーザ作成
        username = item.get('username')
        if username:
            user = User(username=username, organization_id=org_id)
            user.set_password("password") # 初期パスワード
            db.session.add(user)
            db.session.flush()
            student.user_id = user.id
            
        db.session.add(student)
    db.session.commit()
    flash('生徒情報をインポートしました')
    return redirect(url_for('students'))

# (以下、既存コードはそのまま)...

# ログインチェックデコレータ
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# 組織チェックデコレータ
def organization_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        user = User.query.get(session['user_id'])
        
        # 組織情報を必ずセット
        session['organization_id'] = user.organization_id
        session['org_name'] = user.organization.name
            
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_user():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return dict(current_user=user)

# 管理者チェックデコレータ
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# ログイン
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            session['user_id'] = user.id
            if user.is_admin:
                # 管理者の場合、セッションに組織情報をセット
                if user.organization:
                    session['organization_id'] = user.organization_id
                    session['org_name'] = user.organization.name
                return redirect(url_for('event_select'))
            elif user.student_record:
                return redirect(url_for('student_dashboard'))
            elif user.teacher_record:
                return redirect(url_for('teacher_dashboard'))
            else:
                # どの役割でもない場合、デフォルトの画面へ
                return redirect(url_for('login'))
        return redirect(url_for('login', error="ユーザIDまたはパスワードが正しくありません"))
    return render_template('login.html')

# ログアウト
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

# 組織一覧
@app.route('/organizations')
@admin_required
def organizations():
    if not User.query.get(session['user_id']).is_super_admin:
        abort(403)
    organizations = Organization.query.all()
    return render_template('organizations.html', organizations=organizations)

# 組織追加
@app.route('/organization/add', methods=['POST'])
@admin_required
def org_add():
    if not User.query.get(session['user_id']).is_super_admin:
        abort(403)
    name = request.form['name']
    org = Organization(name=name)
    db.session.add(org)
    db.session.commit()
    return redirect(url_for('organizations'))

# 組織削除
@app.route('/organization/delete/<int:id>')
@admin_required
def org_delete(id):
    if not User.query.get(session['user_id']).is_super_admin:
        abort(403)
    org = Organization.query.get_or_404(id)
    db.session.delete(org)
    db.session.commit()
    return redirect(url_for('organizations'))

# 管理者一覧
@app.route('/users')
@admin_required
def users():
    if not User.query.get(session['user_id']).is_super_admin:
        abort(403)
    # 新規ユーザ作成
    # 全ての管理者は is_admin=True とし、組織管理者かどうかのフラグを別に持たせるべきだが、
    # 今は is_admin を「組織管理者フラグ」として再定義し、
    # 別途「管理者」かどうかを判定するフラグが必要。
    # とりあえず、全ての管理者は is_admin=True とし、is_org_admin を追加する修正は大規模になるため、
    # 既存の is_admin を「組織管理者」フラグとして使い、
    # 管理者一覧には「is_admin=True または is_super_admin=True」のユーザを表示するようにします。
    # 既存のモデル変更を最小限にするため、 is_admin が False でも管理者一覧には表示するようにします。
    
    # ユーザ一覧のロジック修正
    users = User.query.filter(db.or_(User.is_admin==True, User.is_super_admin==True)).all()
    return render_template('users.html', users=users)

# 会場一覧・管理
@app.route('/venues')
@login_required
@organization_required
def venues():
    org_id = session['organization_id']
    if 'org_name' not in session:
        session['org_name'] = Organization.query.get(org_id).name
    venues = Venue.query.filter_by(organization_id=org_id).all()
    return render_template('venues.html', venues=venues)

# 会場保存 (追加・更新)
@app.route('/venue/save', methods=['POST'])
@login_required
@organization_required
def venue_save():
    id = request.form.get('id')
    name = request.form['name']
    org_id = session['organization_id']
    
    if id:
        venue = Venue.query.get_or_404(id)
        if venue.organization_id != org_id:
            abort(403)
        venue.name = name
    else:
        venue = Venue(name=name, organization_id=org_id)
        db.session.add(venue)
    db.session.commit()
    return redirect(url_for('venues'))

# 会場削除
@app.route('/venue/delete/<int:id>')
@login_required
@organization_required
def venue_delete(id):
    venue = Venue.query.get_or_404(id)
    if venue.organization_id != session['organization_id']:
        abort(403)
    db.session.delete(venue)
    db.session.commit()
    return redirect(url_for('venues'))

import re

# ユーザIDのバリデーション関数
def is_valid_username(username):
    return bool(re.match("^[a-zA-Z0-9]+$", username))

# ユーザ追加
@app.route('/user/add', methods=['POST'])
@admin_required
def user_add():
    if not User.query.get(session['user_id']).is_super_admin:
        abort(403)
    username = request.form['username']
    if not is_valid_username(username):
        return "ユーザIDは英数字のみにしてください", 400
        
    user = User.query.filter_by(username=username).first()
    is_org_admin = ('is_org_admin' in request.form)
    if user:
        # 既存ユーザならパスワードと名前を更新
        if request.form.get('password'):
            user.set_password(request.form['password'])
        user.name = request.form['name']
        user.is_admin = True
        user.is_org_admin = is_org_admin
        user.organization_id = request.form['organization_id']
    else:
        # 新規ユーザ作成
        password = request.form['password']
        user = User(username=username, name=request.form['name'], is_admin=True, is_org_admin=is_org_admin, organization_id=request.form['organization_id'])
        user.set_password(password)
        db.session.add(user)
    db.session.commit()
    return redirect(url_for('users'))
# ユーザ編集用 (GET)
@app.route('/user/edit/<int:id>')
@admin_required
def user_edit(id):
    if not User.query.get(session['user_id']).is_super_admin:
        abort(403)
    if id == 0:
        user = None
    else:
        user = User.query.get_or_404(id)
    organizations = Organization.query.all()
    return render_template('user_edit.html', user=user, organizations=organizations)

# ユーザ削除
@app.route('/user/delete/<int:id>')
@admin_required
def user_delete(id):
    if id == session.get('user_id'):
        return "自分自身を削除することはできません", 400
    user = User.query.get_or_404(id)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('users'))

# イベント選択
@app.route('/event/select', methods=['GET', 'POST'])
@login_required
@organization_required
def event_select():
    org_id = session.get('organization_id')
    
    if request.method == 'POST':
        event_id = request.form.get('event_id')
        if event_id:
            event = Event.query.get(event_id)
            if event.organization_id != org_id:
                abort(403)
            session['selected_event_id'] = event.id
            session['selected_event_name'] = event.name
            session['selected_event_date'] = event.date.strftime('%Y-%m-%d')
            session['selected_event_status'] = event.status
        else:
            session.pop('selected_event_id', None)
            session.pop('selected_event_name', None)
            session.pop('selected_event_date', None)
            session.pop('selected_event_status', None)
        return redirect(url_for('event_select'))
    
    events = Event.query.filter_by(organization_id=org_id).order_by(Event.date).all()
    return render_template('event_select.html', events=events)

# 講師一覧
@app.route('/teachers')
@login_required
@organization_required
def teachers():
    org_id = session['organization_id']
    event_id = session.get('selected_event_id')
    event_info = None
    all_teachers = Teacher.query.filter_by(organization_id=org_id).all()
    all_students = Student.query.filter_by(organization_id=org_id).all()
    venues = Venue.query.filter_by(organization_id=org_id).all()
    saved = request.args.get('saved', False)
    
    if event_id:
        event = Event.query.get(event_id)
        if event and event.organization_id == org_id:
            # 講師一覧の公開制限: 公開先が「生徒」の場合は非表示
            if request.endpoint == 'teachers' and event.publish_to == '生徒':
                for t in all_teachers:
                    t.attendance = None
                return render_template('teachers.html', teachers=all_teachers, event_info=None, venues=venues, saved=saved)
            # 生徒一覧の公開制限: 公開先が「講師」の場合は非表示
            if request.endpoint == 'students' and event.publish_to == '講師':
                for s in all_students:
                    s.attendance = None
                return render_template('students.html', students=all_students, event_info=None, venues=venues)

            event_info = {'id': event.id, 'name': event.name, 'date': event.date.strftime('%Y-%m-%d'), 'status': event.status, 'publish_to': event.publish_to}
            attendances = EventAttendance.query.filter_by(event_id=event_id).all()
            
            attendance_map = {a.user_id: a for a in attendances}
            
            # 出欠情報を付与
            for t in all_teachers:
                attendance = attendance_map.get(t.user_id)
                if not attendance and event.status in ['実施前', '実施']:
                    # 未登録の場合、デフォルトで欠席状態のダミーレコードを作成して付与
                    attendance = EventAttendance(event_id=event_id, user_id=t.user_id, attend=False, subject1='欠席', subject2='欠席')
                t.attendance = attendance
                
            return render_template('teachers.html', teachers=all_teachers, event_info=event_info, venues=venues, saved=saved)
    
    # イベント未選択またはイベントが無効な場合、全講師を表示
    for t in all_teachers:
        t.attendance = None
    return render_template('teachers.html', teachers=all_teachers, event_info=None, venues=venues, saved=saved)

# 講師追加
@app.route('/teacher/add', methods=['GET', 'POST'])
@login_required
@organization_required
def teacher_add():
    if request.method == 'POST':
        # 優先度マッピング
        grade_priority = request.form['grade_priority']
        if grade_priority == '中3':
            pref_mid1, pref_mid2, pref_mid3 = 3, 3, 1
        elif grade_priority == '中12':
            pref_mid1, pref_mid2, pref_mid3 = 1, 1, 3
        else: # 不問
            pref_mid1, pref_mid2, pref_mid3 = 2, 2, 2
        
        teacher = Teacher(
            name=request.form['name'],
            age=request.form['age'],
            gender=request.form['gender'],
            math=int(request.form['math']),
            english=int(request.form['english']),
            japanese=int(request.form['japanese']),
            science=int(request.form['science']),
            social=int(request.form['social']),
            pref_gender=request.form['pref_gender'],
            pref_mid1_priority=pref_mid1,
            pref_mid2_priority=pref_mid2,
            pref_mid3_priority=pref_mid3,
            default_venue_id=request.form.get('default_venue_id') or None,
            attend=True,
            organization_id=session['organization_id']
        )
        
        # ユーザ作成
        username = request.form.get('username')
        password = request.form.get('password')
        if username and password:
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                org_name = existing_user.organization.name if existing_user.organization else "不明な組織"
                venues = Venue.query.filter_by(organization_id=session['organization_id']).all()
                return render_template('teacher_edit.html', teacher=None, venues=venues, error=f"そのユーザIDは既に他の組織（{org_name}）で使われています")
            user = User(username=username, name=request.form['name'], organization_id=session['organization_id'])
            user.set_password(password)
            db.session.add(user)
            db.session.flush() # ID生成
            teacher.user_id = user.id
            
        db.session.add(teacher)
        db.session.commit()
        return redirect(url_for('teachers'))
    
    venues = Venue.query.filter_by(organization_id=session['organization_id']).all()
    return render_template('teacher_edit.html', teacher=None, venues=venues)

# ... (teacher_dashboard 等はそのまま)

# 講師編集（プロフィール）
@app.route('/teacher/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def teacher_edit(id):
    teacher = Teacher.query.get_or_404(id)
    current_user = User.query.get(session['user_id'])
    # 管理者チェック: 本人または管理者のみ編集可能
    if not current_user.is_admin and current_user.id != teacher.user_id:
        abort(403)
        
    if request.method == 'POST':
        # 氏名を編集可能に
        teacher.name = request.form['name']
        if teacher.user:
            teacher.user.name = request.form['name']
        teacher.age = request.form['age']
        teacher.gender = request.form['gender']
        teacher.math = int(request.form['math'])
        teacher.english = int(request.form['english'])
        teacher.japanese = int(request.form['japanese'])
        teacher.science = int(request.form['science'])
        teacher.social = int(request.form['social'])
        teacher.pref_gender = request.form['pref_gender']
        
        # 優先度マッピング
        grade_priority = request.form['grade_priority']
        if grade_priority == '中3':
            teacher.pref_mid1_priority = 3
            teacher.pref_mid2_priority = 3
            teacher.pref_mid3_priority = 1
        elif grade_priority == '中12':
            teacher.pref_mid1_priority = 1
            teacher.pref_mid2_priority = 1
            teacher.pref_mid3_priority = 3
        else: # 不問
            teacher.pref_mid1_priority = 2
            teacher.pref_mid2_priority = 2
            teacher.pref_mid3_priority = 2
        
        teacher.default_venue_id = request.form.get('default_venue_id') or None
        
        # ユーザ更新
        username = request.form.get('username')
        password = request.form.get('password')
        if username and current_user.is_admin: # 管理者のみユーザ名変更可
            if teacher.user:
                teacher.user.username = username
        if password:
            teacher.user.set_password(password)
                
        db.session.commit()
        if current_user.is_admin:
            return redirect(url_for('teachers'))
        else:
            return redirect(url_for('teacher_dashboard'))
    
    venues = Venue.query.filter_by(organization_id=session.get('organization_id') or teacher.organization_id).all()
    return render_template('teacher_edit.html', teacher=teacher, venues=venues, is_admin=current_user.is_admin)

# 講師の出席一括更新
@app.route('/teacher/attend_update', methods=['POST'])
@login_required
@organization_required
def teacher_attend_update():
    # ... (existing code, perhaps keeping it for other bulk updates if necessary)
    return redirect(url_for('teachers'))

# 講師の個別出席更新
@app.route('/teacher/attend_save_individual', methods=['POST'])
@login_required
@organization_required
def teacher_attend_save_individual():
    teacher_id = int(request.form.get('teacher_id'))
    event_id = request.form.get('event_id')
    
    teacher = Teacher.query.get(teacher_id)
    is_attend = (request.form.get('attend') == 'true')
    
    if event_id:
        # イベント選択中の場合、EventAttendance を更新
        attendance = EventAttendance.query.filter_by(event_id=int(event_id), user_id=teacher.user_id).first()
        if not attendance:
            attendance = EventAttendance(event_id=int(event_id), user_id=teacher.user_id)
            db.session.add(attendance)
        
        attendance.attend = is_attend
        event = Event.query.get(int(event_id))
        if event.name == '学習会':
            # 会場
            attendance.venue_id = int(request.form.get('venue_id')) if request.form.get('venue_id') else None
            # 前半・後半
            attendance.subject1 = request.form.get('sub1') if is_attend else '欠席'
            attendance.subject2 = request.form.get('sub2') if is_attend else '欠席'
            # 達成度・相性
            if event.status == '実施後':
                attendance.achievement = request.form.get('achievement')
                attendance.compatibility = request.form.get('compatibility')
        else:
            # 学習会以外は会場、前半、後半は不要
            attendance.venue_id = None
            attendance.subject1 = '欠席'
            attendance.subject2 = '欠席'
        attendance.updated_by = 'admin'
    else:
        # イベント未選択の場合は Teacher レコードを更新 (従来通り)
        teacher.attend = is_attend
        teacher.subject1 = request.form.get('sub1') if is_attend else '欠席'
        teacher.subject2 = request.form.get('sub2') if is_attend else '欠席'
            
    db.session.commit()
    flash('出席状況を保存しました')
    return redirect(url_for('teachers'))

# 講師の出席切り替え (個別用)
@app.route('/teacher/toggle/<int:id>')
@login_required
def teacher_toggle(id):
    teacher = Teacher.query.get(id)
    teacher.attend = not teacher.attend
    db.session.commit()
    return redirect(url_for('teachers'))

# 講師削除
@app.route('/teacher/delete/<int:id>')
@login_required
def teacher_delete(id):
    teacher = Teacher.query.get_or_404(id)
    # 関連するユーザも削除
    if teacher.user:
        db.session.delete(teacher.user)
    db.session.delete(teacher)
    db.session.commit()
    return redirect(url_for('teachers'))

# 生徒一覧
@app.route('/students')
@login_required
@organization_required
def students():
    org_id = session['organization_id']
    event_id = session.get('selected_event_id')
    event_info = None
    all_teachers = Teacher.query.filter_by(organization_id=org_id).all()
    all_students = Student.query.filter_by(organization_id=org_id).all()
    venues = Venue.query.filter_by(organization_id=org_id).all()
    saved = request.args.get('saved', False)
    
    if event_id:
        event = Event.query.get(event_id)
        if event and event.organization_id == org_id:
            # 講師一覧の公開制限: 公開先が「生徒」の場合は非表示
            if request.endpoint == 'teachers' and event.publish_to == '生徒':
                for t in all_teachers:
                    t.attendance = None
                return render_template('teachers.html', teachers=all_teachers, event_info=None, venues=venues, saved=saved)
            # 生徒一覧の公開制限: 公開先が「講師」の場合は非表示
            if request.endpoint == 'students' and event.publish_to == '講師':
                for s in all_students:
                    s.attendance = None
                return render_template('students.html', students=all_students, event_info=None, venues=venues)

            event_info = {'id': event.id, 'name': event.name, 'date': event.date.strftime('%Y-%m-%d'), 'status': event.status, 'publish_to': event.publish_to}
            attendances = EventAttendance.query.filter_by(event_id=event_id).all()
            
            attendance_map = {a.user_id: a for a in attendances}
            
            # 出欠情報を付与
            for s in all_students:
                attendance = attendance_map.get(s.user_id)
                if not attendance and event.status in ['実施前', '実施']:
                    # 未登録の場合、デフォルトで「なし」状態のダミーレコードを作成して付与
                    attendance = EventAttendance(event_id=event_id, user_id=s.user_id, attend=False, subject1='なし', subject2='なし')
                s.attendance = attendance
            return render_template('students.html', students=all_students, event_info=event_info, venues=venues)

    # イベント未選択またはイベントが無効な場合、全生徒を表示
    for s in all_students:
        s.attendance = None
    return render_template('students.html', students=all_students, event_info=None, venues=venues)

# 生徒追加
@app.route('/student/add', methods=['GET', 'POST'])
@login_required
@organization_required
def student_add():
    if request.method == 'POST':
        # 重複チェック (組織内)
        if Student.query.filter_by(name=request.form['name'], organization_id=session['organization_id']).first():
            return "その名前は既に登録されています", 400

        # 優先度マッピング
        pref_age_priority = request.form['pref_age_priority']
        if pref_age_priority == 'ヤング':
            pref_age1020, pref_age3040, pref_age50 = 1, 3, 3
        elif pref_age_priority == 'アダルト':
            pref_age1020, pref_age3040, pref_age50 = 3, 3, 1
        else: # 不問
            pref_age1020, pref_age3040, pref_age50 = 2, 2, 2

        student = Student(
            name=request.form['name'],
            grade=request.form['grade'],
            gender=request.form['gender'],
            subject1='数学', # 初期値
            subject2='なし', # 初期値
            pref_gender=request.form['pref_gender'],
            pref_age1020_priority=pref_age1020,
            pref_age3040_priority=pref_age3040,
            pref_age50_priority=pref_age50,
            default_venue_id=request.form.get('default_venue_id') or None,
            attend=True,
            organization_id=session['organization_id']
        )

        # ユーザ作成
        username = request.form.get('username')
        password = request.form.get('password')
        if username and password:
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                org_name = existing_user.organization.name if existing_user.organization else "不明な組織"
                venues = Venue.query.filter_by(organization_id=session['organization_id']).all()
                return render_template('student_edit.html', student=None, venues=venues, error=f"そのユーザIDは既に他の組織（{org_name}）で使われています")
            user = User(username=username, organization_id=session['organization_id'])
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            student.user_id = user.id

        db.session.add(student)
        db.session.commit()
        return redirect(url_for('students'))
    
    venues = Venue.query.filter_by(organization_id=session['organization_id']).all()
    return render_template('student_edit.html', student=None, venues=venues)

# 生徒編集（プロフィール）
@app.route('/student/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def student_edit(id):
    student = Student.query.get_or_404(id)
    # 管理者チェック: 本人または管理者のみ編集可能
    current_user = User.query.get(session['user_id'])
    if not current_user.is_admin and current_user.id != student.user_id:
        abort(403)
        
    if request.method == 'POST':
        # 氏名を編集可能に
        student.name = request.form['name']
        if student.user:
            student.user.name = request.form['name']
        student.grade = request.form['grade']
        student.gender = request.form['gender']
        student.pref_gender = request.form['pref_gender']
        
        # 優先度マッピング
        pref_age_priority = request.form['pref_age_priority']
        if pref_age_priority == 'ヤング':
            student.pref_age1020_priority, student.pref_age3040_priority, student.pref_age50_priority = 1, 3, 3
        elif pref_age_priority == 'アダルト':
            student.pref_age1020_priority, student.pref_age3040_priority, student.pref_age50_priority = 3, 3, 1
        else: # 不問
            student.pref_age1020_priority, student.pref_age3040_priority, student.pref_age50_priority = 2, 2, 2
            
        student.default_venue_id = request.form.get('default_venue_id') or None
        
        # ユーザ更新
        username = request.form.get('username')
        password = request.form.get('password')
        if username and current_user.is_admin: # 管理者のみユーザ名変更可
            if student.user:
                student.user.username = username
        if password:
            student.user.set_password(password)
                
        db.session.commit()
        if current_user.is_admin:
            return redirect(url_for('students'))
        else:
            return redirect(url_for('student_dashboard'))
    
    venues = Venue.query.filter_by(organization_id=session.get('organization_id') or student.organization_id).all()
    return render_template('student_edit.html', student=student, venues=venues, is_admin=current_user.is_admin)

# 生徒の個別出席更新
@app.route('/student/attend_save_individual', methods=['POST'])
@login_required
@organization_required
def student_attend_save_individual():
    student_id = int(request.form.get('student_id'))
    event_id = request.form.get('event_id')
    
    student = Student.query.get(student_id)
    is_attend = (request.form.get('attend') == 'true')
    
    if event_id:
        # イベント選択中の場合、EventAttendance を更新
        attendance = EventAttendance.query.filter_by(event_id=int(event_id), user_id=student.user_id).first()
        if not attendance:
            attendance = EventAttendance(event_id=int(event_id), user_id=student.user_id)
            db.session.add(attendance)
        
        attendance.attend = is_attend
        event = Event.query.get(int(event_id))
        if event.name == '学習会':
            # 会場
            attendance.venue_id = int(request.form.get('venue_id')) if request.form.get('venue_id') else None
            # 前半・後半
            attendance.subject1 = request.form.get('sub1') if is_attend else 'なし'
            attendance.subject2 = request.form.get('sub2') if is_attend else 'なし'
            # 達成度・相性
            if event.status == '実施後':
                attendance.achievement = request.form.get('achievement')
                attendance.compatibility = request.form.get('compatibility')
        else:
            # 学習会以外は会場、前半、後半は不要
            attendance.venue_id = None
            attendance.subject1 = 'なし'
            attendance.subject2 = 'なし'
        attendance.updated_by = 'admin'
    else:
        # イベント未選択の場合は Student レコードを更新 (従来通り)
        student.attend = is_attend
        student.subject1 = request.form.get('sub1') if is_attend else 'なし'
        student.subject2 = request.form.get('sub2') if is_attend else 'なし'
            
    db.session.commit()
    flash('出席状況を保存しました')
    return redirect(url_for('students'))

# 講師ダッシュボード
@app.route('/teacher/dashboard', methods=['GET'])
@login_required
def teacher_dashboard():
    # 講師の所属組織を取得
    user = User.query.get(session['user_id'])
    org_id = user.organization_id
    
    # イベント取得: 公開先が「生徒」のイベントは除外
    events = Event.query.filter(Event.organization_id == org_id, 
                                Event.status.in_(['実施前', '実施']),
                                Event.publish_to.in_(['両方', '講師'])).order_by(Event.date).all()
    
    # 会場取得
    venues = Venue.query.filter_by(organization_id=org_id).all()
    
    # ユーザーの全出席記録を取得（イベントIDをキーにする）
    all_attendances = {a.event_id: a for a in EventAttendance.query.filter_by(user_id=session['user_id']).all()}
    
    return render_template('teacher_dashboard.html', events=events, venues=venues, all_attendances=all_attendances)

# 生徒ダッシュボード
@app.route('/student/dashboard', methods=['GET'])
@login_required
def student_dashboard():
    # 生徒の所属組織を取得
    user = User.query.get(session['user_id'])
    org_id = user.organization_id
    
    # イベント取得: 公開先が「講師」のイベントは除外
    events = Event.query.filter(Event.organization_id == org_id, 
                                Event.status.in_(['実施前', '実施']),
                                Event.publish_to.in_(['両方', '生徒'])).order_by(Event.date).all()
    
    # 会場取得
    venues = Venue.query.filter_by(organization_id=org_id).all()
    
    # ユーザーの全出席記録を取得（イベントIDをキーにする）
    all_attendances = {a.event_id: a for a in EventAttendance.query.filter_by(user_id=session['user_id']).all()}
    
    return render_template('student_dashboard.html', events=events, venues=venues, all_attendances=all_attendances)

# 生徒の出席切り替え (個別用)
@app.route('/student/toggle/<int:id>')
@login_required
def student_toggle(id):
    student = Student.query.get(id)
    student.attend = not student.attend
    db.session.commit()
    return redirect(url_for('students'))

# 生徒削除
@app.route('/student/delete/<int:id>')
@login_required
def student_delete(id):
    student = Student.query.get_or_404(id)
    # 関連するユーザも削除
    if student.user:
        db.session.delete(student.user)
    db.session.delete(student)
    db.session.commit()
    return redirect(url_for('students'))

# イベント削除
@app.route('/event/delete/<int:id>')
@admin_required
def event_delete(id):
    event = Event.query.get_or_404(id)
    # 現在選択中のイベントならセッションから削除
    if session.get('selected_event_id') == event.id:
        session.pop('selected_event_id', None)
        session.pop('selected_event_name', None)
        session.pop('selected_event_date', None)
    
    # 関連する出欠データを削除
    EventAttendance.query.filter_by(event_id=id).delete()
    
    db.session.delete(event)
    db.session.commit()
    return redirect(url_for('events'))

# イベント一覧
@app.route('/events')
@login_required
@organization_required
def events():
    org_id = session['organization_id']
    events = Event.query.filter_by(organization_id=org_id).order_by(Event.date).all()
    configs = {c.key: c.value for c in Config.query.filter_by(organization_id=org_id).all()}
    return render_template('events.html', events=events, configs=configs)

# イベント保存 (追加・更新)
@app.route('/event/save', methods=['POST'])
@login_required
@organization_required
def event_save():
    id = request.form.get('id')
    date_str = request.form.get('date')
    date = datetime.strptime(date_str, '%Y-%m-%d')
    name = request.form.get('event_type')
    if name == 'そのほか':
        name = request.form.get('custom_event_name')

    venue_ids = request.form.getlist('venue_ids') # 複数選択

    teacher_start = request.form.get('teacher_start')
    teacher_end = request.form.get('teacher_end')
    student_start = request.form.get('student_start')
    student_end = request.form.get('student_end')
    publish_to = request.form.get('publish_to')
    status = request.form.get('status')

    # バリデーション: 「実施」状態は1つのみ
    if status == '実施':
        existing_active = Event.query.filter_by(organization_id=session['organization_id'], status='実施').first()
        if existing_active and (str(existing_active.id) != str(id)):
            flash('既に「実施」状態のイベントが存在します', 'error')
            return redirect(url_for('events'))

    if id:
        event = Event.query.get(id)
        if event.organization_id != session['organization_id']:
            abort(403)
        event.date = date
        event.name = name
        event.teacher_start = teacher_start
        event.teacher_end = teacher_end
        event.student_start = student_start
        event.student_end = student_end
        event.publish_to = publish_to
        event.status = status
        # 会場の更新
        event.venues = Venue.query.filter(Venue.id.in_(venue_ids)).all()
    else:
        event = Event(date=date, name=name, 
                      teacher_start=teacher_start, teacher_end=teacher_end,
                      student_start=student_start, student_end=student_end,
                      publish_to=publish_to,
                      status=status,
                      organization_id=session['organization_id'])
        # 会場の追加
        event.venues = Venue.query.filter(Venue.id.in_(venue_ids)).all()
        db.session.add(event)
    db.session.commit()
    flash('イベントを保存しました')
    return redirect(url_for('events'))

# イベント出欠登録
@app.route('/event/attendance/save', methods=['POST'])
@login_required
def event_attendance_save():
    event_id = request.form.get('event_id')
    user_id = session['user_id']
    event = Event.query.get(event_id)
    attend = ('attend' in request.form)
    subject1 = request.form.get('subject1')
    subject2 = request.form.get('subject2')

    # バリデーション
    if event.name == '学習会' and attend:
        user = User.query.get(user_id)
        if user.teacher_record:
            if subject1 == '欠席' and subject2 == '欠席':
                return redirect(url_for('teacher_dashboard', error="出席する場合は、前半または後半の少なくとも一方を「出席」にしてください"))
        elif user.student_record:
            if subject1 == 'なし' and subject2 == 'なし':
                return redirect(url_for('student_dashboard', error="出席する場合は、前半科目または後半科目を選択してください"))

    attendance = EventAttendance.query.filter_by(event_id=event_id, user_id=user_id).first()
    if not attendance:
        attendance = EventAttendance(event_id=event_id, user_id=user_id)
        db.session.add(attendance)

    attendance.attend = attend
    attendance.subject1 = subject1
    attendance.subject2 = subject2
    
    venue_id = request.form.get('venue_id')
    if venue_id:
        attendance.venue_id = int(venue_id)
    else:
        attendance.venue_id = None
        
    attendance.updated_by = 'user'

    db.session.commit()

    flash('出席状況を保存しました')

    user = User.query.get(user_id)
    if user.teacher_record:
        return redirect(url_for('teacher_dashboard'))
    else:
        return redirect(url_for('student_dashboard'))



# マッチング
@app.route('/matching/setup', methods=['GET'])
@login_required
@organization_required
def matching_setup():
    org_id = session.get('organization_id')
    events = Event.query.filter_by(organization_id=org_id, name='学習会').order_by(Event.date).all()
    selected_event = None
    event_id = session.get('selected_event_id')
    if event_id:
        selected_event = Event.query.get(event_id)
    
    teachers = []
    students = []
    if selected_event:
        attendances = EventAttendance.query.filter_by(event_id=selected_event.id).all()
        attendance_map = {a.user_id: a for a in attendances}
        
        all_teachers = Teacher.query.filter_by(organization_id=org_id).all()
        for t in all_teachers:
            t.attendance = attendance_map.get(t.user_id)
            if t.attendance and t.attendance.attend:
                teachers.append(t)
        
        all_students = Student.query.filter_by(organization_id=org_id).all()
        for s in all_students:
            s.attendance = attendance_map.get(s.user_id)
            if s.attendance and s.attendance.attend:
                students.append(s)
    
    return render_template('matching_setup.html', events=events, selected_event=selected_event, teachers=teachers, students=students)

# マッチング設定
@app.route('/matching/config', methods=['GET', 'POST'])
@login_required
@admin_required
def matching_config():
    org_id = session['organization_id']
    if request.method == 'POST':
        for key in request.form.keys():
            value = request.form[key]
            config = Config.query.filter_by(key=key, organization_id=org_id).first()
            if config:
                config.value = value
            else:
                config = Config(key=key, value=value, organization_id=org_id)
                db.session.add(config)
        db.session.commit()
        flash('設定を保存しました')
        return redirect(url_for('matching_config'))
    
    configs = {c.key: c.value for c in Config.query.filter_by(organization_id=org_id).all()}
    return render_template('matching_config.html', configs=configs)

@app.route('/matching/adjustment', methods=['GET'])
@login_required
@admin_required
def matching_adjustment():
    event_id = session.get('selected_event_id')
    if not event_id:
        return redirect(url_for('event_select'))
    
    # 1. 固定表示用: 自動マッチング結果
    fixed_matches = MatchResult.query.filter_by(event_id=event_id).all()
    
    # 2. 調整用: 調整結果 (なければ自動マッチング結果を使用)
    adj_matches = AdjustedMatch.query.filter_by(event_id=event_id).all()
    if not adj_matches:
        adj_matches = fixed_matches

    # 講師IDのセット (どちらかの結果に含まれる講師)
    teacher_ids = set([m.teacher_id for m in fixed_matches] + [m.teacher_id for m in adj_matches])
    teachers = Teacher.query.filter(Teacher.id.in_(teacher_ids)).order_by(Teacher.name).all()
    
    # データ構造の構築
    adj_map = {}
    for t in teachers:
        adj_map[t.id] = {
            'teacher': t,
            'fixed_students': [Student.query.get(m.student_id) for m in fixed_matches if m.teacher_id == t.id],
            'adj_students': [Student.query.get(m.student_id) for m in adj_matches if m.teacher_id == t.id]
        }
        
    return render_template('matching_adjustment.html', adj_map=adj_map, event_id=event_id)

@app.route('/matching/save_adjustment', methods=['POST'])
@login_required
@admin_required
def save_adjustment():
    payload = request.json
    event_id = payload.get('event_id')
    data = payload.get('data')
    
    AdjustedMatch.query.filter_by(event_id=event_id).delete()
    
    for t_id, s_ids in data.items():
        for s_id in s_ids:
            t = Teacher.query.get(t_id)
            s = Student.query.get(s_id)
            adj = AdjustedMatch(
                event_id=event_id,
                venue_id=t.default_venue_id or 1,
                teacher_id=t.id,
                student_id=s.id,
                teacher=t.name,
                student=s.name
            )
            db.session.add(adj)
    db.session.commit()
    return jsonify({"status": "success"})


from flask import send_file
# ... (他のインポート)

import pandas as pd
from io import BytesIO

# ... (既存のコード) ...

# PDF関連 import の削除を確認してください。

@app.route('/matching/export_excel', methods=['GET'])
@login_required
@admin_required
def export_adjustment_excel():
    event_id = session.get('selected_event_id')
    if not event_id:
        return redirect(url_for('event_select'))
    
    event = Event.query.get(event_id)
    filename = f"{event.date.strftime('%Y%m%d')}_組合せ.xlsx"
    
    # 調整結果または自動マッチング結果を取得
    matches = AdjustedMatch.query.filter_by(event_id=event_id).all()
    if not matches:
        matches = MatchResult.query.filter_by(event_id=event_id).all()
    
    # 講師ごとに生徒をグループ化
    # 講師名順でソートするために、まず全講師の情報を取得して並べる
    teacher_map = {m.teacher_id: m.teacher for m in matches}
    
    # 講師IDを講師名順にソート
    sorted_teacher_ids = sorted(teacher_map.keys(), key=lambda tid: teacher_map[tid])
    
    adj_map = {}
    for t_id in sorted_teacher_ids:
        adj_map[t_id] = {'name': teacher_map[t_id], 'students': []}
        
    for m in matches:
        adj_map[m.teacher_id]['students'].append(m.student)
    
    data = []
    for t_id in sorted_teacher_ids:
        data.append({'講師': adj_map[t_id]['name'], '生徒': ", ".join(adj_map[t_id]['students'])})
    
    # Excel生成 (メモリ上)
    df = pd.DataFrame(data)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='組合せ')
        
    buffer.seek(0)
    return send_file(buffer, download_name=filename, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')



# マッチング
@app.route('/matching', methods=['GET', 'POST'])
@login_required
def matching():
    if request.method == 'POST':
        event_id = request.form.get('event_id')
    else:
        # GET の場合はセッションから取得
        event_id = session.get('selected_event_id')

    if not event_id:
        return "イベントが選択されていません", 400
    
    org_id = session.get('organization_id')
    # 設定をDBから取得
    configs = {c.key: c.value for c in Config.query.filter_by(organization_id=org_id).all()}
        
    attendances = EventAttendance.query.filter_by(event_id=event_id, attend=True).all()
    
    # 講師・生徒の絞り込み
    teacher_user_ids = [a.user_id for a in attendances if User.query.get(a.user_id) and User.query.get(a.user_id).teacher_record]
    student_user_ids = [a.user_id for a in attendances if User.query.get(a.user_id) and User.query.get(a.user_id).student_record]
    
    teachers = Teacher.query.filter(Teacher.user_id.in_(teacher_user_ids)).all()
    students = Student.query.filter(Student.user_id.in_(student_user_ids)).all()
    
    # マッチングロジック (設定を渡すように変更)
    results, energy = simulated_annealing(teachers, students, configs)

    session['last_energy'] = energy

    MatchResult.query.filter_by(event_id=event_id).delete()

    attendance_map = {a.user_id: a for a in attendances}

    for t, s in results:
        # 講師または生徒の出席レコードから venue_id を取得
        t_attendance = attendance_map.get(t.user_id)
        s_attendance = attendance_map.get(s.user_id)
        venue_id = None
        if t_attendance and t_attendance.venue_id:
            venue_id = t_attendance.venue_id
        elif s_attendance and s_attendance.venue_id:
            venue_id = s_attendance.venue_id
        elif t.default_venue_id:
            venue_id = t.default_venue_id
        elif s.default_venue_id:
            venue_id = s.default_venue_id
            
        if not venue_id:
            # venue_id が取得できない場合、適当なデフォルト値を使う
            first_venue = Venue.query.filter_by(organization_id=org_id).first()
            if first_venue:
                venue_id = first_venue.id
            else:
                # 会場が一つもない場合はエラーとするかダミーIDを入れる必要があるが、
                # ここではIntegrityErrorを避けるためダミー値として1を設定 (会場IDは1から始まる前提)
                venue_id = 1 

        r = MatchResult(
            event_id=event_id,
            venue_id=venue_id,
            teacher_id=t.id,
            student_id=s.id,
            teacher=t.name,
            student=s.name,
        )
        db.session.add(r)

    db.session.commit()
    flash('マッチングを再実行しました')
    return redirect(url_for('result', event_id=event_id))

@app.route('/result')
@login_required
def result():
    sort_by = request.args.get('sort', 'teacher')
    event_id = request.args.get('event_id', type=int) or session.get('selected_event_id')
    query = MatchResult.query
    if event_id:
        query = query.filter_by(event_id=event_id)
    else:
        # 対象イベントがない場合、過去イベントの結果を誤って表示しない。
        query = query.filter(False)

    if sort_by == 'student':
        results = query.order_by(MatchResult.student, MatchResult.student_id).all()
    else:
        results = query.order_by(MatchResult.teacher, MatchResult.teacher_id).all()
    return render_template('result.html', results=results, sort_by=sort_by)

# 学習会実施ダッシュボード
@app.route('/post_study_session', methods=['GET'])
@login_required
def post_study_session():
    user = User.query.get(session['user_id'])
    org_id = user.organization_id
    
    # 共通のベースクエリ
    query = Event.query.filter(Event.organization_id == org_id, Event.name == '学習会', Event.status == '実施後')
    
    # 生徒の場合は出席しているイベントのみ抽出
    if user.student_record:
        attended_event_ids = [a.event_id for a in EventAttendance.query.filter_by(user_id=user.id, attend=True).all()]
        query = query.filter(Event.id.in_(attended_event_ids))
    
    events = query.order_by(Event.date.desc()).all()
    
    attendances = EventAttendance.query.filter(EventAttendance.user_id == user.id, EventAttendance.event_id.in_([e.id for e in events])).all()
    attendance_map = {a.event_id: a for a in attendances}
    
    return render_template('post_study_session.html', events=events, attendance_map=attendance_map, is_teacher=(user.teacher_record is not None))

# 学習会実施データ保存
@app.route('/post_study_session/save', methods=['POST'])
@login_required
def post_study_session_save():
    event_id = request.form.get('event_id')
    student_id = Student.query.filter_by(user_id=session['user_id']).first().id
    
    # 前半・後半それぞれの評価を保存
    for sub in ['前半', '後半']:
        achievement = request.form.get(f'achievement_{sub}')
        learnability = request.form.get(f'learnability_{sub}')
        
        # 該当する講師IDをTeacherEvaluationから取得
        t_eval = TeacherEvaluation.query.filter_by(event_id=event_id, student_id=student_id, subject_type=sub).first()
        teacher_id = t_eval.teacher_id if t_eval else None
        
        if teacher_id:
            eval = StudentEvaluation.query.filter_by(event_id=event_id, teacher_id=teacher_id, student_id=student_id, subject_type=sub).first()
            if not eval:
                eval = StudentEvaluation(event_id=event_id, teacher_id=teacher_id, student_id=student_id, subject_type=sub)
                db.session.add(eval)
            
            eval.achievement = int(achievement)
            eval.learnability = int(learnability)
            eval.registered_by = 'student' # 生徒による登録
    
    db.session.commit()
    flash('学習会実績を保存しました')
    return redirect(url_for('post_study_session'))

# 設定一覧
@app.route('/settings', methods=['GET', 'POST'])
@login_required
@organization_required
def settings():
    org_id = session['organization_id']
    if request.method == 'POST':
        for key, value in request.form.items():
            config = Config.query.filter_by(key=key, organization_id=org_id).first()
            if config:
                config.value = value
            else:
                config = Config(key=key, value=value, organization_id=org_id)
                db.session.add(config)
        db.session.commit()
        return redirect(url_for('settings', saved=True))
    
    configs = {c.key: c.value for c in Config.query.filter_by(organization_id=org_id).all()}
    saved = request.args.get('saved', False)
    return render_template('settings.html', configs=configs, saved=saved)

# 評価関連
@app.route('/evaluation/teacher', methods=['GET', 'POST'])
@login_required
@admin_required
def evaluation_teacher():
    event_id = session.get('selected_event_id')
    if not event_id:
        return redirect(url_for('event_select'))
    
    # 評価ラベル定義
    achievement_map = {'4': 'とてもよくできた', '3': 'よくできた', '2': 'あまりできなかった', '1': 'できなかった'}
    teachability_map = {'4': 'とても教えやすい', '3': '教えやすい', '2': 'あまり教えやすくない', '1': '教えやすくない'}
    
    # 出席している講師のみ取得
    attendances = EventAttendance.query.filter_by(event_id=event_id, attend=True).all()
    teacher_user_ids = [a.user_id for a in attendances if User.query.get(a.user_id) and User.query.get(a.user_id).teacher_record]
    participating_teachers = Teacher.query.filter(Teacher.user_id.in_(teacher_user_ids)).order_by(Teacher.name).all()
    
    matches = AdjustedMatch.query.filter_by(event_id=event_id).all()
    if not matches:
        matches = MatchResult.query.filter_by(event_id=event_id).all()
        
    if request.method == 'POST':
        for key, value in request.form.items():
            if key.startswith('achievement_') or key.startswith('teachability_'):
                # achievement_studentId_teacherId_sub
                _, student_id, teacher_id, sub = key.split('_')
                
                # 新しい値をPOSTデータから取得 (講師変更に対応)
                selected_teacher_id = int(request.form.get(f'teacher_{student_id}_{sub}'))
                
                eval = TeacherEvaluation.query.filter_by(event_id=event_id, teacher_id=selected_teacher_id, student_id=student_id, subject_type=sub).first()
                if not eval:
                    eval = TeacherEvaluation(event_id=event_id, teacher_id=selected_teacher_id, student_id=student_id, subject_type=sub)
                    db.session.add(eval)
                
                if key.startswith('achievement_'):
                    eval.achievement = int(value)
                else:
                    eval.teachability = int(value)
        db.session.commit()
        flash('評価を保存しました')
        return redirect(url_for('evaluation_teacher'))

    # 生徒単位でデータを集約
    data_map = {}
    for m in matches:
        if m.student_id not in data_map:
            data_map[m.student_id] = {
                'student': Student.query.get(m.student_id),
                'evals': {'前半': None, '後半': None},
                'teachers': {'前半': m.teacher_id, '後半': m.teacher_id} # デフォルト
            }
        
        # 評価取得
        for sub in ['前半', '後半']:
            eval = TeacherEvaluation.query.filter_by(event_id=event_id, teacher_id=m.teacher_id, student_id=m.student_id, subject_type=sub).first()
            if eval:
                data_map[m.student_id]['evals'][sub] = eval
                data_map[m.student_id]['teachers'][sub] = eval.teacher_id

    # ソート用にリスト化
    data = list(data_map.values())
    # 前半担当講師の氏名でソート
    data.sort(key=lambda x: Teacher.query.get(x['teachers']['前半']).name if x['teachers']['前半'] else "")
        
    return render_template('evaluation_teacher.html', data=data, teachers=participating_teachers, 
                           achievement_map=achievement_map, teachability_map=teachability_map)

@app.route('/evaluation/student', methods=['GET', 'POST'])
@login_required
@admin_required
def evaluation_student():
    event_id = session.get('selected_event_id')
    if not event_id:
        return redirect(url_for('event_select'))
    
    # 評価ラベル定義
    achievement_map = {'4': 'とてもよくできた', '3': 'よくできた', '2': 'あまりできなかった', '1': 'できなかった'}
    learnability_map = {'4': 'とても学習しやすい', '3': '学習しやすい', '2': 'あまり学習しやすくない', '1': '学習しやすくない'}
    
    matches = AdjustedMatch.query.filter_by(event_id=event_id).all()
    if not matches:
        matches = MatchResult.query.filter_by(event_id=event_id).all()

    if request.method == 'POST':
        # 個別保存処理
        student_id = int(request.form.get('student_id'))
        
        # 評価保存ロジック
        for sub in ['前半', '後半']:
            # 該当する講師IDをTeacherEvaluationから取得
            t_eval = TeacherEvaluation.query.filter_by(event_id=event_id, student_id=student_id, subject_type=sub).first()
            teacher_id = t_eval.teacher_id if t_eval else None
            
            if teacher_id:
                eval = StudentEvaluation.query.filter_by(event_id=event_id, teacher_id=teacher_id, student_id=student_id, subject_type=sub).first()
                if not eval:
                    eval = StudentEvaluation(event_id=event_id, teacher_id=teacher_id, student_id=student_id, subject_type=sub)
                    db.session.add(eval)
                
                eval.achievement = int(request.form.get(f'achievement_{sub}'))
                eval.learnability = int(request.form.get(f'learnability_{sub}'))
                eval.registered_by = 'admin' # 管理者による保存
        
        db.session.commit()
        flash(f'生徒ID: {student_id} の評価を保存しました')
        return redirect(url_for('evaluation_student'))

    # 生徒単位でデータを集約
    data_map = {}
    for m in matches:
        if m.student_id not in data_map:
            data_map[m.student_id] = {
                'student': Student.query.get(m.student_id),
                'evals': {'前半': None, '後半': None},
                'teachers': {'前半': None, '後半': None},
                'registered_by': None
            }
        
        # 評価と講師を取得
        for sub in ['前半', '後半']:
            t_eval = TeacherEvaluation.query.filter_by(event_id=event_id, student_id=m.student_id, subject_type=sub).first()
            if t_eval:
                data_map[m.student_id]['teachers'][sub] = Teacher.query.get(t_eval.teacher_id)
                eval = StudentEvaluation.query.filter_by(event_id=event_id, teacher_id=t_eval.teacher_id, student_id=m.student_id, subject_type=sub).first()
                data_map[m.student_id]['evals'][sub] = eval
                if eval and eval.registered_by:
                    data_map[m.student_id]['registered_by'] = eval.registered_by
            else:
                # データがない場合はマッチング結果から取得
                data_map[m.student_id]['teachers'][sub] = Teacher.query.get(m.teacher_id)

    # ソート用にリスト化
    data = list(data_map.values())
    # 生徒名順でソート
    data.sort(key=lambda x: x['student'].name)
            
    return render_template('evaluation_student.html', data=data, 
                           achievement_map=achievement_map, learnability_map=learnability_map)

if __name__ == '__main__':
    app.run(debug=True)

