import openjij as oj
import numpy as np

def get_subject_proficiency(teacher, sub_name):
    # 1:得意(10点), 2:対応可(5点), 3:不得意(0点)
    prof_map = {1: 10, 2: 5, 3: 0}
    mapping = {
        "数学": teacher.math,
        "英語": teacher.english,
        "国語": teacher.japanese,
        "理科": teacher.science,
        "社会": teacher.social
    }
    val = mapping.get(sub_name, 3)
    return prof_map.get(val, 0)

def score(teacher, student):
    total = 0
    total += get_subject_proficiency(teacher, student.subject1)
    if student.subject2 != "なし":
        total += get_subject_proficiency(teacher, student.subject2)

    priority_bonus = {1: 20, 2: 10, 3: 5}

    if teacher.pref_gender == "不問" or teacher.pref_gender == student.gender[0]:
        total += 5
    
    grade_priority_map = {
        "中1": teacher.pref_mid1_priority,
        "中2": teacher.pref_mid2_priority,
        "中3": teacher.pref_mid3_priority
    }
    p_grade = grade_priority_map.get(student.grade, 2)
    total += priority_bonus.get(p_grade, 10)

    if student.pref_gender == "不問" or student.pref_gender == teacher.gender[0]:
        total += 5
    
    age_priority_map = {
        "10～20代": student.pref_age1020_priority,
        "30～40代": student.pref_age3040_priority,
        "50代以上": student.pref_age50_priority
    }
    p_age = age_priority_map.get(teacher.age, 2)
    total += priority_bonus.get(p_age, 10)

    return total

def simulated_annealing(teachers, students):
    if not teachers or not students:
        return []

    num_t = len(teachers)
    num_s = len(students)

    # 各講師の理想的な担当人数を計算 (平準化)
    base_count = num_s // num_t
    remainder = num_s % num_t
    target_counts = [base_count + (1 if j < remainder else 0) for j in range(num_t)]

    # QUBOの構築
    # 変数インデックス: student_idx * num_t + teacher_idx
    qubo = {}

    def get_idx(s_idx, t_idx):
        return s_idx * num_t + t_idx

    # パラメータ (制約の強さ)
    # スコアが最大 60点程度なので、制約（ペナルティ）はそれより十分大きく設定
    lambda_1 = 100 # 生徒1人につき講師1人の制約
    lambda_2 = 100 # 講師の担当人数の制約

    # 1. 目的関数: スコアの最大化 -> -スコアの最小化
    for i in range(num_s):
        for j in range(num_t):
            idx = get_idx(i, j)
            s_val = score(teachers[j], students[i])
            qubo[(idx, idx)] = qubo.get((idx, idx), 0) - s_val

    # 2. 制約1: 各生徒 i は必ず1人の講師を選択する (Σ_j x_i,j - 1)^2 = 0
    # 展開: Σ_j x_i,j + 2 Σ_{j<k} x_i,j x_i,k - 2 Σ_j x_i,j + 1
    # バイナリ変数なので x^2 = x
    # -> Σ_j (1-2) x_i,j + 2 Σ_{j<k} x_i,j x_i,k + 1
    # -> - Σ_j x_i,j + 2 Σ_{j<k} x_i,j x_i,k
    for i in range(num_s):
        for j in range(num_t):
            idx_j = get_idx(i, j)
            qubo[(idx_j, idx_j)] = qubo.get((idx_j, idx_j), 0) - lambda_1
            for k in range(j + 1, num_t):
                idx_k = get_idx(i, k)
                qubo[(idx_j, idx_k)] = qubo.get((idx_j, idx_k), 0) + 2 * lambda_1

    # 3. 制約2: 各講師 j は target_counts[j] 人を担当する (Σ_i x_i,j - C_j)^2 = 0
    # 展開: Σ_i x_i,j + 2 Σ_{i<k} x_i,j x_k,j - 2 C_j Σ_i x_i,j + C_j^2
    # -> (1 - 2 C_j) Σ_i x_i,j + 2 Σ_{i<k} x_i,j x_k,j
    for j in range(num_t):
        Cj = target_counts[j]
        for i in range(num_s):
            idx_i = get_idx(i, j)
            qubo[(idx_i, idx_i)] = qubo.get((idx_i, idx_i), 0) + lambda_2 * (1 - 2 * Cj)
            for k in range(i + 1, num_s):
                idx_k = get_idx(k, j)
                qubo[(idx_i, idx_k)] = qubo.get((idx_i, idx_k), 0) + 2 * lambda_2

    # OpenJijで解く
    sampler = oj.SASampler()
    response = sampler.sample_qubo(qubo, num_reads=1)
    
    # 最良解とエネルギーを取得
    best_solution = response.first
    sample = best_solution.sample
    energy = best_solution.energy
    
    results = []
    for i in range(num_s):
        assigned_t_idx = -1
        for j in range(num_t):
            if sample[get_idx(i, j)] == 1:
                assigned_t_idx = j
                break
        
        # 万が一制約が破れて何も割り当てられなかった場合のフォールバック
        if assigned_t_idx == -1:
            scores = [score(teachers[j], students[i]) for j in range(num_t)]
            assigned_t_idx = np.argmax(scores)
            
        results.append((teachers[assigned_t_idx], students[i]))

    return results, energy
