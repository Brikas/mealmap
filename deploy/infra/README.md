# Infrastructure Directory Structure

The directory tree presented below represents a high-level industry standard for organizing Infrastructure-as-Code (IaC) assets. This structure ensures modularity, flexibility, and maintainability—key characteristics of a well-architected infrastructure codebase.

## Directory Layout

```plaintext
├── infra/                           # Root directory for all infrastructure-related assets.
│   ├── terraform/                   # Terraform IaC root.
│   │   ├── modules/                 # Reusable Terraform modules.
│   │   │   ├── database/           # Database-related TF modules.
│   │   │   ├── server/             # Compute-related TF modules.
│   │   │   └── network/            # Network-related TF modules.
│   │   ├── staging/                # Staging environment TF configurations.
│   │   ├── production/             # Production environment TF configurations.
│   │   └── common.tfvars           # Shared variables across environments.
│   ├── pulumi/                     # Pulumi IaC root. If using both, choose either Pulumi or Terraform.
│   │   ├── shared/                 # Shared Pulumi codes across environments.
│   │   ├── dev/                    # Pulumi stack for the development environment.
│   │   └── prod/                   # Pulumi stack for the production environment.
│   ├── kubernetes/                 # Kubernetes configurations and manifests.
│   │   ├── base/                   # Base Kubernetes configurations.
│   │   ├── overlays/               # Kustomize overlays for environment-based customization.
│   │   │   ├── staging/            # Kustomize overlay for staging.
│   │   │   └── production/         # Kustomize overlay for production.
│   │   └── helm/                   # Helm charts directory.
│   │       └── my-app-chart/       # Example Helm chart.
│   │           ├── templates/      # Helm templates for the given chart.
│   │           └── values.yaml     # Default configuration values for the given chart.
```

## Detailed Explanations

### Terraform

- **modules/**: Encapsulating recurring infrastructure patterns in modules enables the code's reusability and ensures consistent configurations across resources or environments.
- **staging/** & **production/**: Environments must be strictly isolated. Hence, separate directories facilitate clarity and minimize risks.
- **common.tfvars**: It's prudent to centralize configurations shared across environments. This ensures consistency and simplifies potential changes.

### Pulumi

- **shared/**: A dedicated space for shared infrastructure configurations. This could contain, for instance, VPC or database configurations commonly required across multiple environments.
- **dev/** & **prod/**: Stacks in Pulumi correspond to isolated, independently configurable instances of a Pulumi program. Individual directories for each environment streamline the separation of configurations.

### Kubernetes

- **base/**: Fundamental K8s configurations that serve as a foundation. Specific configurations for different environments can later extend these.
- **overlays/staging/** & **overlays/production/**: Leveraging Kustomize, these overlays allow for environment-specific customization without duplicating base configurations.
- **helm/my-app-chart/**: Helm offers an abstraction over raw Kubernetes configurations, making it easier to manage, version, and deploy complex applications.

This directory structure is a manifestation of best practices, intended to equip development and operations teams with a clear, logical, and sustainable approach for infrastructure management.

## Alternatives

* https://github.com/kube-hetzner/terraform-hcloud-kube-hetzner
