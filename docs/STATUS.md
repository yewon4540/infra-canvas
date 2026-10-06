# Implementation Status

## 제공되는 기능

| 영역 | 구현 |
| --- | --- |
| AWS 설계 | Canvas 편집, 템플릿·fragment, HCL 생성, 구조 검증 |
| AWS 연결 | 재사용 가능한 connection, Role onboarding, STS 검증 |
| 실행 | 비동기 Plan, preview/Apply-ready 구분, 승인, single-use Apply/Destroy |
| 추적 | Canvas snapshot, artifact store, 단계별 이벤트, audit, 실행 이력 |
| 상태 연결 기반 | Apply 후 state에서 리소스 binding 추출·저장 |
| 설계 검토 | 검토 기준 입력, LLM 피드백, deterministic baseline rules |
| Kubernetes 기반 | Target 등록, RBAC 안내, secret resolver, YAML 생성·로컬 검증 |

## 아직 제공하지 않는 기능

- Kubernetes live API 연결 검증, inventory refresh, cluster-side dry-run
- 실제 클러스터 데이터 기반 리소스 탐색기, 로그 콘솔, Pod exec
- AWS live discovery, 주기적 refresh·drift detection, import/adopt
- CloudFormation Change Set 실행
- 자동 복구·자동 Apply, 실시간 실행 출력 스트리밍

## 알려진 한계

- `applied`는 마지막 Apply 성공을 뜻합니다. 실시간 리소스 정상 상태가 아닙니다.
- Kubernetes Resource Tree는 Canvas graph 미리보기입니다.
- Kubernetes diagram에서 리소스 겹침과 panel 가림이 관찰됐습니다. 추가 시각화 개선은 보류하고 트리·상세 중심 탐색을 검토합니다.
- Canvas 상세 page와 일부 router에 책임이 집중돼 있습니다. 새 동작을 추가할 때 hook/service/provider 경계로 분리해야 합니다.
- 실제 AWS 실행의 초기 검증 범위는 S3 생성·삭제입니다. 모든 AWS 리소스 조합의 운영 적합성을 검증한 상태는 아닙니다.

## 검증 범위

단위 테스트는 graph 변환·제약 검사, artifact 무결성, 승인·single-use 경계, Target 인증정보 준비 상태와 실행 결과 처리를 확인합니다. 외부 AWS/OpenTofu 작업은 모의 처리합니다.

TypeScript 검사와 Next.js build는 소스의 타입 및 빌드 가능성을 확인합니다. 실제 UI 사용성·실클러스터 연동·프로덕션 배포 검증을 대체하지 않습니다.

최근 실행 결과는 [개발 가이드](DEVELOPMENT.md)의 검증 기록에 정리합니다.
