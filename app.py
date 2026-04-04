from flask import Flask, render_template, request, redirect, url_for, session
from models import db, Teacher, Student, MatchResult
from matching import simulated_annealing

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = "secret"

# 初期化
db.init_app(app)

with app.app_context():
    db.create_all()

# ログイン
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['login'] = True
        return redirect(url_for('teachers'))
    return render_template('login.html')

# 講師一覧
@app.route('/teachers')
def teachers():
    teachers = Teacher.query.all()
    return render_template('teachers.html', teachers=teachers)

# 講師追加
@app.route('/teacher/add', methods=['GET', 'POST'])
def teacher_add():
    if request.method == 'POST':
        # 重複チェック
        if Teacher.query.filter_by(name=request.form['name']).first():
            return "その名前は既に登録されています", 400
            
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
            pref_mid1_priority=int(request.form['pref_mid1_priority']),
            pref_mid2_priority=int(request.form['pref_mid2_priority']),
            pref_mid3_priority=int(request.form['pref_mid3_priority']),
            attend=True
        )
        db.session.add(teacher)
        db.session.commit()
        return redirect(url_for('teachers'))
    return render_template('teacher_edit.html', teacher=None)

# 講師編集
@app.route('/teacher/edit/<int:id>', methods=['GET', 'POST'])
def teacher_edit(id):
    teacher = Teacher.query.get_or_404(id)
    if request.method == 'POST':
        # 自分以外の重複チェック
        existing = Teacher.query.filter_by(name=request.form['name']).first()
        if existing and existing.id != id:
            return "その名前は既に登録されています", 400
            
        teacher.name = request.form['name']
        teacher.age = request.form['age']
        teacher.gender = request.form['gender']
        teacher.math = int(request.form['math'])
        teacher.english = int(request.form['english'])
        teacher.japanese = int(request.form['japanese'])
        teacher.science = int(request.form['science'])
        teacher.social = int(request.form['social'])
        teacher.pref_gender = request.form['pref_gender']
        teacher.pref_mid1_priority = int(request.form['pref_mid1_priority'])
        teacher.pref_mid2_priority = int(request.form['pref_mid2_priority'])
        teacher.pref_mid3_priority = int(request.form['pref_mid3_priority'])
        db.session.commit()
        return redirect(url_for('teachers'))
    return render_template('teacher_edit.html', teacher=teacher)

# 講師の出席一括更新
@app.route('/teacher/attend_update', methods=['POST'])
def teacher_attend_update():
    teachers = Teacher.query.all()
    attend_ids = [int(i) for i in request.form.getlist('attend')]
    for t in teachers:
        t.attend = (t.id in attend_ids)
    db.session.commit()
    return redirect(url_for('teachers'))

# 講師の出席切り替え (個別用)
@app.route('/teacher/toggle/<int:id>')
def teacher_toggle(id):
    teacher = Teacher.query.get(id)
    teacher.attend = not teacher.attend
    db.session.commit()
    return redirect(url_for('teachers'))

# 講師削除
@app.route('/teacher/delete/<int:id>')
def teacher_delete(id):
    teacher = Teacher.query.get(id)
    db.session.delete(teacher)
    db.session.commit()
    return redirect(url_for('teachers'))

# 生徒一覧
@app.route('/students')
def students():
    students = Student.query.all()
    return render_template('students.html', students=students)

# 生徒追加
@app.route('/student/add', methods=['GET', 'POST'])
def student_add():
    if request.method == 'POST':
        # 重複チェック
        if Student.query.filter_by(name=request.form['name']).first():
            return "その名前は既に登録されています", 400

        student = Student(
            name=request.form['name'],
            grade=request.form['grade'],
            gender=request.form['gender'],
            subject1='数学', # 初期値
            subject2='なし', # 初期値
            pref_gender=request.form['pref_gender'],
            pref_age1020_priority=int(request.form['pref_age1020_priority']),
            pref_age3040_priority=int(request.form['pref_age3040_priority']),
            pref_age50_priority=int(request.form['pref_age50_priority']),
            attend=True
        )
        db.session.add(student)
        db.session.commit()
        return redirect(url_for('students'))
    return render_template('student_edit.html', student=None)

# 生徒編集
@app.route('/student/edit/<int:id>', methods=['GET', 'POST'])
def student_edit(id):
    student = Student.query.get_or_404(id)
    if request.method == 'POST':
        # 自分以外の重複チェック
        existing = Student.query.filter_by(name=request.form['name']).first()
        if existing and existing.id != id:
            return "その名前は既に登録されています", 400

        student.name = request.form['name']
        student.grade = request.form['grade']
        student.gender = request.form['gender']
        student.pref_gender = request.form['pref_gender']
        student.pref_age1020_priority = int(request.form['pref_age1020_priority'])
        student.pref_age3040_priority = int(request.form['pref_age3040_priority'])
        student.pref_age50_priority = int(request.form['pref_age50_priority'])
        db.session.commit()
        return redirect(url_for('students'))
    return render_template('student_edit.html', student=student)

# 生徒の出席と学習科目の一括更新
@app.route('/student/list_update', methods=['POST'])
def student_list_update():
    students = Student.query.all()
    attend_ids = [int(i) for i in request.form.getlist('attend')]
    
    for s in students:
        s.attend = (s.id in attend_ids)
        s.subject1 = request.form.get(f'sub1_{s.id}')
        s.subject2 = request.form.get(f'sub2_{s.id}')
    
    db.session.commit()
    return redirect(url_for('students'))

# 生徒の出席切り替え (個別用)
@app.route('/student/toggle/<int:id>')
def student_toggle(id):
    student = Student.query.get(id)
    student.attend = not student.attend
    db.session.commit()
    return redirect(url_for('students'))

# 生徒削除
@app.route('/student/delete/<int:id>')
def student_delete(id):
    student = Student.query.get(id)
    db.session.delete(student)
    db.session.commit()
    return redirect(url_for('students'))

# マッチング
@app.route('/matching')
def matching():
    teachers = Teacher.query.filter_by(attend=True).all()
    students = Student.query.filter_by(attend=True).all()

    results, energy = simulated_annealing(teachers, students)

    session['last_energy'] = energy

    MatchResult.query.delete()

    for t, s in results:
        r = MatchResult(teacher=t.name, student=s.name)
        db.session.add(r)

    db.session.commit()
    return redirect(url_for('result'))

@app.route('/result')
def result():
    sort_by = request.args.get('sort', 'teacher')
    if sort_by == 'student':
        results = MatchResult.query.order_by(MatchResult.student).all()
    else:
        results = MatchResult.query.order_by(MatchResult.teacher).all()
    return render_template('result.html', results=results, sort_by=sort_by)

if __name__ == '__main__':
    app.run(debug=True)
