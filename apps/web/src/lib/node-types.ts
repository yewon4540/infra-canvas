// AWS 노드 타입 정의. CANVAS-SCHEMA.md 의 11종 완성 (2026-06-01).
// 아이콘: apps/web/public/icons/aws/{iconFile}.
// iconFile 미지정 시 AwsNode 가 컬러 dot 으로 fallback (SG 만 해당 — 전용 SVG 없음).

import { type EdgeKind } from "@/lib/edge-types";

export interface AwsNodeTypeDef {
  type: string;
  displayName: string;
  englishName: string;
  color: string;
  iconFile?: string;
  defaultProperties: Record<string, unknown>;
  presentation?: {
    mode: "node" | "properties_slot";
    slotLabel?: string;
  };
  association?: {
    attachableTo?: string[];
    edgeTypes?: EdgeKind[];
  };
}

export const AWS_NODE_TYPES: AwsNodeTypeDef[] = [
  {
    type: "aws.ec2.instance",
    displayName: "EC2 인스턴스",
    englishName: "EC2",
    color: "#FF9900",
    iconFile: "ec2.svg",
    defaultProperties: {
      instance_type: "t3.micro",
      ami_id: "",
      security_group_ids: "",
    },
  },
  {
    type: "aws.ec2.alb",
    displayName: "Application Load Balancer",
    englishName: "ALB",
    color: "#8C4FFF",
    iconFile: "alb.svg",
    defaultProperties: {
      scheme: "internet-facing",
      listener_port: 80,
      security_group_ids: "",
    },
  },
  {
    type: "aws.ec2.asg",
    displayName: "Auto Scaling Group",
    englishName: "ASG",
    color: "#ED7100",
    iconFile: "asg.svg",
    defaultProperties: {
      min_size: 1,
      max_size: 3,
      desired_capacity: 1,
      instance_template: "",
    },
  },
  {
    type: "aws.rds.db_instance",
    displayName: "RDS 데이터베이스",
    englishName: "RDS",
    color: "#3B48CC",
    iconFile: "rds.svg",
    defaultProperties: {
      engine: "postgres",
      instance_class: "db.t3.micro",
      multi_az: false,
      security_group_ids: "",
    },
  },
  {
    type: "aws.s3.bucket",
    displayName: "S3 버킷",
    englishName: "S3",
    color: "#00A86B",
    iconFile: "s3.svg",
    defaultProperties: {
      bucket_name: "",
      versioning: false,
      public_access_block: true,
    },
  },
  {
    type: "aws.ec2.security_group",
    displayName: "보안 그룹",
    englishName: "SG",
    color: "#DD344C",
    presentation: {
      mode: "properties_slot",
      slotLabel: "SG",
    },
    association: {
      attachableTo: [
        "aws.ec2.instance",
        "aws.ec2.alb",
        "aws.rds.db_instance",
        "aws.ec2.asg",
      ],
      edgeTypes: ["network", "reference"],
    },
    defaultProperties: {
      ingress_rules: [],
      egress_rules: [],
    },
  },
  {
    type: "aws.iam.role",
    displayName: "IAM 역할",
    englishName: "IAM Role",
    color: "#C7131F",
    iconFile: "iam-role.svg",
    defaultProperties: {
      assume_role_policy: "ec2",
      attached_policies: "",
    },
  },
  {
    type: "aws.route53.record",
    displayName: "Route53 레코드",
    englishName: "Route53",
    color: "#4D72F3",
    iconFile: "route53.svg",
    defaultProperties: {
      zone_id: "",
      record_type: "A",
      value: "",
    },
  },
  {
    type: "aws.ec2.internet_gateway",
    displayName: "Internet Gateway",
    englishName: "IGW",
    color: "#7C5AE0",
    iconFile: "internet-gateway.svg",
    defaultProperties: {},
  },
  {
    type: "aws.ec2.nat_gateway",
    displayName: "NAT Gateway",
    englishName: "NAT GW",
    color: "#9B6BE8",
    iconFile: "nat-gateway.svg",
    defaultProperties: {
      elastic_ip_id: "",
    },
  },
  {
    type: "aws.ec2.route_table",
    displayName: "Route Table",
    englishName: "RT",
    color: "#5A4BC0",
    iconFile: "route-table.svg",
    defaultProperties: {
      routes: "",
    },
  },
];

export const KUBERNETES_NODE_TYPES: AwsNodeTypeDef[] = [
  {
    type: "kubernetes.namespace",
    displayName: "Namespace",
    englishName: "NS",
    color: "#326CE5",
    defaultProperties: {
      name: "",
    },
  },
  {
    type: "kubernetes.deployment",
    displayName: "Deployment",
    englishName: "Deploy",
    color: "#2F7DE1",
    defaultProperties: {
      namespace: "default",
      replicas: 2,
      image: "nginx:1.27",
      container_port: 80,
    },
  },
  {
    type: "kubernetes.service",
    displayName: "Service",
    englishName: "SVC",
    color: "#0E9F6E",
    defaultProperties: {
      namespace: "default",
      service_type: "ClusterIP",
      port: 80,
      target_port: 80,
      selector: "",
    },
  },
  {
    type: "kubernetes.ingress",
    displayName: "Ingress",
    englishName: "Ingress",
    color: "#7C3AED",
    defaultProperties: {
      namespace: "default",
      host: "",
      path: "/",
      service_name: "",
      service_port: 80,
      ingress_class_name: "",
    },
  },
  {
    type: "kubernetes.config_map",
    displayName: "ConfigMap",
    englishName: "CM",
    color: "#0891B2",
    defaultProperties: {
      namespace: "default",
      data: "",
    },
  },
  {
    type: "kubernetes.secret_ref",
    displayName: "Secret Reference",
    englishName: "Secret",
    color: "#BE123C",
    defaultProperties: {
      namespace: "default",
      name: "",
    },
  },
  {
    type: "kubernetes.pvc",
    displayName: "PersistentVolumeClaim",
    englishName: "PVC",
    color: "#B45309",
    defaultProperties: {
      namespace: "default",
      storage: "10Gi",
      access_mode: "ReadWriteOnce",
      storage_class_name: "",
    },
  },
  {
    type: "kubernetes.hpa",
    displayName: "HorizontalPodAutoscaler",
    englishName: "HPA",
    color: "#475569",
    defaultProperties: {
      namespace: "default",
      target_deployment: "",
      min_replicas: 1,
      max_replicas: 5,
      cpu_utilization: 70,
    },
  },
];

export const ALL_NODE_TYPES = [...AWS_NODE_TYPES, ...KUBERNETES_NODE_TYPES];

export function getNodeTypeDef(type: string): AwsNodeTypeDef | undefined {
  return ALL_NODE_TYPES.find((t) => t.type === type);
}
