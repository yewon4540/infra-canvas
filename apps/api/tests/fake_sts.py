"""Small STS-compatible server for isolated integration tests."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

ACCOUNT_ID = "123456789012"
ASSUMED_ARN = (
    f"arn:aws:sts::{ACCOUNT_ID}:assumed-role/EolgaeDeployRole/eolgae-plan"
)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = parse_qs(self.rfile.read(length).decode())
        action = payload.get("Action", [""])[0]
        if action == "AssumeRole":
            result = f"""
<AssumeRoleResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/">
  <AssumeRoleResult>
    <Credentials>
      <AccessKeyId>ASIATESTACCESSKEY</AccessKeyId>
      <SecretAccessKey>test-secret-access-key</SecretAccessKey>
      <SessionToken>test-session-token</SessionToken>
      <Expiration>2030-01-01T00:00:00Z</Expiration>
    </Credentials>
    <AssumedRoleUser>
      <Arn>{ASSUMED_ARN}</Arn>
      <AssumedRoleId>AROATEST:eolgae-plan</AssumedRoleId>
    </AssumedRoleUser>
  </AssumeRoleResult>
  <ResponseMetadata><RequestId>test-request</RequestId></ResponseMetadata>
</AssumeRoleResponse>
"""
        elif action == "GetCallerIdentity":
            result = f"""
<GetCallerIdentityResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/">
  <GetCallerIdentityResult>
    <Arn>{ASSUMED_ARN}</Arn>
    <UserId>AROATEST:eolgae-plan</UserId>
    <Account>{ACCOUNT_ID}</Account>
  </GetCallerIdentityResult>
  <ResponseMetadata><RequestId>test-request</RequestId></ResponseMetadata>
</GetCallerIdentityResponse>
"""
        else:
            self.send_error(400, f"unsupported action: {action}")
            return

        body = result.strip().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/xml")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 9000), Handler).serve_forever()
