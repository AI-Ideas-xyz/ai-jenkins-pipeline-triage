#!/usr/bin/env python3
"""Generates synthetic EKS deployment failure logs for pipeline triage demo."""
import sys
import random
import datetime

_NAMESPACE  = "backend"
_DEPLOYMENT = "myapp"
_IMAGE      = "myapp:v2.3.1"
_POD_SUFFIX = "7d9f8b6c4f"
_SUFFIXES   = ["xkp2q", "zmt8r", "p9lnk", "q2vws"]


def _pod(n: int = 0) -> str:
    return f"{_DEPLOYMENT}-{_POD_SUFFIX}-{_SUFFIXES[n % len(_SUFFIXES)]}"


def _ts(delta: int = 0) -> str:
    t = datetime.datetime.utcnow() - datetime.timedelta(seconds=delta)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _crashloop() -> str:
    return f"""$ kubectl rollout status deployment/{_DEPLOYMENT} -n {_NAMESPACE} --timeout=300s
Waiting for deployment "{_DEPLOYMENT}" rollout to finish: 0 of 2 updated replicas are available...
error: deployment "{_DEPLOYMENT}" exceeded its progress deadline

$ kubectl get pods -n {_NAMESPACE} -l app={_DEPLOYMENT}
NAME                              READY   STATUS             RESTARTS   AGE
{_pod(0)}   0/1     CrashLoopBackOff   7          6m12s
{_pod(1)}   0/1     CrashLoopBackOff   7          6m12s

$ kubectl describe pod {_pod(0)} -n {_NAMESPACE}
Name:         {_pod(0)}
Namespace:    {_NAMESPACE}
Image:        {_IMAGE}
State:        Waiting
  Reason:     CrashLoopBackOff
Last State:   Terminated
  Reason:     Error
  Exit Code:  1
  Started:    {_ts(120)}
  Finished:   {_ts(115)}
Events:
  Warning  BackOff    2m (x15 over 6m)  kubelet  Back-off restarting failed container
  Normal   Pulled     6m                kubelet  Successfully pulled image "{_IMAGE}"
  Warning  Unhealthy  3m                kubelet  Liveness probe failed: HTTP probe failed with statuscode: 500

$ kubectl logs {_pod(0)} -n {_NAMESPACE} --previous
[ERROR] Database connection refused: connect ECONNREFUSED 10.0.1.45:5432
[ERROR] Application startup failed — exiting with code 1
"""


def _oomkilled() -> str:
    return f"""$ kubectl rollout status deployment/{_DEPLOYMENT} -n {_NAMESPACE} --timeout=300s
Waiting for deployment "{_DEPLOYMENT}" rollout to finish: 0 of 2 updated replicas are available...
error: deployment "{_DEPLOYMENT}" exceeded its progress deadline

$ kubectl get pods -n {_NAMESPACE} -l app={_DEPLOYMENT}
NAME                              READY   STATUS      RESTARTS   AGE
{_pod(0)}   0/1     OOMKilled   3          3m45s

$ kubectl describe pod {_pod(0)} -n {_NAMESPACE}
Name:         {_pod(0)}
Namespace:    {_NAMESPACE}
Image:        {_IMAGE}
State:        Terminated
  Reason:     OOMKilled
  Exit Code:  137
  Started:    {_ts(200)}
  Finished:   {_ts(190)}
Limits:
  memory: 256Mi
Requests:
  memory: 128Mi
Events:
  Warning  OOMKilling  90s  kernel  Out of memory: Kill process 3421 (node) score 999 or sacrifice child
  Normal   Pulled      3m   kubelet Successfully pulled image "{_IMAGE}"
"""


def _imagepull() -> str:
    return f"""$ kubectl rollout status deployment/{_DEPLOYMENT} -n {_NAMESPACE} --timeout=300s
Waiting for deployment "{_DEPLOYMENT}" rollout to finish: 0 of 2 updated replicas are available...
error: deployment "{_DEPLOYMENT}" exceeded its progress deadline

$ kubectl get pods -n {_NAMESPACE} -l app={_DEPLOYMENT}
NAME                              READY   STATUS             RESTARTS   AGE
{_pod(0)}   0/1     ImagePullBackOff   0          2m30s
{_pod(1)}   0/1     ImagePullBackOff   0          2m30s

$ kubectl describe pod {_pod(0)} -n {_NAMESPACE}
Name:         {_pod(0)}
Namespace:    {_NAMESPACE}
Image:        {_IMAGE}
State:        Waiting
  Reason:     ImagePullBackOff
Events:
  Warning  Failed   90s (x3 over 2m)  kubelet  Failed to pull image "{_IMAGE}": rpc error: code = Unknown desc = failed to resolve reference "docker.io/{_IMAGE}": unexpected status code 401 Unauthorized
  Warning  BackOff  60s (x4 over 2m)  kubelet  Back-off pulling image "{_IMAGE}"
"""


def _readiness() -> str:
    return f"""$ kubectl rollout status deployment/{_DEPLOYMENT} -n {_NAMESPACE} --timeout=300s
Waiting for deployment "{_DEPLOYMENT}" rollout to finish: 0 of 2 updated replicas are available...
error: deployment "{_DEPLOYMENT}" exceeded its progress deadline

$ kubectl get pods -n {_NAMESPACE} -l app={_DEPLOYMENT}
NAME                              READY   STATUS    RESTARTS   AGE
{_pod(0)}   0/1     Running   0          5m10s
{_pod(1)}   0/1     Running   0          5m10s

$ kubectl describe pod {_pod(0)} -n {_NAMESPACE}
Name:         {_pod(0)}
Namespace:    {_NAMESPACE}
Image:        {_IMAGE}
State:        Running
  Started:    {_ts(310)}
Readiness:    http-get http://:8080/healthz delay=10s timeout=5s period=10s #success=1 #failure=3
Events:
  Warning  Unhealthy  2m (x18 over 5m)  kubelet  Readiness probe failed: HTTP probe failed with statuscode: 503
  Normal   Pulled     5m                kubelet  Successfully pulled image "{_IMAGE}"
  Normal   Started    5m                kubelet  Started container {_DEPLOYMENT}
"""


SCENARIOS = {
    "CrashLoopBackOff":     _crashloop,
    "OOMKilled":            _oomkilled,
    "ImagePullBackOff":     _imagepull,
    "ReadinessProbeFailed": _readiness,
}


def generate(scenario: str) -> str:
    if scenario not in SCENARIOS:
        raise ValueError(
            f"Unknown scenario '{scenario}'. Choose from: {list(SCENARIOS)}"
        )
    return SCENARIOS[scenario]()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        chosen = random.choice(list(SCENARIOS))
        print(f"No scenario specified — picking randomly: {chosen}", file=sys.stderr)
    else:
        chosen = sys.argv[1]
    print(generate(chosen))
