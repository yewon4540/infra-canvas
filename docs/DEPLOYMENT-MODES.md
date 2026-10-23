# 배포 모드와 Terrakube 연결

기본 설치는 조회·설계용 web/api/postgres와 선택적 Caddy로 구성한다. 직접 실행은
standalone overlay로, 외부 Terrakube 연결은 terrakube overlay로 선택한다.

| 조합 | 서비스/용도 |
| --- | --- |
| `compose.yml` + `compose.proxy.yml` | web, api, postgres, caddy |
| 위 조합 + `compose.observation.yml` | Kubernetes 읽기 전용 profile mount 추가 |
| 기본 + `compose.standalone.yml` + proxy | valkey, 실행 worker, OpenTofu 추가 |
| 기본 + `compose.terrakube.yml` + proxy | 외부 Terrakube API 연결, 실행 worker 없음 |
| 조합 마지막에 `compose.external-db.yml` | 내장 postgres 제외, 외부 DATABASE_URL 사용 |

## 첫 실행

```sh
cp .env.compose.example .env.compose.local
chmod 600 .env.compose.local
```

JWT_SECRET과 POSTGRES_PASSWORD를 서로 다른 무작위 값으로 채운다. DB password는
URL-safe 값으로 준비한다. 로컬 HTTP는 COOKIE_SECURE=false, 운영 HTTPS는 true를 사용한다.

```sh
docker compose --env-file .env.compose.local -p eolgae \
  -f compose.yml -f compose.proxy.yml config --quiet
docker compose --env-file .env.compose.local -p eolgae \
  -f compose.yml -f compose.proxy.yml up -d --build --wait
```

접속 주소는 `http://127.0.0.1:8080`이다. API/Web/DB는 직접 포트를 publish하지 않는다.
Kubernetes 설정은 [Resources 가이드](KUBERNETES-RESOURCES.md)를 따른다.

## Terrakube 조회와 선택적 Plan

이미 운영 중인 Terrakube를 연결한다. Eolgae Compose가 Terrakube 서버를 설치하지 않는다.
보호된 파일에 token만 저장하고 `.env.compose.local`에 다음 값을 설정한다.

```dotenv
TERRAKUBE_API_URL=https://terrakube.example.com/api/v1
TERRAKUBE_UI_URL=https://terrakube.example.com
TERRAKUBE_ORGANIZATION_ID=<organization-uuid>
TERRAKUBE_WORKSPACE_IDS=<workspace-uuid>
TERRAKUBE_USER_IDS=<eolgae-user-uuid>
TERRAKUBE_TOKEN_FILE=/absolute/private/terrakube.token
TERRAKUBE_PLAN_ENABLED=false
```

허용 목록은 쉼표로 구분한다. 사용자 UUID는 Eolgae 로그인 응답의 user.id다. token은
이미지·Git·브라우저에 넣지 않는다. 위 실행 명령에 `-f compose.terrakube.yml`을 추가한다.
환경설정 → 실행 및 Terrakube 연동에서 허용 Workspace와 최근 Run을 조회한다.
연결 설정됨이나 API healthy 표시는 원격 인증 성공을 보장하지 않는다.

Plan 요청을 허용하려면 아래 값을 추가한다. 사용자는 조회 목록에도 포함되어야 한다.
원격 token에는 해당 범위 조회와 Plan Job 생성 권한이 필요하다.

```dotenv
TERRAKUBE_PLAN_ENABLED=true
TERRAKUBE_PLAN_TEMPLATE_ID=<standard-plan-template-uuid>
TERRAKUBE_PLAN_USER_IDS=<eolgae-user-uuid>
```

표준 템플릿 본문만 허용한다. 이름만 Plan인 템플릿은 충분하지 않다.

```yaml
flow:
  - type: "terraformPlan"
    name: "Plan"
    step: 100
```

설정 반영 후 실행 이력이 없는 본인 Canvas를 Workspace에 연결한다. 설치당 Organization
1개, Workspace당 Canvas 1개를 지원한다. 연결 후 직접 실행이나 Workspace 변경은 차단된다.
연결한 Canvas와 40자리 Git commit SHA를 선택해 Plan을 요청하고 결과 카드에서 상태를 확인한다.
실행 코드는 원격 Git에 존재해야 한다. Canvas HCL을 자동 업로드하지 않으며 Canvas는 참조 버전이다.
승인·Apply·Destroy·State 관리는 Terrakube에 남는다.

중복 요청은 기존 요청으로 확인한다. timeout·불명확한 결과는 unknown으로 남고 새 제출을 차단한다.
상태 확인은 기존 Run을 조회하며 자동으로 새 Job을 만들지 않는다. 원격 연결 실패 시 직접 실행으로
전환하지 않는다. 상세 로그·변수·State·artifact URL은 Eolgae로 복제하지 않는다.

## 변경과 기존 설치

환경변수 변경은 `restart` 대신 동일 조합의 `up -d`로 반영한다. token 파일을 원자적으로
교체한 경우 API를 `up -d --no-deps --force-recreate --wait api`로 재생성한다.
외부 DB overlay의 `!reset`을 지원하는 Docker Compose가 필요하다.
API 시작 시 Alembic migration을 적용한다. 기존 설치에는 0021/0022가 추가되므로 DB를
백업하고 migration 권한을 확인한다. Resources 자체는 추가 migration이 없다.

기존 `docker-compose*.yml`은 직접 실행 개발 구성이다. 새 기본 파일과 혼동하지 않도록
명령에 모든 `-f`를 명시한다. project와 volume 이름을 확인하고 `down -v`를 사용하지 않는다.
모드 변경으로 남은 worker는 실행 중인 작업을 확인한 후 중지한다. AWS 쓰기 권한은 opt-in이다.
