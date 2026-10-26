# Credentials and Execution Boundaries

## 설정과 데이터

- `.env.example`에는 변수 이름과 공개 예제만 둡니다. 실제 값은 추적하지 않는 `.env`에서 설정합니다.
- AWS 임시 credential과 Kubernetes token/CA를 소스, 테스트 fixture, issue, 실행 로그에 붙여 넣지 않습니다.
- `.env`, 키 파일, Terraform state, binary Plan, DB dump, 실행 artifact와 backup은 Git 및 Docker build context에서 제외합니다.
- Target은 secret reference를 저장합니다. 환경변수 resolver가 해석한 token/CA material을 DB/API 응답에 보관하지 않습니다.
- AI 피드백은 설정한 외부 LLM 서비스에 graph와 검토 기준을 전달할 수 있습니다. 설계 이름·속성에 비밀을 넣지 않아야 합니다.

## AWS 변경

Cross-account onboarding template의 `EnableApplyPermissions` 기본값은 `false`입니다. 권한 확장과 Plan 승인은 별도 단계입니다.

Apply-ready Plan에는 state backend와 실행 artifact가 필요합니다. 승인된 artifact만 실행하며, checksum을 검증하고 한 번만 사용합니다. Destroy 역시 별도 Plan과 승인을 거칩니다.

Apply 권한을 활성화하면 Plan 준비 중 S3/DynamoDB state backend bootstrap이 발생할 수 있습니다. Plan이라는 이름만으로 모든 AWS 요청이 읽기 전용이라고 판단하지 않습니다.

## 보존 정보

실행 이력, HCL, binary Plan, state에는 리소스 식별자나 민감한 입력이 포함될 수 있습니다. 이 데이터는 소스 공개 대상이 아닙니다. 실제 배포에서는 저장소 접근 제어, 백업·보존 정책, HTTPS, 인증 설정을 환경에 맞게 구성해야 합니다.

## 공개 전 검사

```bash
gitleaks dir . --redact
gitleaks git . --redact --log-opts="--all"
git ls-files
```

자동 탐지만으로 내부 주소·개인 경로·운영 기록을 모두 판별할 수는 없습니다. 설정 예제, 문서, fixture, commit metadata도 함께 검토합니다. 발견한 실제 credential은 공개 issue에 기재하지 않습니다.

## Kubernetes observation and remote execution

Kubernetes read profiles are operator-owned files. Each profile binds an exact HTTPS endpoint,
Eolgae user IDs, namespace scope, and server-side token/CA file paths. Resource requests also
check Target ownership. Redirects, environment proxies, insecure TLS, Secret payloads, raw YAML,
container environment values, and arbitrary Kubernetes commands are not supported.

Terrakube credentials are mounted server-side files. Workspace/read-user and Plan-user scopes
are separate; Plan submission is disabled by default. A bound Canvas cannot fall back to direct
execution. Unknown submission results are reconciled against the existing Run, not resubmitted.
Remote approval, Apply/Destroy, State and locks remain owned by Terrakube.

운영 관측은 정규화 metadata만 저장한다. 조회 때 현재 Target/profile 범위를 재검증한다. AWS 조회는 제한된 STS session policy를 사용하며 임시 자격증명을 저장하지 않는다. AI 분석은 기본 비활성이며 명시 요청 시 선택 metadata를 설정된 LLM 제공자에게 전송한다. 출력은 근거 ID를 검사하며 자동 실행하지 않는다.
