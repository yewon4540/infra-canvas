# 2026-10-23 기능 갱신

조회·설계 기본 구성과 선택적 직접 실행/Terrakube 실행을 분리했다. Kubernetes Resources는
관리자 profile과 read-only 권한으로 수동 목록·상세·관계를 제공한다.

- Terrakube: 허용 Workspace 조회, Canvas 연결, 지정 Git commit Plan 요청·상태·결과.
- 직접 실행: standalone overlay에만 Valkey·worker·OpenTofu를 포함한다.
- Kubernetes: Namespace, Deployment, ReplicaSet, Pod, Service, Ingress 수동 조회.
- 후속: 자동 수집, drift, Kubernetes 쓰기/exec, 운영 AI 분석, AWS inventory.

설정은 [배포 모드](DEPLOYMENT-MODES.md), [Kubernetes Resources](KUBERNETES-RESOURCES.md)를 참고한다.
