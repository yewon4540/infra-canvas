# AWS Connection

## 연결 모델

Eolgae의 source principal이 대상 AWS 계정의 Role을 AssumeRole합니다. 연결 정보에는 계정·리전·Role ARN·External ID를 저장하고, 실행 시 발급받은 임시 credential은 DB에 저장하지 않습니다.

AWS 연결은 사용자 단위로 재사용합니다. Canvas마다 Role을 생성하는 구조가 아니며, Canvas의 state key를 분리합니다.

## 로컬 source 설정

실제 값을 Git에 기록하지 않는 루트 `.env`에서 설정합니다.

```dotenv
EOLGAE_AWS_ACCOUNT_ID=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_SESSION_TOKEN=
AWS_REGION=ap-northeast-2
```

Source principal에는 대상 Role을 AssumeRole할 권한이 필요합니다. 대상 Role에도 source principal과 External ID를 허용하는 trust policy가 필요합니다.

현재 제공하는 [CloudFormation template](../infrastructure/cross-account-role.yaml)의 trust policy는 source IAM user ARN을 사용합니다. 배포 환경의 instance/task role을 source로 사용하려면 해당 principal에 맞게 trust policy를 별도로 구성해야 합니다.

## 연결 순서

1. AWS Connections 화면에서 대상 계정 ID와 리전을 입력합니다.
2. 생성된 External ID와 onboarding template을 확인합니다.
3. 대상 계정에서 template과 IAM 권한을 검토하고 stack을 생성합니다.
4. 생성된 Role ARN을 Eolgae에 입력합니다.
5. Verify를 실행해 STS 연결 결과를 확인합니다.

이 절차에는 실제 AWS IAM 리소스 생성이 포함됩니다. 로컬 Canvas 확인만 할 때는 필요하지 않습니다.

| Template parameter | 의미 |
| --- | --- |
| `ExternalId` | Eolgae가 생성한 연결별 값 |
| `SourceAccountId` | AssumeRole을 호출하는 source 계정 |
| `SourcePrincipalName` | source IAM user 이름 |
| `RoleName` | 대상 계정에 생성할 Role 이름 |
| `EnableApplyPermissions` | 기본 `false`; write 권한을 허용하려면 명시적으로 활성화 |

기본 read-only 모드는 Verify와 preview Plan용입니다. Write 모드를 활성화하면 template에 정의된 서비스 변경 권한이 추가되므로 정책의 실제 범위를 검토해야 합니다.

## Plan과 변경 실행

Canvas에서 연결을 선택하고 Plan을 생성합니다. Backend 생성 권한이 부족하면 read-only preview Plan이 반환될 수 있습니다. 해당 결과는 승인·Apply 대상이 아닙니다.

Apply-ready Plan은 대상 계정의 S3 state backend와 DynamoDB lock table 및 저장된 artifact를 사용합니다. Plan 준비 과정에서 backend bootstrap이 발생할 수 있습니다. 변경 내용을 검토한 뒤 별도 승인·Apply를 수행합니다.

Destroy는 이미 Apply된 Canvas에서 Destroy Plan을 생성하고 검토·승인한 뒤 실행합니다. 같은 승인 Plan을 반복 실행하지 않습니다.
