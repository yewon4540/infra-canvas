# Development

새 설치는 [배포 모드 가이드](DEPLOYMENT-MODES.md)를 우선 사용한다. 아래는 기존 직접 실행 개발 구성이다.

## 환경

- Python 3.13 이상
- Node.js 24, pnpm 9.12.0
- Docker Engine/Desktop와 Docker Compose
- 컨테이너의 OpenTofu 버전: 1.12.1

루트 `.env`는 Compose 치환용이고, `apps/web/.env.local`은 웹 개발 서버용입니다. 두 파일은 Git에 포함되지 않습니다. 실제 AWS/LLM 설정 없이 로컬 UI·저장·코드 생성부터 확인할 수 있습니다.

## 시작

```bash
cp .env.example .env
cp apps/web/.env.local.example apps/web/.env.local
```

`POSTGRES_PASSWORD`, `JWT_SECRET`를 서로 다른 임의 값으로 설정합니다. 예제 파일의 빈 값을 그대로 두면 Compose가 실행을 거부합니다. 다른 credential 변수는 필요한 기능을 사용할 때만 설정합니다.

```bash
docker compose -f docker-compose.yml -f docker-compose.override.yml up --build postgres valkey api worker
```

API는 시작 시 `alembic upgrade head`를 실행합니다. 새 환경에서는 Docker volume에 DB와 artifact를 저장합니다. 개발용 override는 API·worker 코드를 bind mount하며, worker 코드 변경 후에는 worker를 재시작해야 합니다.

별도 터미널:

```bash
pnpm install --frozen-lockfile
pnpm --dir apps/web dev
```

- Web: `http://localhost:3000`
- API health: `http://localhost:8000/health`
- API schema: `http://localhost:8000/docs`

회원가입 → Canvas 생성 → 리소스 배치·속성 편집 → HCL 미리보기 순서로 확인합니다. LLM 키가 없으면 AI 피드백 요청은 사용할 수 없습니다. AWS Plan/Apply는 [AWS 연결 설정](AWS-CONNECTION.md)이 필요합니다.

기존 로컬 서비스가 5432, 6379, 8000, 3000 포트를 사용한다면 Compose 포트와 웹 API 주소를 함께 조정합니다. `docker compose down`은 컨테이너를 정지·제거하며, `-v`를 추가하면 저장된 개발 데이터도 삭제됩니다.

이 가이드는 웹을 호스트의 pnpm 개발 서버로 실행합니다. 전체 컨테이너의 Caddy/Nginx 선택과 전환은 [프록시 실행 가이드](REVERSE-PROXY.md)를 참고합니다. TLS, OAuth, Kubernetes 실클러스터 연결, 프로덕션 운영 검증은 이 로컬 확인 범위에 포함하지 않습니다.

## 테스트

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e 'apps/api[dev]'
PYTHONPATH=apps/api:. python -m pytest apps/api/tests
pnpm --dir apps/web exec tsc --noEmit --incremental false
pnpm --dir apps/web build
```

`test_*.py`는 외부 클라이언트·실행 경계를 모의 처리하는 단위 테스트입니다. `integration_async_plan.py`는 DB와 worker가 필요한 별도 수동 통합 도구이므로 기본 pytest 명령에서 실행되지 않습니다.

Backend 수정 시 관련 Python 테스트와 `py_compile`을 실행합니다. Frontend 수정 시 TypeScript 검사와 변경 화면의 브라우저 검증을 수행합니다. Build 성공만으로 화면 배치나 실클러스터 동작을 검증했다고 기록하지 않습니다.

## 코드 구조 원칙

- Page/router는 조립과 입출력 경계에 집중합니다.
- Graph 해석, validation, provider 출력, 외부 실행은 별도 책임으로 둡니다.
- 300줄 이상 파일은 분리를 검토하고, 500줄 이상 파일의 신규 동작은 먼저 분리 계획을 세웁니다.
- 기존 Canvas 상세 page와 router의 규모를 늘리기보다 hook/service를 추출합니다.
- AWS write 권한은 opt-in으로 유지하며, 실제 Apply/Destroy는 명시적으로 승인한 경우에만 수행합니다.
- 인증정보는 실행 중 메모리·환경으로만 전달하고 fixture나 DB에 임시 credential을 저장하지 않습니다.

## 검증 기록

2026-10-06 검증 결과:

- Python 단위 테스트: 58 passed.
- TypeScript: `tsc --noEmit --incremental false` 통과.
- Next.js production build 통과.
- Docker Compose 설정 검사와 API Docker 이미지 build 통과.
- 네트워크를 차단한 API 컨테이너에서 application import 통과.

실계정 AWS 변경, 실클러스터 Kubernetes 명령, 전체 Compose 기동 및 브라우저 UI 검증은 이번 검사에 포함하지 않았습니다.

## 2026-10-23 검증

- 현재 소스 Python 단위 테스트 130개 통과. 새 API 이미지의 의존성 환경에서도 동일하게 통과.
- TypeScript 검사와 Docker Web production build 통과.
- core/standalone/Terrakube/observation 및 기존 프록시 구성 7개 조합의 Compose 해석 확인.
- 격리된 로컬 kind 클러스터에서 6종 리소스, 4개 관계, Target 실제 연결 검증, 빈 namespace,
  namespace 권한 제한과 종류별 RBAC 부분 실패 확인.
- 브라우저에서 조회·검색·관계 이동·이전 관측·잘못된 profile 차단을 확인.
- 실제 운영 Kubernetes와 AWS Apply/Destroy 검증을 뜻하지 않는다. Kubernetes 쓰기 기능은 제공하지 않는다.

## 2026-10-26 verification

- Python: 150 passed; one opt-in PostgreSQL test is skipped in the unit suite.
- The PostgreSQL test passed separately, covering persistence, retention, ownership, execution links and analysis.
- TypeScript and production Web build passed.
- AWS SDK schema/permissions and LLM output/evidence validation use mocks; no live provider was configured.
