import openjij as oj

# 制約用定数
LAMBDA_STUDENT_CONSTRAINT = 500 # 各生徒は1人の講師
LAMBDA_TEACHER_CONSTRAINT = 1000 # 各講師の担当人数均等化

# デフォルト設定値
DEFAULT_CONFIG = {
    "prof_excellent": 10, "prof_good": 5, "prof_poor": 0,
    "subject_mismatch_penalty": -40,
    "gender_match_teacher": 5, "gender_no_pref_teacher": 0, "gender_mismatch_teacher": -5,
    "gender_match_student": 5, "gender_no_pref_student": 0, "gender_mismatch_student": -5,
    "grade_match_teacher": 20, "grade_no_pref_teacher": 10, "grade_mismatch_teacher": 0,
    "age_match_student": 20, "age_no_pref_student": 10, "age_mismatch_student": 0,
    "eval_t_ach_4": 2, "eval_t_ach_3": 1, "eval_t_ach_2": -1, "eval_t_ach_1": -2,
    "weight_eval_t_ach": 1.0,
    "eval_t_tea_4": 2, "eval_t_tea_3": 1, "eval_t_tea_2": -1, "eval_t_tea_1": -2,
    "weight_eval_t_tea": 1.0,
    "eval_s_ach_4": 2, "eval_s_ach_3": 1, "eval_s_ach_2": -1, "eval_s_ach_1": -2,
    "weight_eval_s_ach": 1.0,
    "eval_s_lea_4": 2, "eval_s_lea_3": 1, "eval_s_lea_2": -1, "eval_s_lea_1": -2,
    "weight_eval_s_lea": 1.0
}

def safe_get_gender_char(gender_str):
    if not gender_str:
        return ""
    return gender_str[0]

def get_subject_proficiency(teacher, sub_name, config=None):
    config = config or DEFAULT_CONFIG
    if not sub_name or sub_name == "なし":
        return 0
        
    attr_name = sub_name_to_attr(sub_name)
    if not attr_name:
        return 0

    prof_val = getattr(teacher, attr_name, None)
    if prof_val not in [1, 2, 3]:
        return 0
        
    prof_map = {
        1: int(config.get("prof_excellent", 10)),
        2: int(config.get("prof_good", 5)),
        3: int(config.get("prof_poor", 0))
    }
    return prof_map.get(prof_val, 0)

def sub_name_to_attr(sub_name):
    mapping = {"数学": "math", "英語": "english", "国語": "japanese", "理科": "science", "社会": "social"}
    return mapping.get(sub_name)

def evaluation_rating_to_score(rating):
    """評価1〜4を、悪い評価が負になるスコアへ変換する。"""
    if rating not in [1, 2, 3, 4]:
        return 0.0
    return float(rating) - 2.5

# 禁止マッチング用コスト
PROHIBITED_PENALTY = 1000000

def get_normalized_score(val, min_val, max_val, weight):
    """値を0.0〜1.0に正規化し、重みを掛ける。"""
    range_val = max_val - min_val
    if range_val == 0: return 0
    norm = (val - min_val) / range_val
    return norm * weight

def get_subject_score(teacher, sub_name, config):
    if not sub_name or sub_name == "なし": return 0
    attr_name = sub_name_to_attr(sub_name)
    if not attr_name: return 0
    
    val = getattr(teacher, attr_name, 3) # default: 不得意(3)
    # 設定から得点を取得
    scores = {
        1: int(config.get("prof_excellent", 10)),
        2: int(config.get("prof_good", 5)),
        3: int(config.get("prof_poor", 0))
    }
    
    # 正規化用の範囲
    min_s = min(scores.values())
    max_s = max(scores.values())
    
    return get_normalized_score(scores.get(val, 0), min_s, max_s, float(config.get("weight_subject", 1.0)))

def score(teacher, s1_sub, s2_sub, student_grade, teacher_age, student_pref_age1020_priority, student_pref_age3040_priority, student_pref_age50_priority, teacher_pref_gender, student_pref_gender, teacher_gender, student_gender, config=None, historical_data=None):
    config = config or DEFAULT_CONFIG
    
    # 正規化パラメータの設定
    def get_norm(val, min_v, max_v, weight_key):
        return get_normalized_score(val, min_v, max_v, float(config.get(weight_key, 1.0)))

    details = {}
    
    # 科目
    details['科目1'] = get_subject_score(teacher, s1_sub, config)
    details['科目2'] = get_subject_score(teacher, s2_sub, config)
    
    mismatch_penalty = float(config.get("subject_mismatch_penalty", -40))
    if (s1_sub and s1_sub not in ["なし", "欠席"] and get_subject_proficiency(teacher, s1_sub, config) == 0):
        details['科目1'] += mismatch_penalty / 10
    if (s2_sub and s2_sub not in ["なし", "欠席"] and get_subject_proficiency(teacher, s2_sub, config) == 0):
        details['科目2'] += mismatch_penalty / 10

    # 性別
    def calc_gender(pref, gender, match_k, no_pref_k, mismatch_k, weight_k):
        scores = [int(config.get(match_k, 5)), int(config.get(no_pref_k, 0)), int(config.get(mismatch_k, -5))]
        if pref == "不問": return get_norm(scores[1], min(scores), max(scores), weight_k)
        if pref and gender and pref == safe_get_gender_char(gender): return get_norm(scores[0], min(scores), max(scores), weight_k)
        return get_norm(scores[2], min(scores), max(scores), weight_k)

    details['講師性別'] = calc_gender(teacher.pref_gender, student_gender, "gender_match_teacher", "gender_no_pref_teacher", "gender_mismatch_teacher", "weight_gender_t")
    details['生徒性別'] = calc_gender(student_pref_gender, teacher_gender, "gender_match_student", "gender_no_pref_student", "gender_mismatch_student", "weight_gender_s")

    # 学年評価
    def calc_grade(grade, t_mid1, t_mid2, t_mid3):
        scores = [int(config.get("grade_match_teacher", 20)), int(config.get("grade_no_pref_teacher", 10)), int(config.get("grade_mismatch_teacher", 0))]
        if grade == '中1' and t_mid1 == 3: return get_norm(scores[0], min(scores), max(scores), "weight_grade")
        if grade == '中2' and t_mid2 == 3: return get_norm(scores[0], min(scores), max(scores), "weight_grade")
        if grade == '中3' and t_mid3 == 3: return get_norm(scores[0], min(scores), max(scores), "weight_grade")
        return get_norm(scores[2], min(scores), max(scores), "weight_grade")

    details['学年評価'] = calc_grade(student_grade, teacher.pref_mid1_priority, teacher.pref_mid2_priority, teacher.pref_mid3_priority)

    # 年齢評価
    def calc_age(pref_1020, pref_3040, pref_50, age):
        scores = [int(config.get("age_match_student", 20)), int(config.get("age_no_pref_student", 10)), int(config.get("age_mismatch_student", 0))]
        try: age_int = int(age)
        except: age_int = 30
        age_cat = '1020' if age_int < 30 else ('3040' if age_int < 50 else '50')
        priority = (pref_1020 if age_cat == '1020' else (pref_3040 if age_cat == '3040' else pref_50))
        
        if priority == 3: return get_norm(scores[0], min(scores), max(scores), "weight_age")
        if priority == 2: return get_norm(scores[1], min(scores), max(scores), "weight_age")
        return get_norm(scores[2], min(scores), max(scores), "weight_age")

    details['年齢評価'] = calc_age(student_pref_age1020_priority, student_pref_age3040_priority, student_pref_age50_priority, teacher_age)

    # 実績評価
    details['実績t_ach'] = get_norm(0, -2, 2, 'weight_eval_t_ach')
    details['実績t_tea'] = get_norm(0, -2, 2, 'weight_eval_t_tea')
    details['実績s_ach'] = get_norm(0, -2, 2, 'weight_eval_s_ach')
    details['実績s_lea'] = get_norm(0, -2, 2, 'weight_eval_s_lea')
    if historical_data:
        details['実績t_ach'] = get_norm(historical_data.get('t_ach', 0), -2, 2, 'weight_eval_t_ach')
        details['実績t_tea'] = get_norm(historical_data.get('t_tea', 0), -2, 2, 'weight_eval_t_tea')
        details['実績s_ach'] = get_norm(historical_data.get('s_ach', 0), -2, 2, 'weight_eval_s_ach')
        details['実績s_lea'] = get_norm(historical_data.get('s_lea', 0), -2, 2, 'weight_eval_s_lea')

    total = sum(details.values())
    return total, details

def simulated_annealing(teachers, students, attendances, config=None, prohibited_matches=None, evaluation_map=None):
    config = config or DEFAULT_CONFIG
    if not teachers or not students:
        return [], 0.0

    num_t = len(teachers)
    num_s = len(students)
    
    # attendanceのマップを作成
    att_map = {a.user_id: a for a in attendances}

    # 各講師の担当人数
    base_count = num_s // num_t
    remainder = num_s % num_t
    target_counts = [base_count + (1 if j < remainder else 0) for j in range(num_t)]

    qubo = {}
    def get_idx(s_idx, t_idx):
        return s_idx * num_t + t_idx

    # スコア計算補助関数
    def get_pair_score(t, s):
        att = att_map.get(s.user_id)
        if not att: return 0
        total, _ = score(t, att.subject1, att.subject2, s.grade, t.age, 
                     s.pref_age1020_priority, s.pref_age3040_priority, s.pref_age50_priority,
                     t.pref_gender, s.pref_gender, t.gender, s.gender, config, 
                     historical_data=(evaluation_map or {}).get((s.id, t.id)))
        return total

    # 1. 目的関数
    for i in range(num_s):
        for j in range(num_t):
            idx = get_idx(i, j)
            if prohibited_matches and (students[i].id, teachers[j].id) in prohibited_matches:
                qubo[(idx, idx)] = qubo.get((idx, idx), 0) + PROHIBITED_PENALTY
            else:
                s_val = get_pair_score(teachers[j], students[i])
                qubo[(idx, idx)] = qubo.get((idx, idx), 0) - s_val

    # 2. 制約1 (各生徒1講師)
    for i in range(num_s):
        for j in range(num_t):
            idx_j = get_idx(i, j)
            qubo[(idx_j, idx_j)] = qubo.get((idx_j, idx_j), 0) - LAMBDA_STUDENT_CONSTRAINT
            for k in range(j + 1, num_t):
                idx_k = get_idx(i, k)
                qubo[(idx_j, idx_k)] = qubo.get((idx_j, idx_k), 0) + 2 * LAMBDA_STUDENT_CONSTRAINT

    # 3. 制約2 (各講師担当人数)
    for j in range(num_t):
        Cj = target_counts[j]
        for i in range(num_s):
            idx_i = get_idx(i, j)
            qubo[(idx_i, idx_i)] = qubo.get((idx_i, idx_i), 0) + LAMBDA_TEACHER_CONSTRAINT * (1 - 2 * Cj)
            for k in range(i + 1, num_s):
                idx_k = get_idx(k, j)
                qubo[(idx_i, idx_k)] = qubo.get((idx_i, idx_k), 0) + 2 * LAMBDA_TEACHER_CONSTRAINT

    sampler = oj.SASampler()
    response = sampler.sample_qubo(qubo, num_reads=int(config.get("num_reads", 100)))
    best_solution = response.first
    sample = best_solution.sample
    
    assigned_teachers = [None] * num_s
    teacher_load = [0] * num_t
    
    # 簡易的な割り当て補修
    for i in range(num_s):
        for j in range(num_t):
            if sample.get(get_idx(i, j), 0) == 1 and teacher_load[j] < target_counts[j]:
                assigned_teachers[i] = j
                teacher_load[j] += 1
                break
    
    # 未割り当てを補填
    for i in range(num_s):
        if assigned_teachers[i] is None:
            for j in range(num_t):
                if teacher_load[j] < target_counts[j]:
                    assigned_teachers[i] = j
                    teacher_load[j] += 1
                    break
    
    results = [(teachers[assigned_teachers[i]], students[i]) for i in range(num_s) if assigned_teachers[i] is not None]
    return results, best_solution.energy


