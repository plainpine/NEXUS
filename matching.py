import openjij as oj

# 制約用定数
LAMBDA_STUDENT_CONSTRAINT = 500 # 各生徒は1人の講師
LAMBDA_TEACHER_CONSTRAINT = 1000 # 各講師の担当人数均等化

# デフォルト設定値
DEFAULT_CONFIG = {
    "subject_proficiency_weight": 2.0,
    "subject_mismatch_penalty": -40,
    "gender_weight": 5,
    "priority_1_bonus": 20,
    "priority_2_bonus": 10,
    "priority_3_bonus": 5
}

def safe_get_gender_char(gender_str):
    if not gender_str:
        return ""
    return gender_str[0]

def get_subject_proficiency(teacher, sub_name):
    # None、空文字列、「なし」は0点。未知の科目名も同様。
    if not sub_name or sub_name == "なし":
        return 0
        
    attr_name = sub_name_to_attr(sub_name)
    if not attr_name:
        return 0

    # teacher に属性が存在しない場合も0点とする
    prof_val = getattr(teacher, attr_name, None)
    
    # 正常な適性値(1, 2, 3)以外は0点
    if prof_val not in [1, 2, 3]:
        return 0
        
    # 得意:10, 対応可:5, 不得意:0
    prof_map = {1: 10, 2: 5, 3: 0}
    return prof_map.get(prof_val, 0)

def sub_name_to_attr(sub_name):
    mapping = {"数学": "math", "英語": "english", "国語": "japanese", "理科": "science", "社会": "social"}
    return mapping.get(sub_name)

def score(teacher, student, config=None, prohibited_matches=None):
    config = config or DEFAULT_CONFIG
    
    # 0. 禁止マッチングチェック
    if prohibited_matches and (student.id, teacher.id) in prohibited_matches:
        return -1000000 # 十分大きな負の値

    total = 0
    
    # 1. 科目のマッチング
    s1_prof = get_subject_proficiency(teacher, student.subject1)
    s2_prof = get_subject_proficiency(teacher, student.subject2)
    
    # 科目不一致ペナルティ
    mismatch_penalty = float(config.get("subject_mismatch_penalty", DEFAULT_CONFIG["subject_mismatch_penalty"]))
    if student.subject1 and student.subject1 != "なし" and s1_prof == 0:
        total += mismatch_penalty
    if student.subject2 and student.subject2 != "なし" and s2_prof == 0:
        total += mismatch_penalty
        
    proficiency_weight = float(config.get("subject_proficiency_weight", DEFAULT_CONFIG["subject_proficiency_weight"]))
    total += (s1_prof + s2_prof) * proficiency_weight

    # 2. 性別マッチング (講師・生徒双方の希望を重視)
    gender_weight = float(config.get("gender_weight", DEFAULT_CONFIG["gender_weight"]))
    if teacher.pref_gender == "不問" or (teacher.pref_gender and student.gender and teacher.pref_gender == safe_get_gender_char(student.gender)):
        total += gender_weight
    if student.pref_gender == "不問" or (student.pref_gender and teacher.gender and student.pref_gender == safe_get_gender_char(teacher.gender)):
        total += gender_weight
    
    # 3. 優先度マッチング (学年・年齢)
    bonus_map = {
        1: int(config.get("priority_1_bonus", DEFAULT_CONFIG["priority_1_bonus"])),
        2: int(config.get("priority_2_bonus", DEFAULT_CONFIG["priority_2_bonus"])),
        3: int(config.get("priority_3_bonus", DEFAULT_CONFIG["priority_3_bonus"]))
    }
    
    # 学年 (講師の希望)
    p_grade = 2
    if student.grade == "中3":
        p_grade = teacher.pref_mid3_priority or 2
    elif student.grade == "中2":
        p_grade = teacher.pref_mid2_priority or 2
    elif student.grade == "中1":
        p_grade = teacher.pref_mid1_priority or 2
    total += bonus_map.get(p_grade, 10)

    # 年齢 (生徒の希望)
    p_age = 2
    if teacher.age == "ヤング":
        p_age = student.pref_age1020_priority or 2
    elif teacher.age == "アダルト":
        p_age = min(student.pref_age3040_priority or 2, student.pref_age50_priority or 2)
    total += bonus_map.get(p_age, 10)

    return total

def simulated_annealing(teachers, students, config=None, prohibited_matches=None):
    config = config or DEFAULT_CONFIG
    # 1. 堅牢性の向上：空入力時の処理
    if not teachers or not students:
        return [], 0.0

    num_t = len(teachers)
    num_s = len(students)

    # 各講師の担当人数の下限・上限。
    min_teacher_load = num_s // num_t

    # 最終結果は、下限人数に余りを加えた目標人数へ合わせる。
    # これにより、下限・上限の範囲内でも一部の講師に偏ることを防ぐ。
    base_count = num_s // num_t
    remainder = num_s % num_t
    target_counts = [base_count + (1 if j < remainder else 0) for j in range(num_t)]

    # QUBOの構築
    qubo = {}

    def get_idx(s_idx, t_idx):
        return s_idx * num_t + t_idx

    # 1. 目的関数: スコアの最大化 -> -スコアの最小化
    for i in range(num_s):
        for j in range(num_t):
            idx = get_idx(i, j)
            s_val = score(teachers[j], students[i], config, prohibited_matches)
            # 目的関数にマイナスをつける（最小化問題にするため）
            qubo[(idx, idx)] = qubo.get((idx, idx), 0) - s_val

    # 2. 制約1: 各生徒 i は必ず1人の講師を選択する
    for i in range(num_s):
        for j in range(num_t):
            idx_j = get_idx(i, j)
            qubo[(idx_j, idx_j)] = qubo.get((idx_j, idx_j), 0) - LAMBDA_STUDENT_CONSTRAINT
            for k in range(j + 1, num_t):
                idx_k = get_idx(i, k)
                qubo[(idx_j, idx_k)] = qubo.get((idx_j, idx_k), 0) + 2 * LAMBDA_STUDENT_CONSTRAINT

    # 3. 制約2: 各講師 j は target_counts[j] 人を担当する
    for j in range(num_t):
        Cj = target_counts[j]
        for i in range(num_s):
            idx_i = get_idx(i, j)
            qubo[(idx_i, idx_i)] = qubo.get((idx_i, idx_i), 0) + LAMBDA_TEACHER_CONSTRAINT * (1 - 2 * Cj)
            for k in range(i + 1, num_s):
                idx_k = get_idx(k, j)
                qubo[(idx_i, idx_k)] = qubo.get((idx_i, idx_k), 0) + 2 * LAMBDA_TEACHER_CONSTRAINT

    # 4. アルゴリズム改善：複数回サンプリング
    sampler = oj.SASampler()
    num_reads = int(config.get("num_reads", 100))
    response = sampler.sample_qubo(qubo, num_reads=num_reads)
    
    # 最良解を取得
    best_solution = response.first
    sample = best_solution.sample
    energy = best_solution.energy
    
    results = []
    # 各生徒を必ず1人の講師に割り当てるためのロジック
    # 生徒ごとにスコア計算をしておく
    student_teacher_scores = []
    for i in range(num_s):
        scores = [score(teachers[j], students[i], config, prohibited_matches) for j in range(num_t)]
        student_teacher_scores.append(scores)
        
    assigned_teachers = [None] * num_s
    teacher_load = [0] * num_t
    
    # まず各講師の下限人数を確保する。
    # これを後回しにすると、スコアの高い講師に生徒が集中して下限を満たせない。
    for teacher_idx in range(num_t):
        while teacher_load[teacher_idx] < min_teacher_load:
            available_students = [
                i for i in range(num_s)
                if assigned_teachers[i] is None
            ]
            if not available_students:
                raise RuntimeError("講師の担当人数下限を満たせません")
            student_idx = max(
                available_students,
                key=lambda i: student_teacher_scores[i][teacher_idx],
            )
            assigned_teachers[student_idx] = teacher_idx
            teacher_load[teacher_idx] += 1

    # 下限を確保した残りの生徒は、QUBOのサンプルをベースに割り当てる。
    for i in range(num_s):
        if assigned_teachers[i] is not None:
            continue

        potential_assignments = [
            j for j in range(num_t)
            if sample.get(get_idx(i, j), 0) == 1
        ]
        available_assignments = [
            j for j in potential_assignments
            if teacher_load[j] < target_counts[j]
        ]
        if available_assignments:
            best_t_idx = max(available_assignments, key=lambda j: student_teacher_scores[i][j])
            assigned_teachers[i] = best_t_idx
            teacher_load[best_t_idx] += 1
            
    # 未割り当ての生徒は、目標人数に達していない講師のうちスコア最高へ割り当てる。
    for i in range(num_s):
        if assigned_teachers[i] is None:
            available_teachers = [
                j for j in range(num_t)
                if teacher_load[j] < target_counts[j]
            ]
            if not available_teachers:
                raise RuntimeError("講師ごとの目標担当人数内に全生徒を割り当てられません")
            best_t_idx = max(
                available_teachers,
                key=lambda j: student_teacher_scores[i][j],
            )
            assigned_teachers[i] = best_t_idx
            teacher_load[best_t_idx] += 1
            
    # 最終的な結果作成
    for i in range(num_s):
        results.append((teachers[assigned_teachers[i]], students[i]))

    return results, energy
