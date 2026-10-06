// Group (VPC / Subnet) 타입 정의 — CANVAS-SCHEMA.md §Group 따름.
// 1차 진입은 *시각만* — 큰 배경 박스 + 라벨. 자동 parent containment / resize 는 후속.
// 데이터는 nodes[] 안에 박힘 (groups[] 활용은 추후 정교화 시점에 격상).

export interface AwsGroupTypeDef {
  type: string;
  displayName: string;
  englishName: string;
  fillColor: string;
  borderColor: string;
  iconFile?: string;
  defaultProperties: Record<string, unknown>;
  defaultSize: { width: number; height: number };
}

export const AWS_GROUP_TYPES: AwsGroupTypeDef[] = [
  {
    type: "aws.ec2.vpc",
    displayName: "VPC",
    englishName: "VPC",
    fillColor: "rgba(33, 150, 243, 0.06)",
    borderColor: "#1976D2",
    iconFile: "vpc.svg",
    defaultProperties: {
      cidr: "10.0.0.0/16",
      region: "ap-northeast-2",
    },
    defaultSize: { width: 720, height: 480 },
  },
  {
    type: "aws.ec2.subnet",
    displayName: "서브넷",
    englishName: "Subnet",
    fillColor: "rgba(123, 31, 162, 0.06)",
    borderColor: "#7B1FA2",
    iconFile: "subnet.svg",
    defaultProperties: {
      cidr: "10.0.1.0/24",
      availability_zone: "ap-northeast-2a",
      type: "private",
    },
    defaultSize: { width: 360, height: 240 },
  },
];

export function getGroupTypeDef(type: string): AwsGroupTypeDef | undefined {
  return AWS_GROUP_TYPES.find((t) => t.type === type);
}

export function isGroupType(type: string | undefined): boolean {
  if (!type) return false;
  return AWS_GROUP_TYPES.some((t) => t.type === type);
}
