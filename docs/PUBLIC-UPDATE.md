# 2026-10-23 기능 갱신

조회·설계 기본 구성과 선택적 직접 실행/Terrakube 실행을 분리했다. Kubernetes Resources는
관리자 profile과 read-only 권한으로 수동 목록·상세·관계를 제공한다.

- Terrakube: 허용 Workspace 조회, Canvas 연결, 지정 Git commit Plan 요청·상태·결과.
- 직접 실행: standalone overlay에만 Valkey·worker·OpenTofu를 포함한다.
- Kubernetes: Namespace, Deployment, ReplicaSet, Pod, Service, Ingress 수동 조회.
- 당시 후속이었던 운영 분석·AWS inventory의 10/26 구현 범위는 아래 항목을 따른다. 자동 수집·IaC drift·Kubernetes 쓰기/exec는 계속 후속이다.

설정은 [배포 모드](DEPLOYMENT-MODES.md), [Kubernetes Resources](KUBERNETES-RESOURCES.md)를 참고한다.

## 2026-10-26 운영 기능

Resources에 명시적 Canvas 실행 이력 연결, 정규화 관측 저장·복원·변경 비교, Kubernetes Events/상태 신호, 근거 기반 규칙/선택적 AI 분석, AWS VPC/Subnet/SecurityGroup/EC2 조회를 추가했다.
Alembic `0023_resource_observations`가 필요하다. 자동 수집·IaC drift·자동 조치는 포함하지 않는다.
설정과 한도는 [운영 기능 가이드](RESOURCE-OPERATIONS.md)를 따른다.
