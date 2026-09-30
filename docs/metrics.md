# Metrics

Prometheus discovers each cluster node and scrapes its kubelet `/metrics` endpoint through the
Kubernetes API server. The `kubernetes-kubelet` job needs `get` access to `nodes/proxy` for this
route. This permission also grants broad access to kubelet APIs, so protect the Prometheus service
account token. K3s exposes metrics from other embedded components on the same endpoint, so the job
keeps only `kubelet_*` metrics. The Targets page shows one kubelet target per node.

The `node-exporter` DaemonSet exposes host metrics on port 9100 from every node. It uses the host
network and process namespaces and mounts the host root read-only so its collectors see node data.
Prometheus discovers its annotated pods through the `kubernetes-pods` scrape job. Port 9100 must be
available on each node.

The `local-path-pvc-exporter` DaemonSet reports `local_path_pvc_used_bytes` for PVC directories
under `/var/lib/rancher/k3s/storage` on each node. It measures allocated disk blocks, like `du`,
and labels each series with `pvc_namespace`, `persistentvolumeclaim`, and `node`. Use this metric for
directory usage: on local-path volumes, `kubelet_volume_stats_used_bytes` can report usage of the
shared node filesystem instead. If K3s uses a different local-path storage directory, update the
exporter's hostPath mount. The existing pod scrape job discovers the exporter automatically. The
exporter runs as root with `DAC_OVERRIDE` to traverse private PVC directories; its host storage
mount is read-only and it has no Kubernetes service account token.

Prometheus discovers **pods**, rather than Deployment objects, in every namespace in this
Kubernetes cluster. A workload is only scraped when its pod template opts in with the annotations
below.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: another-project
spec:
  template:
    metadata:
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/path: /metrics       # optional; this is Prometheus's default
        prometheus.io/port: "8080"         # the container's metrics port
        # prometheus.io/scheme: https      # optional; defaults to http
```

The application must serve Prometheus-format metrics on the specified port and bind to the pod
network interface.

If the target namespace uses a `NetworkPolicy` with ingress isolation, allow traffic from the
Prometheus pods in `monitoring` to the metrics port. For example, add this ingress rule to the
target's policy (or create a separate policy for that port):

```yaml
ingress:
  - from:
      - namespaceSelector:
          matchLabels:
            kubernetes.io/metadata.name: monitoring
        podSelector:
          matchLabels:
            app: prometheus
    ports:
      - protocol: TCP
        port: 8080
```

The Prometheus Targets page is available locally with:

```sh
kubectl -n monitoring port-forward service/prometheus 9090:9090
```

Then visit `http://localhost:9090/targets`. The `kubernetes-pods` job shows any failed discovery
or scrape with its error message.

