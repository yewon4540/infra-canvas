// FE 공유 상수. BE(apps/api/eolgae/schemas/auth.py)와 런타임이 달라 값 공유는 불가 —
// 동일 값을 양쪽에서 유지. (단일 소스화는 OpenAPI codegen 등 후속 검토)

// 비밀번호 최소 길이. BE MIN_PASSWORD_LENGTH 와 일치시킬 것.
export const MIN_PASSWORD_LENGTH = 4;
