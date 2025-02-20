from flask import Flask, render_template, request, jsonify, send_from_directory, send_file, redirect, url_for, session
from datetime import datetime
import json
import os
import pandas as pd
import io
from functools import wraps

app = Flask(__name__, static_folder='static')
# 안전한 세션을 위한 비밀키 설정 - 실제 운영 시에는 환경변수로 관리하는 것이 좋습니다
app.secret_key = 'your-secret-key-123'  

# 관리자 계정 정보 - 실제 운영 시에는 데이터베이스나 환경변수로 관리하는 것이 좋습니다
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password123"

# 관리자 인증이 필요한 페이지에 적용할 데코레이터
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = '잘못된 계정 정보입니다.'
    
    return render_template('admin_login.html', error=error)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    # 통계 정보 수집
    stats = survey_manager.generate_report()
    return render_template('admin_dashboard.html', stats=stats)

@app.route('/download_excel')
@admin_required
def download_excel():
    """설문 결과를 엑셀 파일로 변환하여 다운로드 (관리자 전용)"""
    try:
        # 기존의 엑셀 다운로드 코드는 그대로 유지...
        
        all_responses_file = f"{RESULTS_DIR}/all_survey_responses.json"
        
        if not os.path.exists(all_responses_file):
            return jsonify({"error": "데이터가 없습니다."}), 404
            
        with open(all_responses_file, 'r', encoding='utf-8') as f:
            responses = json.load(f)
            
        df = pd.DataFrame(responses)
        
        # 타임스탬프로 정렬
        if 'timestamp' in df.columns:
            df = df.sort_values('timestamp')
        
        # 열 이름 한글화 및 정렬
        column_mapping = {
            'timestamp': '응답시간',
            'ethics_평균점수': '윤리의식',
            'character_평균점수': '리더 개인적 특성',
            'leadership_평균점수': '리더십',
            'culture_평균점수': '조직문화',
            'labor_평균점수': '노동조합의 이해',
            '총점': '총점',
            '기타의견': '기타의견'
        }
        
        df = df.rename(columns=column_mapping)
        desired_columns = ['응답시간', '윤리의식', '리더 개인적 특성', '리더십', 
                         '조직문화', '노동조합의 이해', '총점', '기타의견']
        df = df[desired_columns]
        
        score_columns = ['윤리의식', '리더 개인적 특성', '리더십', '조직문화', 
                        '노동조합의 이해', '총점']
        df[score_columns] = df[score_columns].round(2)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='설문결과')
            
            worksheet = writer.sheets['설문결과']
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(str(col))
                )
                worksheet.column_dimensions[chr(65 + idx)].width = max_length + 2
        
        output.seek(0)
        
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'설문조사_결과_{current_time}.xlsx'
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 결과 저장을 위한 디렉토리 설정
RESULTS_DIR = "survey_results"
if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)

class SurveyManager:
    def __init__(self):
        # 설문 문항 구조 정의
        # 각 카테고리별로 2개의 질문이 있는 구조
        self.questions = {
            "윤리의식": [
                "기관장은 업무에 대한 공정성과 공익성을 충분히 갖추고 있다.",
                "기관장은 업무권한에 걸친 정립의식이 몸과 행동에 녹아있다."
            ],
            "리더 개인적 특성": [
                "기관장은 상대방을 무시하거나 비하하지 않고 인격적으로 대우하며 의견을 존중하는 등 바람직한 성품과 인격을 갖추고 있다.",
                "기관장은 직원의 특성 및 애로사항을 파악하여 배려함으로써 직원들이 업무를 잘 수행할 수 있도록 돕고 있다."
            ],
            "리더십": [
                "기관장은 관련법령과 업무위임을 직접하게 하고 있으며, 부하직원의 업무능력 향상을 위해 많은 도움을 준다.",
                "기관장은 정책의 민주적 결정을 존중하고, 부하직원과 소통하며 의사결정 및 업무를 수진하고 있다."
            ],
            "조직문화": [
                "기관장은 부하 직원에게 부당한 요구를 하거나 편의를 제공받지 않는 등 수평적인 조직 문화를 만들어가는 데 모범이 되고 있다.",
                "기관장은 직원들의 일과 가정(개인사생활)이 조화롭게 양립할 수 있도록 배려하고 있다."
            ],
            "노동조합의 이해": [
                "기관장은 노동조합을 인정하고 노사간 갈등 사전 예방 등 수평적인 노사문화를 만들어가는데 모범이 되고 있다.",
                "기관장은 노사상생을 위해 노동조합과 협력 상생관계 유지를 위해 노동조합 활동을 배려하고 있다."
            ]
        }

    def save_response(self, response_data):
        """
        설문 응답을 JSON 파일로 저장하는 메서드
        개별 응답 파일과 통합 응답 파일 모두 관리
        """
        # 응답 시간 기록
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{RESULTS_DIR}/survey_response_{timestamp}.json"
        
        # 응답 데이터에 타임스탬프 추가
        response_data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 개별 응답 저장
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(response_data, f, ensure_ascii=False, indent=4)
        
        # 모든 응답을 포함하는 통합 파일 업데이트
        all_responses_file = f"{RESULTS_DIR}/all_survey_responses.json"
        
        if os.path.exists(all_responses_file):
            with open(all_responses_file, 'r', encoding='utf-8') as f:
                all_responses = json.load(f)
        else:
            all_responses = []
            
        all_responses.append(response_data)
        
        with open(all_responses_file, 'w', encoding='utf-8') as f:
            json.dump(all_responses, f, ensure_ascii=False, indent=4)
        
        return filename

    def generate_report(self):
        """
        전체 설문 결과에 대한 통계 보고서 생성
        평균 점수와 응답 수 등의 기본 통계 제공
        """
        all_responses_file = f"{RESULTS_DIR}/all_survey_responses.json"
        
        if not os.path.exists(all_responses_file):
            return {"message": "아직 설문 응답이 없습니다."}
            
        with open(all_responses_file, 'r', encoding='utf-8') as f:
            responses = json.load(f)
            
        # pandas DataFrame으로 변환하여 통계 처리
        df = pd.DataFrame(responses)
        
        # 기본 통계 계산
        stats = {
            "총 응답 수": len(responses),
            "영역별 평균 점수": {},
            "전체 평균 점수": 0
        }
        
        # 각 영역별 평균 계산
        for category in self.questions.keys():
            category_scores = [r.get(f"{category}_평균점수", 0) for r in responses]
            stats["영역별 평균 점수"][category] = round(sum(category_scores) / len(category_scores), 2)
        
        # 전체 평균 계산
        stats["전체 평균 점수"] = round(sum(stats["영역별 평균 점수"].values()) / len(stats["영역별 평균 점수"]), 2)
        
        return stats

# 설문 관리자 인스턴스 생성
survey_manager = SurveyManager()

@app.route('/favicon.ico')
def favicon():
    """파비콘 제공을 위한 라우트"""
    return send_from_directory(os.path.join(app.root_path, 'static'),
                             'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/')
def index():
    """메인 페이지 렌더링"""
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit_survey():
    """
    설문 응답 제출 처리
    AJAX 요청을 통해 전송된 설문 데이터를 저장
    """
    try:
        response_data = request.json
        filename = survey_manager.save_response(response_data)
        return jsonify({
            "status": "success", 
            "message": "설문이 성공적으로 제출되었습니다.", 
            "file": filename
        })
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500

@app.route('/report')
def get_report():
    """설문 결과 보고서 조회"""
    stats = survey_manager.generate_report()
    return jsonify(stats)

if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0')