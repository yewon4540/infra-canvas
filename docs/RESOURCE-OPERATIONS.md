# Resources 운영 기능 가이드

2026-10-26. Resources는 Kubernetes와 AWS를 수동 조회하고, 저장된 관측·운영 신호·실행 근거를 함께 보여준다.

## 설치와 데이터 보관

API 시작 시 Alembic `0023_resource_observations`가 필요하다. 업그레이드 전 PostgreSQL을 백업한다.
이 migration은 `resource_observations`, `resource_execution_links` 테이블을 추가하며 기존 실행 State를 변경하지 않는다.
다운그레이드는 이 두 테이블의 관측·연결 데이터를 삭제하므로 백업 후 검토한다.

새로고침은 `POST /targets/{id}/observations`를 호출해 정규화한 관측을 저장한다.
Target/조회 범위를 다시 선택하면 최신 저장 결과를 복원하고, **저장된 관측**에서 이전 결과를 선택할 수 있다.
저장 시 범위별 최근 20개, Target별 최대 100개와 30일 보관 한도를 적용한다. 자동 정리 작업은 없으며 다음 수집 때 정리한다.
기존 `GET /targets/{id}/resources`는 저장하지 않는 호환 조회 API다.

사용자·Target 소유권과 현재 허용 namespace/Region을 저장 결과 조회 때도 검사한다.
endpoint·credential reference·AWS Connection/Role이 변경되면 이전 연결의 관측을 재사용하지 않는다.
원시 YAML, Secret, 환경변수, 이벤트 메시지, AWS 태그·UserData, token·임시 credential은 저장하지 않는다.
관측 metadata에는 리소스 이름·식별자·상태·CIDR 등이 포함되므로 DB는 운영 정보로 보호한다.

## 1. 실행 이력 연결

1. Canvas 설정에서 Resources와 같은 Target을 연결한다.
2. 리소스 상세의 **실행 이력 연결**에서 소유한 Canvas를 선택하고 **연결 저장**을 누른다.
3. 직접 실행은 로컬 Plan/Apply/Destroy 이력을 보여준다.
4. Terrakube는 로컬 Plan 제출 기록을 보여주고 **실행 이력 새로고침**으로 허용 Workspace의 원격 Run을 조회한다.
5. commit/revision/Run 상태와 원본 링크를 확인한다. 원격 장애는 오류로 표시하고 저장된 제출 이력은 유지한다.

연결은 Target·조회 범위·리소스 UID에 대한 사용자 지정 연관이다. 이름으로 자동 연결하거나 State 소유권을 옮기지 않는다.
Run이 해당 리소스를 변경했다는 증명이나 장애 원인 판정이 아니다. 최근 20개 이력을 표시한다.
삭제 후 같은 이름으로 재생성된 Kubernetes 리소스는 다른 UID이므로 기존 연결을 상속하지 않는다.

## 2. 관측 비교

- `baseline`: 처음 관측한 기준선.
- `added`: 이전 저장 결과에 없던 UID를 관측. 생성 시각을 증명하지 않는다.
- `changed`: 상태·요약 변화와 before/after 값.
- `removed`: 해당 종류를 완전히 조회했을 때 이전 UID가 사라짐.

실패하거나 페이지 제한에 도달한 종류의 기존 리소스는 이전 관측 시각으로 유지한다.
이 종류는 삭제로 판단하지 않는다. 보존 목록도 종류별 최대 1,000개로 제한한다.
이는 관측 간 차이이며 Git/Terraform desired state와 비교하는 **IaC drift가 아니다**.

## 3. Kubernetes 운영 신호

기존 6종 리소스 조회에 core `events`의 `get/list` 권한을 선택적으로 추가한다.
Events 권한이 없어도 리소스 조회는 동작하며 신호 권한 오류를 별도로 표시한다.
Pod의 CrashLoopBackOff/ImagePullBackOff/OOMKilled 등 제한된 상태 코드, Deployment 진행 실패,
관측 간 재시작 횟수 증가, 같은 UID/namespace를 참조하는 Event 이유·횟수·시각을 표시한다.

이벤트 원문과 컨테이너 로그는 수집하지 않는다. Kubernetes Events는 장기 감사 로그가 아니며
조회 범위·수집 시점 밖 이벤트는 누락될 수 있다. 신호가 없다고 정상으로 판정하지 않는다.
리소스와 Events는 각각 최대 20초 조회 예산을 사용한다. 자동 polling/수집은 없다.

## 4. 근거 기반 분석

**규칙 분석**은 외부 호출 없이 현재 선택한 저장 관측에서 경고·누적 재시작을 설명한다.
근거 목록에는 선택 리소스, 관련 신호, 관측 변화, 명시 연결된 Canvas의 저장 실행 이력을 제공한다.
5분 이상 지난 관측·불완전한 조회·운영 신호 미수집은 경고한다.

선택적 LLM 분석은 운영자가 다음 설정을 해야 활성화된다.

```dotenv
RESOURCE_AI_ENABLED=true
# 기존 ANTHROPIC_API_KEY 또는 OPENAI_API_KEY / OPENAI_BASE_URL 구성 사용
```

`compose.yml`은 이 설정을 API에 전달한다. 기존 배포에는 API를 재생성한다.
LLM 키/endpoint가 없으면 분석 요청은 안전한 오류로 끝나며 규칙 분석을 계속 사용할 수 있다.
**근거를 AI에 보내 분석**을 누르면 화면에 안내된 metadata가 설정된 제공자에게 전송된다.
AI 요청은 최대 24,000자 근거, 최대 1,800 출력 토큰, 30초 timeout/재시도 없음으로 제한한다.
출력 형식·근거 ID를 검증하고 알 수 없는 근거를 인용하면 결과를 거절한다.
분석 결과는 원인 후보와 사람이 확인할 절차이며 자동 조치나 명령 실행으로 연결되지 않는다.

## 5. AWS 조회

1. 기존 AWS Connections에서 소유 계정의 AssumeRole 연결을 verified로 만든다.
2. AWS Account Target에 해당 Connection을 연결한다.
3. Resources에서 Target을 선택한다. 조회 범위는 Connection의 default Region 한 개다.
4. 새로고침하면 VPC, Subnet, SecurityGroup, EC2와 VPC/Subnet/보안 그룹 관계를 조회한다.

호스트의 source AWS 자격증명은 기존 AssumeRole 흐름을 사용한다. 실제 credential을 Target에 넣지 않는다.
조회 시 Role과 계정 일치를 확인하고, 다음 네 작업만 허용한 session policy로 AssumeRole한다.
역할 자체도 해당 조회 권한을 허용해야 한다. 세션 정책은 역할 권한을 확장하지 않는다.

```json
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["ec2:DescribeVpcs","ec2:DescribeSubnets","ec2:DescribeSecurityGroups","ec2:DescribeInstances"],"Resource":"*"}]}
```

임시 자격증명은 boto3 client 메모리에서만 사용한다. 데이터베이스/API 응답에 저장하지 않는다.
종류별 최대 5페이지·1,000개, 전체 조회 예산 30초이며 진행 중 요청 timeout은 추가될 수 있다.
접근 거절·timeout·페이지 제한은 부분 관측으로 표시한다. AWS 운영 이벤트/메트릭과 import는 이 범위에 없다.
AWS/AI 실제 외부 연결 검증은 유효한 사용자 설정이 필요하다. 모의 SDK/LLM 검증과 구분한다.

## 확인 명령

```sh
PYTHONPATH=apps/api:. python -m pytest apps/api/tests
pnpm --dir apps/web exec tsc --noEmit --incremental false
```

PostgreSQL 통합 테스트는 마이그레이션한 로컬 테스트 DB에서 `RESOURCE_DB_TEST=1`로
`tests/test_resource_store_integration.py`를 실행한다. 테스트 fixture는 바깥 transaction에서 rollback한다.

참고: [Kubernetes Event](https://kubernetes.io/docs/reference/kubernetes-api/core/event-v1/),
[STS AssumeRole session policy](https://docs.aws.amazon.com/boto3/latest/reference/services/sts/client/assume_role.html),
[EC2 DescribeInstances](https://docs.aws.amazon.com/boto3/latest/reference/services/ec2/client/describe_instances.html).
