# 급식 관리 시스템 — 프로젝트 컨텍스트

## 목적
인공지능 대학원 과제. 학교 급식 수령 관리 + AI 데이터 분석 시스템.

## 기술 스택
- **웹 프레임워크**: Streamlit (멀티페이지)
- **DB**: Supabase (PostgreSQL + Auth + RLS)
- **QR**: qrcode (생성), streamlit-qrcode-scanner (스캔)
- **분석**: pandas, plotly, scikit-learn, prophet
- **PDF**: reportlab

## 파일 구조
```
대학원과제/
├── app.py                  # 메인 진입점 (로그인/라우팅)
├── pages/
│   ├── 01_학생관리.py
│   ├── 02_QR생성.py
│   ├── 03_체크인.py
│   ├── 04_대시보드.py
│   └── 05_AI분석.py
├── utils/
│   ├── __init__.py
│   ├── db.py               # Supabase DB 연결 및 쿼리
│   ├── auth.py             # 인증 유틸
│   ├── qr_utils.py         # QR 생성/검증
│   ├── pdf_utils.py        # PDF/학생증 생성
│   └── config.py           # 환경변수 로드
├── assets/                 # 이미지, 로고 등
├── logs/                   # 로그 파일
├── supabase_schema.sql     # DB 스키마 (Supabase에서 실행)
├── sample_students.csv     # 테스트용 학생 50명
├── .env.example            # 환경변수 템플릿
├── .env                    # 실제 환경변수 (gitignore)
├── requirements.txt
└── README.md
```

## Supabase 테이블 구조
- `users`: 교사 계정 (Supabase Auth 연동)
- `students`: 학생 정보 (학번, 이름, 학년, 반, 알레르기)
- `meal_records`: 급식 수령 기록 (student_id, meal_date, checkin_time)
- `menus`: 일별 메뉴 (선택사항)

## 사용자 역할
- **admin**: 급식 담당 선생님 — 전체 기능 접근
- **staff**: 배식 선생님 — 체크인 + 대시보드만

## QR 보안
- 학생증 QR에 학번 직접 노출 금지
- HMAC-SHA256으로 토큰 생성: `hmac(SECRET_KEY, student_id + date_salt)`
- 당일 유효 토큰 (daily rotation)

## 개발 단계
1. ✅ 파일 구조 + Supabase 스키마 + 기본 설정
2. 학생 정보 관리 (CSV 업로드, 수정/삭제, 진급)
3. QR 생성 + PDF 학생증
4. 체크인 기능 (QR 스캔, 중복 방지)
5. 실시간 대시보드
6. AI 분석 (예측, 클러스터링, 이상치)
7. 배포

## 환경변수
- `SUPABASE_URL`: Supabase 프로젝트 URL
- `SUPABASE_ANON_KEY`: anon public key
- `SUPABASE_SERVICE_KEY`: service role key (서버사이드 전용)
- `QR_SECRET_KEY`: QR 토큰 서명용 비밀키

## 주의사항
- `.env`는 절대 커밋 금지
- service key는 클라이언트에 노출 금지
- 모든 DB 작업은 try-except + 한글 에러 메시지
