# Logging Stack

Self-hosted observability stack for my side projects.

## 📦 Components

- **Grafana** for dashboards, with Loki and Prometheus data sources
- **Loki** and **Alloy** for collecting and querying pod logs
- **Prometheus**, **node-exporter**, and **local-path-pvc-exporter** for application, node, and PVC metrics

## 🚀 Deploy

Configure your SOPS key, Grafana credentials, domain, and Traefik cert resolver as described in the
[deployment guide](docs/deployment.md) and [security guide](docs/security.md). Then, from the
repository root:

```sh
kustomize build --enable-alpha-plugins --enable-exec . | kubectl apply -f -
```

## 📚 Documentation

- [Deployment and prerequisites](docs/deployment.md)
- [Metrics and application scraping](docs/metrics.md)
- [Secrets and Grafana access](docs/security.md)

## 📜 License

Distributed under the MIT License. See [License](/LICENSE) for more information.
