import Link from "next/link";
export function ResourcesConnectionHint(){
  return <p className="mt-2 max-w-3xl text-xs leading-relaxed text-[var(--color-text-muted)]">Resources 실제 조회는 관리자의 Kubernetes 파일 profile 설정이 필요합니다. Secret Reference에 profile 이름을 입력하고 endpoint를 일치시키세요. 파일 profile 방식에서는 Env 칸을 비워 둡니다. <Link href="/resources" className="underline">Resources 열기</Link></p>;
}
