import {
  CheckboxField,
  FormField,
  inputClass,
} from "@/components/properties/FormControls";

interface FormProps {
  properties: Record<string, unknown>;
  onUpdate: (key: string, value: unknown) => void;
}

type SecurityRule = {
  protocol: string;
  port_range: string;
  source: string;
  description?: string;
};

export function PropertiesForm({
  nodeType,
  properties,
  onUpdate,
}: {
  nodeType: string;
  properties: Record<string, unknown>;
  onUpdate: (key: string, value: unknown) => void;
}) {
  switch (nodeType) {
    case "aws.ec2.instance":
      return <Ec2Form properties={properties} onUpdate={onUpdate} />;
    case "aws.ec2.alb":
      return <AlbForm properties={properties} onUpdate={onUpdate} />;
    case "aws.ec2.asg":
      return <AsgForm properties={properties} onUpdate={onUpdate} />;
    case "aws.rds.db_instance":
      return <RdsForm properties={properties} onUpdate={onUpdate} />;
    case "aws.s3.bucket":
      return <S3Form properties={properties} onUpdate={onUpdate} />;
    case "aws.ec2.security_group":
      return <SgForm properties={properties} onUpdate={onUpdate} />;
    case "aws.iam.role":
      return <IamRoleForm properties={properties} onUpdate={onUpdate} />;
    case "aws.route53.record":
      return <Route53Form properties={properties} onUpdate={onUpdate} />;
    case "aws.ec2.internet_gateway":
      return <IgwForm />;
    case "aws.ec2.nat_gateway":
      return <NatGatewayForm properties={properties} onUpdate={onUpdate} />;
    case "aws.ec2.route_table":
      return <RouteTableForm properties={properties} onUpdate={onUpdate} />;
    case "kubernetes.namespace":
      return <KubernetesNamespaceForm properties={properties} onUpdate={onUpdate} />;
    case "kubernetes.deployment":
      return <KubernetesDeploymentForm properties={properties} onUpdate={onUpdate} />;
    case "kubernetes.service":
      return <KubernetesServiceForm properties={properties} onUpdate={onUpdate} />;
    case "kubernetes.ingress":
      return <KubernetesIngressForm properties={properties} onUpdate={onUpdate} />;
    case "kubernetes.config_map":
      return <KubernetesConfigMapForm properties={properties} onUpdate={onUpdate} />;
    case "kubernetes.secret_ref":
      return <KubernetesSecretRefForm properties={properties} onUpdate={onUpdate} />;
    case "kubernetes.pvc":
      return <KubernetesPvcForm properties={properties} onUpdate={onUpdate} />;
    case "kubernetes.hpa":
      return <KubernetesHpaForm properties={properties} onUpdate={onUpdate} />;
    default:
      return (
        <div className="mt-3 text-xs text-[var(--color-text-subtle)]">
          지원하지 않는 노드 타입
        </div>
      );
  }
}

function NamespaceField({ properties, onUpdate }: FormProps) {
  return (
    <FormField label="네임스페이스 (namespace)">
      <input
        type="text"
        value={(properties.namespace as string) || "default"}
        onChange={(e) => onUpdate("namespace", e.target.value)}
        placeholder="default"
        className={inputClass}
      />
    </FormField>
  );
}

function KubernetesNamespaceForm({ properties, onUpdate }: FormProps) {
  return (
    <FormField label="이름 (name)">
      <input
        type="text"
        value={(properties.name as string) || ""}
        onChange={(e) => onUpdate("name", e.target.value)}
        placeholder="platform"
        className={inputClass}
      />
    </FormField>
  );
}

function KubernetesDeploymentForm({ properties, onUpdate }: FormProps) {
  return (
    <>
      <NamespaceField properties={properties} onUpdate={onUpdate} />
      <FormField label="이미지 (image)">
        <input
          type="text"
          value={(properties.image as string) || "nginx:1.27"}
          onChange={(e) => onUpdate("image", e.target.value)}
          className={inputClass}
        />
      </FormField>
      <FormField label="레플리카 수 (replicas)">
        <input
          type="number"
          min={0}
          value={(properties.replicas as number) ?? 2}
          onChange={(e) => onUpdate("replicas", parseInt(e.target.value, 10) || 0)}
          className={inputClass}
        />
      </FormField>
      <FormField label="컨테이너 포트 (container_port)">
        <input
          type="number"
          min={1}
          value={(properties.container_port as number) || 80}
          onChange={(e) =>
            onUpdate("container_port", parseInt(e.target.value, 10) || 80)
          }
          className={inputClass}
        />
      </FormField>
    </>
  );
}

function KubernetesServiceForm({ properties, onUpdate }: FormProps) {
  return (
    <>
      <NamespaceField properties={properties} onUpdate={onUpdate} />
      <FormField label="서비스 타입 (service_type)">
        <select
          value={(properties.service_type as string) || "ClusterIP"}
          onChange={(e) => onUpdate("service_type", e.target.value)}
          className={inputClass}
        >
          <option value="ClusterIP">ClusterIP</option>
          <option value="NodePort">NodePort</option>
          <option value="LoadBalancer">LoadBalancer</option>
        </select>
      </FormField>
      <FormField label="포트 (port)">
        <input
          type="number"
          min={1}
          value={(properties.port as number) || 80}
          onChange={(e) => onUpdate("port", parseInt(e.target.value, 10) || 80)}
          className={inputClass}
        />
      </FormField>
      <FormField label="대상 포트 (target_port)">
        <input
          type="number"
          min={1}
          value={(properties.target_port as number) || 80}
          onChange={(e) =>
            onUpdate("target_port", parseInt(e.target.value, 10) || 80)
          }
          className={inputClass}
        />
      </FormField>
      <FormField label="셀렉터 app 값 (selector)">
        <input
          type="text"
          value={(properties.selector as string) || ""}
          onChange={(e) => onUpdate("selector", e.target.value)}
          placeholder="비우면 Service 이름 사용"
          className={inputClass}
        />
      </FormField>
    </>
  );
}

function KubernetesIngressForm({ properties, onUpdate }: FormProps) {
  return (
    <>
      <NamespaceField properties={properties} onUpdate={onUpdate} />
      <FormField label="호스트 (host)">
        <input
          type="text"
          value={(properties.host as string) || ""}
          onChange={(e) => onUpdate("host", e.target.value)}
          placeholder="app.example.com"
          className={inputClass}
        />
      </FormField>
      <FormField label="경로 (path)">
        <input
          type="text"
          value={(properties.path as string) || "/"}
          onChange={(e) => onUpdate("path", e.target.value)}
          className={inputClass}
        />
      </FormField>
      <FormField label="서비스 이름 (service_name)">
        <input
          type="text"
          value={(properties.service_name as string) || ""}
          onChange={(e) => onUpdate("service_name", e.target.value)}
          className={inputClass}
        />
      </FormField>
      <FormField label="서비스 포트 (service_port)">
        <input
          type="number"
          min={1}
          value={(properties.service_port as number) || 80}
          onChange={(e) =>
            onUpdate("service_port", parseInt(e.target.value, 10) || 80)
          }
          className={inputClass}
        />
      </FormField>
      <FormField label="IngressClass (ingress_class_name)">
        <input
          type="text"
          value={(properties.ingress_class_name as string) || ""}
          onChange={(e) => onUpdate("ingress_class_name", e.target.value)}
          placeholder="nginx"
          className={inputClass}
        />
      </FormField>
    </>
  );
}

function KubernetesConfigMapForm({ properties, onUpdate }: FormProps) {
  return (
    <>
      <NamespaceField properties={properties} onUpdate={onUpdate} />
      <FormField label="데이터 (data, key=value 줄바꿈)">
        <textarea
          rows={4}
          value={(properties.data as string) || ""}
          onChange={(e) => onUpdate("data", e.target.value)}
          placeholder={"LOG_LEVEL=info\nFEATURE_FLAG=true"}
          className={inputClass}
        />
      </FormField>
    </>
  );
}

function KubernetesSecretRefForm({ properties, onUpdate }: FormProps) {
  return (
    <>
      <NamespaceField properties={properties} onUpdate={onUpdate} />
      <FormField label="기존 Secret 이름 (name)">
        <input
          type="text"
          value={(properties.name as string) || ""}
          onChange={(e) => onUpdate("name", e.target.value)}
          placeholder="app-secret"
          className={inputClass}
        />
      </FormField>
    </>
  );
}

function KubernetesPvcForm({ properties, onUpdate }: FormProps) {
  return (
    <>
      <NamespaceField properties={properties} onUpdate={onUpdate} />
      <FormField label="요청 용량 (storage)">
        <input
          type="text"
          value={(properties.storage as string) || "10Gi"}
          onChange={(e) => onUpdate("storage", e.target.value)}
          className={inputClass}
        />
      </FormField>
      <FormField label="접근 모드 (access_mode)">
        <select
          value={(properties.access_mode as string) || "ReadWriteOnce"}
          onChange={(e) => onUpdate("access_mode", e.target.value)}
          className={inputClass}
        >
          <option value="ReadWriteOnce">ReadWriteOnce</option>
          <option value="ReadOnlyMany">ReadOnlyMany</option>
          <option value="ReadWriteMany">ReadWriteMany</option>
          <option value="ReadWriteOncePod">ReadWriteOncePod</option>
        </select>
      </FormField>
      <FormField label="StorageClass (storage_class_name)">
        <input
          type="text"
          value={(properties.storage_class_name as string) || ""}
          onChange={(e) => onUpdate("storage_class_name", e.target.value)}
          placeholder="비우면 클러스터 기본값"
          className={inputClass}
        />
      </FormField>
    </>
  );
}

function KubernetesHpaForm({ properties, onUpdate }: FormProps) {
  return (
    <>
      <NamespaceField properties={properties} onUpdate={onUpdate} />
      <FormField label="대상 Deployment (target_deployment)">
        <input
          type="text"
          value={(properties.target_deployment as string) || ""}
          onChange={(e) => onUpdate("target_deployment", e.target.value)}
          className={inputClass}
        />
      </FormField>
      <FormField label="최소 레플리카 (min_replicas)">
        <input
          type="number"
          min={1}
          value={(properties.min_replicas as number) || 1}
          onChange={(e) =>
            onUpdate("min_replicas", parseInt(e.target.value, 10) || 1)
          }
          className={inputClass}
        />
      </FormField>
      <FormField label="최대 레플리카 (max_replicas)">
        <input
          type="number"
          min={1}
          value={(properties.max_replicas as number) || 5}
          onChange={(e) =>
            onUpdate("max_replicas", parseInt(e.target.value, 10) || 1)
          }
          className={inputClass}
        />
      </FormField>
      <FormField label="CPU 목표 사용률 (cpu_utilization)">
        <input
          type="number"
          min={1}
          max={100}
          value={(properties.cpu_utilization as number) || 70}
          onChange={(e) =>
            onUpdate("cpu_utilization", parseInt(e.target.value, 10) || 70)
          }
          className={inputClass}
        />
      </FormField>
    </>
  );
}

function IgwForm() {
  return (
    <div className="mt-3 text-xs text-[var(--color-text-subtle)]">
      Internet Gateway 는 별도 properties 없음. VPC 에 attach 되어 사용.
    </div>
  );
}

function NatGatewayForm({ properties, onUpdate }: FormProps) {
  return (
    <FormField label="Elastic IP ID (elastic_ip_id)">
      <input
        type="text"
        value={(properties.elastic_ip_id as string) || ""}
        onChange={(e) => onUpdate("elastic_ip_id", e.target.value)}
        placeholder="eipalloc-... (없으면 .tf 에 자동 생성 안내)"
        className={inputClass}
      />
    </FormField>
  );
}

function RouteTableForm({ properties, onUpdate }: FormProps) {
  return (
    <FormField label="라우트 규칙 (routes, 줄바꿈 구분)">
      <textarea
        rows={3}
        value={(properties.routes as string) || ""}
        onChange={(e) => onUpdate("routes", e.target.value)}
        placeholder="0.0.0.0/0 -> igw-xxx&#10;10.0.0.0/16 -> local"
        className={inputClass}
      />
    </FormField>
  );
}

function Ec2Form({ properties, onUpdate }: FormProps) {
  return (
    <>
      <FormField label="인스턴스 타입 (instance_type)">
        <select
          value={(properties.instance_type as string) || "t3.micro"}
          onChange={(e) => onUpdate("instance_type", e.target.value)}
          className={inputClass}
        >
          <option value="t3.micro">t3.micro</option>
          <option value="t3.small">t3.small</option>
          <option value="t3.medium">t3.medium</option>
          <option value="t3.large">t3.large</option>
          <option value="m5.large">m5.large</option>
          <option value="m5.xlarge">m5.xlarge</option>
        </select>
      </FormField>
      <FormField label="AMI ID (ami_id)">
        <input
          type="text"
          value={(properties.ami_id as string) || ""}
          onChange={(e) => onUpdate("ami_id", e.target.value)}
          placeholder="ami-..."
          className={inputClass}
        />
      </FormField>
    </>
  );
}

function AlbForm({ properties, onUpdate }: FormProps) {
  return (
    <>
      <FormField label="스킴 (scheme)">
        <select
          value={(properties.scheme as string) || "internet-facing"}
          onChange={(e) => onUpdate("scheme", e.target.value)}
          className={inputClass}
        >
          <option value="internet-facing">internet-facing (외부 공개)</option>
          <option value="internal">internal (내부)</option>
        </select>
      </FormField>
      <FormField label="리스너 포트 (listener_port)">
        <input
          type="number"
          value={(properties.listener_port as number) || 80}
          onChange={(e) =>
            onUpdate("listener_port", parseInt(e.target.value, 10) || 80)
          }
          className={inputClass}
        />
      </FormField>
    </>
  );
}

function RdsForm({ properties, onUpdate }: FormProps) {
  return (
    <>
      <FormField label="엔진 (engine)">
        <select
          value={(properties.engine as string) || "postgres"}
          onChange={(e) => onUpdate("engine", e.target.value)}
          className={inputClass}
        >
          <option value="postgres">postgres</option>
          <option value="mysql">mysql</option>
          <option value="mariadb">mariadb</option>
          <option value="oracle-ee">oracle-ee</option>
        </select>
      </FormField>
      <FormField label="인스턴스 클래스 (instance_class)">
        <select
          value={(properties.instance_class as string) || "db.t3.micro"}
          onChange={(e) => onUpdate("instance_class", e.target.value)}
          className={inputClass}
        >
          <option value="db.t3.micro">db.t3.micro</option>
          <option value="db.t3.small">db.t3.small</option>
          <option value="db.t3.medium">db.t3.medium</option>
          <option value="db.m5.large">db.m5.large</option>
        </select>
      </FormField>
      <FormField label="Multi-AZ (multi_az)">
        <CheckboxField
          label="Multi-AZ 활성"
          checked={Boolean(properties.multi_az)}
          onChange={(v) => onUpdate("multi_az", v)}
        />
      </FormField>
    </>
  );
}

function AsgForm({ properties, onUpdate }: FormProps) {
  return (
    <>
      <FormField label="최소 인스턴스 수 (min_size)">
        <input
          type="number"
          min={0}
          value={(properties.min_size as number) ?? 1}
          onChange={(e) => onUpdate("min_size", parseInt(e.target.value, 10) || 0)}
          className={inputClass}
        />
      </FormField>
      <FormField label="최대 인스턴스 수 (max_size)">
        <input
          type="number"
          min={1}
          value={(properties.max_size as number) ?? 3}
          onChange={(e) => onUpdate("max_size", parseInt(e.target.value, 10) || 1)}
          className={inputClass}
        />
      </FormField>
      <FormField label="원하는 용량 (desired_capacity)">
        <input
          type="number"
          min={0}
          value={(properties.desired_capacity as number) ?? 1}
          onChange={(e) =>
            onUpdate("desired_capacity", parseInt(e.target.value, 10) || 0)
          }
          className={inputClass}
        />
      </FormField>
      <FormField label="런치 템플릿 (instance_template, 이름/ID)">
        <input
          type="text"
          value={(properties.instance_template as string) || ""}
          onChange={(e) => onUpdate("instance_template", e.target.value)}
          placeholder="lt-xxxx 또는 EC2 노드 id"
          className={inputClass}
        />
      </FormField>
    </>
  );
}

function SgForm({ properties, onUpdate }: FormProps) {
  return (
    <>
      <SecurityRuleEditor
        title="인바운드 규칙"
        emptyText="인바운드 규칙 없음"
        rules={normalizeRules(properties.ingress_rules)}
        onChange={(rules) => onUpdate("ingress_rules", rules)}
      />
      <SecurityRuleEditor
        title="아웃바운드 규칙"
        emptyText="아웃바운드 규칙 없음"
        rules={normalizeRules(properties.egress_rules)}
        onChange={(rules) => onUpdate("egress_rules", rules)}
      />
    </>
  );
}

function normalizeRules(value: unknown): SecurityRule[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item): item is Record<string, unknown> => Boolean(item))
    .map((item) => ({
      protocol: String(item.protocol || "tcp"),
      port_range: String(item.port_range || ""),
      source: String(item.source || ""),
      description: String(item.description || ""),
    }));
}

function SecurityRuleEditor({
  title,
  emptyText,
  rules,
  onChange,
}: {
  title: string;
  emptyText: string;
  rules: SecurityRule[];
  onChange: (rules: SecurityRule[]) => void;
}) {
  function updateRule(index: number, patch: Partial<SecurityRule>) {
    onChange(
      rules.map((rule, idx) =>
        idx === index ? { ...rule, ...patch } : rule,
      ),
    );
  }

  function addRule() {
    onChange([
      ...rules,
      {
        protocol: "tcp",
        port_range: "",
        source: "",
        description: "",
      },
    ]);
  }

  function removeRule(index: number) {
    onChange(rules.filter((_, idx) => idx !== index));
  }

  return (
    <div className="mt-4 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]">
      <div className="flex items-center justify-between border-b border-[var(--color-border)] px-2.5 py-2">
        <div className="text-xs font-semibold text-[var(--color-text-muted)]">
          {title}
        </div>
        <button
          type="button"
          onClick={addRule}
          className="rounded border border-[var(--color-border-strong)] px-2 py-1 text-[11px] font-medium text-[var(--color-text)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
        >
          규칙 추가
        </button>
      </div>
      {rules.length === 0 ? (
        <div className="px-2.5 py-3 text-xs text-[var(--color-text-subtle)]">
          {emptyText}
        </div>
      ) : (
        <div className="divide-y divide-[var(--color-border)]">
          {rules.map((rule, index) => (
            <div key={index} className="space-y-2 px-2.5 py-2.5">
              <div className="grid grid-cols-[1fr_1fr] gap-2">
                <label className="text-[11px] text-[var(--color-text-muted)]">
                  프로토콜
                  <select
                    value={rule.protocol}
                    onChange={(e) =>
                      updateRule(index, { protocol: e.target.value })
                    }
                    className={inputClass}
                  >
                    <option value="tcp">TCP</option>
                    <option value="udp">UDP</option>
                    <option value="icmp">ICMP</option>
                    <option value="-1">All</option>
                  </select>
                </label>
                <label className="text-[11px] text-[var(--color-text-muted)]">
                  포트 범위
                  <input
                    type="text"
                    value={rule.port_range}
                    onChange={(e) =>
                      updateRule(index, { port_range: e.target.value })
                    }
                    placeholder="80 또는 80-443"
                    className={inputClass}
                  />
                </label>
              </div>
              <label className="block text-[11px] text-[var(--color-text-muted)]">
                소스 / 대상
                <input
                  type="text"
                  value={rule.source}
                  onChange={(e) => updateRule(index, { source: e.target.value })}
                  placeholder="0.0.0.0/0 또는 sg-..."
                  className={inputClass}
                />
              </label>
              <label className="block text-[11px] text-[var(--color-text-muted)]">
                설명
                <input
                  type="text"
                  value={rule.description || ""}
                  onChange={(e) =>
                    updateRule(index, { description: e.target.value })
                  }
                  placeholder="선택"
                  className={inputClass}
                />
              </label>
              <button
                type="button"
                onClick={() => removeRule(index)}
                className="text-[11px] font-medium text-[var(--color-danger)]"
              >
                삭제
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function IamRoleForm({ properties, onUpdate }: FormProps) {
  return (
    <>
      <FormField label="Assume Role Principal (서비스명)">
        <select
          value={(properties.assume_role_policy as string) || "ec2"}
          onChange={(e) => onUpdate("assume_role_policy", e.target.value)}
          className={inputClass}
        >
          <option value="ec2">ec2.amazonaws.com</option>
          <option value="lambda">lambda.amazonaws.com</option>
          <option value="ecs-tasks">ecs-tasks.amazonaws.com</option>
          <option value="rds">rds.amazonaws.com</option>
          <option value="s3">s3.amazonaws.com</option>
        </select>
      </FormField>
      <FormField label="첨부 정책 (attached_policies, 쉼표 구분 ARN 또는 단축명)">
        <textarea
          rows={3}
          value={(properties.attached_policies as string) || ""}
          onChange={(e) => onUpdate("attached_policies", e.target.value)}
          placeholder="AmazonS3ReadOnlyAccess, AmazonRDSDataFullAccess"
          className={inputClass}
        />
      </FormField>
    </>
  );
}

function Route53Form({ properties, onUpdate }: FormProps) {
  return (
    <>
      <FormField label="Hosted Zone ID (zone_id)">
        <input
          type="text"
          value={(properties.zone_id as string) || ""}
          onChange={(e) => onUpdate("zone_id", e.target.value)}
          placeholder="Z01234567ABCDEF"
          className={inputClass}
        />
      </FormField>
      <FormField label="레코드 타입 (record_type)">
        <select
          value={(properties.record_type as string) || "A"}
          onChange={(e) => onUpdate("record_type", e.target.value)}
          className={inputClass}
        >
          <option value="A">A</option>
          <option value="AAAA">AAAA</option>
          <option value="CNAME">CNAME</option>
          <option value="ALIAS">ALIAS</option>
          <option value="TXT">TXT</option>
          <option value="MX">MX</option>
        </select>
      </FormField>
      <FormField label="값 (value)">
        <input
          type="text"
          value={(properties.value as string) || ""}
          onChange={(e) => onUpdate("value", e.target.value)}
          placeholder="alb.example.com 또는 IP 등"
          className={inputClass}
        />
      </FormField>
    </>
  );
}

function S3Form({ properties, onUpdate }: FormProps) {
  const pabValue =
    properties.public_access_block === undefined
      ? true
      : Boolean(properties.public_access_block);
  return (
    <>
      <FormField label="버킷 이름 (bucket_name)">
        <input
          type="text"
          value={(properties.bucket_name as string) || ""}
          onChange={(e) => onUpdate("bucket_name", e.target.value)}
          placeholder="my-bucket-name"
          className={inputClass}
        />
      </FormField>
      <FormField label="버전 관리 (versioning)">
        <CheckboxField
          label="Versioning 활성"
          checked={Boolean(properties.versioning)}
          onChange={(v) => onUpdate("versioning", v)}
        />
      </FormField>
      <FormField label="퍼블릭 액세스 차단 (public_access_block)">
        <CheckboxField
          label="모든 public access 차단"
          checked={pabValue}
          onChange={(v) => onUpdate("public_access_block", v)}
        />
      </FormField>
    </>
  );
}
