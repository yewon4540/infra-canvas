# Caddy / Nginx 실행 구성

두 파일 모두 독립적으로 실행할 수 있다. 기본 상태에서는 Caddy를 사용한다.

| 파일 | 구성 |
| --- | --- |
| `docker-compose.yml` | Caddy 활성화, Nginx 대체 서비스는 주석 처리 |
| `docker-compose-without_nginx.yml` | Caddy 전용, Nginx 서비스 없음 |
| `docker-compose.override.yml` | 개발용 bind mount, API reload, 웹 HMR |
| `nginx/default.conf` | Nginx를 선택했을 때 사용하는 HTTP 프록시 설정 |

웹 Docker 빌드 context는 저장소 루트이며, 커밋된 `pnpm-lock.yaml`로 의존성 버전을 고정한다. 개발 override는 `/workspace/apps/web`에 소스를 마운트하고 의존성은 별도 named volume에 유지한다.

두 Compose 파일의 공통 서비스·환경변수·볼륨은 동일하게 유지한다. 파일을 함께 병합하지 않고 하나를 선택한다. 같은 디렉터리에서 파일만 바꾸면 같은 Compose 프로젝트와 데이터 볼륨을 사용한다.

## 기본 Caddy 실행

루트 `.env`의 `POSTGRES_PASSWORD`, `JWT_SECRET`를 먼저 설정한다. 웹 컨테이너는 루트 `.env`의 `NEXT_PUBLIC_API_URL`을 사용하며, 기본값은 `http://localhost/api`이다. 호스트에서 `pnpm dev`를 실행할 때 사용하는 `apps/web/.env.local`과 구분한다.

```bash
# Production 이미지로 실행 (개발 override 제외)
docker compose -f docker-compose-without_nginx.yml up --build -d

# 또는 기본 파일의 Caddy 구성으로 실행
docker compose -f docker-compose.yml up --build -d
```

개발 모드에서는 override를 명시적으로 추가한다.

```bash
docker compose -f docker-compose-without_nginx.yml -f docker-compose.override.yml up --build
```

`docker compose up --build`는 기본 파일과 개발 override를 자동으로 읽는다. `-f`를 지정하면 사용할 override도 명시해야 한다.

- 웹: `http://localhost`
- 프록시 경유 API health: `http://localhost/api/health`
- API 문서 직접 접근: `http://localhost:8000/docs`

## Nginx로 전환

1. 현재 Caddy 컨테이너를 정지한다.

   ```bash
   docker compose -f docker-compose-without_nginx.yml stop caddy
   ```

2. `docker-compose.yml`의 `caddy:` 서비스 전체를 주석 처리하고, `nginx:` 서비스 블록의 주석을 해제한다. 하단의 `caddy_data`, `caddy_config` 볼륨 선언은 복귀를 위해 남겨도 된다.
3. 설정을 검사하고 실행한다.

   ```bash
   docker compose -f docker-compose.yml config --quiet
   docker compose -f docker-compose.yml up --build -d --remove-orphans
   docker compose -f docker-compose.yml exec nginx nginx -t
   curl --fail http://localhost/api/health
   ```

개발 모드는 위 실행 명령에 `-f docker-compose.override.yml`을 추가한다. `--remove-orphans`는 같은 프로젝트에서 더 이상 선언되지 않은 Caddy 컨테이너를 제거한다. 데이터 볼륨은 삭제하지 않는다.

## Caddy로 복귀

Nginx 선택 상태의 기본 파일로 Nginx를 정지한 뒤 Caddy 전용 파일을 실행한다.

```bash
docker compose -f docker-compose.yml stop nginx
docker compose -f docker-compose-without_nginx.yml up --build -d --remove-orphans
```

기본 파일로도 Caddy를 사용하려면 `docker-compose.yml`에서 Nginx를 다시 주석 처리하고 Caddy의 주석을 해제한다. `down -v`는 DB·artifact 등 데이터 볼륨을 삭제하므로 전환 절차에 사용하지 않는다.

## 요청 경로와 배포 범위

두 프록시는 `/api/` 접두사를 제거해 API로 전달한다. 예를 들어 `/api/auth/login`은 API의 `/auth/login`으로 전달된다. 나머지는 웹으로 전달한다. Refresh cookie의 `Path=/auth/refresh`도 브라우저 요청 경로인 `/api/auth/refresh`로 바꾼다. Nginx 설정은 SSE 응답 버퍼링을 끄고 웹 개발 서버의 WebSocket upgrade를 전달한다.

현재 예제는 로컬 HTTP 구성이다. Caddy의 443 포트 매핑만으로 HTTPS가 활성화되지는 않는다. Caddy 자동 TLS를 사용하려면 전역 `auto_https off`를 제거하고 `:80`을 실제 도메인으로 바꾼 뒤 DNS와 80/443 접근을 설정한다. Nginx는 인증서 발급·갱신, 443 listen과 인증서 mount를 별도로 구성해야 한다.

브라우저 접속 주소가 바뀌면 루트 `.env`의 `NEXT_PUBLIC_API_URL`을 `https://실제도메인/api`와 같이 바꾸고 웹 이미지를 재빌드한다. `NEXT_PUBLIC_*`는 빌드 결과에 포함되므로 실행 환경변수만 바꿔서는 production 웹에 반영되지 않는다. Refresh cookie는 기본적으로 Secure이며, 외부 도메인에서는 HTTPS를 사용한다. OAuth와 사용자 지정 도메인의 CORS 정책은 별도 설정·검증 대상이다.

이 변경은 프록시 선택용 구성이다. DB/API 등의 기존 호스트 포트 공개 정책은 그대로이므로 외부 서버에 배포할 때는 접근 범위를 별도로 설정한다. AWS write 권한과 Plan 승인 경계는 기존 opt-in 정책을 유지하며, 이 설정으로 실제 AWS Apply/Destroy를 실행하지 않는다. 임시 AWS credential을 파일·DB에 새로 기록하지 않는다. DB 스키마 변경이나 Alembic migration은 필요하지 않다.

## 실패 시 확인

| 증상 | 확인 |
| --- | --- |
| 80 포트 충돌 | 기존 Caddy/Nginx 또는 호스트 웹서버가 실행 중인지 확인 |
| `502 Bad Gateway` | API/웹 기동 상태와 로그 확인. Nginx 사용 중 upstream 컨테이너 재생성 후 문제가 생기면 Nginx 재시작 |
| `/api/health`가 404 | Nginx `proxy_pass`의 마지막 `/`, Caddy `handle_path` 확인 |
| API 요청이 localhost:8000으로 나감 | Compose의 API URL과 웹 재빌드 여부 확인 |
| 로그인 갱신 실패 | cookie Path, HTTPS/Secure, 브라우저 접속 도메인 확인 |
| SSE가 한꺼번에 표시됨 | Nginx의 `proxy_buffering off`와 앞단 프록시의 버퍼링 확인 |
| `413 Request Entity Too Large` | Nginx 예제의 요청 본문 상한 10 MB 확인 |

참고: [Compose 파일 병합](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/), [Nginx proxy 모듈](https://nginx.org/en/docs/http/ngx_http_proxy_module.html), [WebSocket 전달](https://nginx.org/en/docs/http/websocket.html), [Caddy reverse_proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).

## 구성 검증 기록 (2026-10-08)

- 두 Compose 파일의 기본/개발 설정 해석과 공통 서비스 일치 확인.
- Nginx 주석 해제·Caddy 비활성화 상태의 기본/개발 설정 해석 확인.
- 격리 컨테이너의 `nginx -t`, `caddy validate` 통과.
- 모의 upstream으로 API 접두사 제거, query 보존, 웹 라우팅, cookie Path, Host/proto 전달, SSE 첫 이벤트 지연, WebSocket 101 응답 확인.
- `pnpm exec tsc --noEmit --incremental false` 통과.
- lockfile 기반 웹 production/dev Docker 이미지 빌드 통과. 각각 `/login` HTTP 200과 브라우저 bundle의 API URL 반영 확인. 개발 검사는 소스와 의존성 볼륨을 마운트한 상태로 수행.

프록시 동작 검사는 모의 upstream을 사용했다. 전체 DB/API/worker 연동, 실제 로그인·갱신 흐름의 브라우저 검사, TLS 발급, 외부 서버 배포와 AWS Apply는 수행하지 않았다. 임시 검증 컨테이너·네트워크는 제거했다.
