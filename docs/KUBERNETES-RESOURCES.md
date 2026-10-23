# Kubernetes Resources 조회 설정

2026-10-23. Resources는 Canvas·배포 이력·Terrakube 연결 없이 사용하는 수동 조회 화면이다.
Namespace, Deployment, ReplicaSet, Pod, Service, Ingress를 지원한다. API는 GET만 사용하며
Secret, 환경변수, annotation, 원시 YAML과 로그를 응답이나 DB에 복제하지 않는다.

## 관리자 설정

1. 전용 ServiceAccount와 조회 RBAC를 준비한다. 전체 namespace에는 아래 규칙의
   ClusterRole/ClusterRoleBinding, 제한된 범위에는 namespace별 Role/RoleBinding을 사용한다.
   Namespace 객체 자체의 조회는 별도 권한이며 없으면 부분 실패로 표시된다.

```yaml
rules:
  - apiGroups: [""]
    resources: [namespaces, pods, services]
    verbs: [get, list]
  - apiGroups: [apps]
    resources: [deployments, replicasets]
    verbs: [get, list]
  - apiGroups: [networking.k8s.io]
    resources: [ingresses]
    verbs: [get, list]
```

2. 보호된 호스트 디렉터리에 `reader.token`, `ca.crt`, `profiles.json`을 저장한다.
   token은 `Bearer ` 없이 한 줄, CA는 PEM 또는 Base64 PEM으로 준비한다.
   파일 권한 600, 디렉터리 700으로 제한하고 token은 만료 전에 운영자가 갱신한다.
3. 아래 profile의 주소·사용자·namespace·credential 연결을 관리자가 지정한다.
   사용자 UUID는 Eolgae 로그인 응답의 `user.id`다. 브라우저 입력만으로 다른 서버에
   token을 전송하거나 다른 사용자 profile을 사용할 수 없다.

```json
[
  {
    "name": "test-cluster-reader",
    "endpoint": "https://kubernetes.example.com:6443",
    "user_ids": ["00000000-0000-0000-0000-000000000001"],
    "namespaces": ["demo"],
    "token_file": "/run/eolgae/kubernetes/reader.token",
    "ca_file": "/run/eolgae/kubernetes/ca.crt"
  }
]
```

`namespaces: ["*"]`는 전체 namespace 조회를 허용한다. 기본은 필요한 범위만 연다.
endpoint는 Target에 저장한 문자열과 정확히 일치해야 한다. HTTPS/CA 검증은 필수이고
redirect·환경 proxy는 사용하지 않는다. 동일 사용자·이름·endpoint의 중복 profile은 거절한다.

4. `.env.compose.local`에 `KUBERNETES_CONFIG_DIR=/absolute/private/kubernetes`를 추가한다.
   기존 배포 조합에 `compose.observation.yml`을 추가한다.

```sh
docker compose --env-file .env.compose.local -p eolgae \
  -f compose.yml -f compose.proxy.yml -f compose.observation.yml config --quiet
docker compose --env-file .env.compose.local -p eolgae \
  -f compose.yml -f compose.proxy.yml -f compose.observation.yml up -d --build --wait
```

Terrakube 설치에는 기존 `compose.terrakube.yml`도 유지한다. observation overlay는 API에
읽기 전용 mount만 추가하며 worker·Valkey·OpenTofu를 추가하지 않는다. 파일은 매 요청마다
읽는다. 디렉터리 아래 파일 교체는 반영되지만 환경·mount 경로 변경은 `up -d`가 필요하다.

## 화면 사용

1. 환경설정 → Targets에서 Kubernetes Cluster를 추가한다.
2. API endpoint와 기본 namespace를 입력한다. **Secret Reference**에 profile의 `name`을
   넣는다. 파일 profile 방식에서는 기존 Token/CA/Endpoint Env 칸을 비워 둔다.
3. **연결 검증**은 기본 namespace의 6종 API를 실제 조회한다. 전체 성공은 ready,
   일부 실패는 error와 종류별 확인 결과를 반환한다. ready는 리소스 건강 상태가 아니다.
4. **Resources**에서 Target·namespace를 선택하고 **새로고침**을 누른다.
5. 이름·namespace 검색과 종류 필터로 리소스를 찾는다. 상세에서 관측 시각·상태 요약과
   ownerReference·Service selector·Ingress backend 관계를 확인한다.
6. 관계 항목을 누르면 관련 리소스로 이동한다. 관계는 조회 근거이며 실제 트래픽 성공이나
   IaC 관리 소유권을 의미하지 않는다.

## 실패와 불완전한 관측

- 허용 profile 없음: 403. profile/token/CA 파일 오류: 503. namespace 형식 오류: 422.
- 원격 401·403·404·410·429, timeout, TLS 실패를 종류별로 구분한다.
- 실패한 종류의 이전 결과는 같은 화면·Target·범위에서만 보존하고 **이전 관측**으로 표시한다.
  성공한 종류는 갱신한다. Target·namespace를 바꾸면 기존 결과를 비운다.
- 실패한 종류의 관계는 갱신 결과에서 제외한다.
- 200개 단위 최대 5페이지/종류, 응답당 8 MiB, 전체 조회 예산 20초다. 진행 중 요청은
  최대 5초 timeout까지 더 걸릴 수 있다. 제한에 도달하면 불완전한 목록으로 표시한다.
  관계는 최대 5,000개이며 제한 시 일부 관계 표시 안내를 제공한다.
- 불완전한 조회를 “리소스 없음”이나 삭제로 판정하지 않는다.
- 자동 polling, 백그라운드 수집, drift, 명령 콘솔, Pod exec, 쓰기 API, AI 운영 분석은 후속이다.

새 DB migration은 필요 없다. Target에는 연결 metadata와 profile 이름만 저장한다.
관측 결과는 요청 응답과 현재 화면 메모리에서만 사용한다.

API: `GET /targets/{id}/resource-scope`, `GET /targets/{id}/resources?namespace=demo`.
두 API 모두 Target 소유권과 관리자 profile 범위를 확인한다.

참고: [Kubernetes API pagination](https://kubernetes.io/docs/reference/using-api/api-concepts/),
[owner references](https://kubernetes.io/docs/concepts/overview/working-with-objects/owners-dependents/).
