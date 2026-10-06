// Edge 종류 자동 추론 — node type pair 매트릭스 (rule-base, 1차).
// 1차 MVP 4 종 노드 기준 (EC2 / ALB / RDS / S3). 매트릭스 미정의 = network fallback.
//
// 배치와 연결 정보에서 리소스 간 참조를 추론해 반복 입력을 줄인다.
// 운영자는 추론 결과를 PropertiesPanel 에서 즉시 override 가능 (확정 단계 분리 없음).

import { type EdgeKind, DEFAULT_EDGE_KIND } from "./edge-types";

const PAIR_MATRIX: Record<string, Record<string, EdgeKind>> = {
  "aws.ec2.alb": {
    "aws.ec2.instance": "network",
    "aws.ec2.asg": "network",
    "aws.rds.db_instance": "network",
    "aws.s3.bucket": "data_flow",
    "aws.ec2.security_group": "reference",
  },
  "aws.ec2.instance": {
    "aws.ec2.instance": "depends_on",
    "aws.rds.db_instance": "network",
    "aws.s3.bucket": "data_flow",
    "aws.ec2.alb": "depends_on",
    "aws.iam.role": "reference",
    "aws.ec2.security_group": "reference",
  },
  "aws.ec2.asg": {
    "aws.rds.db_instance": "network",
    "aws.s3.bucket": "data_flow",
    "aws.iam.role": "reference",
    "aws.ec2.security_group": "reference",
  },
  "aws.rds.db_instance": {
    "aws.s3.bucket": "data_flow",
    "aws.ec2.security_group": "reference",
  },
  "aws.s3.bucket": {
    "aws.iam.role": "reference",
  },
  "aws.route53.record": {
    "aws.ec2.alb": "network",
    "aws.ec2.instance": "network",
    "aws.s3.bucket": "data_flow",
  },
  // 네트워크 토폴로지 (route 엣지)
  "aws.ec2.subnet": {
    "aws.ec2.route_table": "route",
    "aws.ec2.internet_gateway": "route",
    "aws.ec2.nat_gateway": "route",
  },
  "aws.ec2.route_table": {
    "aws.ec2.internet_gateway": "route",
    "aws.ec2.nat_gateway": "route",
  },
  "aws.ec2.vpc": {
    "aws.ec2.internet_gateway": "reference",
  },
  "aws.ec2.nat_gateway": {
    "aws.ec2.internet_gateway": "route",
  },
};

export function inferEdgeKind(
  sourceType: string | undefined,
  targetType: string | undefined,
): EdgeKind {
  if (!sourceType || !targetType) return DEFAULT_EDGE_KIND;
  // (s, t) 우선. 미스 시 (t, s) fallback — handle 위치(위/아래) 에 따라
  // source/target 이 뒤집혀도 동일 type 추론. 의미가 강한 방향성(network 등)은
  // 매트릭스에 양방향 모두 명시되지 않은 한 fallback 으로 잡힘.
  return (
    PAIR_MATRIX[sourceType]?.[targetType] ??
    PAIR_MATRIX[targetType]?.[sourceType] ??
    DEFAULT_EDGE_KIND
  );
}
