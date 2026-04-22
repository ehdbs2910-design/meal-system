# 🍱 급식 관리 시스템

학교 급식 수령 관리 + AI 데이터 분석 시스템 (인공지능 대학원 과제)

## 기술 스택
- **웹**: Streamlit (멀티페이지)
- **DB**: Supabase (PostgreSQL + Auth + RLS)
- **QR**: qrcode / streamlit-qrcode-scanner
- **분석**: pandas, plotly, scikit-learn, prophet
- **PDF**: reportlab

---

## 1. Supabase 설정

### 1-1. 프로젝트 생성
1. [supabase.com](https://supabase.com) 접속 → 새 프로젝트 생성
2. **Settings → API** 에서 `URL`, `anon key`, `service role key` 복사

### 1-2. DB 스키마 적용
1. Supabase 대시보드 → **SQL Editor** 열기
2. [`supabase_schema.sql`](supabase_schema.sql) 내용 전체 복사 붙여넣기 후 실행

### 1-3. 관리자 계정 생성
1. Supabase 대시보드 → **Authentication → Users** → `Invite user`로 계정 생성
2. 생성된 User UUID 확인
3. SQL Editor에서 실행:
```sql
INSERT INTO public.users (id, email, name, role)
VALUES ('<User UUID>', 'admin@school.kr', '급식담당교사', 'admin');
```

---

## 2. 로컬 환경 설정

### 2-1. 패키지 설치
```bash
pip install -r requirements.txt
```

### 2-2. 환경변수 설정
```bash
cp .env.example .env
# .env 파일 열어서 실제 값 입력
```

`.env` 파일 예시:
```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...
QR_SECRET_KEY=your-random-secret-key-min-32-chars
SCHOOL_NAME=○○고등학교
```

QR_SECRET_KEY 생성:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 3. 실행

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속

---

## 4. 테스트 데이터 적재

1. 앱 실행 후 관리자 계정으로 로그인
2. **학생 관리** 페이지 → CSV 업로드
3. [`sample_students.csv`](sample_students.csv) 파일 업로드 (50명 샘플)

CSV 형식:
```
student_number,name,grade,class_number,allergies
20240101,홍길동,1,1,1|2
```
- `allergies`: 알레르기 번호를 `|`로 구분 (없으면 빈칸)
- 알레르기 번호: 학교급식법 기준 1~18번

---

## 5. 기능 목록

| 메뉴 | 기능 | 권한 |
|------|------|------|
| 학생 관리 | CSV 업로드, 수정/삭제, 학년 진급 | 관리자 |
| QR 생성 | 학생별 QR, PDF 학생증 출력 | 관리자 |
| 체크인 | QR 스캔, 중복 방지, 알레르기 경고 | 전체 |
| 대시보드 | 실시간 수령 현황, 학년/반별 통계 | 전체 |
| AI 분석 | 패턴 분석, 결식 예측, 클러스터링 | 관리자 |

---

## 6. 보안

- `.env` 파일은 절대 Git 커밋 금지
- QR 토큰: HMAC-SHA256 서명 + 당일만 유효
- Supabase RLS: 인증된 사용자만 데이터 접근
- service role key는 서버사이드에서만 사용

---

## 7. 개발 단계

- [x] 1단계: 파일 구조 + Supabase 스키마 + 기본 설정
- [ ] 2단계: 학생 정보 관리
- [ ] 3단계: QR 생성 + PDF 학생증
- [ ] 4단계: 체크인 기능
- [ ] 5단계: 실시간 대시보드
- [ ] 6단계: AI 분석
- [ ] 7단계: 배포

---

## 8. 로그

`logs/app_YYYY-MM-DD.log` 파일에 자동 저장 (30일 보관)
